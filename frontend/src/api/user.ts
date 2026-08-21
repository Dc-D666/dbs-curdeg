/** 用户公开资料 API。 */
import { request, type Page } from './http'

export interface PublicUser {
  id: number
  username: string
  nickname: string
  avatar_url: string
  bio: string
  gender: number
  province: string
  city: string
  user_type: number
  created_at: string
}

export interface FollowUserItem {
  id: number
  nickname: string
  username: string
  avatar_url: string
  followed_at: string | null
}

export const userApi = {
  get(id: number) {
    return request<PublicUser>({ url: `/users/${id}` })
  },
  // 用户互关（P0）
  follow(id: number) {
    return request<{ following: boolean; count: number }>({ url: `/users/${id}/follow`, method: 'POST' })
  },
  unfollow(id: number) {
    return request<{ following: boolean; count: number }>({ url: `/users/${id}/follow`, method: 'DELETE' })
  },
  followStatus(id: number) {
    return request<{ following: boolean }>({ url: `/users/${id}/follow-status` })
  },
  myFollowing(page = 1, pageSize = 20) {
    return request<Page<FollowUserItem>>({ url: '/me/following', params: { page, page_size: pageSize } })
  },
  myFollowers(page = 1, pageSize = 20) {
    return request<Page<FollowUserItem>>({ url: '/me/followers', params: { page, page_size: pageSize } })
  },
}
