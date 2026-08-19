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
    { path: '/notifications', name: 'notifications', component: () => import('@/views/NotificationView.vue') },
    { path: '/me/feed', name: 'my-feed', component: () => import('@/views/MyFeedView.vue') },
    { path: '/users/:id', name: 'user', component: () => import('@/views/UserProfileView.vue') },
    { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/views/NotFoundView.vue') },
  ],
})

// 需要登录的页面守卫
router.beforeEach((to) => {
  const authed = !!tokenStore.access
  if ((to.name === 'me' || to.name === 'community-admin' || to.name === 'notifications') && !authed) return { name: 'login' }
  if ((to.name === 'login' || to.name === 'register') && authed) return { name: 'home' }
  return true
})

export default router
