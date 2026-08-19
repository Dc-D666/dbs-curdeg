<template>
  <div class="app-shell">
    <router-view />

    <nav v-if="showTabbar" class="tabbar">
      <router-link v-for="t in tabs" :key="t.path" :to="t.path" class="tab-item"
        :class="{ active: route.path === t.path }">
        <component :is="t.icon" class="tab-icon" />
        <span class="tab-label">{{ t.label }}</span>
      </router-link>
    </nav>
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
/* 底部导航：TDesign 设计 token + TDesign 图标自绘（tdesign-vue-next 无 TabBar 组件，
   该组件属 TDesign Mobile 版；此处按 TDesign starter 视觉实现） */
.tabbar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  height: var(--tabbar-height);
  max-width: 100vw;
  overflow: hidden;
  background: var(--td-bg-color-container);
  border-top: 1px solid var(--td-component-border);
  display: flex;
  z-index: 50;
}
.tab-item {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  color: var(--td-text-color-placeholder);
  text-decoration: none;
  transition: color var(--anim-duration) var(--anim-ease);
}
.tab-item.active {
  color: var(--td-brand-color);
}
.tab-icon {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
}
.tab-icon :deep(svg) {
  width: 24px;
  height: 24px;
  display: block;
}
.tab-label {
  font-size: 12px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
