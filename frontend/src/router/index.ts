import { createRouter, createWebHistory } from 'vue-router'
import { tokenStore } from '@/api/http'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('@/views/HomeView.vue') },
    { path: '/discover', name: 'discover', component: () => import('@/views/DiscoverView.vue') },
    { path: '/c/:id', name: 'community', component: () => import('@/views/CommunityDetailView.vue') },
    { path: '/c/:id/admin', name: 'community-admin', component: () => import('@/views/AdminView.vue') },
    { path: '/c/:id/boards/:bid/post/new', name: 'post-create', component: () => import('@/views/PostCreateView.vue') },
    { path: '/p/:id', name: 'post', component: () => import('@/views/PostDetailView.vue') },
    { path: '/login', name: 'login', component: () => import('@/views/auth/LoginView.vue') },
    { path: '/register', name: 'register', component: () => import('@/views/auth/RegisterView.vue') },
    { path: '/me', name: 'me', component: () => import('@/views/MeView.vue') },
    { path: '/me/profile', name: 'my-profile', component: () => import('@/views/me/ProfileView.vue') },
    { path: '/me/channels', name: 'my-channels', component: () => import('@/views/me/MyChannelsView.vue') },
    { path: '/me/notification-settings', name: 'my-notification-settings', component: () => import('@/views/me/NotificationSettingsView.vue') },
    { path: '/me/security', name: 'my-security', component: () => import('@/views/me/SecurityView.vue') },
    { path: '/me/favorites', name: 'my-favorites', component: () => import('@/views/FavoritesView.vue') },
    { path: '/notifications', name: 'notifications', component: () => import('@/views/NotificationView.vue') },
    { path: '/dashboard', name: 'dashboard', component: () => import('@/views/DashboardView.vue') },
    { path: '/me/feed', name: 'my-feed', component: () => import('@/views/MyFeedView.vue') },
    { path: '/users/:id', name: 'user', component: () => import('@/views/UserProfileView.vue') },
    { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/views/NotFoundView.vue') },
  ],
})

// 需要登录的页面守卫：发帖页也要拦截，否则游客写完一整篇才发现要登录（只能靠草稿兜底）
const guardedNames = ['community-admin', 'notifications', 'dashboard', 'post-create']
router.beforeEach((to) => {
  const authed = !!tokenStore.access
  const needAuth = to.path === '/me' || to.path.startsWith('/me/') || guardedNames.includes(String(to.name))
  if (needAuth && !authed) {
    // 带上来源地址，登录后自动回到原页面
    return { name: 'login', query: to.fullPath === '/' ? {} : { redirect: to.fullPath } }
  }
  if ((to.name === 'login' || to.name === 'register') && authed) return { name: 'home' }
  return true
})

export default router
