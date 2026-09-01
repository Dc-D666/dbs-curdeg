<template>
  <main class="page">
    <header class="page-header">
      <router-link to="/me" class="back">
        <ArrowLeftIcon class="back-icon" /> 我的
      </router-link>
      <h1 class="page-title">审核记录</h1>
    </header>

    <ErrorState v-if="loadError" :text="loadError" @retry="load" />
    <template v-else>
      <div v-if="loading && items.length === 0" class="state"><t-skeleton :row="3" animation="gradient" /></div>
      <EmptyState v-else-if="items.length === 0" text="你的内容都顺利通过了审核" />

      <div v-else class="panel">
        <div v-for="r in items" :key="r.id" class="review-row">
          <div class="review-main">
            <div class="review-head">
              <t-tag size="small" variant="light" :theme="statusTheme(r.status)">{{ statusLabel(r.status) }}</t-tag>
              <span class="review-target">{{ targetLabel(r) }}</span>
              <span class="review-time">{{ timeAgo(r.created_at) }}</span>
            </div>
            <p v-if="r.violation_type" class="review-violation">
              违规类型：{{ r.violation_type }}<template v-if="r.violation_detail">（{{ r.violation_detail }}）</template>
            </p>
            <p v-if="r.result" class="review-result">{{ r.result }}</p>
            <p v-if="r.appeal_at" class="review-appeal">已于 {{ r.appeal_at }} 申诉</p>
          </div>
          <!-- 驳回且未申诉过 → 可申诉（AI 复审：通过/驳回/转人工三态） -->
          <t-button
            v-if="r.status === 2 && !r.appeal_at"
            variant="outline"
            size="small"
            :loading="appealingId === r.id"
            @click="onAppeal(r)"
          >申诉复审</t-button>
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
import { ArrowLeftIcon } from 'tdesign-icons-vue-next'
import { postApi, type ReviewItem } from '@/api/post'
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import { timeAgo } from '@/utils/time'
import { confirmDialog } from '@/utils/confirm'
import { errMessage } from '@/utils/error'
import { toast } from '@/utils/toast'

const items = ref<ReviewItem[]>([])
const page = ref(0)
const total = ref(0)
const hasMore = ref(false)
const loading = ref(false)
const loadError = ref('')
const appealingId = ref<number | null>(null)

function statusLabel(s: number): string {
  return ['待审核', '已通过', '已驳回', '转人工复审'][s] ?? '未知'
}
function statusTheme(s: number): string {
  // tdesign tag theme：待审 warning / 通过 success / 驳回 danger / 转人工 primary
  return (['warning', 'success', 'danger', 'primary'] as const)[s] ?? 'default'
}
function targetLabel(r: ReviewItem): string {
  return `${r.content_type === 1 ? '帖子' : '评论'} #${r.content_id}`
}

async function loadPage(p: number) {
  loading.value = true
  try {
    const data = await postApi.myReviews(p, 20)
    items.value = p === 1 ? data.items : [...items.value, ...data.items]
    page.value = p
    total.value = data.total
    hasMore.value = items.value.length < data.total
  } catch (e) {
    loadError.value = errMessage(e, '加载审核记录失败')
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

/** 申诉被 AI 驳回的内容 → AI 复审（通过/驳回/转人工三态），结果刷新到列表。 */
async function onAppeal(r: ReviewItem) {
  if (!(await confirmDialog('申诉复审', `确定对${targetLabel(r)}的驳回结果发起申诉？将提交 AI 复审，通过后内容恢复可见。`))) return
  appealingId.value = r.id
  try {
    const updated = await postApi.appealReview(r.id)
    const idx = items.value.findIndex((x) => x.id === r.id)
    if (idx >= 0) items.value[idx] = updated
    toast('申诉已受理，复审完成', 'success')
  } catch (e) {
    toast(e instanceof Error ? e.message : '申诉失败', 'error')
  } finally {
    appealingId.value = null
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
.review-row {
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
.review-row:hover {
  border-color: var(--brand);
  box-shadow: var(--shadow-sm);
}
.review-main {
  min-width: 0;
  flex: 1;
}
.review-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
.review-target {
  font-size: var(--fs-body);
  font-weight: 600;
  color: var(--text-1);
}
.review-time {
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.review-violation,
.review-result,
.review-appeal {
  margin: var(--sp-1) 0 0;
  font-size: var(--fs-caption);
  color: var(--text-2);
  word-break: break-word;
}
.review-appeal {
  color: var(--text-3);
}
.load-more {
  margin-top: var(--sp-2);
}
</style>
