<template>
  <Transition name="pill">
    <button v-if="show" class="new-pill" @click="view">
      <span class="pill-dot" />有 {{ live.count }} 条新讨论，点击查看
    </button>
  </Transition>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useLiveStore } from '@/stores/live'

const route = useRoute()
const live = useLiveStore()

// 仅在信息流页顶部显示（首页/发现/频道/关注），避免设置页也弹
const FEED_ROUTES = new Set(['home', 'discover', 'community', 'my-feed'])
const isFeedRoute = computed(() => FEED_ROUTES.has(route.name as string))
const show = computed(() => isFeedRoute.value && live.count > 0)

// 自动消失：出现后 8s 若无点击则清零（F2）
const autoDismiss = ref<ReturnType<typeof setTimeout> | null>(null)
watch(
  () => live.count,
  (v) => {
    if (autoDismiss.value) clearTimeout(autoDismiss.value)
    if (v > 0) {
      autoDismiss.value = setTimeout(() => {
        live.reset()
      }, 8000)
    }
  },
)
onBeforeUnmount(() => {
  if (autoDismiss.value) clearTimeout(autoDismiss.value)
})

function view() {
  live.reset()
  // 通知当前信息流重新拉取首页（FeedStreamList / CommunityDetailView 监听）
  window.dispatchEvent(new CustomEvent('live:refresh'))
}
</script>

<style scoped>
.new-pill {
  position: fixed;
  top: 64px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 900;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: calc(100vw - 32px);
  padding: 10px 18px;
  border: none;
  border-radius: 999px;
  background: var(--brand);
  color: #fff;
  font-size: var(--fs-body);
  cursor: pointer;
  box-shadow: var(--shadow-overlay);
  transition: background var(--anim-duration) var(--anim-ease),
    transform var(--anim-duration) var(--anim-ease);
}
.new-pill:hover {
  background: var(--brand-hover);
}
.pill-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.7);
  animation: dot-pulse 1.6s infinite;
}
@keyframes dot-pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.7);
  }
  70% {
    box-shadow: 0 0 0 8px rgba(255, 255, 255, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(255, 255, 255, 0);
  }
}
.pill-enter-active,
.pill-leave-active {
  transition: opacity 0.25s ease, transform 0.25s var(--anim-ease);
}
.pill-enter-from,
.pill-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-12px);
}
</style>
