<template>
  <main class="dash">
    <header class="page-header">
      <router-link to="/me" class="back">
        <ArrowLeftIcon class="back-icon" /> 返回
      </router-link>
      <h1 class="page-title">运营管理</h1>
    </header>

    <t-tabs v-model="tab" class="tabs">
      <!-- 总览 -->
      <t-tab-panel value="overview" label="总览">
        <div v-if="loading" class="state">加载中…</div>
        <template v-else-if="stats">
          <section class="cards">
            <div class="card"><span class="card-num">{{ stats.users_total }}</span><span class="card-label">用户</span></div>
            <div class="card"><span class="card-num">{{ stats.communities_total }}</span><span class="card-label">频道</span></div>
            <div class="card"><span class="card-num">{{ stats.posts_total }}</span><span class="card-label">帖子</span></div>
            <div class="card"><span class="card-num">{{ stats.comments_total }}</span><span class="card-label">评论</span></div>
            <div class="card"><span class="card-num">{{ stats.likes_total }}</span><span class="card-label">点赞</span></div>
            <div class="card hot"><span class="card-num">{{ stats.posts_today }}</span><span class="card-label">今日发帖</span></div>
          </section>

          <section class="panel">
            <div class="panel-title-row">
              <h3 class="panel-title">近 7 天发帖趋势</h3>
              <!-- 峰值参考：纯 CSS 柱图无 y 轴，至少给出刻度锚点（#57） -->
              <div class="trend-ops">
                <span v-if="trendMax > 0" class="trend-max">峰值 {{ trendMax }} 帖/天</span>
                <t-button variant="outline" size="small" :loading="exporting" @click="exportTrend">{{ exporting ? '导出中…' : '导出 CSV' }}</t-button>
              </div>
            </div>
            <div v-if="trend.length" class="trend" role="img" :aria-label="`近7天发帖趋势，峰值${trendMax}帖`">
              <div
                v-for="t in trend"
                :key="t.date"
                class="trend-col"
                :title="`${t.date}：${t.count} 帖`"
              >
                <span class="trend-val">{{ t.count }}</span>
                <div class="trend-bar" :style="{ height: barHeight(t.count) }" />
                <span class="trend-date">{{ t.date.slice(5) }}</span>
              </div>
            </div>
            <p v-else class="muted">近 7 天暂无发帖</p>
          </section>
        </template>
        <!-- 总览加载失败：不能只给一行错误文本，必须可重试 -->
        <ErrorState v-else :text="error" @retry="retryOverview" />
      </t-tab-panel>

      <!-- 举报处理 -->
      <t-tab-panel value="reports" label="举报处理">
        <div class="panel">
          <div class="reports-toolbar">
            <span v-if="reportsPage > 0" class="reports-count">共 {{ reportsTotal }} 条举报（已加载 {{ reports.length }} 条）</span>
            <span v-else-if="reportsLoading" class="reports-count">加载中…</span>
          </div>
          <div class="report-row" v-for="r in reports" :key="r.id">
            <div class="report-main">
              <span class="report-type">{{ reportTypeName(r.target_type) }} #{{ r.target_id }}</span>
              <span class="report-reason">{{ r.reason_type }}</span>
              <span class="report-status">{{ reportStatusName(r.status) }}</span>
            </div>
            <p v-if="r.detail" class="report-detail">{{ r.detail }}</p>
            <p class="report-meta">举报人：{{ r.reporter_nickname }} · {{ formatTime(r.created_at) }}</p>
            <div class="report-ops">
              <t-button v-if="r.status === 0" variant="outline" size="small" @click="handleReport(r, 'processing')">受理</t-button>
              <t-button variant="outline" size="small" @click="handleReport(r, 'done')">办结</t-button>
              <t-button variant="outline" size="small" theme="danger" @click="handleReport(r, 'rejected')">驳回</t-button>
            </div>
          </div>
          <div v-if="reportsLoading && reports.length === 0" class="state">加载中…</div>
          <t-empty v-else-if="reports.length === 0" description="暂无举报" />
          <!-- 举报不再只拉前 50 条静默截断：分页 + 总数可见 -->
          <t-button
            v-if="reports.length < reportsTotal"
            variant="outline"
            block
            class="load-more"
            :loading="reportsLoading"
            @click="loadMoreReports()"
          >{{ reportsLoading ? '加载中…' : `加载更多（${reports.length}/${reportsTotal}）` }}</t-button>
        </div>
      </t-tab-panel>

      <!-- 敏感词库 -->
      <t-tab-panel value="words" label="敏感词库">
        <div class="panel">
          <div class="word-form">
            <t-input v-model="wordForm.word" class="word-input" placeholder="敏感词" maxlength="64" clearable />
            <t-select v-model="wordForm.category" class="word-cat">
              <t-option value="涉政" label="涉政" />
              <t-option value="涉黄" label="涉黄" />
              <t-option value="广告" label="广告" />
              <t-option value="诈骗" label="诈骗" />
              <t-option value="辱骂" label="辱骂" />
              <t-option value="其他" label="其他" />
            </t-select>
            <t-button theme="primary" size="small" :disabled="!wordForm.word" @click="addWord">添加</t-button>
          </div>
          <div class="word-row" v-for="w in words" :key="w.id">
            <span class="word-text">{{ w.word }}</span>
            <t-tag size="small" variant="light">{{ w.category }}</t-tag>
            <t-switch :value="w.enabled" size="small" @change="(v: boolean) => toggleWord(w, v)" />
            <t-button variant="text" size="small" theme="danger" @click="removeWord(w)">删除</t-button>
          </div>
          <t-empty v-if="words.length === 0" description="暂无敏感词" />
        </div>
      </t-tab-panel>

      <!-- 系统配置 -->
      <t-tab-panel value="configs" label="系统配置">
        <div class="panel">
          <div class="cfg-row" v-for="c in configs" :key="c.key">
            <span class="cfg-key">{{ c.key }}</span>
            <span class="cfg-desc">{{ c.description }}</span>
            <t-input v-model="cfgForm[c.key]" size="small" class="cfg-input" />
            <t-button variant="outline" size="small" @click="saveConfig(c.key)">保存</t-button>
          </div>
        </div>
      </t-tab-panel>

      <!-- AI 配置 -->
      <t-tab-panel value="ai" label="AI 配置">
        <div class="panel">
          <div class="ai-row" v-for="c in aiConfigs" :key="c.feature">
            <span class="ai-feature">{{ featureLabel(c.feature) }}</span>
            <t-switch :value="c.enabled" size="small" @change="(v: boolean) => toggleAi(c.feature, v)" />
            <span class="ai-model">{{ c.model || '默认模型' }}</span>
          </div>
          <p class="muted">AI 功能开关与模型展示；详细配置请在数据库中维护。</p>
        </div>
      </t-tab-panel>
    </t-tabs>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ArrowLeftIcon } from 'tdesign-icons-vue-next'
import { request } from '@/api/http'
import { adminApi, type ReportItem, type SensitiveWordItem } from '@/api/admin'
import { toast } from '@/utils/toast'
import { formatTime } from '@/utils/time'
import { confirmDialog } from '@/utils/confirm'
import ErrorState from '@/components/ErrorState.vue'

const tab = ref<'overview' | 'reports' | 'words' | 'configs' | 'ai'>('overview')
const loading = ref(true)
const error = ref('')
const stats = ref<Record<string, any> | null>(null)
const trend = ref<Array<{ date: string; count: number }>>([])

// 举报：分页拉取（不再只拉前 50 条静默截断）
const reports = ref<ReportItem[]>([])
const reportsPage = ref(0)
const reportsTotal = ref(0)
const reportsLoading = ref(false)
// 敏感词
const words = ref<SensitiveWordItem[]>([])
const wordForm = reactive({ word: '', category: '其他' })
// 配置
const configs = ref<Array<{ key: string; value: string; description: string }>>([])
const cfgForm = reactive<Record<string, string>>({})
// AI 配置
const aiConfigs = ref<Array<{ feature: string; enabled: boolean; model: string }>>([])

function barHeight(count: number): string {
  const max = Math.max(1, ...trend.value.map((t) => t.count))
  return `${Math.max(8, Math.round((count / max) * 120))}px`
}

/** 趋势峰值（y 轴锚点，#57） */
const trendMax = computed(() => Math.max(0, ...trend.value.map((t) => t.count)))

// CSV 导出中状态：避免慢网络下重复点击（#57）
const exporting = ref(false)

function reportTypeName(t: number): string {
  return t === 1 ? '帖子' : t === 2 ? '评论' : t === 3 ? '用户' : t === 4 ? '频道' : '内容'
}
function reportStatusName(s: number): string {
  return s === 0 ? '待处理' : s === 1 ? '处理中' : s === 2 ? '已办结' : s === 3 ? '驳回' : '未知'
}
function featureLabel(f: string): string {
  const map: Record<string, string> = { assist: 'AI 帮写', review: '内容审核', rag: '问答机器人', summary: 'AI 摘要', draw: 'AI 绘画' }
  return map[f] || f
}

async function loadOverview() {
  try {
    stats.value = await request<Record<string, any>>({ url: '/admin/stats' })
    trend.value = stats.value?.posts_trend_7d ?? []
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

/** 总览失败重试：回到加载态重新拉取。 */
async function retryOverview() {
  loading.value = true
  error.value = ''
  stats.value = null
  await loadOverview()
}

async function loadReports(page: number, append = false) {
  if (reportsLoading.value) return
  reportsLoading.value = true
  try {
    const data = await adminApi.reports(undefined, page, 20)
    reports.value = append ? [...reports.value, ...data.items] : data.items
    reportsPage.value = page
    reportsTotal.value = data.total
  } catch (e) {
    toast(e instanceof Error ? e.message : '加载失败', 'error')
  } finally {
    reportsLoading.value = false
  }
}

function loadMoreReports() {
  return loadReports(reportsPage.value + 1, true)
}

async function loadWords() {
  try {
    words.value = (await adminApi.sensitiveWords(undefined, 1, 50)).items
  } catch (e) {
    toast(e instanceof Error ? e.message : '加载失败', 'error')
  }
}

async function loadConfigs() {
  try {
    configs.value = await adminApi.configs()
    for (const c of configs.value) cfgForm[c.key] = c.value
  } catch (e) {
    toast(e instanceof Error ? e.message : '加载失败', 'error')
  }
}

async function loadAiConfigs() {
  try {
    aiConfigs.value = await adminApi.aiConfigs()
  } catch (e) {
    toast(e instanceof Error ? e.message : '加载失败', 'error')
  }
}

/** 举报处理：办结/驳回会改变举报状态且影响申请人反馈，先二次确认（#56）。 */
async function handleReport(r: ReportItem, action: 'processing' | 'done' | 'rejected') {
  if (action === 'done') {
    if (!(await confirmDialog('办结举报', `确定办结该举报（${reportTypeName(r.target_type)} #${r.target_id}）？办结后不可再受理。`))) return
  } else if (action === 'rejected') {
    if (!(await confirmDialog('驳回举报', `确定驳回该举报（${reportTypeName(r.target_type)} #${r.target_id}）？驳回后将不再跟进。`))) return
  }
  try {
    await adminApi.handleReport(r.id, action)
    toast('已处理')
    await loadReports(1)
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

async function addWord() {
  if (!wordForm.word.trim()) return
  try {
    await adminApi.addSensitiveWord(wordForm.word.trim(), wordForm.category)
    wordForm.word = ''
    await loadWords()
    toast('已添加敏感词')
  } catch (e) {
    toast(e instanceof Error ? e.message : '添加失败', 'error')
  }
}

async function toggleWord(w: SensitiveWordItem, enabled: boolean) {
  try {
    await adminApi.setSensitiveWordEnabled(w.id, enabled)
    w.enabled = enabled
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

/** 删除敏感词：立即从审核词库移除，先二次确认（#56）。 */
async function removeWord(w: SensitiveWordItem) {
  if (!(await confirmDialog('删除敏感词', `确定删除敏感词「${w.word}」（${w.category}）？删除后相关内容将不再被拦截。`))) return
  try {
    await adminApi.deleteSensitiveWord(w.id)
    words.value = words.value.filter((x) => x.id !== w.id)
    toast('已删除')
  } catch (e) {
    toast(e instanceof Error ? e.message : '删除失败', 'error')
  }
}

async function saveConfig(key: string) {
  try {
    await adminApi.setConfig(key, cfgForm[key] ?? '')
    toast('配置已保存')
  } catch (e) {
    toast(e instanceof Error ? e.message : '保存失败', 'error')
  }
}

async function toggleAi(feature: string, enabled: boolean) {
  try {
    await adminApi.updateAiConfig(feature, { enabled })
    const c = aiConfigs.value.find((x) => x.feature === feature)
    if (c) c.enabled = enabled
    toast('配置已保存')
  } catch (e) {
    toast(e instanceof Error ? e.message : '保存失败', 'error')
  }
}

async function exportTrend() {
  if (exporting.value) return
  exporting.value = true
  try {
    const res = await adminApi.exportDashboard(7)
    if (!res.ok) return
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'stats_report.csv'
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    toast('导出失败', 'error')
  } finally {
    exporting.value = false
  }
}

onMounted(async () => {
  await loadOverview()
  loadReports(1)
  loadWords()
  loadConfigs()
  loadAiConfigs()
})
</script>

<style scoped>
.dash {
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
.state {
  padding: 48px 0;
  text-align: center;
  color: var(--text-3);
}
.cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--sp-3);
  margin-top: var(--sp-4);
}
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: var(--sp-4);
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.card.hot {
  background: var(--brand);
  color: #fff;
  border-color: var(--brand);
}
.card-num {
  font-size: 22px;
  font-weight: 700;
}
.card-label {
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.card.hot .card-label {
  color: rgba(255, 255, 255, 0.8);
}
.panel {
  margin-top: var(--sp-4);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: var(--sp-4);
}
.panel-title {
  margin: 0;
  font-size: var(--fs-body);
  font-weight: 600;
}
.panel-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-3);
}
.trend {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  height: 160px;
  /* x 轴基线（#57）：纯 CSS 柱图至少有坐标锚点 */
  border-bottom: 1px solid var(--border);
  padding-bottom: 2px;
}
.trend-ops {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}
.trend-max {
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.trend-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  height: 100%;
  justify-content: flex-end;
  cursor: default;
  border-radius: 4px;
}
/* 悬停高亮（#57）：配合 title 提示当天的具体数据 */
.trend-col:hover .trend-bar {
  background: var(--brand-hover);
}
.trend-col:hover .trend-date {
  color: var(--text-2);
  font-weight: 600;
}
.trend-val {
  font-size: var(--fs-caption);
  color: var(--text-2);
}
.trend-bar {
  width: 100%;
  max-width: 32px;
  background: var(--brand);
  border-radius: 4px 4px 0 0;
  min-height: 8px;
}
.trend-date {
  font-size: 10px;
  color: var(--text-3);
}
.muted {
  color: var(--text-3);
  font-size: var(--fs-caption);
}
.reports-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-2);
}
.reports-count {
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.load-more {
  margin-top: var(--sp-2);
}
.report-row {
  padding: var(--sp-3) 0;
  border-bottom: 1px dashed var(--border);
}
.report-row:last-child {
  border-bottom: none;
}
.report-main {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
.report-type {
  font-weight: 600;
}
.report-reason {
  color: var(--brand);
  background: var(--brand-weak);
  border-radius: 4px;
  padding: 0 6px;
  font-size: var(--fs-caption);
}
.report-status {
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.report-detail {
  margin: var(--sp-1) 0 0;
  font-size: var(--fs-caption);
  color: var(--text-2);
}
.report-meta {
  margin: 4px 0 0;
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.report-ops {
  margin-top: var(--sp-2);
  display: flex;
  gap: var(--sp-2);
}
.word-form {
  display: flex;
  gap: var(--sp-2);
  margin-bottom: var(--sp-3);
  flex-wrap: wrap;
}
.word-input {
  flex: 1;
  min-width: 140px;
}
.word-cat {
  width: 100px;
}
.word-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) 0;
  border-bottom: 1px dashed var(--border);
}
.word-row:last-child {
  border-bottom: none;
}
.word-text {
  flex: 1;
  font-weight: 600;
}
.cfg-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) 0;
  border-bottom: 1px dashed var(--border);
  flex-wrap: wrap;
}
.cfg-key {
  width: 150px;
  font-family: Consolas, monospace;
  font-size: var(--fs-caption);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cfg-desc {
  flex: 1;
  min-width: 100px;
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.cfg-input {
  width: 180px;
}
.ai-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-2) 0;
  border-bottom: 1px dashed var(--border);
}
.ai-row:last-child {
  border-bottom: none;
}
.ai-feature {
  flex: 1;
  font-weight: 600;
}
.ai-model {
  font-size: var(--fs-caption);
  color: var(--text-3);
}
</style>
