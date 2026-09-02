<template>
  <main class="ops">
    <header class="page-header">
      <router-link to="/" class="back">
        <ArrowLeftIcon class="back-icon" /> 返回主页
      </router-link>
      <h1 class="page-title">运营中心</h1>
      <t-button variant="outline" size="small" :loading="refreshing" @click="refresh">刷新</t-button>
    </header>

    <div v-if="loading" class="state"><t-skeleton :row="5" animation="gradient" /></div>

    <ErrorState v-else-if="loadError" :text="loadError" :retryable="!noPermission" @retry="init">
      <router-link :to="`/c/${cid}`" class="state-link">返回频道</router-link>
    </ErrorState>

    <template v-else-if="data">
      <p class="ops-note">{{ data.note }} · 统计基准日 {{ data.date }}</p>

      <!-- 三个可切换 bar：昨日数据 / 用户数据 / 内容数据 -->
      <t-tabs v-model="tab" class="ops-tabs">
        <!-- 昨日数据（含今日对比） -->
        <t-tab-panel value="yesterday" label="昨日数据">
          <section class="panel">
            <h2 class="panel-title">昨日（{{ data.date }}）</h2>
            <div class="cards">
              <div class="card"><span class="card-num">{{ data.yesterday.new_members }}</span><span class="card-label">新增成员</span></div>
              <div class="card"><span class="card-num">{{ data.yesterday.left_members }}</span><span class="card-label">退出成员</span></div>
              <div class="card"><span class="card-num">{{ data.yesterday.visits }}</span><span class="card-label">访问次数</span></div>
              <div class="card"><span class="card-num">{{ data.yesterday.visitors }}</span><span class="card-label">访问人数</span></div>
              <div class="card"><span class="card-num">{{ data.yesterday.posts }}</span><span class="card-label">新增帖子</span></div>
              <div class="card"><span class="card-num">{{ data.yesterday.views }}</span><span class="card-label">帖子浏览量</span></div>
              <div class="card"><span class="card-num">{{ data.yesterday.post_authors }}</span><span class="card-label">发帖人数</span></div>
              <div class="card"><span class="card-num">{{ data.yesterday.new_likes }}</span><span class="card-label">新增点赞</span></div>
              <div class="card"><span class="card-num">{{ data.yesterday.new_comments }}</span><span class="card-label">新增评论</span></div>
            </div>
          </section>

          <section class="panel">
            <h2 class="panel-title">今日（对比参考）</h2>
            <div class="cards cards-3">
              <div class="card"><span class="card-num">{{ data.today.new_members }}</span><span class="card-label">今日新增成员</span></div>
              <div class="card"><span class="card-num">{{ data.today.visits }}</span><span class="card-label">今日访问</span></div>
              <div class="card"><span class="card-num">{{ data.today.posts }}</span><span class="card-label">今日发帖</span></div>
            </div>
          </section>
        </t-tab-panel>

        <!-- 用户数据 -->
        <t-tab-panel value="user" label="用户数据">
          <section class="panel">
            <div class="period-toolbar">
              <t-radio-group v-model="userPeriod" variant="default-filled" size="small">
                <t-radio-button value="yesterday">昨日</t-radio-button>
                <t-radio-button value="d7">近 7 天</t-radio-button>
                <t-radio-button value="d30">近 30 天</t-radio-button>
              </t-radio-group>
              <div class="cum-stats">
                <span class="cum-stat"><b>{{ data.user.total_members }}</b> 成员</span>
                <span class="cum-stat"><b>{{ data.user.total_posts }}</b> 帖子</span>
              </div>
            </div>

            <div class="cards cards-4">
              <div class="card"><span class="card-num">{{ userPeriodData.new_members }}</span><span class="card-label">新增成员</span></div>
              <div class="card"><span class="card-num">{{ userPeriodData.visits }}</span><span class="card-label">访问次数</span></div>
              <div class="card"><span class="card-num">{{ userPeriodData.visitors }}</span><span class="card-label">访问人数</span></div>
              <div class="card"><span class="card-num">{{ userPeriodData.active_members }}</span><span class="card-label">活跃成员</span></div>
              <div class="card"><span class="card-num">{{ userPeriodData.active_rate }}%</span><span class="card-label">成员活跃率</span></div>
            </div>

            <!-- 7/30 天折线图（tdesign sparkline） -->
            <template v-if="userPeriod !== 'yesterday' && userSeries">
              <h3 class="sub-title">新增成员趋势</h3>
              <div class="chart-box"><Sparkline :data="userSeries.new_members" :height="120" /></div>
              <h3 class="sub-title">访问趋势</h3>
              <div class="chart-box"><Sparkline :data="userSeries.visits" :height="120" /></div>
              <h3 class="sub-title">活跃成员趋势</h3>
              <div class="chart-box"><Sparkline :data="userSeries.active_members" :height="120" /></div>
            </template>

            <h3 class="sub-title">成员排名（活跃度：发帖 + 评论）</h3>
            <div class="rank-list">
              <div v-for="(m, i) in data.user.member_rank" :key="m.user_id" class="rank-row">
                <span class="rank-no" :class="{ top: i < 3 }">{{ i + 1 }}</span>
                <span class="rank-name">{{ m.nickname || `#${m.user_id}` }}</span>
                <span class="rank-tag" v-if="m.member_type === 0">频道主</span>
                <span class="rank-tag" v-else-if="m.member_type === 1">管理员</span>
                <span class="rank-meta">Lv.{{ m.level }} · 发帖 {{ m.posts }} · 评论 {{ m.comments }}</span>
              </div>
              <p v-if="data.user.member_rank.length === 0" class="muted">暂无成员数据</p>
            </div>
          </section>
        </t-tab-panel>

        <!-- 内容数据 -->
        <t-tab-panel value="content" label="内容数据">
          <section class="panel">
            <div class="period-toolbar">
              <t-radio-group v-model="contentPeriod" variant="default-filled" size="small">
                <t-radio-button value="yesterday">昨日</t-radio-button>
                <t-radio-button value="d7">近 7 天</t-radio-button>
                <t-radio-button value="d30">近 30 天</t-radio-button>
              </t-radio-group>
            </div>

            <div class="cards cards-4">
              <div class="card"><span class="card-num">{{ contentPeriodData.posts }}</span><span class="card-label">发帖</span></div>
              <div class="card"><span class="card-num">{{ contentPeriodData.views }}</span><span class="card-label">浏览量</span></div>
              <div class="card"><span class="card-num">{{ contentPeriodData.likes }}</span><span class="card-label">点赞</span></div>
              <div class="card"><span class="card-num">{{ contentPeriodData.comments }}</span><span class="card-label">评论</span></div>
            </div>

            <!-- 7/30 天折线图 -->
            <template v-if="contentPeriod !== 'yesterday' && contentSeries">
              <h3 class="sub-title">发帖趋势</h3>
              <div class="chart-box"><Sparkline :data="contentSeries.posts" :height="120" /></div>
              <h3 class="sub-title">浏览量趋势</h3>
              <div class="chart-box"><Sparkline :data="contentSeries.views" :height="120" /></div>
              <h3 class="sub-title">点赞/评论趋势</h3>
              <div class="chart-box"><Sparkline :data="contentSeries.likes" :height="120" /><Sparkline :data="contentSeries.comments" :height="120" /></div>
            </template>

            <h3 class="sub-title">帖子排名（周期内活跃度 Top10）</h3>
            <div class="rank-list">
              <router-link v-for="(p, i) in contentPeriodData.post_rank" :key="p.id" :to="`/p/${p.id}`" class="rank-row rank-link">
                <span class="rank-no" :class="{ top: i < 3 }">{{ i + 1 }}</span>
                <span class="rank-name post-title">{{ p.title }}</span>
                <span class="rank-meta">热度 {{ p.heat }} · {{ p.view_count }} 浏览 · {{ p.like_count }} 赞 · {{ p.comment_count }} 评</span>
              </router-link>
              <p v-if="contentPeriodData.post_rank.length === 0" class="muted">该周期暂无帖子</p>
            </div>

            <!-- 按板块（仅昨日口径） -->
            <h3 class="sub-title">板块概览（昨日）</h3>
            <div class="tbl">
              <div class="tbl-head tbl-row">
                <span>板块</span><span>昨日帖子</span><span>累计浏览量</span><span>昨日删除</span>
              </div>
              <div v-for="b in data.content.boards" :key="b.board_id" class="tbl-row">
                <span class="tbl-name">{{ b.board_name }}</span>
                <span>{{ b.yesterday_posts }}</span>
                <span>{{ b.views }}</span>
                <span class="tbl-deleted">{{ b.deleted_posts }}</span>
              </div>
              <p v-if="data.content.boards.length === 0" class="muted">暂无板块</p>
            </div>
          </section>
        </t-tab-panel>
      </t-tabs>
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeftIcon } from 'tdesign-icons-vue-next'
import { communityApi, type OpsCenterData } from '@/api/community'
import { ApiError } from '@/api/http'
import ErrorState from '@/components/ErrorState.vue'
import Sparkline from '@/components/Sparkline.vue'
import { loadErrorMessage } from '@/utils/error'

defineOptions({ name: 'OpsCenterView' })

const route = useRoute()
const cid = computed(() => Number(route.params.id))

const data = ref<OpsCenterData | null>(null)
const loading = ref(true)
const refreshing = ref(false)
const loadError = ref('')
const noPermission = ref(false)
const communityName = ref('')

// 三 bar 切换
const tab = ref<'yesterday' | 'user' | 'content'>('yesterday')
// 用户/内容数据周期选择
const userPeriod = ref<'yesterday' | 'd7' | 'd30'>('yesterday')
const contentPeriod = ref<'yesterday' | 'd7' | 'd30'>('yesterday')

const userPeriodData = computed(() => data.value?.user[userPeriod.value] ?? { new_members: 0, visits: 0, visitors: 0, active_members: 0, active_rate: 0 })
const userSeries = computed(() => (userPeriod.value !== 'yesterday' ? (data.value?.user[userPeriod.value] as { series?: OpsCenterData['user']['d7']['series'] })?.series : undefined))
const contentPeriodData = computed(() => data.value?.content[contentPeriod.value] ?? { posts: 0, views: 0, likes: 0, comments: 0, post_rank: [] })
const contentSeries = computed(() => (contentPeriod.value !== 'yesterday' ? (data.value?.content[contentPeriod.value] as { series?: OpsCenterData['content']['d7']['series'] })?.series : undefined))

async function fetchOps() {
  const [ops, community] = await Promise.all([
    communityApi.opsCenter(cid.value),
    communityApi.get(cid.value).catch(() => null),
  ])
  data.value = ops
  communityName.value = community?.name || ''
}

/** 首次加载：骨架屏 + 错误态。 */
async function init() {
  loading.value = true
  loadError.value = ''
  noPermission.value = false
  data.value = null
  try {
    await fetchOps()
  } catch (e) {
    const r = loadErrorMessage(e, '运营中心', '需要频道主或成员管理权限')
    loadError.value = r.text
    noPermission.value = e instanceof ApiError && e.status === 403
  } finally {
    loading.value = false
  }
}

/** 手动刷新：静默更新，不清空已渲染数据，失败仅提示。 */
async function refresh() {
  if (refreshing.value) return
  refreshing.value = true
  try {
    await fetchOps()
  } catch (e) {
    // 静默失败：保留旧数据，不打断查看
    loadErrorMessage(e, '运营中心')
  } finally {
    refreshing.value = false
  }
}

// 实时刷新：页面停留时每 30s 静默拉一次「今日/昨日」等数据；
// 切回标签页时立即刷新一次，让运营中心接近实时。
let timer: ReturnType<typeof setInterval> | null = null
function onVisibility() {
  if (document.visibilityState === 'visible') refresh()
}

onMounted(() => {
  init()
  timer = setInterval(refresh, 30000)
  document.addEventListener('visibilitychange', onVisibility)
})
onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
  document.removeEventListener('visibilitychange', onVisibility)
})
</script>

<style scoped>
.ops {
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
  border: none;
  background: none;
  padding: 6px 4px;
  cursor: pointer;
  text-decoration: none;
}
.back:hover {
  color: var(--brand);
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
.ops-note {
  margin: var(--sp-3) 0 0;
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.ops-tabs {
  margin-top: var(--sp-2);
}
.panel {
  margin-top: var(--sp-4);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: var(--sp-4);
  box-shadow: var(--shadow-sm);
}
.panel-title {
  margin: 0 0 var(--sp-3);
  font-size: var(--fs-body);
  font-weight: 600;
}
.sub-title {
  margin: var(--sp-4) 0 var(--sp-2);
  font-size: var(--fs-body);
  font-weight: 600;
}
.cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--sp-3);
}
.cards-3 {
  grid-template-columns: repeat(3, 1fr);
}
.cards-4 {
  grid-template-columns: repeat(5, 1fr);
}
.card {
  background: var(--surface);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-card);
  padding: var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.card-num {
  font-size: 20px;
  font-weight: 700;
}
.card-label {
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.period-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  flex-wrap: wrap;
  margin-bottom: var(--sp-4);
}
.cum-stats {
  display: flex;
  gap: var(--sp-4);
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.cum-stat b {
  color: var(--text-1);
}
.chart-box {
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-card);
  padding: var(--sp-3);
  margin-bottom: var(--sp-3);
  background: var(--surface);
}
.rank-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: var(--sp-1);
}
.rank-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-2);
  border-bottom: 1px dashed var(--border);
}
.rank-row:last-child {
  border-bottom: none;
}
.rank-link {
  text-decoration: none;
  color: inherit;
}
.rank-link:hover {
  background: var(--surface);
}
.rank-no {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--surface);
  border: 1px solid var(--border);
  font-size: var(--fs-caption);
  color: var(--text-3);
  flex-shrink: 0;
}
.rank-no.top {
  background: var(--brand);
  border-color: var(--brand);
  color: #fff;
}
.rank-name {
  font-weight: 600;
  flex-shrink: 0;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rank-tag {
  font-size: 10px;
  color: var(--brand);
  background: var(--brand-weak);
  border-radius: 4px;
  padding: 0 6px;
  line-height: 1.6;
  flex-shrink: 0;
}
.rank-meta {
  font-size: var(--fs-caption);
  color: var(--text-3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.post-title {
  flex: 1;
  min-width: 0;
  max-width: none;
}
.muted {
  color: var(--text-3);
  font-size: var(--fs-caption);
}
.tbl {
  display: flex;
  flex-direction: column;
}
.tbl-head {
  font-weight: 600;
  color: var(--text-3);
  font-size: var(--fs-caption);
}
.tbl-row {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) repeat(3, minmax(56px, 1fr));
  gap: var(--sp-2);
  align-items: center;
  padding: var(--sp-2) 0;
  border-bottom: 1px dashed var(--border);
  text-align: center;
  font-size: var(--fs-caption);
}
.tbl-head.tbl-row {
  border-bottom: 1px solid var(--border);
}
.tbl-name {
  font-weight: 600;
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tbl-deleted {
  color: var(--danger);
}
@media (max-width: 720px) {
  .cards,
  .cards-3,
  .cards-4 {
    grid-template-columns: repeat(2, 1fr);
  }
  .tbl-row {
    grid-template-columns: minmax(0, 1.2fr) repeat(3, minmax(48px, 1fr));
  }
}
</style>
