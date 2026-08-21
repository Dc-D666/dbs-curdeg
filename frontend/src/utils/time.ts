/**
 * 时间显示工具：把后端时间字符串转成友好的相对时间 / 绝对时间。
 * 用法：timeAgo('2026-08-20 12:00:00')    → “3 分钟前”
 *       formatTime(d)                      → “08-20 12:00”
 */

/** 解析后端常见格式时间串（"YYYY-MM-DD HH:mm:ss" 或 ISO 8601）。无效返回 null。 */
export function parseTime(value: string | number | Date | null | undefined): Date | null {
  if (value == null) return null
  const d = value instanceof Date ? value : new Date(value)
  return Number.isNaN(d.getTime()) ? null : d
}

/** 相对时间：刚刚 / N 分钟前 / N 小时前 / N 天前。超过 7 天回退到绝对时间。 */
export function timeAgo(value: string | number | Date | null | undefined): string {
  const d = parseTime(value)
  if (!d) return ''
  const diff = Date.now() - d.getTime()
  if (diff < 0) return formatTime(d)
  const minute = 60_000
  const hour = 60 * minute
  const day = 24 * hour
  if (diff < minute) return '刚刚'
  if (diff < hour) return `${Math.floor(diff / minute)} 分钟前`
  if (diff < day) return `${Math.floor(diff / hour)} 小时前`
  if (diff < 7 * day) return `${Math.floor(diff / day)} 天前`
  return formatTime(d)
}

/** 绝对时间：MM-DD HH:mm（跨年补 YYYY）。 */
export function formatTime(value: string | number | Date | null | undefined): string {
  const d = parseTime(value)
  if (!d) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  const mm = pad(d.getMonth() + 1)
  const dd = pad(d.getDate())
  const hh = pad(d.getHours())
  const mi = pad(d.getMinutes())
  const base = `${mm}-${dd} ${hh}:${mi}`
  return d.getFullYear() !== new Date().getFullYear() ? `${d.getFullYear()} ${base}` : base
}