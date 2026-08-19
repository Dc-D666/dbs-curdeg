<template>
  <div class="rich-editor">
    <div class="re-toolbar">
      <button type="button" class="re-btn" title="插入链接" @click="insertLink">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8">
          <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" stroke-linecap="round" />
          <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" stroke-linecap="round" />
        </svg>
        <span>链接</span>
      </button>
      <label class="re-btn" title="插入图片">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <circle cx="8.5" cy="8.5" r="1.5" />
          <path d="m21 15-5-5L5 21" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <span>{{ uploading ? '上传中…' : '图片' }}</span>
        <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden @change="onPickImage" />
      </label>
    </div>
    <div
      ref="editorEl"
      class="re-content"
      contenteditable="true"
      data-placeholder="分享你的内容… 支持插入链接与图片"
      @input="onInput"
      @paste="onPaste"
    ></div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { request } from '@/api/http'

export interface RichSegment {
  type: number
  text?: string
  url?: string
  display_text?: string
  url_type?: number
}

const props = defineProps<{ modelValue: RichSegment[]; initialImages?: string[] }>()
const emit = defineEmits<{
  'update:modelValue': [RichSegment[]]
  'update:images': [string[]]
}>()

const editorEl = ref<HTMLDivElement | null>(null)
const uploading = ref(false)
const images = ref<string[]>([])

onMounted(() => {
  renderSegments(props.modelValue, props.initialImages ?? [])
})

// 外部值变化（编辑模式加载）时回填
watch(
  () => props.modelValue,
  (segs) => {
    if (editorEl.value && editorEl.value.textContent === '' && segs.length > 0) {
      renderSegments(segs)
    }
  },
  { deep: true },
)

// ---------- 序列化：DOM → 4.4 分片 ----------

function onInput() {
  const segs = serialize()
  images.value = collectImages()
  emit('update:modelValue', segs)
  emit('update:images', images.value)
}

function serialize(): RichSegment[] {
  const segs: RichSegment[] = []
  const el = editorEl.value
  if (!el) return segs
  const walk = (node: Node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      const t = node.textContent || ''
      if (t.trim()) segs.push({ type: 1, text: t })
    } else if (node instanceof HTMLElement) {
      if (node.dataset.type === 'link' && node.dataset.url) {
        segs.push({
          type: 3,
          url: node.dataset.url,
          display_text: node.textContent || node.dataset.url,
          url_type: 10,
        })
      } else {
        node.childNodes.forEach(walk)
      }
    }
  }
  el.childNodes.forEach(walk)
  return segs
}

function collectImages(): string[] {
  const el = editorEl.value
  if (!el) return []
  const urls: string[] = []
  el.querySelectorAll('img').forEach((img) => {
    if (img.src && !urls.includes(img.src)) urls.push(img.src)
  })
  return urls
}

// ---------- 反序列化：分片 → DOM ----------

function renderSegments(segs: RichSegment[], initialImages: string[] = []) {
  const el = editorEl.value
  if (!el) return
  el.innerHTML = ''
  images.value = []
  for (const seg of segs) {
    if (seg.type === 1 && seg.text) {
      el.append(document.createTextNode(seg.text))
    } else if (seg.type === 3 && seg.url) {
      el.append(buildLink(seg.url, seg.display_text || seg.url))
    }
  }
  // 旧帖兼容：images 字段的图片渲染进编辑器（编辑时保留）
  for (const url of initialImages) {
    const img = document.createElement('img')
    img.src = url
    img.className = 're-img'
    el.append(document.createTextNode(' '))
    el.append(img)
  }
  if (initialImages.length) images.value = [...initialImages]
}

function buildLink(url: string, text: string): HTMLAnchorElement {
  const a = document.createElement('a')
  a.href = url
  a.dataset.type = 'link'
  a.dataset.url = url
  a.textContent = text
  a.className = 're-link'
  return a
}

// ---------- 插入 ----------

function saveRange(): Range | null {
  const sel = window.getSelection()
  if (!sel || sel.rangeCount === 0) return null
  const range = sel.getRangeAt(0)
  const el = editorEl.value
  if (!el) return null
  if (!el.contains(range.commonAncestorContainer)) return null
  return range.cloneRange()
}

let savedRange: Range | null = null

function insertLink() {
  const url = window.prompt('链接地址（https://…）')
  if (!url) return
  const text = window.prompt('显示文字') || url
  const el = editorEl.value
  if (!el) return
  el.focus()
  const sel = window.getSelection()
  const range = savedRange || (sel && sel.rangeCount ? sel.getRangeAt(0) : null)
  if (range && el.contains(range.commonAncestorContainer)) {
    range.deleteContents()
    range.insertNode(buildLink(url, text))
    range.collapse(false)
    savedRange = null
  } else {
    el.append(document.createTextNode(' '))
    el.append(buildLink(url, text))
  }
  onInput()
}

async function onPickImage(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || uploading.value) return
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const up = await request<{ url: string }>({ url: '/uploads', method: 'POST', data: fd })
    const el = editorEl.value
    if (!el) return
    el.focus()
    const img = document.createElement('img')
    img.src = up.url
    img.className = 're-img'
    const sel = window.getSelection()
    const range = savedRange || (sel && sel.rangeCount ? sel.getRangeAt(0) : null)
    if (range && el.contains(range.commonAncestorContainer)) {
      range.deleteContents()
      range.insertNode(img)
      range.collapse(false)
      savedRange = null
    } else {
      el.append(document.createTextNode(' '))
      el.append(img)
    }
    onInput()
  } catch (err) {
    window.alert(err instanceof Error ? err.message : '上传失败')
  } finally {
    uploading.value = false
  }
}

function onPaste(e: ClipboardEvent) {
  // 粘贴转纯文本，防 XSS
  e.preventDefault()
  const text = e.clipboardData?.getData('text/plain') ?? ''
  document.execCommand('insertText', false, text)
  onInput()
}

// 输入/点击时记住光标
function onMouseUp() {
  savedRange = saveRange()
}
</script>

<style scoped>
.rich-editor {
  border: 1px solid var(--border);
  border-radius: var(--radius-btn);
  overflow: hidden;
  background: var(--bg-card);
}
.rich-editor:focus-within {
  border-color: var(--brand);
}
.re-toolbar {
  display: flex;
  gap: 4px;
  padding: 6px 8px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-secondary);
}
.re-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 28px;
  padding: 0 10px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--text-2);
  font-size: 12px;
  cursor: pointer;
  transition: background var(--anim-duration) var(--anim-ease);
}
.re-btn:hover {
  background: var(--brand-weak);
  color: var(--brand);
}
.re-content {
  min-height: 160px;
  padding: 10px 12px;
  font-size: var(--fs-body);
  line-height: 1.7;
  color: var(--text-1);
  outline: none;
  word-break: break-word;
}
.re-content:empty::before {
  content: attr(data-placeholder);
  color: var(--text-3);
  pointer-events: none;
}
.re-link {
  color: var(--brand);
  text-decoration: underline;
}
.re-img {
  display: block;
  max-width: 100%;
  max-height: 300px;
  border-radius: var(--radius-btn);
  margin: 4px 0;
}
</style>
