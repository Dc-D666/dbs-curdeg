<template>
  <main class="create-page">
    <header class="page-header">
      <router-link :to="`/c/${cid}`" class="back">
        <ArrowLeftIcon class="back-icon" /> 返回
      </router-link>
      <h1 class="page-title">{{ editing ? '编辑帖子' : '发帖' }}</h1>
    </header>

    <section class="panel">
      <div class="field">
        <label class="field-label">标题</label>
        <t-input v-model.trim="form.title" size="large" maxlength="128" placeholder="一句话说清楚" clearable />
        <div class="ai-bar">
          <span class="ai-bar-label">🤖 AI 帮写</span>
          <t-button size="small" variant="outline" :loading="aiBusy === 'title'" :disabled="!!aiBusy" @click="aiRun('title')">
            📝 起标题
          </t-button>
          <t-button size="small" variant="outline" :loading="aiBusy === 'write'" :disabled="!!aiBusy" @click="aiRun('write')">
            ✍️ 写正文
          </t-button>
          <t-button size="small" variant="outline" :loading="aiBusy === 'polish'" :disabled="!!aiBusy" @click="aiRun('polish')">
            🪄 润色
          </t-button>
        </div>
      </div>

      <div class="field">
        <span class="field-label">内容</span>
        <RichEditor ref="editorRef" v-model="form.rich" :cid="cid" :initial-images="initialImages" @update:images="onImages" />
        <p class="field-hint">支持插入链接与图片（最多 9 张图片）</p>
      </div>

      <!-- AI 生成预览（打字机效果） -->
      <section v-if="aiText" class="ai-preview">
        <div class="ai-preview-head">
          <span>✨ AI 生成{{ aiBusy ? '中…' : '' }}</span>
          <div v-if="!aiBusy">
            <t-button size="small" theme="primary" variant="text" @click="aiApply">插入内容</t-button>
            <t-button size="small" variant="text" @click="aiText = ''">丢弃</t-button>
          </div>
        </div>
        <p class="ai-preview-body">{{ aiText }}<span v-if="aiBusy" class="ai-cursor">▍</span></p>
      </section>

      <p v-if="error" class="error">{{ error }}</p>

      <t-button theme="primary" size="large" class="submit" :loading="submitting || loading" @click="onSubmit">
        {{ submitting ? '保存中…' : editing ? '保存' : '发布' }}
      </t-button>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeftIcon } from 'tdesign-icons-vue-next'
import RichEditor from '@/components/RichEditor.vue'
import { postApi, type RichSegment } from '@/api/post'
import { tokenStore } from '@/api/http'
import { toast } from '@/utils/toast'
import { streamPost } from '@/utils/sse'

const route = useRoute()
const router = useRouter()
const cid = Number(route.params.id)
const bid = Number(route.params.bid)
const editId = Number(route.query.edit) || 0

const form = reactive({ title: '', rich: [] as RichSegment[], images: [] as string[] })
const initialImages = ref<string[]>([])
const error = ref('')
const submitting = ref(false)
const editing = ref(editId > 0)
const loading = ref(false)
const editorRef = ref<InstanceType<typeof RichEditor> | null>(null)

// AI 帮写（阶段 6）
const aiBusy = ref<'write' | 'polish' | 'title' | ''>('')
const aiText = ref('')
let aiMode: 'append' | 'replace' = 'append'

function aiPlainContent(): string {
  return form.rich
    .map((s) => (s.type === 1 ? (s as { text?: string }).text || '' : (s as { display_text?: string }).display_text || ''))
    .join('')
}

async function aiRun(action: 'write' | 'polish' | 'title') {
  if (aiBusy.value) return
  if (!tokenStore.access) {
    window.location.href = `/login?redirect=${encodeURIComponent(route.fullPath)}`
    return
  }
  aiBusy.value = action
  aiText.value = ''
  try {
    if (action === 'title') {
      // 直接打字机写入标题输入框
      const before = form.title
      form.title = ''
      await streamPost('/api/v1/ai/assist', { action, title: before, content: aiPlainContent() }, (d) => {
        form.title += d
      })
    } else {
      aiMode = action === 'polish' ? 'replace' : 'append'
      await streamPost('/api/v1/ai/assist', { action, title: form.title, content: aiPlainContent() }, (d) => {
        aiText.value += d
      })
      if (!aiText.value) aiText.value = '（AI 未返回内容）'
    }
    toast('AI 生成完成，可继续编辑', 'success')
  } catch (e) {
    toast(e instanceof Error ? e.message : 'AI 生成失败', 'error')
    aiText.value = ''
  } finally {
    aiBusy.value = ''
  }
}

function aiApply() {
  if (!aiText.value) return
  editorRef.value?.insertText(aiText.value, aiMode)
  aiText.value = ''
  toast('已插入编辑器', 'success')
}

onMounted(async () => {
  if (!editing.value) return
  loading.value = true
  try {
    const post = await postApi.get(editId)
    form.title = post.title
    form.rich = post.rich_content
    form.images = [...post.images]
    initialImages.value = [...post.images] // 旧帖图片渲染进编辑器
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载帖子失败'
  } finally {
    loading.value = false
  }
})

function onImages(urls: string[]) {
  form.images = urls
}

async function onSubmit() {
  if (submitting.value) return
  if (!tokenStore.access) {
    window.location.href = `/login?redirect=${encodeURIComponent(route.fullPath)}`
    return
  }
  if (!form.title) {
    error.value = '请填写标题'
    return
  }
  if (form.rich.length === 0 && form.images.length === 0) {
    error.value = '请填写内容'
    return
  }
  if (form.images.length > 9) {
    error.value = '图片最多 9 张'
    return
  }
  submitting.value = true
  error.value = ''
  try {
    if (editing.value) {
      const post = await postApi.update(editId, {
        title: form.title,
        rich_content: form.rich,
        images: form.images,
      })
      toast('已保存', 'success')
      router.push(`/p/${post.id}`)
    } else {
      const post = await postApi.create(cid, bid, {
        title: form.title,
        rich_content: form.rich,
        images: form.images,
      })
      router.push(`/p/${post.id}`)
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '发布失败'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.create-page {
  max-width: var(--page-max);
  margin: 0 auto;
  padding: 0 var(--sp-4) var(--sp-6);
}
.page-header {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  height: var(--nav-height);
  border-bottom: 1px solid var(--border);
}
.back {
  color: var(--text-3);
  font-size: var(--fs-body);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.back-icon {
  width: 16px;
  height: 16px;
}
.page-title {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
  flex: 1;
}
.panel {
  margin-top: var(--sp-4);
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-component-border);
  border-radius: var(--td-radius-large);
  padding: var(--sp-4);
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.field {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}
.field-label {
  font-size: var(--fs-caption);
  color: var(--td-text-color-secondary);
}
.field-hint {
  margin: 0;
  font-size: var(--fs-caption);
  color: var(--td-text-color-placeholder);
}
.ai-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  flex-wrap: wrap;
}
.ai-bar-label {
  font-size: var(--fs-caption);
  color: var(--td-text-color-placeholder);
}
.ai-preview {
  margin-top: 4px;
  padding: 12px 14px;
  background: var(--brand-weak);
  border-radius: var(--radius-card);
}
.ai-preview-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: var(--fs-caption);
  color: var(--brand);
  font-weight: 600;
}
.ai-preview-body {
  margin: 8px 0 0;
  font-size: var(--fs-body);
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-1);
}
.ai-cursor {
  display: inline-block;
  width: 2px;
  height: 14px;
  background: var(--brand);
  vertical-align: -2px;
  animation: blink 0.8s steps(1) infinite;
}
@keyframes blink {
  50% {
    opacity: 0;
  }
}
.error {
  margin: 0;
  font-size: var(--fs-caption);
  color: var(--td-error-color);
}
.submit {
  align-self: stretch;
}
</style>
