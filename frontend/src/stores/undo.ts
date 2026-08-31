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

  /** 只清理状态，不触发任何回调。 */
  function reset() {
    clear()
    visible.value = false
    message.value = ''
    onUndo = null
    onCommit = null
  }

  /** 结算当前未决操作：有 onCommit 就立即执行（延迟执行型），否则仅丢弃撤销机会。
   *
   * 新操作到来前必须先结算上一条，否则 onCommit 会被覆盖 ——
   * 表现为「评论在 UI 上消失了，但服务端的删除从未发生」，刷新后内容复活。
   */
  function commitPending() {
    const commit = onCommit
    reset()
    commit?.()
  }

  /** 外部主动隐藏：等同结算（绝不静默丢弃未执行的删除）。 */
  function hide() {
    commitPending()
  }

  /** 展示撤销 Snackbar；超时未撤销才执行 onCommit，撤销则执行 onUndo。 */
  function notify(msg: string, undoFn: () => void, commitFn?: () => void, durationMs = 5000) {
    // 队列语义：已有未决操作时先立即结算上一条，再开新条
    if (visible.value) commitPending()
    message.value = msg
    onUndo = undoFn
    onCommit = commitFn ?? null
    visible.value = true
    clear()
    timer = setTimeout(() => {
      const commit = onCommit
      reset()
      commit?.()
    }, durationMs)
  }

  function undo() {
    const fn = onUndo
    reset()
    fn?.()
  }

  return { message, visible, notify, undo, hide, commitPending }
})
