/** 桌面端全局快捷键（P2 Polish & Shortcuts）。
 *
 * - J / K：信息流中上下切换帖子（滚动到下一/上一张 FeedCard）
 * - /     ：聚焦全局搜索（跳转 /discover 并聚焦搜索框）
 * - Esc/方向键：由 Lightbox 等全局组件自行处理（此处不拦截）
 *
 * 仅在非输入态生效（input/textarea/contenteditable 内不触发），
 * 监听挂在 App.vue 全局，避免在各视图重复实现。
 */
import { onBeforeUnmount, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const EDITABLE_TAGS = ['INPUT', 'TEXTAREA', 'SELECT']

export function useGlobalShortcuts() {
  const router = useRouter()

  function isEditable(target: EventTarget | null): boolean {
    const el = target as HTMLElement | null
    if (!el) return false
    return EDITABLE_TAGS.includes(el.tagName) || el.isContentEditable
  }

  /** 聚焦 /discover 页的搜索输入框。 */
  function focusSearch() {
    if (!router.currentRoute.value.path.startsWith('/discover')) {
      router.push('/discover')
    }
    // 路由切换后下一帧再聚焦
    requestAnimationFrame(() => {
      setTimeout(() => {
        const input = document.querySelector('.search-input input') as HTMLInputElement | null
        input?.focus()
      }, 120)
    })
  }

  /** 找到视口内最近的 FeedCard，按 dir 滚动到下一/上一张。 */
  function navFeed(dir: 1 | -1) {
    const cards = Array.from(document.querySelectorAll<HTMLElement>('.feed-card'))
    if (cards.length === 0) return
    const viewport = window.innerHeight
    // 当前激活：最接近视口中线的卡片
    let activeIdx = 0
    let bestDist = Infinity
    cards.forEach((c, i) => {
      const r = c.getBoundingClientRect()
      const center = (r.top + r.bottom) / 2
      const dist = Math.abs(center - viewport / 2)
      if (dist < bestDist) {
        bestDist = dist
        activeIdx = i
      }
    })
    const target = cards[Math.min(Math.max(activeIdx + dir, 0), cards.length - 1)]
    target?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    // 居中后短暂高亮，给用户一个焦点反馈
    target.classList.remove('feed-kbd-focus')
    // 强制回流以重启动画
    void (target as HTMLElement).offsetWidth
    target.classList.add('feed-kbd-focus')
  }

  function onKeydown(e: KeyboardEvent) {
    if (isEditable(e.target)) return
    const k = e.key
    if (k === '/') {
      e.preventDefault()
      focusSearch()
    } else if (k === 'j') {
      e.preventDefault()
      navFeed(1)
    } else if (k === 'k') {
      e.preventDefault()
      navFeed(-1)
    }
  }

  onMounted(() => window.addEventListener('keydown', onKeydown))
  onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
}
