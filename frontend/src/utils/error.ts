/** 错误归类工具：配合 api/http.ts 的 ApiError，把「网络错误」和「内容不存在」区分开。 */
import { ApiError } from '@/api/http'

/** 取可展示的错误文案。
 *
 * status=0 表示压根没拿到响应（断网/超时/请求被取消），此时 axios 的 message
 * 是 "Network Error" 之类英文原文，直接展示给用户没有意义 —— 统一回落到中文兜底文案。
 */
export function errMessage(e: unknown, fallback = '请求失败'): string {
  if (isNetworkError(e)) return fallback
  const msg = e instanceof Error ? e.message.trim() : ''
  return msg || fallback
}

/** HTTP 404：目标确实不存在/已删除，重试没意义。 */
export function isNotFound(e: unknown): boolean {
  return e instanceof ApiError && e.status === 404
}

/** 断网 / 超时 / 无法连接：status 为 0。 */
export function isNetworkError(e: unknown): boolean {
  return e instanceof ApiError && e.status === 0
}

/** 列表/详情首屏加载的失败文案：404 说“不存在”，断网说“网络异常”，其余透传后端文案。 */
export function loadErrorMessage(
  e: unknown,
  subject: string,
  notFoundText = `${subject}不存在或已被删除`,
): { text: string; notFound: boolean } {
  if (isNotFound(e)) return { text: notFoundText, notFound: true }
  if (isNetworkError(e)) return { text: `网络异常，${subject}加载失败`, notFound: false }
  return { text: errMessage(e, `${subject}加载失败`), notFound: false }
}
