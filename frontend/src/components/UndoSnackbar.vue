<template>
  <Teleport to="body">
    <Transition name="undo">
      <div v-if="undo.visible" class="undo-snackbar" role="status">
        <span class="undo-msg">{{ undo.message }}</span>
        <button class="undo-action" @click="undo.undo()">撤销</button>
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
