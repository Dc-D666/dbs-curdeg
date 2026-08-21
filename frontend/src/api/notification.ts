/** 通知相关 API（阶段 5）。 */
import { request, type Page } from '@/api/http'

export interface NotificationItem {
  id: number
  type: 'mention' | 'like' | 'comment' | 'follow' | 'system' | 'review_result' | 'report_feedback'
  actor_id: number | null
  actor_nickname: string
  actor_avatar: string
  community_id: number | null
  community_name: string
  ref_id: number | null
  title: string
  summary: string
  is_read: boolean
  read_at: string | null
  created_at: string | null
}

export interface NotifySettings {
  mention: boolean
  like: boolean
  comment: boolean
  follow: boolean
  system: boolean
  review: boolean
  report: boolean
}

export const notificationApi = {
  list: (page = 1, page_size = 20) =>
    request<Page<NotificationItem>>({ url: '/notifications', params: { page, page_size } }),
  unreadCount: () => request<{ count: number }>({ url: '/notifications/unread-count' }),
  read: (id: number) => request({ url: `/notifications/${id}/read`, method: 'POST' }),
  readAll: () => request<{ marked: number }>({ url: '/notifications/read-all', method: 'POST' }),
  remove: (id: number) => request({ url: `/notifications/${id}`, method: 'DELETE' }),
  getSettings: () => request<NotifySettings>({ url: '/notifications/settings' }),
  updateSettings: (patch: Partial<NotifySettings>) =>
    request<NotifySettings>({ url: '/notifications/settings', method: 'PUT', data: patch }),
}
