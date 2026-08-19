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
  level: number
  join_time: string
  shutup_expire_at: string | null
  is_blocked: boolean
  role_id: number | null
  role_name: string
  username: string
  user_nickname: string
  avatar_url: string
}

export interface RoleItem {
  id: number
  community_id: number
  name: string
  color: string
  level: number
  sort: number
  perms: string[]
  is_default: boolean
  is_level_role: boolean
  created_at: string
}

export interface MyRole {
  role_id: number | null
  name: string
  sort: number
  is_owner: boolean
}

export interface OpLogItem {
  id: number
  action: string
  target_type: string
  target_id: number | null
  detail: Record<string, unknown> | null
  created_at: string
  operator_nickname: string
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

// ---------- 身份组（阶段 4） ----------

export const roleApi = {
  list(cid: number) {
    return request<RoleItem[]>({ url: `/communities/${cid}/roles` })
  },
  my(cid: number) {
    return request<MyRole>({ url: `/communities/${cid}/roles/my` })
  },
  create(cid: number, data: { name: string; color?: string; level?: number; perms?: string[]; is_level_role?: boolean }) {
    return request<RoleItem>({ url: `/communities/${cid}/roles`, method: 'POST', data })
  },
  update(cid: number, roleId: number, data: Partial<RoleItem>) {
    return request<RoleItem>({ url: `/communities/${cid}/roles/${roleId}`, method: 'PUT', data })
  },
  move(cid: number, roleId: number, direction: 'up' | 'down') {
    return request<RoleItem>({ url: `/communities/${cid}/roles/${roleId}/move`, method: 'POST', data: { direction } })
  },
  remove(cid: number, roleId: number) {
    return request<null>({ url: `/communities/${cid}/roles/${roleId}`, method: 'DELETE' })
  },
  assign(cid: number, userId: number, roleId: number | null) {
    return request<Member>({
      url: `/communities/${cid}/members/${userId}/role`,
      method: 'POST',
      data: { role_id: roleId },
    })
  },
}

// ---------- 管理动作（阶段 4） ----------

export const manageApi = {
  shutup(cid: number, userId: number, hours: number) {
    return request<Member>({ url: `/communities/${cid}/members/${userId}/shutup`, method: 'POST', data: { hours } })
  },
  unshutup(cid: number, userId: number) {
    return request<Member>({ url: `/communities/${cid}/members/${userId}/unshutup`, method: 'POST' })
  },
  kick(cid: number, userId: number) {
    return request<Member>({ url: `/communities/${cid}/members/${userId}/kick`, method: 'POST' })
  },
  block(cid: number, userId: number) {
    return request<Member>({ url: `/communities/${cid}/members/${userId}/block`, method: 'POST' })
  },
  unblock(cid: number, userId: number) {
    return request<Member>({ url: `/communities/${cid}/members/${userId}/unblock`, method: 'POST' })
  },
  ops(cid: number, page = 1, pageSize = 20) {
    return request<Page<OpLogItem>>({ url: `/communities/${cid}/ops`, params: { page, page_size: pageSize } })
  },
}
