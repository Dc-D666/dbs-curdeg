/** SSE 流式读取：POST + ReadableStream 解析 data: {json} 行（AI 帮写 / RAG 问答都用）。 */
import { tokenStore } from '@/api/http'

export interface SseEvent {
  type?: string
  delta?: string
  message?: string
  stage?: 'search' | 'embed' | 'answer'
  done?: number
  total?: number
  references?: Array<{ id: number; title: string }>
}

export async function streamPost(
  url: string,
  data: unknown,
  onDelta: (text: string) => void,
  opts: { signal?: AbortSignal; onEvent?: (event: SseEvent) => void } = {},
): Promise<void> {
  const token = tokenStore.access
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(data),
    signal: opts.signal,
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
        const obj = JSON.parse(payload) as SseEvent
        opts.onEvent?.(obj)
        if (typeof obj.delta === 'string') onDelta(obj.delta)
      } catch {
        /* 忽略坏行 */
      }
    }
  }
}
