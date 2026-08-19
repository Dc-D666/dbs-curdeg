<template>
  <span class="avatar" :style="style">
    <img v-if="src" :src="src" alt="" />
    <span v-else class="avatar-letter">{{ initial }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{ name: string; src?: string; size?: number }>(),
  { src: '', size: 32 },
)

const initial = computed(() => (props.name || 'U').slice(0, 1).toUpperCase())
const style = computed(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
  fontSize: `${Math.round(props.size * 0.42)}px`,
}))
</script>

<style scoped>
.avatar {
  border-radius: 50%;
  background: var(--brand-weak);
  color: var(--brand);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  flex-shrink: 0;
  overflow: hidden;
}
.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.avatar-letter {
  line-height: 1;
}
</style>
