<template>
  <!-- 全局唯一灯箱实例（#59）：所有卡片/详情页共用，通过 lightbox store 控制 -->
  <Lightbox
    ref="lbRef"
    :images="store.images"
    :index="store.index"
    @update:index="store.setIndex"
    @close="store.close"
  />
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import Lightbox from '@/components/Lightbox.vue'
import { useLightboxStore } from '@/stores/lightbox'

const store = useLightboxStore()
const lbRef = ref<InstanceType<typeof Lightbox> | null>(null)

// store.visible 置真 → 调 Lightbox 实例的 open()（其内部管理可见态/滚动锁/键盘监听）。
// 关闭方向由 Lightbox 发出 close 事件 → store.close() 同步，双向不会脱节。
watch(
  () => store.visible,
  async (v) => {
    if (v) {
      // 先等 props（images/index）传递到 Lightbox，再触发打开
      await nextTick()
      lbRef.value?.open()
    }
  },
  { immediate: true },
)
</script>
