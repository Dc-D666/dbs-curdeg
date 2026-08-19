<template>
  <main class="nf">
    <t-result title="404" description="页面不存在或已删除" status="404">
      <template #footer>
        <t-button theme="primary" @click="$router.push('/')">回到首页</t-button>
      </template>
    </t-result>
  </main>
</template>

<style scoped>
.nf {
  min-height: 70vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--sp-4);
}
</style>
