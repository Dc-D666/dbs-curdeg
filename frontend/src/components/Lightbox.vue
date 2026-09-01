<template>
  <!-- 图片查看器：基于 tdesign ImageViewer（自带缩放/旋转/切换/下载），
       替代早期手写灯箱，统一视觉并减少维护成本 -->
  <t-image-viewer
    v-model:visible="visible"
    :images="imageUrls"
    :default-index="props.index"
    :z-index="1000"
    @close="onClose"
    @change="onChange"
  />
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { proxifyImage } from '@/utils/image'

const props = withDefaults(
  defineProps<{ images: string[]; index?: number }>(),
  { index: 0 },
)

const emit = defineEmits<{ (e: 'update:index', i: number): void; (e: 'close'): void }>()

const visible = ref(false)
const curIndex = ref(props.index)

// 图片统一走代理（外链/防盗链图床），保证 ImageViewer 能正常加载
const imageUrls = computed(() => props.images.map((u) => proxifyImage(u)))

function open() {
  curIndex.value = props.index
  visible.value = true
}

function close() {
  visible.value = false
  emit('close')
}

function onClose() {
  emit('close')
}

function onChange(i: number) {
  curIndex.value = i
  emit('update:index', i)
}

// 父组件 v-if 挂载时也受 props.images 驱动；保留 open() 供 ref 调用
watch(
  () => props.index,
  (i) => {
    if (visible.value) curIndex.value = i
  },
)

defineExpose({ open, close })
</script>
