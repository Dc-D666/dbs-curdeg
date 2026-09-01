/** 频道/版块/成员 API。 */
import { request, tokenStore, type Page } from './http'

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
  /** 全员禁言截止时间（频道主/管理员设置；发帖与评论被禁，点赞不禁） */
  all_muted_until: string | null
  created_at: string
  is_member: boolean
  my_member_type: number | null
  /** 是否频道主（member_type==0）：前端据此显示运营中心/管理入口 */
  is_owner: boolean
  /** 当前用户在频道内的权限点集合（运营中心按成员数据权限显示，super=频道主专属） */
  my_perms: string[]
  /** 平台管理员（user_type=1）标记：前端据此展示封禁/解封等平台级操作 */
  is_platform_admin?: boolean
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
  user_avatar: string
}

export interface TopicItem {
  id: number
  community_id: number
  name: string
  description: string
  cover_url: string
  rules: string
  post_count: number
  heat_value: number
  status: number
  created_at: string | null
}

export interface MyChannels {
  owned: Community[]
  managed: Community[]
  joined: Community[]
}

export interface MyMemberInfo {
  member_id: number
  level: number
  member_type: number
  nickname: string
  role_id: number | null
  role_name: string
  role_color: string
  is_owner: boolean
  join_time: string | null
}

export const communityApi = {
  list(page = 1, pageSize = 20, sort: 'latest' | 'hot' = 'latest') {
    return request<Page<Community>>({ url: '/communities', params: { page, page_size: pageSize, sort } })
  },
  mine() {
    return request<MyChannels>({ url: '/communities/mine' })
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
  /** 我的频道成员信息（我的资料/我的等级） */
  myMember(id: number) {
    return request<MyMemberInfo>({ url: `/communities/${id}/my-member` })
  },
  /** 更新我的频道内昵称 */
  updateMyMember(id: number, nickname: string) {
    return request<null>({ url: `/communities/${id}/my-member`, method: 'PUT', data: { nickname } })
  },
  /** 频道分享二维码 PNG（需登录；返回 blob） */
  qr(id: number) {
    const token = tokenStore.access
    return fetch(`/api/v1/communities/${id}/qr`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
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
  /** 访问打点：进入频道工作台/详情时调用，供运营中心访问统计 */
  visit(id: number) {
    return request<null>({ url: `/communities/${id}/visit`, method: 'POST' })
  },
  /** 频道运营中心（频道主/有成员数据权限）：昨日/用户/内容/排名数据 */
  opsCenter(id: number, boardId?: number) {
    return request<OpsCenterData>({
      url: `/communities/${id}/ops-center`,
      params: boardId ? { board_id: boardId } : undefined,
    })
  },
  boards(cid: number) {
    return request<Board[]>({ url: `/communities/${cid}/boards` })
  },
  createBoard(cid: number, data: { name: string; description?: string; sort?: number; allow_post_role_ids?: number[]; allow_anonymous?: boolean }) {
    return request<Board>({ url: `/communities/${cid}/boards`, method: 'POST', data })
  },
  updateBoard(cid: number, boardId: number, data: Partial<Board>) {
    return request<Board>({ url: `/communities/${cid}/boards/${boardId}`, method: 'PUT', data })
  },
  deleteBoard(cid: number, boardId: number) {
    return request<null>({ url: `/communities/${cid}/boards/${boardId}`, method: 'DELETE' })
  },
  /** 转让频道（仅频道主）：把频道主身份交给目标成员 */
  transfer(cid: number, targetUserId: number) {
    return request<Community>({ url: `/communities/${cid}/transfer`, method: 'POST', data: { target_user_id: targetUserId } })
  },
  /** 全员禁言：hours=0 解除；1-720 小时（发帖/评论禁，点赞不禁） */
  allMute(cid: number, hours: number) {
    return request<Community>({ url: `/communities/${cid}/all-mute`, method: 'PUT', data: { hours } })
  },
  /** 黑名单列表（需 member_manage 权限） */
  blacklist(cid: number, page = 1, pageSize = 50, keyword?: string) {
    return request<Page<Member>>({ url: `/communities/${cid}/blacklist`, params: { page, page_size: pageSize, keyword: keyword || undefined } })
  },
  members(cid: number, page = 1, pageSize = 50, keyword?: string) {
    return request<Page<Member>>({ url: `/communities/${cid}/members`, params: { page, page_size: pageSize, keyword: keyword || undefined } })
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
  // 话题（P0）
  topics(cid: number, sort: 'hot' | 'latest' = 'hot') {
    return request<TopicItem[]>({ url: `/communities/${cid}/topics`, params: { sort } })
  },
  createTopic(cid: number, data: { name: string; description?: string; cover_url?: string; rules?: string }) {
    return request<TopicItem>({ url: `/communities/${cid}/topics`, method: 'POST', data })
  },
  updateTopic(cid: number, topicId: number, data: Partial<{ name: string; description: string; cover_url: string; rules: string }>) {
    return request<TopicItem>({ url: `/communities/${cid}/topics/${topicId}`, method: 'PUT', data })
  },
  deleteTopic(cid: number, topicId: number) {
    return request<null>({ url: `/communities/${cid}/topics/${topicId}`, method: 'DELETE' })
  },
  // 频道 AI 助手（P0）
  ensureAiAssistant(cid: number, nickname = '频道助手') {
    return request<{ member_id: number; user_id: number; nickname: string; avatar_url: string }>({
      url: `/communities/${cid}/ai-assistant`,
      method: 'POST',
      data: { nickname },
    })
  },
}

// ---------- Feed 热度策略（阶段 5，文档⑮） ----------

export interface OpsCenterData {
  date: string
  note: string
  yesterday: {
    new_members: number
    left_members: number
    visits: number
    visitors: number
    posts: number
    views: number
    post_authors: number
    new_likes: number
    new_comments: number
  }
  today: {
    new_members: number
    visits: number
    posts: number
  }
  user_data: {
    total_members: number
    all_visits: number
    all_visitors: number
    active_members_today: number
    active_rate: number
    member_rank: Array<{ user_id: number; nickname: string; level: number; member_type: number; posts: number; comments: number }>
  }
  content_analysis: {
    boards: Array<{
      board_id: number
      board_name: string
      yesterday_posts: number
      views: number
      yesterday_views: number
      yesterday_new_likes: number
      yesterday_new_comments: number
      deleted_posts: number
    }>
  }
  post_rank: Array<{
    id: number
    title: string
    board_id: number
    view_count: number
    like_count: number
    comment_count: number
    favorite_count: number
    heat: number
    created_at: string
  }>
}

export interface FeedStrategy {
  sort_rule: number // 0最新 1热度 2精华优先
  weight_like: number
  weight_comment: number
  weight_favorite: number
  decay_hours: number
  top_weight: number
  cache_ttl: number
}

export const feedStrategyApi = {
  get(cid: number) {
    return request<FeedStrategy>({ url: `/communities/${cid}/feed-strategy` })
  },
  update(cid: number, patch: Partial<FeedStrategy>) {
    return request<FeedStrategy>({ url: `/communities/${cid}/feed-strategy`, method: 'PUT', data: patch })
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
  exportOps(cid: number) {
    // 导出 CSV：走原生请求拿文件下载
    const token = tokenStore.access
    return fetch(`/api/v1/communities/${cid}/ops/export`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
  },
}
