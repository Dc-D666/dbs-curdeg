<template>
  <main class="discover">
    <header class="page-header">
      <h1 class="page-title">发现</h1>
      <t-button theme="primary" size="small" @click="showCreate = true">创建频道</t-button>
    </header>

    <!-- 全站最热门频道 Top10 -->
    <section v-if="hotChannels.length" class="hot-channels">
      <router-link
        v-for="c in hotChannels"
        :key="c.id"
        :to="`/c/${c.id}`"
        class="hot-channel"
        :title="c.name"
      >
        <UserAvatar :src="c.avatar_url" :name="c.name" :size="40" />
        <span class="hot-channel-name">{{ c.name }}</span>
        <span class="hot-channel-meta">{{ c.member_count }} 人</span>
      </router-link>
    </section>

    <!-- 搜索 -->
    <section class="search-box">
      <t-input
        v-model="searchQ"
        class="search-input"
        placeholder="搜索帖子（支持中文关键词）"
        maxlength="64"
        clearable
        @enter="doSearch()"
      />
      <t-button theme="primary" :disabled="!searchQ || searchLoading" :loading="searchLoading" @click="doSearch()">
        {{ searchLoading ? '搜索中…' : '搜索' }}
      </t-button>
    </section>

    <!-- 热门搜索词 -->
    <div v-if="!searching && hotKeywords.length" class="hot-words">
      <span class="hot-label">热门搜索：</span>
      <button v-for="h in hotKeywords" :key="h.keyword" class="hot-word" @click="searchQ = h.keyword; doSearch()">
        {{ h.keyword }}
      </button>
    </div>

    <!-- 搜索结果 -->
    <div v-if="searching" class="search-results">
      <div class="search-meta">
        <span v-if="searchTotal" class="search-count">“{{ lastQ }}” 共 {{ searchTotal }} 条结果</span>
        <t-button variant="text" size="small" @click="clearSearch()">返回帖子流</t-button>
      </div>
      <div v-if="searchLoading" class="state">搜索中…</div>
      <EmptyState v-else-if="searchResults.length === 0" text="没有找到相关帖子" />
      <div v-else class="list">
        <article v-for="p in searchResults" :key="p.id" class="card" @click="goPost(p.id)">
          <div class="card-head">
            <h3 class="card-name search-title" v-html="p.highlight_title || p.title"></h3>
            <span v-if="p.is_top" class="tag tag-top">置顶</span>
            <span v-if="p.is_essence" class="tag tag-essence">精华</span>
          </div>
          <p class="card-profile search-snippet" v-html="p.snippet"></p>
          <div class="card-meta">
            <span>{{ p.community_name }}</span>
            <span>{{ p.board_name }}</span>
            <span>{{ p.author_nickname }}</span>
            <span>{{ p.like_count }} 赞 · {{ p.comment_count }} 评</span>
            <span class="search-time">{{ timeAgo(p.created_at) }}</span>
          </div>
        </article>
      </div>
      <t-button
        v-if="hasMoreSearchResults"
        variant="outline"
        block
        class="load-more"
        :loading="searchLoading"
        @click="loadMoreSearch()"
      >{{ searchLoading ? '搜索中…' : '加载更多结果' }}</t-button>
    </div>

    <!-- 双 Tab 帖子流：已加入的最新 / 全站热门 -->
    <div v-else>
      <t-tabs v-model="activeTab" class="feed-tabs" lazy>
        <t-tab-panel value="mine" label="已加入的最新">
          <template v-if="tokenStore.access">
            <FeedStreamList view="mine" />
          </template>
          <EmptyState v-else text="登录后查看你加入频道的动态" action-text="去登录" to="/login" />
        </t-tab-panel>
        <t-tab-panel value="hot" label="全站热门">
          <FeedStreamList view="hot" />
        </t-tab-panel>
      </t-tabs>
    </div>

    <!-- 创建频道弹层 -->
    <t-dialog
      v-model:visible="showCreate"
      header="创建频道"
      :confirm-btn="{ content: creating ? '创建中…' : '创建', theme: 'primary', loading: creating }"
      :cancel-btn="'取消'"
      @confirm="onCreate"
    >
      <form class="dialog-form" @submit.prevent="onCreate">
        <div class="field">
          <label class="field-label">频道名称</label>
          <t-input v-model.trim="form.name" type="text" maxlength="64" placeholder="频道名称" clearable />
        </div>
        <div class="field">
          <label class="field-label">简介</label>
          <t-textarea v-model.trim="form.profile" :autosize="{ minRows: 3, maxRows: 6 }" maxlength="255" />
        </div>
        <div class="field">
          <label class="field-label">加入方式</label>
          <t-select v-model="form.join_setting">
            <t-option :value="0" label="自由加入" />
            <t-option :value="1" label="审核加入" />
            <t-option :value="2" label="邀请制" />
          </t-select>
        </div>
        <p v-if="error" class="error">{{ error }}</p>
      </form>
    </t-dialog>
  </main>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import FeedStreamList from '@/components/FeedStreamList.vue'
import UserAvatar from '@/components/UserAvatar.vue'
import EmptyState from '@/components/EmptyState.vue'
import { communityApi, type Community } from '@/api/community'
import { searchApi, type HotKeyword, type SearchResult } from '@/api/search'
import { tokenStore } from '@/api/http'
import { toast } from '@/utils/toast'
import { timeAgo } from '@/utils/time'

const router = useRouter()

// 双 Tab：已加入的最新 / 全站热门
const activeTab = ref<'mine' | 'hot'>('mine')

// 全站最热门频道 Top10（横滑条）
const hotChannels = ref<Community[]>([])

// 搜索
const searchQ = ref('')
const searching = ref(false)
const searchLoading = ref(false)
const searchResults = ref<SearchResult[]>([])
const searchTotal = ref(0)
const searchPage = ref(0)
const hasMoreSearchResults = ref(false)
const lastQ = ref('')
const hotKeywords = ref<HotKeyword[]>([])

// 创建频道
const showCreate = ref(false)
const creating = ref(false)
const error = ref('')
const form = reactive({ name: '', profile: '', join_setting: 0 })

onMounted(async () => {
  communityApi
    .list(1, 10, 'hot')
    .then((d) => (hotChannels.value = d.items))
    .catch(() => {})
  searchApi.hot().then((h) => (hotKeywords.value = h)).catch(() => {})
})

async function doSearch() {
  const q = searchQ.value.trim()
  if (!q || searchLoading.value) return
  searching.value = true
  lastQ.value = q
  await loadMoreSearch()
}

async function loadMoreSearch() {
  if (searchLoading.value) return
  searchLoading.value = true
  try {
    const page = searchResults.value.length === 0 ? 1 : searchPage.value + 1
    const data = await searchApi.posts(lastQ.value, { page, page_size: 20 })
    const seen = new Set(searchResults.value.map((p) => p.id))
    searchResults.value = searchResults.value.length === 0
      ? data.items
      : [...searchResults.value, ...data.items.filter((p) => !seen.has(p.id))]
    searchTotal.value = data.total
    searchPage.value = page
    hasMoreSearchResults.value = data.has_more
  } catch (e) {
    toast(e instanceof Error ? e.message : '搜索失败', 'error')
  } finally {
    searchLoading.value = false
  }
}

function clearSearch() {
  searching.value = false
  searchResults.value = []
  searchTotal.value = 0
  searchPage.value = 0
  hasMoreSearchResults.value = false
  searchQ.value = ''
}

function goPost(id: number) {
  router.push(`/p/${id}`)
}

async function onCreate() {
  if (creating.value) return
  // 未登录先跳登录页（登录后回跳继续创建）
  if (!tokenStore.access) {
    router.push(`/login?redirect=${encodeURIComponent('/discover')}`)
    return
  }
  creating.value = true
  error.value = ''
  try {
    const c = await communityApi.create({ ...form })
    showCreate.value = false
    router.push(`/c/${c.id}`)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '创建失败'
  } finally {
    creating.value = false
  }
}
</script>

<style scoped>
.discover {
  max-width: var(--page-max);
  margin: 0 auto;
  padding: 0 var(--sp-4) var(--sp-6);
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--nav-height);
  border-bottom: 1px solid var(--border);
}
.page-title {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
}

/* 全站最热门频道 Top10 横滑条 */
.hot-channels {
  margin-top: var(--sp-3);
  display: flex;
  gap: var(--sp-3);
  overflow-x: auto;
  padding-bottom: var(--sp-1);
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.hot-channels::-webkit-scrollbar {
  display: none;
}
.hot-channel {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  text-decoration: none;
  max-width: 64px;
}
.hot-channel-name {
  max-width: 64px;
  font-size: 11px;
  color: var(--text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hot-channel-meta {
  font-size: 10px;
  color: var(--text-3);
}

/* 搜索 */
.search-box {
  display: flex;
  gap: var(--sp-2);
  margin-top: var(--sp-3);
}
.search-input {
  flex: 1;
  min-width: 0;
}
.search-input :deep(.t-input__inner) {
  height: 36px;
}
.hot-words {
  margin-top: var(--sp-3);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--sp-2);
}
.hot-label {
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.hot-word {
  height: 28px;
  padding: 0 var(--sp-3);
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--bg-card);
  color: var(--text-2);
  font-size: var(--fs-caption);
  cursor: pointer;
  transition: all 0.15s;
}
.hot-word:hover {
  border-color: var(--brand);
  color: var(--brand);
}

/* 双 Tab 帖子流 */
.feed-tabs {
  margin-top: var(--sp-2);
}
.feed-tabs :deep(.t-tabs__panel) {
  padding: 0;
}

/* 搜索结果 */
.search-results {
  margin-top: var(--sp-3);
}
.search-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-2);
}
.search-count {
  font-size: var(--fs-caption);
  color: var(--text-2);
}
.list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: var(--sp-4);
  cursor: pointer;
  transition: border-color 0.15s;
}
.card:hover {
  border-color: var(--brand);
}
.card-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.card-name {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
}
.tag {
  font-size: var(--fs-caption);
  color: var(--text-3);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 1px 6px;
}
.tag-top {
  color: var(--danger);
  border-color: var(--danger);
}
.tag-essence {
  color: #b8860b;
  border-color: #b8860b;
}
.card-profile {
  margin: var(--sp-2) 0 0;
  font-size: var(--fs-body);
  color: var(--text-2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-meta {
  margin-top: var(--sp-3);
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2) var(--sp-4);
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.search-time {
  margin-left: auto;
}
.search-title :deep(em.hl),
.search-snippet :deep(em.hl) {
  font-style: normal;
  font-weight: 600;
  color: var(--brand);
  background: var(--brand-weak);
  border-radius: 2px;
  padding: 0 1px;
}
.load-more {
  margin-top: var(--sp-3);
}
.state {
  padding: var(--sp-6) 0;
  text-align: center;
  color: var(--text-3);
}
.dialog-form {
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
.error {
  margin: 0;
  font-size: var(--fs-caption);
  color: var(--td-error-color);
}
</style>
