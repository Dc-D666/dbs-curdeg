<template>
  <main style="font-family: system-ui, sans-serif; max-width: 640px; margin: 0 auto; padding: 2rem">
    <h1>仿腾讯频道 · Web 前端骨架</h1>
    <p>Vite + Vue3 已就绪。替换本页内容开始开发。</p>
    <hr />
    <p>后端连通性测试：<code id="health">检测中…</code></p>
  </main>
</template>

<script setup>
import { onMounted } from 'vue'

onMounted(async () => {
  const el = document.getElementById('health')
  try {
    const res = await fetch('/api/v1/ping')
    el.textContent = JSON.stringify(await res.json())
  } catch (e) {
    el.textContent = '后端未连通：' + e.message
  }
})
</script>
