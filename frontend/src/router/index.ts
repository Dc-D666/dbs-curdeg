import { createRouter, createWebHistory } from 'vue-router'
import { tokenStore } from '@/api/http'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('@/views/HomeView.vue') },
    { path: '/login', name: 'login', component: () => import('@/views/auth/LoginView.vue') },
    { path: '/register', name: 'register', component: () => import('@/views/auth/RegisterView.vue') },
    { path: '/me', name: 'me', component: () => import('@/views/MeView.vue') },
  ],
})

// 需要登录的页面守卫
router.beforeEach((to) => {
  const authed = !!tokenStore.access
  if (to.name === 'me' && !authed) return { name: 'login' }
  if ((to.name === 'login' || to.name === 'register') && authed) return { name: 'home' }
  return true
})

export default router
