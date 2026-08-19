<template>
  <main class="feed-page">
    <header class="page-header">
      <router-link to="/me" class="back">
        <ArrowLeftIcon class="back-icon" /> 我的
      </router-link>
      <h1 class="page-title">我关注的频道</h1>
    </header>

    <SkeletonFeed v-if="loading && items.length === 0" :count="2" />
    <EmptyState
      v-else-if="items.length === 0"
      text="还没有关注的频道"
      action-text="去发现频道"
      to="/discover"
    />

    <div v-else class="feed-list">
      <FeedCard v-for="p in items" :key="p.id" :post="p" show-community />
    </div>

    <t-button v-if="hasMore" variant="outline" block class="load-more" :loading="loading" @click="loadMore()">
      {{ loading ? '加载中…' : '加载更多' }}
    </t-button>

    <p class="go-discover">
      <router-link to="/discover" class="discover-link">去发现更多频道 <ArrowRightIcon class="discover-arrow" /></router-link>
    </p>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ArrowLeftIcon, ArrowRightIcon } from 'tdesign-icons-vue-next'
import FeedCard from '@/components/FeedCard.vue'
import SkeletonFeed from '@/components/SkeletonFeed.vue'
import EmptyState from '@/components/EmptyState.vue'
import { postApi, type PostItem } from '@/api/post'
import { toast } from '@/utils/toast'

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
    toast(e instanceof Error ? e.message : '加载失败', 'error')
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
  padding: var(--sp-6) 0;
  text-align: center;
  color: var(--text-3);
}
.feed-list {
  margin: var(--sp-4) 0 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.load-more {
  margin-top: var(--sp-3);
}
.go-discover {
  text-align: center;
  margin-top: var(--sp-4);
}
.discover-link {
  color: var(--brand);
  font-size: var(--fs-caption);
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.discover-arrow {
  width: 14px;
  height: 14px;
}
</style>
