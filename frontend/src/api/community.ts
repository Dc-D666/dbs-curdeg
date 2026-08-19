/** 频道/版块/成员 API。 */
import { request, type Page } from './http'

export interface Board {
  id: number
  community_id: number
  name: string
  description: string
  sort: number
  allow_post_role_ids: number[]
  allow_anonymous: boolean
  status: number
}

export interface Community {
  id: number
  number: string
  name: string
  profile: string
  avatar_url: string
  cover_url: string
  member_count: number
  post_count: number
  join_setting: number
  visitor_interact_switch: boolean
  owner_id: number
  status: number
  created_at: string
  is_member: boolean
  my_member_type: number | null
  boards: Board[]
}

export interface Member {
  id: number
  community_id: number
  user_id: number
  nickname: string
  member_type: number
  join_time: string
  shutup_expire_at: string | null
  is_blocked: boolean
  username: string
  user_nickname: string
  avatar_url: string
}

export interface JoinRequestItem {
  id: number
  community_id: number
  user_id: number
  status: number
  created_at: string
  username: string
  user_nickname: string
}

export const communityApi = {
  list(page = 1, pageSize = 20) {
    return request<Page<Community>>({ url: '/communities', params: { page, page_size: pageSize } })
  },
  get(id: number) {
    return request<Community>({ url: `/communities/${id}` })
  },
  create(data: { name: string; profile?: string; join_setting?: number }) {
    return request<Community>({ url: '/communities', method: 'POST', data })
  },
  update(id: number, data: Partial<Community>) {
    return request<Community>({ url: `/communities/${id}`, method: 'PUT', data })
  },
  updateStatus(id: number, status: number) {
    return request<Community>({ url: `/communities/${id}/status`, method: 'PUT', data: { status } })
  },
  dissolve(id: number) {
    return request<null>({ url: `/communities/${id}`, method: 'DELETE' })
  },
  join(id: number) {
    return request<{ status: string; message: string }>({ url: `/communities/${id}/join`, method: 'POST' })
  },
  leave(id: number) {
    return request<null>({ url: `/communities/${id}/leave`, method: 'POST' })
  },
  boards(cid: number) {
    return request<Board[]>({ url: `/communities/${cid}/boards` })
  },
  createBoard(cid: number, data: { name: string; description?: string; sort?: number }) {
    return request<Board>({ url: `/communities/${cid}/boards`, method: 'POST', data })
  },
  members(cid: number, page = 1, pageSize = 50) {
    return request<Page<Member>>({ url: `/communities/${cid}/members`, params: { page, page_size: pageSize } })
  },
  joinRequests(cid: number, page = 1, pageSize = 20) {
    return request<Page<JoinRequestItem>>({ url: `/communities/${cid}/join-requests`, params: { page, page_size: pageSize } })
  },
  handleJoinRequest(cid: number, requestId: number, approve: boolean) {
    return request<null>({
      url: `/communities/${cid}/join-requests/${requestId}`,
      method: 'POST',
      data: { approve },
    })
  },
}
