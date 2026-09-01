/** 全局单例灯箱（#59）。
 *
 * 原实现：每张 FeedCard / 每个帖子详情页各自挂载一个 Teleport Lightbox 实例，
 * 一页 20+ 张卡片就是 20+ 个灯箱组件（各自带键盘监听注册逻辑），纯性能浪费、弱机卡顿。
 * 现改为全局唯一实例（App.vue 挂载一次），任何组件通过 store.open(images, index) 唤起。
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useLightboxStore = defineStore('lightbox', () => {
  const images = ref<string[]>([])
  const index = ref(0)
  const visible = ref(false)

  /** 打开灯箱：urls 为图库，startIndex 为初始图。重复调用即切换图库。 */
  function open(urls: string[], startIndex = 0) {
    images.value = urls
    index.value = startIndex
    visible.value = true
  }

  function close() {
    visible.value = false
  }

  function setIndex(i: number) {
    index.value = i
  }

  return { images, index, visible, open, close, setIndex }
})
