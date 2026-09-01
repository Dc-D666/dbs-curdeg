<template>
  <div class="quick-composer" :class="{ open }">
    <!-- 折叠态：常驻轻量入口 -->
    <button v-if="!open" class="qc-button" @click="expand">
      <PenIcon class="qc-icon" />分享你的想法…
    </button>

    <!-- 展开态：标题 + 正文 + 操作 -->
    <div v-else class="qc-panel">
      <t-input v-model.trim="title" class="qc-title" maxlength="128" placeholder="一句话概括你的核心观点/疑问…" clearable />
      <t-textarea
        v-model="content"
        class="qc-body"
        :autosize="{ minRows: 3, maxRows: 8 }"
        maxlength="5000"
        placeholder="补充细节，支持 Markdown（**粗体** `代码`）…"
      />
      <div class="qc-foot">
        <!-- 字数计数（#44）：标题 128 / 正文 5000，实时显示余量 -->
        <span class="qc-hint">标题 {{ title.length }}/128 · 正文 {{ content.length }}/5000</span>
        <div class="qc-actions">
          <t-button variant="outline" size="small" @click="collapse">取消</t-button>
          <t-button theme="primary" size="small" :loading="submitting" @click="submit">
            {{ submitting ? '发布中…' : '发布' }}
          </t-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { PenIcon } from 'tdesign-icons-vue-next'
import { postApi } from '@/api/post'
import { tokenStore } from '@/api/http'
import { toast } from '@/utils/toast'
import { confirmDialog } from '@/utils/confirm'

const props = withDefaults(defineProps<{ cid: number; bid: number }>(), { bid: 0 })
const emit = defineEmits<{ (e: 'posted'): void }>()

const router = useRouter()
const route = useRoute()
const open = ref(false)
const title = ref('')
const content = ref('')
const submitting = ref(false)

function expand() {
  if (!tokenStore.access) {
    router.push(`/login?redirect=${encodeURIComponent(route.fullPath)}`)
    return
  }
  open.value = true
}

/** 无确认地清空（发布成功后调用）。 */
function reset() {
  open.value = false
  title.value = ''
  content.value = ''
}

/** 有内容时先二次确认，避免误点「取消」丢稿。 */
async function collapse() {
  if (title.value.trim() || content.value.trim()) {
    const ok = await confirmDialog('放弃这条内容？', '关闭后已填写的标题和正文将不会保留。', false)
    if (!ok) return
  }
  reset()
}

async function submit() {
  if (submitting.value) return
  if (!tokenStore.access) {
    router.push(`/login?redirect=${encodeURIComponent(route.fullPath)}`)
    return
  }
  const t = title.value.trim()
  const c = content.value.trim()
  if (!t) {
    toast('请先填写标题', 'warning')
    return
  }
  submitting.value = true
  try {
    await postApi.create(props.cid, props.bid, { title: t, content: c || undefined })
    toast('已发布', 'success')
    reset()
    emit('posted')
  } catch (e) {
    toast(e instanceof Error ? e.message : '发布失败', 'error')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.quick-composer {
  margin-bottom: var(--sp-3);
}
.qc-button {
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  height: 44px;
  padding: 0 var(--sp-4);
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-control);
  background: var(--surface);
  color: var(--text-3);
  font-size: var(--fs-body);
  cursor: pointer;
  text-align: left;
  transition: border-color var(--anim-duration) var(--anim-ease),
    box-shadow var(--anim-duration) var(--anim-ease);
}
.qc-button:hover {
  border-color: var(--brand);
  box-shadow: var(--shadow-sm);
}
.qc-icon {
  width: 16px;
  height: 16px;
  color: var(--brand);
}
.qc-panel {
  padding: var(--sp-3);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-container);
  background: var(--surface);
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.qc-title :deep(.t-input__inner) {
  height: 40px;
}
.qc-body :deep(textarea) {
  line-height: 1.7;
}
.qc-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
}
.qc-hint {
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.qc-actions {
  display: flex;
  gap: var(--sp-2);
}
</style>
