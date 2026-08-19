<template>
  <t-avatar :image="src || undefined" :size="`${size}px`" class="avatar">
    <template #icon>
      <span class="avatar-letter">{{ initial }}</span>
    </template>
  </t-avatar>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{ name: string; src?: string; size?: number }>(),
  { src: '', size: 32 },
)

const initial = computed(() => (props.name || 'U').slice(0, 1).toUpperCase())
</script>

<style scoped>
.avatar {
  flex-shrink: 0;
}
.avatar-letter {
  font-weight: 600;
  color: var(--td-brand-color);
}
</style>
