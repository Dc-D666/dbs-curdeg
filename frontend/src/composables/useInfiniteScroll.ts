/** 无限滚动：列表滚动到接近底部时自动拉取下一页，替代手动「加载更多」按钮。 */
import { onBeforeUnmount, onMounted, type Ref } from 'vue'

interface Options {
  /** 距底部多少 px 触发加载（默认 120） */
  threshold?: number
  /** 容器 ref；不传则监听 window 滚动 */
  container?: Ref<HTMLElement | null>
  /** 是否启用（数据未加载完时 true） */
  enabled: Ref<boolean>
  /** 触发加载的回调 */
  load: () => void
}

/**
 * 用法：
 * const { done } = useInfiniteScroll({ enabled: hasMore, load: loadMore })
 * 组件卸载时自动移除监听。
 */
export function useInfiniteScroll({ threshold = 120, container, enabled, load }: Options) {
  function onScroll() {
    if (!enabled.value) return
    const el = container?.value
    let nearBottom = false
    if (el) {
      nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold
    } else {
      nearBottom =
        window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - threshold
    }
    if (nearBottom) load()
  }

  onMounted(() => {
    if (container?.value) container.value.addEventListener('scroll', onScroll)
    else window.addEventListener('scroll', onScroll)
  })
  onBeforeUnmount(() => {
    if (container?.value) container.value.removeEventListener('scroll', onScroll)
    else window.removeEventListener('scroll', onScroll)
  })

  return { onScroll }
}
