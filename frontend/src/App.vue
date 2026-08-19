<template>
  <div class="app-shell">
    <router-view />

    <t-tab-bar v-if="showTabbar" :value="route.path" class="tabbar">
      <t-tab-bar-item v-for="t in tabs" :key="t.path" :value="t.path" :router-link="{ to: t.path }">
        <template #icon>
          <component :is="t.icon" class="tab-icon" />
        </template>
        {{ t.label }}
      </t-tab-bar-item>
    </t-tab-bar>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { HomeIcon, BrowseIcon, UserIcon } from 'tdesign-icons-vue-next'
import { onMounted } from 'vue'
import { request } from '@/api/http'

const route = useRoute()

const tabs = [
  { path: '/', label: '首页', icon: HomeIcon },
  { path: '/discover', label: '发现', icon: BrowseIcon },
  { path: '/me', label: '我的', icon: UserIcon },
]

// 主 tab 页面显示底部导航；子页面（频道/帖子/发帖/登录注册）全屏
const showTabbar = computed(() =>
  tabs.some((t) => t.path === route.path),
)

onMounted(async () => {
  try {
    const data = await request<{ message: string }>({ url: '/ping' })
    console.log('[SDUdiscord] 后端连通:', data.message)
  } catch (e) {
    console.warn('[SDUdiscord] 后端未连通:', e)
  }
})
</script>

<style>
@import '@/styles/tokens.css';

* {
  box-sizing: border-box;
}
html,
body {
  overflow-x: hidden; /* 防页面内容横向溢出导致布局错乱 */
}
body {
  margin: 0;
  font-family: system-ui, -apple-system, 'Segoe UI', Roboto, 'PingFang SC',
    'Microsoft YaHei', sans-serif;
  font-size: var(--fs-body);
  line-height: 1.5;
  color: var(--text-1);
  background: var(--bg-page);
  -webkit-font-smoothing: antialiased;
}
a {
  color: var(--brand);
  text-decoration: none;
}
button {
  font-family: inherit;
}
#app {
  min-height: 100vh;
  overflow-x: hidden;
}
.app-shell {
  min-height: 100vh;
  padding-bottom: var(--tabbar-height);
}
</style>

<style scoped>
.tabbar {
  max-width: 100vw;
  z-index: 50;
}
.tab-icon {
  width: 24px;
  height: 24px;
}
.tab-icon :deep(svg) {
  width: 24px;
  height: 24px;
  display: block;
}
</style>
