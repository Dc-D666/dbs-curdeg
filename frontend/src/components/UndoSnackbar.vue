<template>
  <Teleport to="body">
    <Transition name="undo">
      <div v-if="undo.visible" class="undo-snackbar" role="status">
        <span class="undo-msg">{{ undo.message }}</span>
        <button class="undo-action" @click="undo.undo()">撤销</button>
        <!-- 倒计时进度条：条走完即自动生效（如评论真删），让「5 秒后不可挽回」可见 -->
        <span class="undo-timer" aria-hidden="true">
          <i class="undo-timer-bar" :style="{ animationDuration: `${undo.duration}ms` }" />
        </span>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { useUndoStore } from '@/stores/undo'

const undo = useUndoStore()
</script>

<style scoped>
.undo-snackbar {
  position: fixed;
  left: 50%;
  bottom: calc(var(--tabbar-height) + 16px);
  transform: translateX(-50%);
  z-index: 1300;
  display: inline-flex;
  align-items: center;
  gap: 12px;
  max-width: calc(100vw - 32px);
  padding: 10px 14px;
  border-radius: var(--radius-control);
  background: #1f2937;
  color: #f9fafb;
  font-size: var(--fs-body);
  box-shadow: var(--shadow-md);
  overflow: hidden; /* 让倒计时条贴底不溢出圆角 */
}
/* 倒计时条：从满宽线性缩短到 0，时长与自动生效倒计时一致；
   每次notify重新创建元素（v-if），动画自动重新开始 */
.undo-timer {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 3px;
  pointer-events: none;
}
.undo-timer-bar {
  display: block;
  height: 100%;
  background: var(--brand);
  animation: undo-countdown linear forwards;
}
@keyframes undo-countdown {
  from {
    width: 100%;
  }
  to {
    width: 0;
  }
}
.undo-msg {
  min-width: 0;
}
.undo-action {
  border: none;
  background: transparent;
  color: var(--brand-hover);
  font-weight: 600;
  font-size: var(--fs-body);
  cursor: pointer;
  padding: 2px 4px;
}
.undo-action:hover {
  color: var(--brand);
}
.undo-enter-active,
.undo-leave-active {
  transition: opacity 0.2s ease, transform 0.2s var(--anim-ease);
}
.undo-enter-from,
.undo-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}
</style>
