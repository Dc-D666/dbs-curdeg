<template>
  <div class="err-state">
    <p class="err-text">{{ text }}</p>
    <div class="err-ops">
      <t-button v-if="retryable" variant="outline" size="small" @click="emit('retry')">重试</t-button>
      <!-- 附加出口：如「去发现频道」链接，给 404/无权限等死胡同一条退路 -->
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
/** 统一的加载失败态：文案 + 重试按钮 + 可选兜底出口。
 *
 * retryable=false 用于「确实不存在 / 无权限」这类重试无意义的场景，
 * 此时应通过默认插槽给出一个离开当前页的链接。
 */
withDefaults(defineProps<{ text: string; retryable?: boolean }>(), { retryable: true })
const emit = defineEmits<{ retry: [] }>()
</script>

<style scoped>
.err-state {
  padding: var(--sp-6) 0;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-3);
}
.err-text {
  margin: 0;
  color: var(--text-3);
  font-size: var(--fs-body);
  max-width: 32em;
}
.err-ops {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
</style>
