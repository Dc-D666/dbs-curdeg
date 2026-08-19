<template>
  <main class="discover">
    <header class="page-header">
      <h1 class="page-title">发现频道</h1>
      <button class="btn-primary btn-sm" @click="showCreate = true">创建频道</button>
    </header>

    <!-- 搜索 -->
    <section class="search-box">
      <input
        v-model.trim="searchQ"
        class="input search-input"
        type="search"
        placeholder="搜索帖子（支持中文关键词）"
        maxlength="64"
        @keyup.enter="doSearch()"
      />
      <button class="btn-primary btn-sm" :disabled="!searchQ || searchLoading" @click="doSearch()">
        {{ searchLoading ? '搜索中…' : '搜索' }}
      </button>
    </section>

    <!-- 搜索结果 -->
    <div v-if="searching" class="search-results">
      <div class="search-meta">
        <span v-if="searchTotal" class="search-count">“{{ lastQ }}” 共 {{ searchTotal }} 条结果</span>
        <button class="btn-ghost btn-sm" @click="clearSearch()">返回频道列表</button>
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
            <span class="search-time">{{ p.created_at.slice(0, 10) }}</span>
          </div>
        </article>
      </div>
    </div>

    <!-- 热门搜索词 -->
    <div v-else-if="hotKeywords.length" class="hot-words">
      <span class="hot-label">热门搜索：</span>
      <button v-for="h in hotKeywords" :key="h.keyword" class="hot-word" @click="searchQ = h.keyword; doSearch()">
        {{ h.keyword }}
      </button>
    </div>

    <div v-if="!searching && loading" class="state">加载中…</div>
    <div v-else-if="!searching && communities.length === 0" class="state empty">还没有频道，创建第一个吧</div>
    <div v-else-if="!searching" class="list">
      <article
        v-for="c in communities"
        :key="c.id"
        class="card"
        @click="goDetail(c.id)"
      >
        <div class="card-head">
          <img v-if="c.avatar_url" :src="c.avatar_url" class="card-avatar" alt="" />
          <h3 class="card-name">{{ c.name }}</h3>
          <span v-if="c.is_member" class="tag tag-member">已加入</span>
          <span v-else-if="c.join_setting === 1" class="tag">审核制</span>
          <span v-else-if="c.join_setting === 2" class="tag">邀请制</span>
        </div>
        <p class="card-profile">{{ c.profile || '暂无简介' }}</p>
        <div class="card-meta">
          <span>{{ c.member_count }} 成员</span>
          <span>#{{ c.number }}</span>
        </div>
      </article>
    </div>

    <!-- 创建频道弹层 -->
    <div v-if="showCreate" class="overlay" @click.self="showCreate = false">
      <div class="dialog">
        <h3 class="dialog-title">创建频道</h3>
        <form @submit.prevent="onCreate">
          <label class="field">
            <span class="field-label">频道名称</span>
            <input v-model.trim="form.name" class="input" type="text" maxlength="64" required />
          </label>
          <label class="field">
            <span class="field-label">简介</span>
            <textarea v-model.trim="form.profile" class="input textarea" rows="3" maxlength="255"></textarea>
          </label>
          <label class="field">
            <span class="field-label">加入方式</span>
            <select v-model.number="form.join_setting" class="input">
              <option :value="0">自由加入</option>
              <option :value="1">审核加入</option>
              <option :value="2">邀请制</option>
            </select>
          </label>
          <p v-if="error" class="error">{{ error }}</p>
          <div class="dialog-actions">
            <button type="button" class="btn-ghost" @click="showCreate = false">取消</button>
            <button type="submit" class="btn-primary" :disabled="creating">
              {{ creating ? '创建中…' : '创建' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { communityApi, type Community } from '@/api/community'
import { searchApi, type HotKeyword, type SearchResult } from '@/api/search'
import { tokenStore } from '@/api/http'
import { toast } from '@/utils/toast'
import EmptyState from '@/components/EmptyState.vue'

const router = useRouter()
const communities = ref<Community[]>([])
const loading = ref(true)
const showCreate = ref(false)
const creating = ref(false)
const error = ref('')
const form = reactive({ name: '', profile: '', join_setting: 0 })

// 搜索
const searchQ = ref('')
const searching = ref(false)
const searchLoading = ref(false)
const searchResults = ref<SearchResult[]>([])
const searchTotal = ref(0)
const lastQ = ref('')
const hotKeywords = ref<HotKeyword[]>([])

onMounted(async () => {
  try {
    const data = await communityApi.list(1, 50)
    communities.value = data.items
  } finally {
    loading.value = false
  }
  searchApi.hot().then((h) => (hotKeywords.value = h)).catch(() => {})
})

async function doSearch() {
  const q = searchQ.value
  if (!q || searchLoading.value) return
  searching.value = true
  searchLoading.value = true
  lastQ.value = q
  try {
    const data = await searchApi.posts(q, { page_size: 20 })
    searchResults.value = data.items
    searchTotal.value = data.total
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
  searchQ.value = ''
}

function goPost(id: number) {
  router.push(`/p/${id}`)
}

async function onCreate() {
  if (creating.value) return
  // 未登录先跳登录页（登录后回跳继续创建）
  if (!tokenStore.access) {
    window.location.href = `/login?redirect=${encodeURIComponent('/discover')}`
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

function goDetail(id: number) {
  router.push(`/c/${id}`)
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
.btn-sm {
  height: 32px;
  padding: 0 var(--sp-3);
  font-size: var(--fs-caption);
}
.state {
  padding: var(--sp-6) 0;
  text-align: center;
  color: var(--text-3);
}
.empty {
  padding: var(--sp-6) 0;
}
.list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  margin-top: var(--sp-4);
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
.card-avatar {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  object-fit: cover;
  border: 1px solid var(--border);
  flex-shrink: 0;
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
.tag-member {
  color: var(--brand);
  border-color: var(--brand-weak);
  background: var(--brand-weak);
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
  gap: var(--sp-4);
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(31, 35, 41, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--sp-4);
}
.dialog {
  width: 100%;
  max-width: 380px;
  background: var(--bg-card);
  border-radius: var(--radius-overlay);
  box-shadow: var(--shadow-overlay);
  padding: var(--sp-5) var(--sp-4);
}
.dialog-title {
  margin: 0 0 var(--sp-4);
  font-size: var(--fs-title);
  font-weight: 600;
}
.dialog form {
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
  height: 40px;
  padding: 0 var(--sp-3);
  font-size: var(--fs-body);
  color: var(--text-1);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-btn);
  outline: none;
  transition: border-color 0.15s;
}
.textarea {
  height: auto;
  padding: var(--sp-2) var(--sp-3);
  resize: vertical;
  font-family: inherit;
}
.input:focus {
  border-color: var(--brand);
}
.error {
  margin: 0;
  font-size: var(--fs-caption);
  color: var(--danger);
}
.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-2);
  margin-top: var(--sp-2);
}
.btn-primary {
  height: 40px;
  padding: 0 var(--sp-4);
  border: none;
  border-radius: var(--radius-btn);
  background: var(--brand);
  color: #fff;
  font-size: var(--fs-body);
  cursor: pointer;
  transition: background 0.15s;
}
.btn-primary:hover {
  background: var(--brand-hover);
}
.btn-primary:disabled {
  background: var(--text-3);
  cursor: not-allowed;
}
.btn-ghost {
  height: 40px;
  padding: 0 var(--sp-4);
  border: 1px solid var(--border);
  border-radius: var(--radius-btn);
  background: var(--bg-card);
  color: var(--text-1);
  font-size: var(--fs-body);
  cursor: pointer;
}
.search-box {
  display: flex;
  gap: var(--sp-2);
  margin-top: var(--sp-3);
}
.search-input {
  flex: 1;
  min-width: 0;
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
.search-title {
  color: var(--text-1);
}
.search-snippet {
  color: var(--text-2);
}
.search-time {
  margin-left: auto;
}
.tag-top {
  color: var(--danger);
  border-color: var(--danger);
}
.tag-essence {
  color: #b8860b;
  border-color: #b8860b;
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
</style>
