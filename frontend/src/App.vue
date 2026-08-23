<template>
  <div class="app-shell">
    <router-view />

    <nav v-if="showTabbar" class="tabbar">
      <router-link v-for="t in tabs" :key="t.path" :to="t.path" class="tab-item"
        :class="{ active: route.path === t.path }">
        <span class="tab-icon-wrap">
          <component :is="t.icon" class="tab-icon" />
          <span v-if="t.badge && notif.unread > 0" class="tab-badge">
            {{ notif.unread > 99 ? '99+' : notif.unread }}
          </span>
        </span>
        <span class="tab-label">{{ t.label }}</span>
      </router-link>
    </nav>

    <!-- AI 问答助手浮窗（阶段 6） -->
    <AiBot />

    <!-- 实时新内容浮动药丸（P1 ③） -->
    <NewPostsPill />

    <!-- 断网/离线横幅（Step 3） -->
    <NetworkBanner />

    <!-- 帖子阅读右侧抽屉（P1 ①：保持一致上下文） -->
    <PostDrawer />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { HomeIcon, BrowseIcon, UserIcon, NotificationIcon } from 'tdesign-icons-vue-next'
import http from '@/api/http'
import { useNotificationStore } from '@/stores/notification'
import { useWebSocket } from '@/composables/useWebSocket'
import { useGlobalShortcuts } from '@/composables/useGlobalShortcuts'
import AiBot from '@/components/AiBot.vue'
import PostDrawer from '@/components/PostDrawer.vue'
import NewPostsPill from '@/components/NewPostsPill.vue'
import NetworkBanner from '@/components/NetworkBanner.vue'

const route = useRoute()
const notif = useNotificationStore()

const tabs = [
  { path: '/', label: '首页', icon: HomeIcon },
  { path: '/discover', label: '发现', icon: BrowseIcon },
  { path: '/notifications', label: '通知', icon: NotificationIcon, badge: true },
  { path: '/me', label: '我的', icon: UserIcon },
]

// 主 tab 页面显示底部导航；子页面（频道/帖子/发帖/登录注册）全屏
const showTabbar = computed(() =>
  tabs.some((t) => t.path === route.path),
)

onMounted(async () => {
  // 全局快捷键（J/K 换帖、/ 聚焦搜索）
  useGlobalShortcuts()
  // WebSocket 通知（登录后自动连接，未读角标实时更新）
  useWebSocket()
  try {
    // /ping 返回裸 {message:"pong"}（无统一 code 包装）。注意 http 实例 baseURL 已是 /api/v1，
    // 这里必须用相对路径 /ping，否则会拼成 /api/v1/api/v1/ping → 404。
    const res = await http.get<{ message: string }>('/ping')
    console.log('[SDUdiscord] 后端连通:', res.data?.message)
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
/* 键盘导航（J/K）落焦卡片的短暂高亮 */
.feed-kbd-focus {
  animation: feed-kbd-focus 0.6s ease;
}
@keyframes feed-kbd-focus {
  0% {
    box-shadow: 0 0 0 2px var(--brand) inset;
  }
  100% {
    box-shadow: 0 0 0 0 transparent inset;
  }
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
.tab-icon-wrap {
  position: relative;
  display: inline-flex;
}
.tab-badge {
  position: absolute;
  top: -6px;
  right: -12px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  background: var(--danger);
  color: #fff;
  font-size: 10px;
  line-height: 16px;
  text-align: center;
  white-space: nowrap;
  box-sizing: border-box;
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
