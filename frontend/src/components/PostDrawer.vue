<template>
  <Teleport to="body">
    <Transition name="pd-fade">
      <div v-if="postId" class="pd-mask" @click.self="close">
        <Transition name="pd-slide" appear>
          <aside class="pd-drawer" role="dialog" :aria-label="`帖子 ${postId}`">
            <header class="pd-head">
              <span class="pd-title">帖子</span>
              <button class="pd-close" title="关闭 (Esc)" @click="close"><CloseIcon /></button>
            </header>
            <div class="pd-body">
              <PostDetailView :key="postId" :post-id="postId" embedded />
            </div>
          </aside>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, watch } from 'vue'
import { CloseIcon } from 'tdesign-icons-vue-next'
import PostDetailView from '@/views/PostDetailView.vue'
import { usePostDrawer } from '@/stores/postDrawer'

const drawer = usePostDrawer()
const postId = computed(() => drawer.postId)

function close() {
  drawer.close()
}

// 打开抽屉时锁定页面滚动（避免背景信息流滚动），关闭时恢复
watch(postId, (v) => {
  document.body.style.overflow = v ? 'hidden' : ''
})

// Esc 关闭抽屉（若灯箱开着则交给灯箱，避免误关）
function onKey(e: KeyboardEvent) {
  if (e.key !== 'Escape') return
  if (document.querySelector('.lightbox')) return
  if (postId.value) close()
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<style scoped>
.pd-mask {
  position: fixed;
  inset: 0;
  z-index: 950;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  justify-content: flex-end;
}
.pd-drawer {
  width: min(560px, 100%);
  height: 100%;
  background: var(--bg-page);
  box-shadow: var(--shadow-overlay);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.pd-head {
  height: 52px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--sp-4);
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
}
.pd-title {
  font-size: var(--fs-title);
  font-weight: 600;
  color: var(--text-1);
}
.pd-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--text-2);
  cursor: pointer;
  transition: background var(--anim-duration) var(--anim-ease);
}
.pd-close:hover {
  background: var(--bg-secondary);
}
.pd-close :deep(svg) {
  width: 18px;
  height: 18px;
}
.pd-body {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}
/* 路由切换动画 */
.pd-fade-enter-active,
.pd-fade-leave-active {
  transition: opacity 0.2s ease;
}
.pd-fade-enter-from,
.pd-fade-leave-to {
  opacity: 0;
}
.pd-slide-enter-active,
.pd-slide-leave-active {
  transition: transform 0.22s var(--anim-ease);
}
.pd-slide-enter-from,
.pd-slide-leave-to {
  transform: translateX(100%);
}
</style>
