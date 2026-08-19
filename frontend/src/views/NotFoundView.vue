<template>
  <main class="nf">
    <p class="nf-code">404</p>
    <p class="nf-text">页面不存在或已删除</p>
    <router-link to="/" class="nf-link">回到首页 →</router-link>
  </main>
</template>

<style scoped>
.nf {
  min-height: 70vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--sp-2);
}
.nf-code {
  margin: 0;
  font-size: 56px;
  font-weight: 700;
  color: var(--text-3);
}
.nf-text {
  margin: 0;
  color: var(--text-2);
}
.nf-link {
  margin-top: var(--sp-3);
  color: var(--brand);
  text-decoration: none;
}
</style>
