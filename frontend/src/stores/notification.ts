/** 通知状态：未读数（WS 实时角标）+ 列表 + 通知开关。 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { notificationApi, type NotificationItem, type NotifySettings } from '@/api/notification'
import { loadErrorMessage } from '@/utils/error'

export const useNotificationStore = defineStore('notification', () => {
  const unread = ref(0)
  const items = ref<NotificationItem[]>([])
  const total = ref(0)
  const page = ref(1)
  const loaded = ref(false)
  const loading = ref(false)
  const error = ref('')
  const settings = ref<NotifySettings | null>(null)

  async function fetchUnread() {
    try {
      unread.value = (await notificationApi.unreadCount()).count
    } catch {
      unread.value = 0
    }
  }

  /** 拉取列表。失败时置 error 态（不再让页面停在骨架屏上），成功清空 error。
   *  scope：system=仅系统通知；interact=仅互动通知；undefined=全部。
   *  用于 /notifications（系统通知）与频道内消息中心（按频道过滤）。 */
  async function fetchList(reset = false, opts: { scope?: 'system' | 'interact'; community_id?: number } = {}) {
    if (reset) {
      page.value = 1
      items.value = []
    }
    loading.value = true
    error.value = ''
    try {
      const data = await notificationApi.list(page.value, 20, opts)
      items.value = reset ? data.items : [...items.value, ...data.items]
      total.value = data.total
      loaded.value = true
    } catch (e) {
      error.value = loadErrorMessage(e, '通知').text
      // 加载更多翻页失败要退回原页码，避免跳过一页数据
      if (!reset && page.value > 1) page.value -= 1
      throw e
    } finally {
      loading.value = false
    }
  }

  /** WS 推送到达：未读数 +1（页面开着时列表可手动刷新）。 */
  function bumpUnread(n = 1) {
    unread.value += n
  }

  async function markRead(id: number) {
    await notificationApi.read(id)
    const it = items.value.find((i) => i.id === id)
    if (it) it.is_read = true
    if (unread.value > 0) unread.value -= 1
  }

  async function markAllRead() {
    const { marked } = await notificationApi.readAll()
    unread.value = Math.max(0, unread.value - marked)
    items.value.forEach((i) => {
      i.is_read = true
    })
  }

  async function removeItem(id: number) {
    await notificationApi.remove(id)
    items.value = items.value.filter((i) => i.id !== id)
    if (total.value > 0) total.value -= 1
  }

  async function loadSettings() {
    settings.value = await notificationApi.getSettings()
  }

  async function saveSettings(patch: Partial<NotifySettings>) {
    settings.value = await notificationApi.updateSettings(patch)
  }

  return {
    unread, items, total, page, loaded, loading, error, settings,
    fetchUnread, fetchList, bumpUnread, markRead, markAllRead, removeItem, loadSettings, saveSettings,
  }
})
