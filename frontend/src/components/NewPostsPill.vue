<template>
  <Transition name="pill">
    <button v-if="live.count > 0" class="new-pill" @click="view">
      <span class="pill-dot" />有 {{ live.count }} 条新讨论，点击查看
    </button>
  </Transition>
</template>

<script setup lang="ts">
import { useLiveStore } from '@/stores/live'

const live = useLiveStore()

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
