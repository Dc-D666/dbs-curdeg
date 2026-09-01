<template>
  <main class="page">
    <header class="page-header">
      <router-link to="/me" class="back">
        <ArrowLeftIcon class="back-icon" /> 我的
      </router-link>
      <h1 class="page-title">我的分享短链</h1>
    </header>

    <ErrorState v-if="loadError" :text="loadError" @retry="load" />
    <template v-else>
      <div v-if="loading && items.length === 0" class="state"><t-skeleton :row="3" animation="gradient" /></div>
      <EmptyState v-else-if="items.length === 0" text="还没有生成过分享短链，在帖子详情页点「分享」即可创建" />

      <div v-else class="panel">
        <div v-for="s in items" :key="s.code" class="share-row">
          <div class="share-main">
            <div class="share-head">
              <t-tag size="small" variant="light" theme="primary">{{ typeLabel(s.target_type) }}</t-tag>
              <router-link :to="targetPath(s)" class="share-target"><LinkIcon class="share-target-icon" /> #{{ s.target_id }}</router-link>
              <span class="share-time">{{ timeAgo(s.created_at) }}</span>
            </div>
            <p class="share-url">/s/{{ s.code }}</p>
            <p class="share-meta">
              访问 {{ s.visit_count }} 次
              <template v-if="isExpired(s)"> · 已失效</template>
            </p>
          </div>
          <div class="share-ops">
            <t-button
              variant="outline"
              size="small"
              @click="copy(s)"
            >复制链接</t-button>
            <t-button
              v-if="!isExpired(s)"
              variant="outline"
              size="small"
              theme="danger"
              @click="onInvalidate(s)"
            >失效</t-button>
          </div>
        </div>
        <t-button
          v-if="hasMore"
          variant="outline"
          block
          class="load-more"
          :loading="loading"
          @click="loadMore"
        >加载更多（{{ items.length }}/{{ total }}）</t-button>
      </div>
    </template>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ArrowLeftIcon, LinkIcon } from 'tdesign-icons-vue-next'
import { postApi, type ShareItem } from '@/api/post'
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import { timeAgo } from '@/utils/time'
import { confirmDialog } from '@/utils/confirm'
import { errMessage } from '@/utils/error'
import { toast } from '@/utils/toast'

const items = ref<ShareItem[]>([])
const page = ref(0)
const total = ref(0)
const hasMore = ref(false)
const loading = ref(false)
const loadError = ref('')
const origin = window.location.origin

function typeLabel(t: number): string {
  return ['', '频道', '帖子', '用户'][t] ?? '未知'
}
function targetPath(s: ShareItem): string {
  if (s.target_type === 1) return `/c/${s.target_id}`
  if (s.target_type === 2) return `/p/${s.target_id}`
  return `/users/${s.target_id}`
}
/** 已过期的短链（失效=置过期时间为过去，懒查询即拦）。 */
function isExpired(s: ShareItem): boolean {
  return !!s.expires_at && new Date(s.expires_at).getTime() <= Date.now()
}

async function loadPage(p: number) {
  loading.value = true
  try {
    const data = await postApi.myShares(p, 20)
    items.value = p === 1 ? data.items : [...items.value, ...data.items]
    page.value = p
    total.value = data.total
    hasMore.value = items.value.length < data.total
  } catch (e) {
    loadError.value = errMessage(e, '加载短链记录失败')
  } finally {
    loading.value = false
  }
}

function load() {
  loadError.value = ''
  loadPage(1)
}

function loadMore() {
  loadPage(page.value + 1)
}

async function copy(s: ShareItem) {
  try {
    await navigator.clipboard.writeText(`${origin}/s/${s.code}`)
    toast('链接已复制', 'success')
  } catch {
    toast('复制失败，请手动复制', 'error')
  }
}

/** 短链失效（不可逆）：已分享出去的链接将无法再打开。 */
async function onInvalidate(s: ShareItem) {
  if (!(await confirmDialog('短链失效', `确定让 /s/${s.code} 失效？已分享出去的链接将无法再打开（不可恢复）。`))) return
  try {
    await postApi.invalidateShare(s.code)
    // 后端把 expires_at 置为过去：本地同步标记，避免再发失效请求
    s.expires_at = new Date(Date.now() - 1000).toISOString()
    toast('短链已失效', 'success')
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

onMounted(load)
</script>

<style scoped>
.page {
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
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--text-2);
  font-size: var(--fs-body);
  text-decoration: none;
}
.back-icon {
  width: 16px;
  height: 16px;
}
.page-title {
  margin: 0;
  font-size: var(--fs-page);
  font-weight: 700;
}
.state {
  padding: var(--sp-8) 0;
  text-align: center;
  color: var(--text-3);
}
.panel {
  margin-top: var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.share-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: var(--sp-3);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  transition: border-color 0.15s, box-shadow 0.2s;
}
.share-row:hover {
  border-color: var(--brand);
  box-shadow: var(--shadow-sm);
}
.share-main {
  min-width: 0;
  flex: 1;
}
.share-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
.share-target {
  font-size: var(--fs-body);
  font-weight: 600;
  color: var(--brand);
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.share-target-icon {
  width: 13px;
  height: 13px;
}
.share-time {
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.share-url {
  margin: var(--sp-1) 0 0;
  font-size: var(--fs-caption);
  color: var(--text-2);
  font-family: monospace;
  word-break: break-all;
}
.share-meta {
  margin: 2px 0 0;
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.share-ops {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  flex-shrink: 0;
}
.load-more {
  margin-top: var(--sp-2);
}
</style>
