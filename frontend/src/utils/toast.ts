/**
 * 轻提示（TDesign Message 风格）：成功/错误/信息，顶部居中滑入，自动消失。
 * 用法：toast('保存成功', 'success') / toast('网络错误', 'error')
 */
export type ToastType = 'success' | 'error' | 'info' | 'warning'

const ICONS: Record<ToastType, string> = {
  success: '✓',
  error: '✕',
  warning: '!',
  info: 'ℹ',
}

let container: HTMLDivElement | null = null

function ensureContainer(): HTMLDivElement {
  if (!container) {
    container = document.createElement('div')
    container.className = 'toast-container'
    document.body.appendChild(container)
  }
  return container
}

export function toast(message: string, type: ToastType = 'info', duration = 2500): void {
  const box = ensureContainer()
  const el = document.createElement('div')
  el.className = `toast-item toast-${type}`

  const icon = document.createElement('span')
  icon.className = 'toast-icon'
  icon.textContent = ICONS[type]
  const text = document.createElement('span')
  text.textContent = message // textContent 防 XSS（message 可能来自后端用户内容）

  el.append(icon, text)
  box.appendChild(el)
  requestAnimationFrame(() => el.classList.add('show'))
  setTimeout(() => {
    el.classList.remove('show')
    setTimeout(() => el.remove(), 300)
  }, duration)
}
