<template>
  <div class="app-shell">
    <!-- 列表页缓存：从帖子/频道详情返回后，搜索关键词、分页结果、滚动位置不丢（#37）。
         仅色含无副作用的列表页；详情/表单页不缓存（各有自己的加载/草稿机制）。 -->
    <router-view v-slot="{ Component }">
      <keep-alive :include="KEEP_ALIVE_VIEWS">
        <component :is="Component" />
      </keep-alive>
    </router-view>

    <!-- AI 问答助手浮窗（阶段 6） -->
    <AiBot />

    <!-- 实时新内容浮动药丸（P1 ③） -->
    <NewPostsPill />

    <!-- 断网/离线横幅（Step 3） -->
    <NetworkBanner />

    <!-- 撤销 Snackbar（B） -->
    <UndoSnackbar />

    <!-- 全局单例灯箱（#59）：所有卡片/详情页共用 -->
    <GlobalLightbox />

    <!-- 桌面端快捷键帮助入口（#60） -->
    <ShortcutHint />

    <!-- 帖子阅读右侧抽屉（P1 ①：保持一致上下文） -->
    <PostDrawer />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useNotificationStore } from '@/stores/notification'
import { useWebSocket } from '@/composables/useWebSocket'
import { useGlobalShortcuts } from '@/composables/useGlobalShortcuts'
import AiBot from '@/components/AiBot.vue'
import PostDrawer from '@/components/PostDrawer.vue'
import NewPostsPill from '@/components/NewPostsPill.vue'
import NetworkBanner from '@/components/NetworkBanner.vue'
import UndoSnackbar from '@/components/UndoSnackbar.vue'
import GlobalLightbox from '@/components/GlobalLightbox.vue'
import ShortcutHint from '@/components/ShortcutHint.vue'

const notif = useNotificationStore()

// 需要缓存的列表页（按组件名匹配，各视图内用 defineOptions 显式声明）
const KEEP_ALIVE_VIEWS = ['HomeView', 'DiscoverView', 'MyFeedView', 'FavoritesView']

onMounted(async () => {
  // 全局快捷键（J/K 换帖、/ 聚焦搜索）
  useGlobalShortcuts()
  // WebSocket 通知（登录后自动连接，未读角标实时更新）
  useWebSocket()
  // 登录态下预取未读数，供首页右上角入口展示角标
  if (localStorage.getItem('sdu_access_token')) {
    notif.fetchUnread().catch(() => {})
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
}
/* 错误态的兜底出口链接（配合 components/ErrorState.vue 使用） */
.state-link {
  color: var(--brand);
  font-size: var(--fs-body);
}
.state-link:hover {
  text-decoration: underline;
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
/* 底部导航已移除：通知/个人中心入口已集成到首页右上角，保留 scoped 空块以稳定样式隔离 */
</style>
