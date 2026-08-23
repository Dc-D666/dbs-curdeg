<template>
  <div v-for="n in count" :key="n" class="sk-card">
    <div class="sk-head">
      <span class="sk-bar sk-title" />
      <span class="sk-bar sk-tag" />
    </div>
    <div class="sk-media">
      <span class="sk-media-block" />
    </div>
    <div class="sk-lines">
      <span class="sk-bar sk-line" style="width: 96%" />
      <span class="sk-bar sk-line" style="width: 72%" />
    </div>
    <div class="sk-meta">
      <span class="sk-bar sk-avatar" />
      <span class="sk-bar sk-meta-text" />
      <span class="sk-bar sk-meta-text" style="width: 48px" />
      <span class="sk-bar sk-meta-text" style="width: 64px" />
    </div>
    <div class="sk-action">
      <span class="sk-bar sk-pill" />
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ count?: number }>(), { count: 3 })
</script>

<style scoped>
.sk-card {
  background: var(--bg-card);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-container);
  padding: var(--sp-4);
  margin-bottom: var(--sp-3);
}
.sk-bar {
  display: block;
  background: linear-gradient(
    90deg,
    rgba(15, 23, 42, 0.06) 25%,
    rgba(15, 23, 42, 0.12) 37%,
    rgba(15, 23, 42, 0.06) 63%
  );
  background-size: 400% 100%;
  animation: sk-shimmer 1.4s ease infinite;
  border-radius: 4px;
}
.sk-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.sk-title {
  width: 60%;
  height: 18px;
}
.sk-tag {
  width: 36px;
  height: 20px;
  border-radius: var(--radius-pill);
}
.sk-media {
  margin-top: var(--sp-3);
}
.sk-media-block {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: var(--radius-control);
  background: rgba(15, 23, 42, 0.05);
}
.sk-lines {
  margin-top: var(--sp-2);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sk-line {
  height: 12px;
}
.sk-meta {
  margin-top: var(--sp-3);
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}
.sk-avatar {
  width: 20px;
  height: 20px;
  border-radius: 50%;
}
.sk-meta-text {
  height: 10px;
  width: 80px;
}
.sk-action {
  margin-top: var(--sp-2);
  padding-top: var(--sp-2);
  border-top: 1px solid var(--border-soft);
}
.sk-pill {
  width: 72px;
  height: 28px;
  border-radius: var(--radius-control);
}
@keyframes sk-shimmer {
  0% {
    background-position: 100% 0;
  }
  100% {
    background-position: -100% 0;
  }
}
</style>
