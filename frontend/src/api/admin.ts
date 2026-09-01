/** 系统管理员 API（P0）：看板、敏感词、系统配置、AI 配置、AI 日志、举报处理。 */
import { request, type Page } from './http'

export interface SensitiveWordItem {
  id: number
  word: string
  category: string
  enabled: boolean
}

export interface ReportItem {
  id: number
  target_type: number
  target_id: number
  reason_type: string
  detail: string
  evidence: string[]
  status: number
  result: string
  handler_nickname: string
  handled_at: string | null
  created_at: string | null
  reporter_nickname: string
}

export interface AiCallLogItem {
  id: number
  feature: string
  user_id: number | null
  model: string
  prompt_tokens: number
  completion_tokens: number
  latency_ms: number
  status: string
  error: string
  created_at: string | null
}

export interface DashboardTrendItem {
  stat_date: string
  new_members: number
  active_members: number
  posts: number
  interactions: number
  violations: number
  ai_calls: number
  retention: number
}

export const adminApi = {
  // 运营看板
  stats() {
    return request<Record<string, unknown>>({ url: '/admin/stats' })
  },
  dashboardTrend(days = 7) {
    return request<{ days: number; items: DashboardTrendItem[]; summary: Record<string, number> }>({
      url: '/admin/dashboard/trend',
      params: { days },
    })
  },
  exportDashboard(days = 7) {
    const token = localStorage.getItem('sdu_access_token')
    return fetch(`/api/v1/admin/dashboard/export?days=${days}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
  },
  // 敏感词库
  sensitiveWords(category?: string, page = 1, pageSize = 20) {
    return request<Page<SensitiveWordItem>>({ url: '/admin/sensitive-words', params: { category, page, page_size: pageSize } })
  },
  addSensitiveWord(word: string, category = '其他') {
    return request<{ id: number; word: string; category: string }>({ url: '/admin/sensitive-words', method: 'POST', data: { word, category } })
  },
  setSensitiveWordEnabled(id: number, enabled: boolean) {
    return request<null>({ url: `/admin/sensitive-words/${id}/enabled`, method: 'PUT', params: { enabled } })
  },
  deleteSensitiveWord(id: number) {
    return request<null>({ url: `/admin/sensitive-words/${id}`, method: 'DELETE' })
  },
  // 系统配置
  configs() {
    return request<Array<{ key: string; value: string; description: string }>>({ url: '/admin/configs' })
  },
  setConfig(key: string, value: string, description = '') {
    return request<{ key: string; value: string }>({ url: '/admin/configs', method: 'PUT', data: { key, value, description } })
  },
  publicConfig() {
    return request<Record<string, string>>({ url: '/public/config' })
  },
  // AI 配置
  aiConfigs() {
    return request<Array<{ feature: string; enabled: boolean; model: string; params: Record<string, unknown>; prompt_template: string; rate_limit: number }>>({ url: '/admin/ai-configs' })
  },
  updateAiConfig(feature: string, data: Partial<{ enabled: boolean; model: string; params: Record<string, unknown>; prompt_template: string; rate_limit: number }>) {
    return request<{ feature: string; enabled: boolean }>({ url: `/admin/ai-configs/${feature}`, method: 'PUT', data })
  },
  // AI 调用日志
  aiLogs(feature?: string, status?: string, page = 1, pageSize = 20) {
    return request<Page<AiCallLogItem>>({ url: '/admin/ai-logs', params: { feature, status, page, page_size: pageSize } })
  },
  aiLogSummary(days = 7) {
    return request<{ days: number; features: Array<{ feature: string; count: number }> }>({ url: '/admin/ai-logs/summary', params: { days } })
  },
  // 举报
  reports(status?: number, page = 1, pageSize = 20) {
    return request<Page<ReportItem>>({ url: '/admin/reports', params: { status, page, page_size: pageSize } })
  },
  handleReport(id: number, action: 'processing' | 'done' | 'rejected', result = '') {
    return request<{ id: number; status: number }>({ url: `/admin/reports/${id}/handle`, method: 'POST', data: { action, result } })
  },
  myReports(page = 1, pageSize = 20) {
    return request<Page<ReportItem>>({ url: '/me/reports', params: { page, page_size: pageSize } })
  },
  // 用户封禁/解封
  setUserStatus(userId: number, status: number) {
    return request<{ id: number; status: number }>({ url: `/admin/users/${userId}/status`, method: 'PUT', data: { status } })
  },
  // 内容审核记录（文档⑪人工复审）
  reviews(status?: number, page = 1, pageSize = 20) {
    return request<Page<AdminReviewItem>>({ url: '/admin/reviews', params: { status, page, page_size: pageSize } })
  },
  handleReview(reviewId: number, approve: boolean) {
    return request<null>({ url: `/admin/reviews/${reviewId}/handle`, method: 'POST', data: { approve } })
  },
  // 平台级频道/用户列表（平台控制台首页）
  adminCommunities(keyword?: string, status?: number, page = 1, pageSize = 20) {
    return request<Page<AdminCommunityItem>>({
      url: '/admin/communities',
      params: { keyword: keyword || undefined, status, page, page_size: pageSize },
    })
  },
  adminUsers(keyword?: string, status?: number, page = 1, pageSize = 20) {
    return request<Page<AdminUserItem>>({
      url: '/admin/users',
      params: { keyword: keyword || undefined, status, page, page_size: pageSize },
    })
  },
}

export interface AdminReviewItem {
  id: number
  content_type: number // 1帖子 2评论
  content_id: number
  status: number // 0待审 1通过 2驳回 3转人工
  violation_type: string
  violation_detail: string
  review_method: number
  appeal_at: string | null
  result: string
  reviewed_at: string | null
  created_at: string | null
  post_title: string
}

// ---------- 平台级频道/用户管理（平台控制台首页用） ----------

export interface AdminCommunityItem {
  id: number
  number: string
  name: string
  profile: string
  avatar_url: string
  member_count: number
  post_count: number
  owner_id: number
  owner_name: string
  /** 频道状态：0正常 1关闭 2违规封禁 */
  status: number
  active_members: number
  created_at: string
}

export interface AdminUserItem {
  id: number
  username: string
  nickname: string
  avatar_url: string
  email: string
  /** 用户状态：0正常 1封禁 2注销 */
  status: number
  /** 0普通 1系统管理员 2AI虚拟账号 */
  user_type: number
  joined_communities: number
  created_at: string
}
