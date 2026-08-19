<template>
  <div class="empty">
    <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
      <path d="M4 13h4l2 3h4l2-3h4" stroke-linecap="round" stroke-linejoin="round" />
      <path d="M5 13V5h14v8" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
    <p class="empty-text">{{ text }}</p>
    <router-link v-if="to" :to="to" class="empty-action">{{ actionText }}</router-link>
    <button v-else-if="actionText" class="empty-action" @click="$emit('action')">{{ actionText }}</button>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{ text: string; actionText?: string; to?: string }>(),
  { actionText: '', to: '' },
)
defineEmits<{ action: [] }>()
</script>

<style scoped>
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-6) 0;
}
.empty-icon {
  width: 48px;
  height: 48px;
  color: var(--text-3);
}
.empty-text {
  margin: 0;
  font-size: var(--fs-body);
  color: var(--text-3);
}
.empty-action {
  margin-top: var(--sp-2);
  height: 32px;
  padding: 0 var(--sp-4);
  border: 1px solid var(--brand);
  border-radius: var(--radius-btn);
  background: var(--bg-card);
  color: var(--brand);
  font-size: var(--fs-caption);
  cursor: pointer;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  transition: background var(--anim-duration) var(--anim-ease);
}
.empty-action:hover {
  background: var(--brand-weak);
}
</style>
