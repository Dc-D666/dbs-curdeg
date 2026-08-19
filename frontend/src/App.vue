<template>
  <div class="app-shell">
    <router-view />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { request } from '@/api/http'

onMounted(async () => {
  // 骨架阶段：探测后端连通性（后续由真实页面取代）
  try {
    const data = await request<{ message: string }>({ url: '/ping' })
    console.log('[SDUdiscord] 后端连通:', data.message)
  } catch (e) {
    console.warn('[SDUdiscord] 后端未连通:', e)
  }
})
</script>

<style>
:root {
  --brand: #1a73e8;
  color-scheme: light;
}
* {
  box-sizing: border-box;
}
body {
  margin: 0;
  font-family: system-ui, -apple-system, 'Segoe UI', Roboto, 'PingFang SC',
    'Microsoft YaHei', sans-serif;
  -webkit-font-smoothing: antialiased;
}
#app {
  min-height: 100vh;
}
</style>
