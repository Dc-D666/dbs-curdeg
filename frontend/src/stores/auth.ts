/** 用户态：token 管理 + 当前用户信息。 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { request, tokenStore } from '@/api/http'

export interface UserInfo {
  id: number
  username: string
  nickname: string
  avatar_url: string
  bio: string
  gender: number
  province: string
  city: string
  email: string
  user_type: number
  created_at: string
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserInfo | null>(null)
  const loaded = ref(false)

  function setTokens(t: TokenPair) {
    tokenStore.access = t.access_token
    tokenStore.refresh = t.refresh_token
  }

  async function fetchMe(): Promise<UserInfo | null> {
    try {
      const me = await request<UserInfo>({ url: '/users/me' })
      user.value = me
      return me
    } catch {
      user.value = null
      return null
    } finally {
      loaded.value = true
    }
  }

  function logout() {
    const rt = tokenStore.refresh
    if (rt) {
      request({ url: '/auth/logout', method: 'POST', data: { refresh_token: rt } }).catch(() => {})
    }
    tokenStore.clear()
    user.value = null
  }

  return { user, loaded, setTokens, fetchMe, logout }
})
