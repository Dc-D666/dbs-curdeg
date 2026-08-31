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

        <!-- 移动端手势：单指左右滑切图 / 双指捏合缩放 / 放大后单指拖拽平移 -->
        <div
          class="lb-stage"
          :class="{ 'is-interacting': interacting }"
          @wheel.prevent="onWheel"
          @mousedown="onDragStart"
          @touchstart="onTouchStart"
          @touchmove.prevent="onTouchMove"
          @touchend="onTouchEnd"
          @touchcancel="onTouchEnd"
        >
          <img
            :src="current"
            :style="imgStyle"
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
import { computed, onBeforeUnmount, ref, watch } from 'vue'
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
// 放大后的平移偏移（px）
const panX = ref(0)
const panY = ref(0)
// 触摸交互进行中：关闭 transform 过渡，否则捏合/拖拽会有粘滞感
const interacting = ref(false)

const current = computed(() => props.images[props.index] ?? props.images[0] ?? '')

const imgStyle = computed(() => ({
  transform: `translate(${panX.value}px, ${panY.value}px) scale(${scale.value})`,
  cursor: dragging.value ? 'grabbing' : 'grab',
}))

function clampScale(v: number) {
  return Math.min(4, Math.max(0.5, +v.toFixed(2)))
}

/** 复位视图（切图 / 重新打开 / 缩回原始尺寸时调用）。 */
function resetView() {
  scale.value = 1
  panX.value = 0
  panY.value = 0
}

/** 打开灯箱：滚动到 index 对应图片并锁定页面滚动。 */
function open() {
  visible.value = true
  resetView()
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
  resetView()
}

function prev() {
  changeIndex(-1)
}
function next() {
  changeIndex(1)
}

function zoom(delta: number) {
  scale.value = clampScale(scale.value + delta)
  // 缩回原始尺寸后归位，避免图片停在偏移位置
  if (scale.value <= 1) {
    panX.value = 0
    panY.value = 0
  }
}

// ---------- 触摸手势（移动端）----------

const SWIPE_THRESHOLD = 50
let touchStart: { x: number; y: number; time: number } | null = null
let pinchStart: { dist: number; scale: number } | null = null
let panOrigin: { x: number; y: number } | null = null

function touchDistance(t: TouchList) {
  return Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY)
}

function onTouchStart(e: TouchEvent) {
  interacting.value = true
  if (e.touches.length >= 2) {
    // 双指：进入捏合缩放，取消单指判定
    pinchStart = { dist: touchDistance(e.touches), scale: scale.value }
    touchStart = null
    panOrigin = null
    return
  }
  const t = e.touches[0]
  touchStart = { x: t.clientX, y: t.clientY, time: Date.now() }
  panOrigin = { x: t.clientX - panX.value, y: t.clientY - panY.value }
}

function onTouchMove(e: TouchEvent) {
  if (e.touches.length >= 2 && pinchStart) {
    const next = clampScale(pinchStart.scale * (touchDistance(e.touches) / pinchStart.dist))
    // 缩到 1 以下时保持不放大状态并归位
    scale.value = next
    if (next <= 1) {
      panX.value = 0
      panY.value = 0
    }
    return
  }
  // 单指：仅在放大状态拖拽平移；未放大时留给 touchend 判定为切图手势
  if (e.touches.length === 1 && panOrigin && scale.value > 1) {
    panX.value = e.touches[0].clientX - panOrigin.x
    panY.value = e.touches[0].clientY - panOrigin.y
  }
}

function onTouchEnd(e: TouchEvent) {
  if (e.touches.length < 2) pinchStart = null
  if (e.touches.length === 0 && touchStart) {
    const t = e.changedTouches[0]
    const dx = t.clientX - touchStart.x
    const dy = t.clientY - touchStart.y
    const dt = Date.now() - touchStart.time
    // 未放大 + 明显横向滑动 + 够快 → 切换上一张/下一张
    if (
      scale.value <= 1 &&
      Math.abs(dx) >= SWIPE_THRESHOLD &&
      Math.abs(dx) > Math.abs(dy) * 1.5 &&
      dt < 800
    ) {
      changeIndex(dx > 0 ? -1 : 1)
    }
    touchStart = null
    panOrigin = null
  }
  if (e.touches.length === 0) {
    interacting.value = false
    if (scale.value <= 1) {
      panX.value = 0
      panY.value = 0
    }
  }
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

// 仅当灯箱可见时注册全局键盘，避免每个卡片/实例常驻监听（F1）
watch(visible, (v) => {
  if (v) window.addEventListener('keydown', onKey)
  else window.removeEventListener('keydown', onKey)
})
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
    if (visible.value) resetView()
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
  /* 交给自定义手势处理：禁止浏览器的滚动/双击缩放抢走事件 */
  touch-action: none;
}
.lb-img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  user-select: none;
  -webkit-user-drag: none;
  transition: transform 0.18s ease;
}
/* 捏合/拖拽进行中去掉过渡，否则跟手性差 */
.lb-stage.is-interacting .lb-img {
  transition: none;
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
