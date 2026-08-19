/**
 * 确认对话框 —— 基于 TDesign DialogPlugin（tdesign.tencent.com/vue-next/components/dialog）。
 * 用法：if (await confirmDialog('删除帖子', '确定删除该帖子？')) { ... }
 */
import { DialogPlugin } from 'tdesign-vue-next'

export function confirmDialog(title: string, content: string, danger = true): Promise<boolean> {
  return new Promise((resolve) => {
    let settled = false
    const done = (v: boolean) => {
      if (settled) return
      settled = true
      resolve(v)
    }
    const dlg = DialogPlugin.confirm({
      header: title,
      body: content,
      confirmBtn: { content: '确定', theme: danger ? 'danger' : 'primary' },
      cancelBtn: '取消',
      onConfirm: () => {
        done(true)
        dlg.destroy()
      },
      onClose: () => done(false),
    })
  })
}
