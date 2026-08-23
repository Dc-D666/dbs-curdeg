/** 撤销机制（B）：轻量破坏性操作直接执行，底部 Snackbar 提供 5s 撤销。
 *
 * 两种用法：
 * 1. 立即执行型（取消关注）：操作马上就做，undo 回调负责“恢复”。
 *    undo.notify('已取消关注', () => reFollow())
 * 2. 延迟执行型（删除评论）：点击先不调 API，仅移除 UI + 显示撤销；
 *    未在 5s 内撤销才真正执行（onCommit），撤销则恢复 UI 且不调 API。
 *    undo.notify('已删除评论', () => restoreUI(), () => api.delete())
 *
 * 关联组件：components/UndoSnackbar.vue，全局挂载一次。
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUndoStore = defineStore('undo', () => {
  const message = ref('')
  const visible = ref(false)
  let onUndo: (() => void) | null = null
  let onCommit: (() => void) | null = null
  let timer: ReturnType<typeof setTimeout> | null = null

  function clear() {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
  }

  function hide() {
    visible.value = false
    onUndo = null
    onCommit = null
    clear()
  }

  /** 展示撤销 Snackbar；超时未撤销才执行 onCommit，撤销则执行 onUndo。 */
  function notify(msg: string, undoFn: () => void, commitFn?: () => void, durationMs = 5000) {
    message.value = msg
    onUndo = undoFn
    onCommit = commitFn ?? null
    visible.value = true
    clear()
    timer = setTimeout(() => {
      const commit = onCommit
      hide()
      commit?.()
    }, durationMs)
  }

  function undo() {
    const fn = onUndo
    hide()
    fn?.()
  }

  return { message, visible, notify, undo, hide }
})
