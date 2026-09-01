<template>
  <main class="home" :class="{ wide: isWide }">
    <header class="home-header">
      <h1 class="brand">SDUdiscord</h1>
      <nav v-if="auth.user" class="nav">
        <router-link to="/me" class="nav-link">
          {{ auth.user.nickname || auth.user.username }}
        </router-link>
        <t-button variant="text" size="small" @click="onLogout">退出</t-button>
      </nav>
      <nav v-else class="nav">
        <router-link to="/login" class="nav-link">登录</router-link>
        <router-link to="/register" class="nav-link">注册</router-link>
      </nav>
    </header>

    <!-- 部署时间窄条（常显，精确到分）：服务器 cron 每 3 分钟拉取重建前端，
         此时间即最近一次部署，用于人工确认 cron 有无生效/漏跑 -->
    <p v-if="buildTime" class="deploy-banner" title="前端最近一次构建/部署时间（北京时间）：cron 每 3 分钟自动拉取重建，时间长时间不变说明 cron 未跑或无新提交">
      最近更新 {{ buildTime }}
    </p>

    <!-- 平台管理员（user_type=1）：首页即平台控制台（浏览全部频道/用户 + 封禁解封等系统级操作），
         不进入会员频道/板块/帖子流工作台 -->
    <PlatformConsole v-if="isPlatformAdmin" class="home-console" />

    <!-- 普通用户：三栏工作台（桌面三栏 / 移动端上中下三栏）。
         仅在登录态已探测完成后渲染，避免平台管理员在 fetchMe 返回前闪一下会员工作台 -->
    <ChannelWorkspace
      v-else-if="auth.loaded && currentCid"
      :cid="currentCid"
      embedded-in-tab
      @change="onChangeChannel"
      @load-error="onWorkspaceLoadError"
    />

    <!-- 无默认频道：加载中 / 加载失败（可重试）/ 普通用户引导 -->
    <div v-else class="state">
      <template v-if="!auth.loaded || picking">
        <p class="state-text">加载中…</p>
      </template>
      <template v-else-if="loadError">
        <p class="state-text">{{ loadError }}</p>
        <t-button variant="outline" @click="retryPick">重试</t-button>
      </template>
      <template v-else>
        <p class="state-text">加入一个频道，开始使用频道工作台</p>
        <t-button theme="primary" @click="router.push('/discover')">去发现频道</t-button>
      </template>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onActivated, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import ChannelWorkspace from '@/components/ChannelWorkspace.vue'
import PlatformConsole from '@/views/PlatformConsole.vue'
import { communityApi } from '@/api/community'
import { useAuthStore } from '@/stores/auth'
import { tokenStore } from '@/api/http'
import { formatBeijing } from '@/utils/time'
import { errMessage } from '@/utils/error'

// 显式组件名：供 App.vue 的 <keep-alive :include> 匹配（返回首页保留工作台状态，#37）
defineOptions({ name: 'HomeView' })

const auth = useAuthStore()
const router = useRouter()

// 首页更新时间：构建时由 Vite define 注入（__BUILD_TIME__），北京时间、精确到分
// （formatBeijing 固定输出 YYYY-MM-DD HH:mm:ss，截掉秒即可）。
// 服务器 cron 每次拉取都重编前端，该时间即最近一次部署，可确认 cron 是否生效。
const buildTime = computed(() => formatBeijing(__BUILD_TIME__).slice(0, 16))

// 桌面宽屏判定：≥1024px 时三栏工作台全宽铺开
const isWide = ref(window.innerWidth >= 1024)
function onResize() {
  isWide.value = window.innerWidth >= 1024
}

// 工作台默认频道：最近访问记忆 → 无则我加入的第一个
const LAST_CHANNEL_KEY = 'sdu_last_channel_id'
const currentCid = ref<number | null>(null)

function remember(id: number) {
  localStorage.setItem(LAST_CHANNEL_KEY, String(id))
}

// 失败不能静默吞掉：否则已登录用户会看到「加入一个频道」的错误引导且无任何重试入口
const picking = ref(false)
const loadError = ref('')

function pickDefault() {
  const saved = Number(localStorage.getItem(LAST_CHANNEL_KEY))
  if (saved && saved > 0) {
    currentCid.value = saved
    return
  }
  pickFromMine()
}

/** 从「我的频道」里选第一个作为默认（无记忆/记忆失效时）。 */
function pickFromMine() {
  if (!tokenStore.access) return // 未登录且无记忆 → 引导
  picking.value = true
  loadError.value = ''
  communityApi
    .mine()
    .then((m) => {
      const all = [...m.owned, ...m.managed, ...m.joined]
      if (all.length) {
        currentCid.value = all[0].id
        remember(all[0].id)
      }
    })
    .catch((e: unknown) => {
      loadError.value = errMessage(e, '加载我的频道失败')
    })
    .finally(() => {
      picking.value = false
    })
}

/** 工作台报告频道加载失败：记忆指向已退出/已解散频道时不能死在「频道不存在」，
 *  清掉失效记忆并自动回退到我加入的第一个频道（游客则落到「去发现」引导）。 */
function onWorkspaceLoadError(notFound: boolean) {
  if (!notFound) return // 网络错误：工作台内已有可重试的错误态，不自动切换
  localStorage.removeItem(LAST_CHANNEL_KEY)
  currentCid.value = null
  if (tokenStore.access) pickFromMine()
}

function retryPick() {
  pickDefault()
}

/** 工作台内就地切换频道：更新当前频道 + 写入最近访问记忆。 */
function onChangeChannel(id: number) {
  currentCid.value = id
  remember(id)
}

// 平台管理员（user_type=1）：不隶属任何频道，首页展示平台控制台而非频道工作台
const isPlatformAdmin = computed(() => auth.user?.user_type === 1)

onMounted(() => {
  auth.fetchMe()
  // 平台管理员不读频道记忆/我的频道，首页固定为平台控制台；
  // 否则会被 localStorage 的 sdu_last_channel_id 带入会员帖子流工作台
  if (!isPlatformAdmin.value) pickDefault()
  window.addEventListener('resize', onResize)
})

// keep-alive 缓存本页（#37）：切账号后 onMounted 不再执行，会把上个账号的
// 工作台/空态原样恢复（Admin 被缓存成「没加入频道」的元凶）。
// onActivated 对比上次初始化时的用户 id，变化则整体重置重新选频道。
let lastPickUid: number | null | undefined
function bindPickUid() {
  lastPickUid = auth.user?.id ?? null
}
onActivated(() => {
  const uid = auth.user?.id ?? null
  if (lastPickUid !== undefined && lastPickUid !== uid) {
    currentCid.value = null
    picking.value = false
    loadError.value = ''
    bindPickUid()
    if (!isPlatformAdmin.value) pickDefault()
  }
})
// 首次挂载记录基准（在 pickDefault 之后，避免 onActivated 首次触发即重置）
onMounted(bindPickUid)
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
})

function onLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.home {
  max-width: var(--page-max);
  margin: 0 auto;
  padding: 0 var(--sp-4) var(--sp-6);
}
/* 桌面宽屏：三栏工作台全宽铺开，header/更新时间保持居中 */
.home.wide {
  max-width: none;
  padding: 0;
}
.home.wide .home-header {
  max-width: var(--page-max);
  margin-left: auto;
  margin-right: auto;
  padding-left: var(--sp-4);
  padding-right: var(--sp-4);
}
.home-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--nav-height);
  border-bottom: 1px solid var(--border);
}
.brand {
  margin: 0;
  font-size: var(--fs-page);
  font-weight: 700;
  color: var(--brand);
}
/* 部署时间窄条：全宽贴边（负 margin 抵消 .home 的横向 padding）、caption 级中性色 */
.deploy-banner {
  margin: 0 calc(-1 * var(--sp-4));
  padding: 4px var(--sp-4);
  font-size: var(--fs-caption);
  color: var(--text-3);
  text-align: center;
  background: var(--surface-2);
  border-bottom: 1px solid var(--border);
}
/* 宽屏下 .home 无横向 padding，窄条天然全宽 */
.home.wide .deploy-banner {
  margin: 0;
}
.nav {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}
.nav-link {
  color: var(--text-1);
  font-size: var(--fs-body);
}
.state {
  padding: var(--sp-10, 48px) 0;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-4);
}
.state-text {
  margin: 0;
  color: var(--text-3);
  font-size: var(--fs-body);
}
</style>
