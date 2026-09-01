<template>
  <t-avatar :image="image || undefined" :size="`${size}px`" class="avatar">
    <template #icon>
      <span class="avatar-letter">{{ initial }}</span>
    </template>
  </t-avatar>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { proxifyImage } from '@/utils/image'

const props = withDefaults(
  defineProps<{ name: string; src?: string; size?: number }>(),
  { src: '', size: 32 },
)

const initial = computed(() => (props.name || 'U').slice(0, 1).toUpperCase())
// QQ CDN 等防盗链外链头像 → 走后端代理
const image = computed(() => proxifyImage(props.src))
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
