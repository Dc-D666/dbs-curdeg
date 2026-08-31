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
        <t-input v-model.trim="form.title" size="large" maxlength="128" placeholder="用一句话概括你的核心观点/疑问（如：如何在 Vue 3 中做性能调优？）" clearable />
        <div class="ai-bar">
          <span class="ai-bar-label"><AiIcon class="ai-bar-cal-icon" /> AI 帮写</span>
          <t-button size="small" variant="outline" :loading="aiBusy === 'title'" :disabled="!!aiBusy" @click="aiRun('title')">
            <template #icon><EditIcon /></template> 起标题
          </t-button>
          <t-button size="small" variant="outline" :loading="aiBusy === 'write'" :disabled="!!aiBusy" @click="aiRun('write')">
            <template #icon><PenIcon /></template> 写正文
          </t-button>
          <t-button size="small" variant="outline" :loading="aiBusy === 'polish'" :disabled="!!aiBusy" @click="aiRun('polish')">
            <template #icon><BrushIcon /></template> 润色
          </t-button>
          <t-button size="small" variant="outline" :loading="drawBusy" :disabled="!!aiBusy" @click="aiDraw">
            <template #icon><ImageIcon /></template> 文生图
          </t-button>
        </div>
      </div>

      <div class="field">
        <label class="field-label">关联话题</label>
        <t-select v-model="form.topic_id" size="large" clearable placeholder="选择一个话题（选填）">
          <t-option v-for="t in topics" :key="t.id" :value="t.id" :label="`#${t.name}（${t.post_count} 帖）`" />
        </t-select>
      </div>

      <!-- AI 文生图描述输入（原 window.prompt） -->
      <t-dialog
        v-model:visible="drawDialog"
        header="AI 文生图"
        :confirm-btn="{ content: '生成', theme: 'primary', loading: drawBusy }"
        cancel-btn="取消"
        @confirm="submitDraw"
      >
        <t-input
          v-model="drawPrompt"
          maxlength="200"
          placeholder="输入画面描述（用于文生图）"
          :disabled="drawBusy"
          @enter="submitDraw"
        />
      </t-dialog>

      <div v-if="drawImage" class="field">
        <span class="field-label">AI 生成图片</span>
        <img :src="drawImage" class="draw-img" alt="" />
        <div class="draw-ops">
          <t-button size="small" variant="outline" @click="useDrawImage">插入到帖子</t-button>
          <t-button size="small" variant="text" @click="drawImage = ''">丢弃</t-button>
        </div>
      </div>

      <div class="field">
        <span class="field-label">内容</span>
        <RichEditor ref="editorRef" v-model="form.rich" :cid="cid" :initial-images="initialImages" @update:images="onImages" />
        <div class="field-hint-row">
          <p class="field-hint">支持插入链接与图片（最多 9 张图片）</p>
          <span class="draft-hint">{{ draftSavedAt ? `已自动保存 ${draftSavedAt}` : '输入内容后每 2 秒自动保存草稿' }}</span>
        </div>
      </div>

      <!-- AI 生成预览（打字机效果） -->
      <section v-if="aiText" class="ai-preview">
        <div class="ai-preview-head">
          <span><AiIcon class="ai-preview-icon" /> AI 生成{{ aiBusy ? '中…' : '' }}</span>
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
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { AiIcon, ArrowLeftIcon, BrushIcon, EditIcon, ImageIcon, PenIcon } from 'tdesign-icons-vue-next'
import RichEditor from '@/components/RichEditor.vue'
import { communityApi, type TopicItem } from '@/api/community'
import { postApi, type RichSegment } from '@/api/post'
import { request, tokenStore } from '@/api/http'
import { toast } from '@/utils/toast'
import { confirmDialog } from '@/utils/confirm'
import { streamPost } from '@/utils/sse'

const route = useRoute()
const router = useRouter()
const cid = Number(route.params.id)
const bid = Number(route.params.bid)
const editId = Number(route.query.edit) || 0

// 草稿自动保存（P0）：每 2 秒防抖写 localStorage；key 区分 发帖/编辑 + 频道/版块，避免串稿
const draftKey = `draft:post:${cid}:${bid}:${editId || 'new'}`
const draftSavedAt = ref('')
const submitted = ref(false)
let draftTimer: number | undefined

const form = reactive({ title: '', rich: [] as RichSegment[], images: [] as string[], topic_id: null as number | null })
const initialImages = ref<string[]>([])
const error = ref('')
const submitting = ref(false)
const editing = ref(editId > 0)
const loading = ref(false)
const editorRef = ref<InstanceType<typeof RichEditor> | null>(null)

// 是否已有可保存的内容（空表单不落草稿，避免残留空稿）
const formDirty = computed(() => {
  return !!(form.title.trim() || form.rich.length > 0 || form.images.length > 0 || form.topic_id != null)
})

// 内容变化 → 防抖 2s 落草稿
watch(
  () => ({ title: form.title, rich: form.rich, images: form.images, topic_id: form.topic_id }),
  () => {
    if (submitted.value || !formDirty.value) return
    window.clearTimeout(draftTimer)
    draftTimer = window.setTimeout(saveDraft, 2000)
  },
  { deep: true },
)

// 话题 / AI 绘画（P0）
const topics = ref<TopicItem[]>([])
const drawBusy = ref(false)
const drawImage = ref('')
const drawDialog = ref(false)
const drawPrompt = ref('')

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
    router.push(`/login?redirect=${encodeURIComponent(route.fullPath)}`)
    return
  }
  aiBusy.value = action
  aiText.value = ''
  // 先留底：AI 失败时回填，避免用户原标题被清空后永久丢失
  const before = action === 'title' ? form.title : ''
  try {
    if (action === 'title') {
      // 直接打字机写入标题输入框
      form.title = ''
      await streamPost('/api/v1/ai/assist', { action, title: before, content: aiPlainContent() }, (d) => {
        form.title += d
      })
      if (!form.title.trim()) form.title = before
    } else {
      aiMode = action === 'polish' ? 'replace' : 'append'
      await streamPost('/api/v1/ai/assist', { action, title: form.title, content: aiPlainContent() }, (d) => {
        aiText.value += d
      })
      if (!aiText.value) aiText.value = '（AI 未返回内容）'
    }
    toast('AI 生成完成，可继续编辑', 'success')
  } catch (e) {
    // 失败回填原标题（生成过半也还原，保证用户内容不丢）
    if (action === 'title') form.title = before
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

/** AI 绘画入口（P0）：后端需配置 draw_api_url/key。用弹窗收集描述，替代 window.prompt。 */
function aiDraw() {
  if (drawBusy.value) return
  if (!tokenStore.access) {
    router.push(`/login?redirect=${encodeURIComponent(route.fullPath)}`)
    return
  }
  drawPrompt.value = ''
  drawDialog.value = true
}

async function submitDraw() {
  const prompt = drawPrompt.value.trim()
  if (!prompt) {
    toast('请输入画面描述', 'warning')
    return
  }
  if (drawBusy.value) return
  drawBusy.value = true
  try {
    const r = await request<{ url: string; b64_json: string }>({ url: '/ai/draw', method: 'POST', data: { prompt } })
    if (r.url) {
      drawImage.value = r.url
    } else if (r.b64_json) {
      drawImage.value = `data:image/png;base64,${r.b64_json}`
    } else {
      toast('未返回图片', 'error')
    }
  } catch (e) {
    toast(e instanceof Error ? e.message : '生成失败', 'error')
  } finally {
    drawBusy.value = false
    drawDialog.value = false
  }
}

function useDrawImage() {
  if (!drawImage.value || form.images.length >= 9) {
    toast('图片已达上限', 'error')
    return
  }
  form.images.push(drawImage.value)
  toast('已加入帖子图片', 'success')
}

onMounted(async () => {
  communityApi.topics(cid, 'hot').then((list) => (topics.value = list)).catch(() => {})
  if (editing.value) {
    loading.value = true
    try {
      const post = await postApi.get(editId)
      form.title = post.title
      form.rich = post.rich_content
      form.images = [...post.images]
      form.topic_id = post.topic_id
      initialImages.value = [...post.images] // 旧帖图片渲染进编辑器
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载帖子失败'
    } finally {
      loading.value = false
    }
  }
  tryRestoreDraft()
  // beforeunload：onBeforeUnmount 在浏览器刷新/关页时不可靠，必须单独兜底
  window.addEventListener('beforeunload', onBeforeUnload)
})

// 离开前拦截：内容未发布时提示（草稿已存，可稍后恢复）
onBeforeRouteLeave(async () => {
  if (submitted.value || !formDirty.value) return true
  const ok = await confirmDialog('离开页面？', '内容尚未发布。草稿已自动保存，可稍后回来继续编辑。', false)
  return ok
})

// 刷新/关闭页前把最后 2 秒内的输入补落一次草稿（同步写 localStorage）
function onBeforeUnload() {
  saveDraft()
}
onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', onBeforeUnload)
  window.clearTimeout(draftTimer)
  saveDraft()
})

function onImages(urls: string[]) {
  form.images = urls
}

// ---------- 草稿自动保存 ----------

function saveDraft() {
  if (submitted.value) return
  try {
    localStorage.setItem(
      draftKey,
      JSON.stringify({
        title: form.title,
        rich: form.rich,
        images: form.images,
        topic_id: form.topic_id,
        savedAt: Date.now(),
      }),
    )
    draftSavedAt.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } catch {
    // localStorage 不可用（隐私模式/超限）：静默忽略，不阻断编辑
  }
}

function tryRestoreDraft() {
  const raw = localStorage.getItem(draftKey)
  if (!raw) return
  let d: { title?: string; rich?: RichSegment[]; images?: string[]; topic_id?: number | null; savedAt?: number }
  try {
    d = JSON.parse(raw)
  } catch {
    localStorage.removeItem(draftKey)
    return
  }
  const hasContent = !!(d.title?.trim() || d.rich?.length || d.images?.length || d.topic_id != null)
  if (!hasContent) {
    localStorage.removeItem(draftKey)
    return
  }
  const when = d.savedAt ? new Date(d.savedAt).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : ''
  confirmDialog(
    '发现未发布草稿',
    when ? `检测到 ${when} 保存的草稿，是否恢复？` : '检测到未发布的草稿，是否恢复？',
    false,
  ).then((ok) => {
    if (ok) {
      form.title = d.title ?? ''
      form.rich = d.rich ?? []
      form.images = d.images ?? []
      form.topic_id = d.topic_id ?? null
      initialImages.value = [...(d.images ?? [])]
      editorRef.value?.setContent(form.rich, form.images)
      toast('已恢复草稿', 'success')
    } else {
      localStorage.removeItem(draftKey)
      draftSavedAt.value = ''
    }
  })
}

async function onSubmit() {
  if (submitting.value) return
  if (!tokenStore.access) {
    router.push(`/login?redirect=${encodeURIComponent(route.fullPath)}`)
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
        topic_id: form.topic_id ?? undefined,
      })
      toast('已保存', 'success')
      localStorage.removeItem(draftKey)
      draftSavedAt.value = ''
      submitted.value = true
      router.push(`/p/${post.id}`)
    } else {
      const post = await postApi.create(cid, bid, {
        title: form.title,
        rich_content: form.rich,
        images: form.images,
        topic_id: form.topic_id ?? undefined,
      })
      localStorage.removeItem(draftKey)
      draftSavedAt.value = ''
      submitted.value = true
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
.field-hint-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
}
.draft-hint {
  font-size: var(--fs-caption);
  color: var(--td-text-color-placeholder);
  white-space: nowrap;
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
.ai-bar-cal-icon {
  width: 16px;
  height: 16px;
  vertical-align: -3px;
  margin-right: 2px;
}
.ai-preview-head .ai-preview-icon {
  width: 14px;
  height: 14px;
  vertical-align: -2px;
  margin-right: 2px;
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
.draw-img {
  max-width: 100%;
  max-height: 300px;
  border-radius: var(--radius-card);
  border: 1px solid var(--border);
}
.draw-ops {
  display: flex;
  gap: var(--sp-2);
}
</style>
