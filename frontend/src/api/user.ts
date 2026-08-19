/** 用户公开资料 API。 */
import { request } from './http'

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

export const userApi = {
  get(id: number) {
    return request<PublicUser>({ url: `/users/${id}` })
  },
}
