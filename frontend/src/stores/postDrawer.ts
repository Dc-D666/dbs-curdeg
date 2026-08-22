/** 帖子阅读抽屉（P1 ①）：右侧抽屉保持频道/信息流上下文，不整页跳转。
 *
 * 桌面端（>=1024px）打开抽屉；移动端仍走整页导航（抽屉在窄屏体验差）。
 * 组件通过 postId 触发挂载 PostDetailView（embedded 模式）。
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const usePostDrawer = defineStore('postDrawer', () => {
  const postId = ref<number | null>(null)

  function open(id: number) {
    postId.value = id
  }

  function close() {
    postId.value = null
  }

  return { postId, open, close }
})
