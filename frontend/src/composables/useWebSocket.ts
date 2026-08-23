/** 全局单例 WebSocket 客户端（阶段 5，协议见 详细开发方案.md §5.3）。

- 首帧 auth（携带 access token）；服务端 10s 未认证断开
- 心跳：30s 一次 ping → pong（浏览器超时保护）
- 断线自动重连（指数退避，上限 30s）；登出/无 token 时断开
- 收到 notification 推送 → 未读角标 +1
- 只在 App.vue 初始化一次；任何页面直接用 store 的 unread
*/
import { watch } from 'vue'
import { ref } from 'vue'
import { tokenStore } from '@/api/http'
import { useNotificationStore } from '@/stores/notification'
import { useLiveStore } from '@/stores/live'

const state = ref<'idle' | 'connecting' | 'open' | 'closed'>('idle')

let ws: WebSocket | null = null
let heartbeatTimer: number | null = null
let reconnectTimer: number | null = null
let attempts = 0

const HEARTBEAT_MS = 30000

function startHeartbeat() {
  stopHeartbeat()
  heartbeatTimer = window.setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping' }))
    }
  }, HEARTBEAT_MS)
}

function stopHeartbeat() {
  if (heartbeatTimer !== null) {
    window.clearInterval(heartbeatTimer)
    heartbeatTimer = null
  }
}

function scheduleReconnect() {
  if (!tokenStore.access) return
  const delay = Math.min(1000 * 2 ** attempts, 30000)
  attempts += 1
  if (reconnectTimer !== null) window.clearTimeout(reconnectTimer)
  reconnectTimer = window.setTimeout(connect, delay)
}

export function connect() {
  if (state.value === 'connecting' || state.value === 'open') return
  const token = tokenStore.access
  if (!token) {
    state.value = 'idle'
    return
  }
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  state.value = 'connecting'
  ws = new WebSocket(`${proto}://${window.location.host}/ws`)

  ws.onopen = () => {
    ws?.send(JSON.stringify({ type: 'auth', token }))
  }

  ws.onmessage = (ev) => {
    let msg: { type?: string; data?: unknown }
    try {
      msg = JSON.parse(ev.data)
    } catch {
      return
    }
    if (msg.type === 'authed') {
      state.value = 'open'
      attempts = 0
      startHeartbeat()
      // 连上后同步一次未读数（角标初始值）
      useNotificationStore().fetchUnread().catch(() => {})
    } else if (msg.type === 'notification') {
      useNotificationStore().bumpUnread(1)
    } else if (msg.type === 'feed_new') {
      // 频道新内容（发帖/评论）→ 浮动药丸计数 +1
      useLiveStore().increment(1)
    }
    // pong：忽略（心跳只是保活）
  }

  ws.onclose = () => {
    state.value = 'closed'
    stopHeartbeat()
    scheduleReconnect()
  }

  ws.onerror = () => {
    try {
      ws?.close()
    } catch {
      /* ignore */
    }
  }
}

export function close() {
  if (reconnectTimer !== null) {
    window.clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  stopHeartbeat()
  if (ws) {
    ws.onclose = null
    try {
      ws.close()
    } catch {
      /* ignore */
    }
    ws = null
  }
  state.value = 'idle'
}

/** App.vue 挂载时调用一次：登录状态变化自动连接/断开。 */
export function useWebSocket() {
  watch(
    () => tokenStore.access,
    (v) => {
      if (v) connect()
      else close()
    },
    { immediate: true },
  )
  return { state, connect, close }
}
