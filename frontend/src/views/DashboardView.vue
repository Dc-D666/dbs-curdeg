<template>
  <main class="dash">
    <header class="page-header">
      <router-link to="/me" class="back">
        <ArrowLeftIcon class="back-icon" /> 返回
      </router-link>
      <h1 class="page-title">运营看板</h1>
    </header>

    <div v-if="loading" class="state">加载中…</div>

    <template v-else-if="stats">
      <!-- 统计卡片 -->
      <section class="cards">
        <div class="card"><span class="card-num">{{ stats.users_total }}</span><span class="card-label">用户</span></div>
        <div class="card"><span class="card-num">{{ stats.communities_total }}</span><span class="card-label">频道</span></div>
        <div class="card"><span class="card-num">{{ stats.posts_total }}</span><span class="card-label">帖子</span></div>
        <div class="card"><span class="card-num">{{ stats.comments_total }}</span><span class="card-label">评论</span></div>
        <div class="card"><span class="card-num">{{ stats.likes_total }}</span><span class="card-label">点赞</span></div>
        <div class="card hot"><span class="card-num">{{ stats.posts_today }}</span><span class="card-label">今日发帖</span></div>
      </section>

      <!-- 近 7 天发帖趋势 -->
      <section class="panel">
        <h3 class="panel-title">近 7 天发帖趋势</h3>
        <div v-if="trend.length" class="trend">
          <div v-for="t in trend" :key="t.date" class="trend-col">
            <span class="trend-val">{{ t.count }}</span>
            <div class="trend-bar" :style="{ height: barHeight(t.count) }" />
            <span class="trend-date">{{ t.date.slice(5) }}</span>
          </div>
        </div>
        <p v-else class="muted">近 7 天暂无发帖</p>
      </section>

      <!-- Top 频道 -->
      <section class="panel">
        <h3 class="panel-title">发帖最多的频道 TOP5</h3>
        <div v-if="stats.top_communities.length" class="top-list">
          <div v-for="(c, i) in stats.top_communities" :key="c.community_id" class="top-row">
            <span class="top-rank">{{ i + 1 }}</span>
            <router-link :to="`/c/${c.community_id}`" class="top-name">{{ c.name }}</router-link>
            <span class="top-posts">{{ c.posts }} 帖</span>
          </div>
        </div>
        <p v-else class="muted">暂无数据</p>
      </section>
    </template>
    <div v-else class="state">{{ error }}</div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ArrowLeftIcon } from 'tdesign-icons-vue-next'
import { request } from '@/api/http'

interface TrendPoint {
  date: string
  count: number
}
interface Stats {
  users_total: number
  communities_total: number
  posts_total: number
  comments_total: number
  likes_total: number
  users_today: number
  posts_today: number
  posts_trend_7d: TrendPoint[]
  top_communities: Array<{ community_id: number; name: string; posts: number }>
}

const loading = ref(true)
const error = ref('')
const stats = ref<Stats | null>(null)

const trend = computed(() => stats.value?.posts_trend_7d ?? [])

function barHeight(count: number): string {
  const max = Math.max(1, ...trend.value.map((t) => t.count))
  return `${Math.max(8, Math.round((count / max) * 120))}px`
}

onMounted(async () => {
  try {
    stats.value = await request<Stats>({ url: '/admin/stats' })
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
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
  margin: 0 0 var(--sp-3);
  font-size: var(--fs-body);
  font-weight: 600;
}
.trend {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  height: 160px;
}
.trend-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  height: 100%;
  justify-content: flex-end;
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
.top-list .top-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}
.top-list .top-row:last-child {
  border-bottom: none;
}
.top-rank {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--brand-weak);
  color: var(--brand);
  font-size: var(--fs-caption);
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.top-name {
  flex: 1;
  color: var(--text-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.top-posts {
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.muted {
  color: var(--text-3);
  font-size: var(--fs-caption);
}
</style>
