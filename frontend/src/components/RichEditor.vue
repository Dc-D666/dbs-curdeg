<template>
  <div class="rich-editor">
    <div class="re-toolbar">
      <button type="button" class="re-btn" title="加粗（**文字**）" @click="exec('bold')"><b>B</b></button>
      <button type="button" class="re-btn" title="斜体（*文字*）" @click="exec('italic')"><i>I</i></button>
      <button type="button" class="re-btn" title="删除线（~~文字~~）" @click="exec('strikeThrough')"><s>S</s></button>
      <span class="re-sep"></span>
      <span class="re-drop">
        <button type="button" class="re-btn" title="文字颜色">A</button>
        <span class="re-panel">
          <button v-for="c in COLORS" :key="c" type="button" class="swatch" :style="{ background: c }" @click="exec('foreColor', c)"></button>
        </span>
      </span>
      <span class="re-drop">
        <button type="button" class="re-btn" title="背景颜色">▦</button>
        <span class="re-panel">
          <button v-for="c in BGS" :key="c" type="button" class="swatch" :style="{ background: c }" @click="exec('hiliteColor', c)"></button>
        </span>
      </span>
      <span class="re-drop">
        <button type="button" class="re-btn" title="字号">T</button>
        <span class="re-panel re-panel-col">
          <button v-for="(s, i) in SIZES" :key="s" type="button" class="re-btn" :style="{ fontSize: s }" @click="exec('fontSize', String(i + 1))">
            {{ s }}
          </button>
        </span>
      </span>
      <span class="re-sep"></span>
      <button type="button" class="re-btn" title="提及成员" @click="openAt">@</button>
      <button type="button" class="re-btn" title="话题" @click="insertTopic">#</button>
      <button type="button" class="re-btn" title="表情" @click="emojiOpen = !emojiOpen">☺</button>
      <button type="button" class="re-btn" title="插入链接" @click="insertLink"><LinkIcon class="re-icon" /></button>
      <label class="re-btn" title="插入图片">
        <ImageIcon class="re-icon" />
        <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden @change="onPickImage" />
      </label>
      <span v-if="uploading" class="re-uploading">上传中…</span>
    </div>

    <!-- @ 成员面板 -->
    <div v-if="atOpen" class="re-overlay" @click.self="atOpen = false">
      <div class="re-dialog">
        <h4 class="re-dialog-title">提及成员</h4>
        <div class="re-member-list">
          <button v-for="m in members" :key="m.id" type="button" class="re-member" @click="insertAt(m)">
            {{ m.user_nickname || m.username }}
            <span class="re-member-tag">{{ memberTypeName(m.member_type) }}</span>
          </button>
          <p v-if="members.length === 0" class="re-dialog-empty">暂无成员</p>
        </div>
      </div>
    </div>

    <!-- emoji 面板 -->
    <div v-if="emojiOpen" class="re-emoji-panel">
      <button v-for="e in EMOJIS" :key="e" type="button" class="re-emoji" @click="insertEmoji(e)">{{ e }}</button>
    </div>

    <div
      ref="editorEl"
      class="re-content"
      contenteditable="true"
      data-placeholder="分享你的内容… 支持 **加粗** *斜体* `代码` ~~删除线~~、@成员、#话题、链接与图片"
      @input="onInput"
      @paste="onPaste"
      @mouseup="rememberRange"
      @keyup="rememberRange"
    ></div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { ImageIcon, LinkIcon } from 'tdesign-icons-vue-next'
import { communityApi, type Member } from '@/api/community'
import { request } from '@/api/http'
import type { RichSegment, SegStyle } from '@/api/post'
import { toast } from '@/utils/toast'

const props = defineProps<{ modelValue: RichSegment[]; cid: number; initialImages?: string[] }>()
const emit = defineEmits<{
  'update:modelValue': [RichSegment[]]
  'update:images': [string[]]
}>()

const COLORS = ['#d54941', '#e37318', '#f7ba1e', '#00a870', '#0052d9', '#7a3ff2']
const BGS = ['#ffefef', '#fff7e6', '#e8f5e9', '#e8f0fe']
const SIZES = ['12px', '14px', '16px', '18px', '20px']
const SIZE_MAP: Record<string, string> = { '1': '12px', '2': '14px', '3': '16px', '4': '18px', '5': '20px', '6': '24px', '7': '28px' }
const EMOJIS = ['😀', '😂', '🤣', '😊', '😍', '🤔', '😭', '😡', '👍', '👎', '👏', '🙏', '💪', '🔥', '❤️', '🎉', '✨', '💯', '🎯', '🤝']

const editorEl = ref<HTMLDivElement | null>(null)
const uploading = ref(false)
const images = ref<string[]>([])
const atOpen = ref(false)
const emojiOpen = ref(false)
const members = ref<Member[]>([])
let membersLoaded = false
let savedRange: Range | null = null

onMounted(() => {
  renderSegments(props.modelValue, props.initialImages ?? [])
})

watch(
  () => props.modelValue,
  (segs) => {
    if (editorEl.value && editorEl.value.textContent === '' && segs.length > 0) {
      renderSegments(segs)
    }
  },
  { deep: true },
)

// ---------- 工具栏 ----------

function exec(cmd: string, value?: string) {
  editorEl.value?.focus()
  document.execCommand(cmd, false, value)
  onInput()
}

function rememberRange() {
  savedRange = saveRange()
}

function saveRange(): Range | null {
  const sel = window.getSelection()
  if (!sel || sel.rangeCount === 0) return null
  const range = sel.getRangeAt(0)
  const el = editorEl.value
  if (!el || !el.contains(range.commonAncestorContainer)) return null
  return range.cloneRange()
}

function restoreRange(): Range | null {
  const el = editorEl.value
  if (!el) return null
  const sel = window.getSelection()
  const range = savedRange || (sel && sel.rangeCount ? sel.getRangeAt(0) : null)
  if (range && el.contains(range.commonAncestorContainer)) return range
  return null
}

function insertNode(node: Node) {
  const el = editorEl.value
  if (!el) return
  el.focus()
  const range = restoreRange()
  if (range) {
    range.deleteContents()
    range.insertNode(node)
    range.collapse(false)
  } else {
    el.append(document.createTextNode(' '))
    el.append(node)
  }
  savedRange = null
  onInput()
}

// ---------- @ / 话题 / emoji / 链接 ----------

async function openAt() {
  if (!membersLoaded) {
    try {
      const data = await communityApi.members(props.cid, 1, 50)
      members.value = data.items
      membersLoaded = true
    } catch (e) {
      toast(e instanceof Error ? e.message : '加载成员失败', 'error')
      return
    }
  }
  atOpen.value = !atOpen.value
}

function memberTypeName(t: number): string {
  return t === 0 ? '频道主' : t === 1 ? '管理员' : '成员'
}

function insertAt(m: Member) {
  const span = document.createElement('span')
  span.className = 're-at'
  span.dataset.type = 'at'
  span.dataset.uid = String(m.user_id)
  span.contentEditable = 'false'
  span.textContent = `@${m.user_nickname || m.username} `
  atOpen.value = false
  insertNode(span)
}

async function insertTopic() {
  const name = window.prompt('话题名称（不带 #，最多 32 字）')
  if (!name) return
  try {
    const data = await request<{ id: number; name: string }>({
      url: `/communities/${props.cid}/topics`,
      method: 'POST',
      data: { name },
    })
    const span = document.createElement('span')
    span.className = 're-topic'
    span.dataset.type = 'topic'
    span.dataset.tid = String(data.id)
    span.contentEditable = 'false'
    span.textContent = `#${data.name} `
    insertNode(span)
  } catch (e) {
    toast(e instanceof Error ? e.message : '创建话题失败', 'error')
  }
}

function insertEmoji(char: string) {
  emojiOpen.value = false
  const span = document.createElement('span')
  span.className = 're-emoji'
  span.dataset.type = 'emoji'
  span.dataset.id = String(EMOJIS.indexOf(char) + 1)
  span.dataset.char = char
  span.contentEditable = 'false'
  span.textContent = char
  insertNode(span)
}

function insertLink() {
  const url = window.prompt('链接地址（https://…）')
  if (!url) return
  const text = window.prompt('显示文字') || url
  const a = document.createElement('a')
  a.href = url
  a.className = 're-link'
  a.dataset.type = 'link'
  a.dataset.url = url
  a.textContent = text
  insertNode(a)
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
    const img = document.createElement('img')
    img.src = up.url
    img.className = 're-img'
    insertNode(img)
  } catch (err) {
    toast(err instanceof Error ? err.message : '上传失败', 'error')
  } finally {
    uploading.value = false
  }
}

function onPaste(e: ClipboardEvent) {
  e.preventDefault() // 粘贴转纯文本防 XSS
  const text = e.clipboardData?.getData('text/plain') ?? ''
  document.execCommand('insertText', false, text)
  onInput()
}

// ---------- 序列化：DOM → 4.4 分片（含 markdown 快捷语法解析） ----------

interface Ctx {
  bold?: boolean
  italic?: boolean
  strike?: boolean
  code?: boolean
  color?: string
  bg?: string
  size?: string
}

function onInput() {
  emit('update:modelValue', serialize())
  images.value = collectImages()
  emit('update:images', images.value)
}

/** 外部注入纯文本（AI 帮写用）：append 追加 / replace 替换，触发序列化。 */
function insertText(text: string, mode: 'append' | 'replace' = 'append') {
  const el = editorEl.value
  if (!el) return
  if (mode === 'replace') {
    el.innerHTML = ''
  }
  el.append(document.createTextNode(text))
  onInput()
  el.focus()
}

defineExpose({ insertText })

function serialize(): RichSegment[] {
  const segs: RichSegment[] = []
  const el = editorEl.value
  if (!el) return segs
  const walk = (node: Node, ctx: Ctx) => {
    if (node.nodeType === Node.TEXT_NODE) {
      const t = node.textContent || ''
      if (t.trim()) segs.push(...parseInline(t, ctx))
    } else if (node instanceof HTMLElement) {
      if (node.dataset.type === 'link' && node.dataset.url) {
        segs.push({ type: 3, url: node.dataset.url, display_text: node.textContent || node.dataset.url, url_type: 10 })
      } else if (node.dataset.type === 'at' && node.dataset.uid) {
        segs.push({ type: 2, at_user: { id: Number(node.dataset.uid), nick: (node.textContent || '').replace(/^@|\s*$/g, '') } })
      } else if (node.dataset.type === 'topic' && node.dataset.tid) {
        segs.push({ type: 8, topic: { topic_id: Number(node.dataset.tid), topic_name: (node.textContent || '').replace(/^#|\s*$/g, '') } })
      } else if (node.dataset.type === 'emoji' && node.dataset.char) {
        segs.push({ type: 4, emoji: { id: node.dataset.id || '0', char: node.dataset.char } })
      } else {
        const next = elementCtx(node, ctx)
        node.childNodes.forEach((c) => walk(c, next))
      }
    }
  }
  el.childNodes.forEach((c) => walk(c, {}))
  return segs
}

function elementCtx(el: HTMLElement, prev: Ctx): Ctx {
  const ctx = { ...prev }
  const tag = el.tagName
  if (tag === 'B' || tag === 'STRONG' || el.style.fontWeight === 'bold' || Number(el.style.fontWeight) >= 600) ctx.bold = true
  if (tag === 'I' || tag === 'EM' || el.style.fontStyle === 'italic') ctx.italic = true
  if (tag === 'S' || tag === 'STRIKE' || tag === 'DEL' || (el.style.textDecorationLine || '').includes('line-through')) ctx.strike = true
  if (tag === 'CODE') ctx.code = true
  const color = el.style.color || el.getAttribute('color') || ''
  if (color) ctx.color = color
  const bg = el.style.backgroundColor || ''
  if (bg) ctx.bg = bg
  const size = el.style.fontSize || SIZE_MAP[el.getAttribute('size') || ''] || ''
  if (size) ctx.size = size
  return ctx
}

function parseInline(text: string, ctx: Ctx): RichSegment[] {
  const segs: RichSegment[] = []
  const re = /(\*\*[^*]+\*\*|\*[^*\n]+\*|`[^`]+`|~~[^~]+~~)/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(text))) {
    if (m.index > last) pushText(segs, text.slice(last, m.index), ctx)
    const raw = m[0]
    const style = { ...ctx }
    if (raw.startsWith('**')) {
      style.bold = true
      pushText(segs, raw.slice(2, -2), style)
    } else if (raw.startsWith('~~')) {
      style.strike = true
      pushText(segs, raw.slice(2, -2), style)
    } else if (raw.startsWith('`')) {
      style.code = true
      pushText(segs, raw.slice(1, -1), style)
    } else if (raw.startsWith('*')) {
      style.italic = true
      pushText(segs, raw.slice(1, -1), style)
    }
    last = m.index + raw.length
  }
  if (last < text.length) pushText(segs, text.slice(last), ctx)
  return segs
}

function pushText(segs: RichSegment[], text: string, style: Ctx) {
  if (!text) return
  const s: SegStyle = {}
  if (style.bold) s.bold = true
  if (style.italic) s.italic = true
  if (style.strike) s.strike = true
  if (style.code) s.code = true
  if (style.color) s.color = style.color
  if (style.bg) s.bg = style.bg
  if (style.size) s.size = style.size
  if (Object.keys(s).length > 0) segs.push({ type: 1, text, style: s })
  else segs.push({ type: 1, text })
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
      el.append(styleText(seg.text, seg.style || {}))
    } else if (seg.type === 2 && seg.at_user) {
      const span = document.createElement('span')
      span.className = 're-at'
      span.dataset.type = 'at'
      span.dataset.uid = String(seg.at_user.id)
      span.contentEditable = 'false'
      span.textContent = `@${seg.at_user.nick} `
      el.append(span)
    } else if (seg.type === 3 && seg.url) {
      const a = document.createElement('a')
      a.href = seg.url
      a.className = 're-link'
      a.dataset.type = 'link'
      a.dataset.url = seg.url
      a.textContent = seg.display_text || seg.url
      el.append(a)
    } else if (seg.type === 4 && seg.emoji) {
      const span = document.createElement('span')
      span.className = 're-emoji'
      span.dataset.type = 'emoji'
      span.dataset.id = seg.emoji.id || '0'
      span.dataset.char = seg.emoji.char || ''
      span.contentEditable = 'false'
      span.textContent = seg.emoji.char || ''
      el.append(span)
    } else if (seg.type === 8 && seg.topic) {
      const span = document.createElement('span')
      span.className = 're-topic'
      span.dataset.type = 'topic'
      span.dataset.tid = String(seg.topic.topic_id)
      span.contentEditable = 'false'
      span.textContent = `#${seg.topic.topic_name} `
      el.append(span)
    }
  }
  for (const url of initialImages) {
    const img = document.createElement('img')
    img.src = url
    img.className = 're-img'
    el.append(document.createTextNode(' '))
    el.append(img)
  }
  if (initialImages.length) images.value = [...initialImages]
}

function styleText(text: string, s: SegStyle): Node {
  let node: Node = document.createTextNode(text)
  if (!Object.keys(s).length) return node
  const span = document.createElement('span')
  span.style.fontWeight = s.bold ? 'bold' : ''
  span.style.fontStyle = s.italic ? 'italic' : ''
  span.style.textDecorationLine = s.strike ? 'line-through' : ''
  if (s.code) span.className = 're-code'
  if (s.color) span.style.color = s.color
  if (s.bg) span.style.backgroundColor = s.bg
  if (s.size) span.style.fontSize = s.size
  span.textContent = text
  return span
}
</script>

<style scoped>
.rich-editor {
  border: 1px solid var(--border);
  border-radius: var(--radius-btn);
  overflow: visible;
  background: var(--bg-card);
}
.rich-editor:focus-within {
  border-color: var(--brand);
}
.re-toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 2px;
  padding: 6px 8px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-secondary);
}
.re-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 28px;
  padding: 0 8px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--text-2);
  font-size: 13px;
  cursor: pointer;
  transition: background var(--anim-duration) var(--anim-ease);
}
.re-btn:hover {
  background: var(--brand-weak);
  color: var(--brand);
}
.re-icon {
  width: 16px;
  height: 16px;
}
.re-sep {
  width: 1px;
  height: 16px;
  background: var(--border);
  margin: 0 4px;
}
.re-drop {
  position: relative;
  display: inline-flex;
}
.re-panel {
  position: absolute;
  top: 30px;
  left: 0;
  z-index: 20;
  display: none;
  flex-wrap: wrap;
  gap: 4px;
  width: 132px;
  padding: 8px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: var(--shadow-overlay);
}
.re-panel-col {
  width: 120px;
  flex-direction: column;
}
.re-drop:hover .re-panel {
  display: flex;
}
.swatch {
  width: 20px;
  height: 20px;
  border: 1px solid var(--border);
  border-radius: 4px;
  cursor: pointer;
}
.re-uploading {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-3);
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
.re-at {
  color: var(--brand);
  background: var(--brand-weak);
  border-radius: 4px;
  padding: 0 2px;
}
.re-topic {
  color: #8a6d1a;
  background: #fff7e6;
  border-radius: 4px;
  padding: 0 4px;
}
.re-emoji {
  font-size: 18px;
}
.re-code {
  font-family: Consolas, Monaco, monospace;
  background: var(--bg-secondary);
  border-radius: 4px;
  padding: 0 4px;
  font-size: 0.92em;
}
.re-img {
  display: block;
  max-width: 100%;
  max-height: 300px;
  border-radius: var(--radius-btn);
  margin: 4px 0;
}
.re-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 80;
  padding: var(--sp-4);
}
.re-dialog {
  width: 100%;
  max-width: 340px;
  max-height: 60vh;
  overflow-y: auto;
  background: var(--bg-card);
  border-radius: var(--radius-overlay);
  padding: var(--sp-4);
  box-shadow: var(--shadow-overlay);
}
.re-dialog-title {
  margin: 0 0 var(--sp-3);
  font-size: var(--fs-title);
}
.re-member-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.re-member {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-1);
  font-size: var(--fs-body);
  cursor: pointer;
  text-align: left;
}
.re-member:hover {
  background: var(--brand-weak);
  color: var(--brand);
}
.re-member-tag {
  font-size: 12px;
  color: var(--text-3);
}
.re-dialog-empty {
  text-align: center;
  color: var(--text-3);
  font-size: var(--fs-caption);
}
.re-emoji-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  padding: 6px 8px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-card);
}
.re-emoji-panel .re-emoji {
  width: 34px;
  height: 34px;
  border: none;
  background: transparent;
  border-radius: 6px;
  font-size: 20px;
  cursor: pointer;
}
.re-emoji-panel .re-emoji:hover {
  background: var(--brand-weak);
}
</style>
