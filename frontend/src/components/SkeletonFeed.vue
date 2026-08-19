<template>
  <div class="sk-card" v-for="n in count" :key="n">
    <div class="sk-line sk-title"></div>
    <div class="sk-line sk-text"></div>
    <div class="sk-line sk-text short"></div>
    <div class="sk-meta">
      <div class="sk-line sk-chip"></div>
      <div class="sk-line sk-chip"></div>
      <div class="sk-line sk-chip"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ count?: number }>(), { count: 3 })
</script>

<style scoped>
.sk-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: var(--sp-4);
  margin-bottom: var(--sp-3);
}
.sk-line {
  border-radius: 4px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e6e6e6 37%, #f0f0f0 63%);
  background-size: 400% 100%;
  animation: sk-shimmer 1.4s ease infinite;
}
.sk-title {
  width: 55%;
  height: 18px;
}
.sk-text {
  width: 100%;
  height: 13px;
  margin-top: 10px;
}
.sk-text.short {
  width: 70%;
}
.sk-meta {
  margin-top: 14px;
  display: flex;
  gap: 8px;
}
.sk-chip {
  width: 52px;
  height: 12px;
}
@keyframes sk-shimmer {
  0% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0 50%;
  }
}
</style>
