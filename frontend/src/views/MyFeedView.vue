<template>
  <main class="feed-page">
    <header class="page-header">
      <router-link to="/me" class="back">← 我的</router-link>
      <h1 class="page-title">我关注的频道</h1>
    </header>

    <p v-if="loading && items.length === 0" class="state">加载中…</p>
    <p v-else-if="items.length === 0" class="state">还没有关注的频道，去发现页逛逛吧</p>

    <ul v-else class="feed-list">
      <li v-for="p in items" :key="p.id" class="feed-item" @click="$router.push(`/p/${p.id}`)">
        <div class="feed-head">
          <span class="feed-title">{{ p.title }}</span>
          <span v-if="p.is_top" class="tag tag-top">置顶</span>
          <span v-if="p.is_essence" class="tag tag-essence">精华</span>
        </div>
        <p class="feed-excerpt">{{ p.source_markdown }}</p>
        <div class="feed-meta">
          <span>{{ p.community_name }}</span>
          <span>{{ p.author_nickname }}</span>
          <span>{{ p.like_count }} 赞</span>
          <span>{{ p.comment_count }} 评论</span>
          <span class="feed-time">{{ p.created_at.slice(0, 16) }}</span>
        </div>
      </li>
    </ul>

    <button v-if="hasMore" class="btn-ghost load-more" :disabled="loading" @click="loadMore()">
      {{ loading ? '加载中…' : '加载更多' }}
    </button>

    <p class="go-discover">
      <router-link to="/discover" class="discover-link">去发现更多频道 →</router-link>
    </p>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { postApi, type PostItem } from '@/api/post'

const items = ref<PostItem[]>([])
const cursor = ref<string | null>(null)
const hasMore = ref(false)
const loading = ref(false)

onMounted(() => loadMore())

async function loadMore() {
  if (loading.value) return
  loading.value = true
  try {
    const data = await postApi.meFeed(cursor.value)
    const seen = new Set(items.value.map((p) => p.id))
    items.value = [...items.value, ...data.items.filter((p) => !seen.has(p.id))]
    cursor.value = data.next_cursor
    hasMore.value = data.has_more
  } catch (e) {
    alert(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.feed-page {
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
.state {
  padding: var(--sp-6) 0;
  text-align: center;
  color: var(--text-3);
}
.feed-list {
  margin: var(--sp-4) 0 0;
  padding: 0;
  list-style: none;
}
.feed-item {
  padding: var(--sp-3) var(--sp-4);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  margin-bottom: var(--sp-3);
  cursor: pointer;
}
.feed-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.feed-title {
  font-size: var(--fs-body);
  font-weight: 600;
  color: var(--text-1);
}
.tag {
  font-size: var(--fs-caption);
  border-radius: 4px;
  padding: 1px 6px;
}
.tag-top {
  color: var(--danger);
  border: 1px solid var(--danger);
}
.tag-essence {
  color: #b8860b;
  border: 1px solid #b8860b;
}
.feed-excerpt {
  margin: var(--sp-1) 0 0;
  font-size: var(--fs-caption);
  color: var(--text-2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.feed-meta {
  margin-top: var(--sp-1);
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-3);
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.feed-time {
  margin-left: auto;
}
.load-more {
  width: 100%;
  justify-content: center;
}
.go-discover {
  text-align: center;
  margin-top: var(--sp-4);
}
.discover-link {
  color: var(--brand);
  font-size: var(--fs-caption);
  text-decoration: none;
}
</style>
