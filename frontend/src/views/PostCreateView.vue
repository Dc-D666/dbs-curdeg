<template>
  <main class="create-page">
    <header class="page-header">
      <router-link :to="`/c/${cid}`" class="back">← 返回</router-link>
      <h1 class="page-title">发帖</h1>
    </header>

    <section class="panel">
      <label class="field">
        <span class="field-label">标题</span>
        <input v-model.trim="form.title" class="input" type="text" maxlength="128" placeholder="一句话说清楚" />
      </label>

      <label class="field">
        <span class="field-label">内容</span>
        <textarea v-model="form.content" class="input textarea" maxlength="10000" placeholder="分享你的内容…" />
      </label>

      <div class="field">
        <span class="field-label">图片（最多 9 张）</span>
        <div class="image-grid">
          <div v-for="(img, i) in form.images" :key="img" class="image-cell">
            <img :src="img" alt="" />
            <button type="button" class="image-remove" @click="form.images.splice(i, 1)">×</button>
          </div>
          <label v-if="form.images.length < 9" class="image-cell add-cell">
            <span>{{ uploading ? '上传中…' : '+' }}</span>
            <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden @change="onPickImage" />
          </label>
        </div>
      </div>

      <p v-if="error" class="error">{{ error }}</p>

      <button class="btn-primary submit" :disabled="submitting" @click="onSubmit">
        {{ submitting ? '发布中…' : '发布' }}
      </button>
    </section>
  </main>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { postApi } from '@/api/post'
import { request, tokenStore } from '@/api/http'

const route = useRoute()
const router = useRouter()
const cid = Number(route.params.id)
const bid = Number(route.params.bid)

const form = reactive({ title: '', content: '', images: [] as string[] })
const error = ref('')
const submitting = ref(false)
const uploading = ref(false)

async function onPickImage(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (uploading.value) return
  uploading.value = true
  error.value = ''
  const fd = new FormData()
  fd.append('file', file)
  try {
    const up = await request<{ url: string }>({ url: '/uploads', method: 'POST', data: fd })
    form.images.push(up.url)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '上传失败'
  } finally {
    uploading.value = false
  }
}

async function onSubmit() {
  if (submitting.value) return
  if (!tokenStore.access) {
    window.location.href = '/login'
    return
  }
  if (!form.title) {
    error.value = '请填写标题'
    return
  }
  if (!form.content) {
    error.value = '请填写内容'
    return
  }
  submitting.value = true
  error.value = ''
  try {
    const post = await postApi.create(cid, bid, { title: form.title, content: form.content, images: form.images })
    router.push(`/p/${post.id}`)
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
}
.page-title {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
  flex: 1;
}
.panel {
  margin-top: var(--sp-4);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
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
  color: var(--text-2);
}
.input {
  padding: var(--sp-2) var(--sp-3);
  font-size: var(--fs-body);
  color: var(--text-1);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-btn);
  outline: none;
}
.input:focus {
  border-color: var(--brand);
}
.textarea {
  min-height: 160px;
  resize: vertical;
  line-height: 1.6;
}
.image-grid {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
}
.image-cell {
  position: relative;
  width: 72px;
  height: 72px;
  border-radius: var(--radius-btn);
  overflow: hidden;
  border: 1px solid var(--border);
}
.image-cell img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.image-remove {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 20px;
  height: 20px;
  border: none;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
}
.add-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  border-style: dashed;
  color: var(--text-3);
  font-size: 24px;
  cursor: pointer;
}
.error {
  margin: 0;
  font-size: var(--fs-caption);
  color: var(--danger);
}
.btn-primary {
  height: 40px;
  border: none;
  border-radius: var(--radius-btn);
  background: var(--brand);
  color: #fff;
  font-size: var(--fs-body);
  cursor: pointer;
}
.btn-primary:hover {
  background: var(--brand-hover);
}
.btn-primary:disabled {
  background: var(--text-3);
  cursor: not-allowed;
}
</style>
