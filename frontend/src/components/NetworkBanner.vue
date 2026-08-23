<template>
  <Transition name="nb-slide">
    <div v-if="offline" class="net-banner" role="status">
      <span class="nb-dot" />网络已断开，正在尝试重连…
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

const offline = ref(false)

function update() {
  offline.value = !navigator.onLine
}

onMounted(() => {
  update()
  window.addEventListener('offline', update)
  window.addEventListener('online', update)
})
onBeforeUnmount(() => {
  window.removeEventListener('offline', update)
  window.removeEventListener('online', update)
})
</script>

<style scoped>
.net-banner {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 1200;
  padding: 8px var(--sp-4);
  background: #fef3c7;
  color: #92400e;
  font-size: var(--fs-body);
  text-align: center;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  box-shadow: var(--shadow-sm);
}
.nb-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
  animation: nb-blink 1s steps(2) infinite;
}
@keyframes nb-blink {
  50% {
    opacity: 0.35;
  }
}
.nb-slide-enter-active,
.nb-slide-leave-active {
  transition: transform 0.25s ease, opacity 0.25s ease;
}
.nb-slide-enter-from,
.nb-slide-leave-to {
  transform: translateY(-100%);
  opacity: 0;
}
</style>
