<template>
  <t-empty :description="text" class="empty">
    <template v-if="to || actionText" #footer>
      <t-button theme="primary" variant="outline" size="small" @click="onAction">
        {{ actionText }}
      </t-button>
    </template>
  </t-empty>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const props = withDefaults(
  defineProps<{ text: string; actionText?: string; to?: string }>(),
  { actionText: '', to: '' },
)
const emit = defineEmits<{ action: [] }>()
const router = useRouter()

function onAction() {
  if (props.to) router.push(props.to)
  else emit('action')
}
</script>

<style scoped>
.empty {
  padding: var(--sp-4) 0;
}
</style>
