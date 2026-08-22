<template>
  <Teleport to="body">
    <Transition name="lb-fade">
      <div v-if="visible" class="lightbox" @click.self="close">
        <div class="lb-toolbar">
          <span class="lb-counter">{{ index + 1 }} / {{ images.length }}</span>
          <div class="lb-toolbar-actions">
            <button class="lb-btn" title="缩小" @click="zoom(-0.2)"><MinusIcon /></button>
            <button class="lb-btn" title="放大" @click="zoom(0.2)"><PlusIcon /></button>
            <a :href="current" target="_blank" rel="noopener" class="lb-btn" title="下载原图" @click.stop><DownloadIcon /></a>
            <button class="lb-btn lb-close" title="关闭 (Esc)" @click="close"><CloseIcon /></button>
          </div>
        </div>

        <button v-if="images.length > 1" class="lb-nav lb-prev" title="上一张 (←)" @click.stop="prev">
          <ChevronLeftIcon />
        </button>
        <button v-if="images.length > 1" class="lb-nav lb-next" title="下一张 (→)" @click.stop="next">
          <ChevronRightIcon />
        </button>

        <div class="lb-stage" @wheel.prevent="onWheel" @mousedown="onDragStart">
          <img
            :src="current"
            :style="{ transform: `scale(${scale})`, cursor: dragging ? 'grabbing' : 'grab' }"
            class="lb-img"
            alt=""
            draggable="false"
          />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  CloseIcon,
  DownloadIcon,
  MinusIcon,
  PlusIcon,
} from 'tdesign-icons-vue-next'

const props = withDefaults(
  defineProps<{ images: string[]; index?: number }>(),
  { index: 0 },
)

const emit = defineEmits<{ (e: 'update:index', i: number): void; (e: 'close'): void }>()

const visible = ref(false)
const scale = ref(1)
const dragging = ref(false)
const dragX = ref(0)

const current = computed(() => props.images[props.index] ?? props.images[0] ?? '')

/** 打开灯箱：滚动到 index 对应图片并锁定页面滚动。 */
function open() {
  visible.value = true
  scale.value = 1
  document.body.style.overflow = 'hidden'
}

function close() {
  visible.value = false
  document.body.style.overflow = ''
  emit('close')
}

function changeIndex(delta: number) {
  const n = props.images.length
  if (n < 2) return
  const next = (props.index + delta + n) % n
  emit('update:index', next)
  scale.value = 1
}

function prev() {
  changeIndex(-1)
}
function next() {
  changeIndex(1)
}

function zoom(delta: number) {
  scale.value = Math.min(4, Math.max(0.5, +(scale.value + delta).toFixed(2)))
}

function onWheel(e: WheelEvent) {
  zoom(e.deltaY < 0 ? 0.2 : -0.2)
}

const THRESHOLD = 60
function onDragStart(e: MouseEvent) {
  dragging.value = true
  dragX.value = e.clientX
  const move = (ev: MouseEvent) => {
    const dx = ev.clientX - dragX.value
    if (Math.abs(dx) > THRESHOLD) {
      changeIndex(dx > 0 ? -1 : 1)
      dragging.value = false
      window.removeEventListener('mousemove', move)
    }
  }
  const up = () => {
    dragging.value = false
    window.removeEventListener('mousemove', move)
  }
  window.addEventListener('mousemove', move)
  window.addEventListener('mouseup', up, { once: true })
}

function onKey(e: KeyboardEvent) {
  if (!visible.value) return
  if (e.key === 'Escape') close()
  else if (e.key === 'ArrowLeft') prev()
  else if (e.key === 'ArrowRight') next()
  else if (e.key === '+' || e.key === '=') zoom(0.2)
  else if (e.key === '-') zoom(-0.2)
}

onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  document.body.style.overflow = ''
})

// 暴露 open 供父组件调用（通过 template ref）
defineExpose({ open, close })

// 父组件通过 v-if 挂载时也可直接控制；这里保留 open() 以支持 ref 调用
watch(
  () => props.images,
  () => {
    if (visible.value) scale.value = 1
  },
)
</script>

<style scoped>
.lightbox {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
}
.lb-toolbar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--sp-4);
  color: #fff;
  z-index: 10;
}
.lb-counter {
  font-size: var(--fs-body);
  opacity: 0.9;
  font-variant-numeric: tabular-nums;
}
.lb-toolbar-actions {
  display: flex;
  gap: var(--sp-2);
}
.lb-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  cursor: pointer;
  text-decoration: none;
  transition: background var(--anim-duration) var(--anim-ease);
}
.lb-btn:hover {
  background: rgba(255, 255, 255, 0.24);
}
.lb-btn :deep(svg) {
  width: 18px;
  height: 18px;
}
.lb-close {
  background: rgba(213, 73, 65, 0.9);
}
.lb-nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 44px;
  height: 44px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  cursor: pointer;
  z-index: 10;
}
.lb-nav:hover {
  background: rgba(255, 255, 255, 0.24);
}
.lb-nav :deep(svg) {
  width: 24px;
  height: 24px;
}
.lb-prev {
  left: var(--sp-4);
}
.lb-next {
  right: var(--sp-4);
}
.lb-stage {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 60px var(--sp-5) var(--sp-5);
  box-sizing: border-box;
}
.lb-img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  user-select: none;
  transition: transform 0.18s ease;
}
.lb-fade-enter-active,
.lb-fade-leave-active {
  transition: opacity 0.2s ease;
}
.lb-fade-enter-from,
.lb-fade-leave-to {
  opacity: 0;
}
</style>
