/** 实时新内容计数（P1 ③）：后端 WS 广播 feed_new 后递增，前端浮动药丸展示。 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useLiveStore = defineStore('live', () => {
  const count = ref(0)

  function increment(n = 1) {
    count.value += n
  }

  function reset() {
    count.value = 0
  }

  return { count, increment, reset }
})
