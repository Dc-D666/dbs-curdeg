<template>
  <div class="sk-card" v-for="n in count" :key="n">
    <t-skeleton :row="4" :loading="true" animation="gradient" />
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
</style>
