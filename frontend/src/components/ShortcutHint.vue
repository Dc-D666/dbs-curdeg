<template>
  <!-- 桌面端快捷键帮助入口（#60）：J/K// 等快捷键无任何发现性，用户根本不知道存在 -->
  <div v-if="isDesktop" class="kbd-help">
    <Transition name="kbd-pop">
      <div v-if="open" class="kbd-help-panel" role="dialog" aria-label="键盘快捷键说明">
        <p class="kbd-help-title">键盘快捷键</p>
        <ul class="kbd-help-list">
          <li><span class="kbd-key">J</span>下一帖</li>
          <li><span class="kbd-key">K</span>上一帖</li>
          <li><span class="kbd-key">/</span>聚焦搜索</li>
          <li><span class="kbd-key">←</span><span class="kbd-key">→</span>灯箱内切换图片</li>
          <li><span class="kbd-key">Esc</span>关闭灯箱 / 弹层</li>
          <li><span class="kbd-key">+</span><span class="kbd-key">−</span>灯箱放大 / 缩小</li>
        </ul>
      </div>
    </Transition>
    <button
      type="button"
      class="kbd-help-btn"
      :class="{ active: open }"
      :aria-expanded="open"
      aria-label="键盘快捷键说明"
      title="键盘快捷键"
      @click="open = !open"
    >
      <HelpCircleIcon class="kbd-help-icon" />
    </button>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { HelpCircleIcon } from 'tdesign-icons-vue-next'

// 快捷键是键盘交互，仅桌面端展示入口
const isDesktop = ref(window.innerWidth >= 1024)
const open = ref(false)

function onResize() {
  isDesktop.value = window.innerWidth >= 1024
}

/** 点击面板外 / Esc 关闭。 */
function onDocClick(e: MouseEvent) {
  if (!open.value) return
  if (!(e.target as HTMLElement).closest('.kbd-help')) open.value = false
}
function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') open.value = false
}

onMounted(() => {
  window.addEventListener('resize', onResize)
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onKey)
})
</script>

<style scoped>
.kbd-help {
  position: fixed;
  /* 叠在 AI 助手悬浮球正上方（48px 球 + 10px 间距） */
  right: 16px;
  bottom: calc(var(--tabbar-height) + 74px);
  z-index: 90;
}
.kbd-help-btn {
  width: 36px;
  height: 36px;
  border: 1px solid var(--border);
  border-radius: 50%;
  background: var(--surface);
  color: var(--text-3);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-md);
  transition: color 0.15s, border-color 0.15s;
}
.kbd-help-btn:hover,
.kbd-help-btn.active {
  color: var(--brand);
  border-color: var(--brand);
}
.kbd-help-icon {
  width: 18px;
  height: 18px;
}
.kbd-help-panel {
  position: absolute;
  right: 0;
  bottom: calc(100% + 10px);
  width: 220px;
  padding: var(--sp-3) var(--sp-4);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-overlay);
}
.kbd-help-title {
  margin: 0 0 var(--sp-2);
  font-size: var(--fs-caption);
  font-weight: 600;
  color: var(--text-3);
}
.kbd-help-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.kbd-help-list li {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-caption);
  color: var(--text-2);
}
.kbd-key {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 5px;
  border: 1px solid var(--border);
  border-bottom-width: 2px;
  border-radius: 4px;
  background: var(--bg-secondary);
  color: var(--text-1);
  font-family: Consolas, Monaco, monospace;
  font-size: 11px;
}
.kbd-pop-enter-active,
.kbd-pop-leave-active {
  transition: opacity 0.15s ease, transform 0.15s var(--anim-ease);
}
.kbd-pop-enter-from,
.kbd-pop-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
</style>
