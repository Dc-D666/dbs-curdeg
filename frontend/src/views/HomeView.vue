<template>
  <main class="home">
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

    <p v-if="buildTime" class="deploy-time" title="前端构建/部署时间，每次 push 由 cron 自动更新">
      更新时间：{{ buildTime }}
    </p>

    <!-- 我的频道：横滑快捷入口（登录且有关注时展示） -->
    <section v-if="myChannels.length" class="chips">
      <router-link v-for="c in myChannels" :key="c.id" :to="`/c/${c.id}`" class="chip" :title="c.name">
        <UserAvatar :src="c.avatar_url" :name="c.name" :size="36" />
        <span class="chip-name">{{ c.name }}</span>
      </router-link>
      <router-link to="/discover" class="chip chip-more">
        <span class="chip-more-icon"><BrowseIcon /></span>
        <span class="chip-name">发现更多</span>
      </router-link>
    </section>

    <!-- 内容导航/筛选（lazy：切换时才挂载并加载） -->
    <t-tabs v-model="activeTab" class="home-tabs" lazy @change="onTabChange">
      <t-tab-panel value="all" label="全部">
        <FeedStreamList v-if="activeTab === 'all'" view="all" />
      </t-tab-panel>
      <t-tab-panel value="hot" label="热门">
        <FeedStreamList v-if="activeTab === 'hot'" view="hot" />
      </t-tab-panel>
      <t-tab-panel value="mine" label="我关注的">
        <FeedStreamList v-if="activeTab === 'mine'" view="mine" />
      </t-tab-panel>
    </t-tabs>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { BrowseIcon } from 'tdesign-icons-vue-next'
import FeedStreamList from '@/components/FeedStreamList.vue'
import UserAvatar from '@/components/UserAvatar.vue'
import { communityApi, type Community } from '@/api/community'
import { useAuthStore } from '@/stores/auth'
import { tokenStore } from '@/api/http'
import { toast } from '@/utils/toast'
import { formatBeijing } from '@/utils/time'

const auth = useAuthStore()
const router = useRouter()

// 首页更新时间：构建时由 Vite define 注入（__BUILD_TIME__），显示为北京时间。
// 服务器 cron 每次 push 都会重编前端，因此该时间可用于确认部署是否生效。
const buildTime = ref(formatBeijing(__BUILD_TIME__))

// 内容 Tab：全部(=最新) / 热门 / 我关注的
const activeTab = ref<'all' | 'hot' | 'mine'>('all')

// 我加入的频道（owned/managed/joined 合并去重），用于首页快捷入口
const myChannels = ref<Community[]>([])
const channelsLoaded = ref(false)

onMounted(() => {
  auth.fetchMe()
  initMyChannels()
})

function onTabChange(val: string | number) {
  if (val === 'mine' && !tokenStore.access) {
    toast('请先登录查看关注动态', 'warning')
    router.push('/login?redirect=' + encodeURIComponent(router.currentRoute.value.fullPath))
    return
  }
  activeTab.value = val as 'all' | 'hot' | 'mine'
}

async function initMyChannels() {
  if (channelsLoaded.value) return
  channelsLoaded.value = true
  if (!tokenStore.access) return
  try {
    const m = await communityApi.mine()
    const seen = new Set<number>()
    myChannels.value = [...m.owned, ...m.managed, ...m.joined].filter((c) => {
      if (seen.has(c.id)) return false
      seen.add(c.id)
      return true
    })
  } catch (e) {
    console.error('加载我的频道失败', e)
  }
}

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

/* 我的频道横滑条 */
.chips {
  margin-top: var(--sp-3);
  display: flex;
  gap: var(--sp-3);
  overflow-x: auto;
  padding-bottom: var(--sp-1);
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.chips::-webkit-scrollbar {
  display: none;
}
.chip {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  text-decoration: none;
  max-width: 64px;
}
.chip-name {
  max-width: 64px;
  font-size: 11px;
  color: var(--text-3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.chip-more {
  justify-content: center;
}
.chip-more-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-3);
}
.chip-more-icon :deep(svg) {
  width: 18px;
  height: 18px;
}

/* 内容 Tab */
.home-tabs {
  margin-top: var(--sp-2);
}
.home-tabs :deep(.t-tabs__nav) {
  margin-bottom: var(--sp-2);
}
.home-tabs :deep(.t-tabs__nav-item) {
  font-size: var(--fs-body);
}
.home-tabs :deep(.t-tabs__panel) {
  padding: 0;
}
</style>