<template>
  <div class="quick-composer" :class="{ open }">
    <!-- 折叠态：常驻轻量入口 -->
    <button v-if="!open" class="qc-button" @click="expand">
      <PenIcon class="qc-icon" />分享你的想法…
    </button>

    <!-- 展开态：标题 + 正文 + 操作 -->
    <div v-else class="qc-panel">
      <t-input v-model.trim="title" class="qc-title" maxlength="128" placeholder="标题" clearable />
      <t-textarea
        v-model="content"
        class="qc-body"
        :autosize="{ minRows: 3, maxRows: 8 }"
        maxlength="5000"
        placeholder="正文"
      />
      <div class="qc-foot">
        <div class="qc-left">
          <!-- 上传图片：选择后显示缩略图，可移除 -->
          <label class="qc-upload" :title="'上传图片'">
            <ImageIcon class="qc-upload-icon" />
            <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden multiple @change="onPickImages" />
          </label>
          <div v-if="images.length" class="qc-imgs">
            <span v-for="(u, i) in images" :key="u" class="qc-img">
              <img :src="u" alt="" />
              <button type="button" class="qc-img-del" @click="removeImage(i)">×</button>
            </span>
          </div>
        </div>
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
import { ImageIcon, PenIcon } from 'tdesign-icons-vue-next'
import { postApi } from '@/api/post'
import { request, tokenStore } from '@/api/http'
import { toast } from '@/utils/toast'
import { confirmDialog } from '@/utils/confirm'

const props = withDefaults(defineProps<{ cid: number; bid: number }>(), { bid: 0 })
const emit = defineEmits<{ (e: 'posted'): void }>()

const router = useRouter()
const route = useRoute()
const open = ref(false)
const title = ref('')
const content = ref('')
const images = ref<string[]>([])
const submitting = ref(false)
const uploading = ref(false)

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
  images.value = []
}

/** 有内容时先二次确认，避免误点「取消」丢稿。 */
async function collapse() {
  if (title.value.trim() || content.value.trim() || images.value.length) {
    const ok = await confirmDialog('放弃这条内容？', '关闭后已填写的标题、正文和图片将不会保留。', false)
    if (!ok) return
  }
  reset()
}

/** 选择图片 → 上传到 /uploads → 收集 URL（最多 9 张）。 */
async function onPickImages(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  if (!files.length) return
  const remain = 9 - images.value.length
  if (files.length > remain) {
    toast(`最多还能上传 ${remain} 张图片`, 'warning')
  }
  uploading.value = true
  try {
    for (const file of files.slice(0, remain)) {
      const fd = new FormData()
      fd.append('file', file)
      const up = await request<{ url: string }>({ url: '/uploads', method: 'POST', data: fd })
      images.value.push(up.url)
    }
  } catch (err) {
    toast(err instanceof Error ? err.message : '上传失败', 'error')
  } finally {
    uploading.value = false
    input.value = ''
  }
}

function removeImage(i: number) {
  images.value.splice(i, 1)
}

async function submit() {
  if (submitting.value || uploading.value) return
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
    await postApi.create(props.cid, props.bid, {
      title: t,
      content: c || undefined,
      images: images.value,
    })
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
.qc-left {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-width: 0;
}
/* 上传图片按钮：图标式入口 */
.qc-upload {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-control);
  color: var(--text-3);
  cursor: pointer;
  flex-shrink: 0;
}
.qc-upload:hover {
  color: var(--brand);
  background: var(--surface-2);
}
.qc-upload-icon {
  width: 18px;
  height: 18px;
}
.qc-imgs {
  display: flex;
  gap: var(--sp-2);
  overflow-x: auto;
  min-width: 0;
}
.qc-img {
  position: relative;
  flex-shrink: 0;
}
.qc-img img {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-btn);
  object-fit: cover;
  border: 1px solid var(--border);
  display: block;
}
.qc-img-del {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: none;
  background: var(--danger);
  color: #fff;
  font-size: 11px;
  line-height: 16px;
  text-align: center;
  cursor: pointer;
  padding: 0;
}
.qc-hint {
  font-size: var(--fs-caption);
  color: var(--text-3);
  white-space: nowrap;
}
.qc-actions {
  display: flex;
  gap: var(--sp-2);
  flex-shrink: 0;
}
</style>
