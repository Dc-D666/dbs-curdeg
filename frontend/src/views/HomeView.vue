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

    <!-- 部署时间：仅当 URL 带 ?debug=1 时对开发者显示，避免暴露给终端用户 -->
    <p v-if="isDebug && buildTime" class="deploy-time" title="前端构建/部署时间，每次 push 由 cron 自动更新">
      更新时间：{{ buildTime }}
    </p>

    <!-- 三栏工作台：桌面三栏 / 移动端上中下三栏 -->
    <ChannelWorkspace
      v-if="currentCid"
      :cid="currentCid"
      embedded-in-tab
      @change="onChangeChannel"
    />

    <!-- 无默认频道：加载中 / 加载失败（可重试）/ 确实没加入（引导去发现页） -->
    <div v-else class="state">
      <template v-if="picking">
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
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import ChannelWorkspace from '@/components/ChannelWorkspace.vue'
import { communityApi } from '@/api/community'
import { useAuthStore } from '@/stores/auth'
import { tokenStore } from '@/api/http'
import { formatBeijing } from '@/utils/time'
import { errMessage } from '@/utils/error'

const auth = useAuthStore()
const router = useRouter()

// 首页更新时间：构建时由 Vite define 注入（__BUILD_TIME__），显示为北京时间。
// 服务器 cron 每次 push 都会重编前端，因此该时间可用于确认部署是否生效。
const buildTime = ref(formatBeijing(__BUILD_TIME__))
// 仅在本机开发者调试（URL 带 ?debug=1）时展示部署时间，避免面向终端用户暴露
const isDebug = /[?&]debug=1/.test(window.location.search)

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

function retryPick() {
  pickDefault()
}

/** 工作台内就地切换频道：更新当前频道 + 写入最近访问记忆。 */
function onChangeChannel(id: number) {
  currentCid.value = id
  remember(id)
}

onMounted(() => {
  auth.fetchMe()
  pickDefault()
  window.addEventListener('resize', onResize)
})
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
.home.wide .home-header,
.home.wide .deploy-time {
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
.deploy-time {
  margin: 0;
  padding: var(--sp-1) 0 0;
  font-size: var(--fs-caption);
  color: var(--text-3);
  text-align: right;
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
