/**
 * 轻提示 —— 基于 TDesign MessagePlugin（tdesign.tencent.com/vue-next/components/message）。
 * 用法：toast('保存成功', 'success') / toast('网络错误', 'error')
 */
import { MessagePlugin } from 'tdesign-vue-next'

export type ToastType = 'success' | 'error' | 'info' | 'warning'

export function toast(message: string, type: ToastType = 'info', duration = 2500): void {
  MessagePlugin[type](message, duration)
}
