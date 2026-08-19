/** 通知状态：未读数（WS 实时角标）+ 列表 + 通知开关。 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { notificationApi, type NotificationItem, type NotifySettings } from '@/api/notification'

export const useNotificationStore = defineStore('notification', () => {
  const unread = ref(0)
  const items = ref<NotificationItem[]>([])
  const total = ref(0)
  const page = ref(1)
  const loaded = ref(false)
  const loading = ref(false)
  const settings = ref<NotifySettings | null>(null)

  async function fetchUnread() {
    try {
      unread.value = (await notificationApi.unreadCount()).count
    } catch {
      unread.value = 0
    }
  }

  async function fetchList(reset = false) {
    if (reset) {
      page.value = 1
      items.value = []
    }
    loading.value = true
    try {
      const data = await notificationApi.list(page.value, 20)
      items.value = reset ? data.items : [...items.value, ...data.items]
      total.value = data.total
      loaded.value = true
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

  async function loadSettings() {
    settings.value = await notificationApi.getSettings()
  }

  async function saveSettings(patch: Partial<NotifySettings>) {
    settings.value = await notificationApi.updateSettings(patch)
  }

  return {
    unread, items, total, page, loaded, loading, settings,
    fetchUnread, fetchList, bumpUnread, markRead, markAllRead, loadSettings, saveSettings,
  }
})
