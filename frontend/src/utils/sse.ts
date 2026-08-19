/** SSE 流式读取（AI 帮写用）：POST + ReadableStream 解析 data: {"delta": "..."} 行。 */
import { tokenStore } from '@/api/http'

export async function streamPost(
  url: string,
  data: unknown,
  onDelta: (text: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const token = tokenStore.access
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(data),
    signal,
  })
  if (!res.ok || !res.body) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.message || 'AI 请求失败')
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const parts = buf.split('\n\n')
    buf = parts.pop() ?? ''
    for (const part of parts) {
      const line = part.trim()
      if (!line.startsWith('data:')) continue
      const payload = line.slice(5).trim()
      if (payload === '[DONE]') continue
      try {
        const obj = JSON.parse(payload) as { delta?: string }
        if (typeof obj.delta === 'string') onDelta(obj.delta)
      } catch {
        /* 忽略坏行 */
      }
    }
  }
}
