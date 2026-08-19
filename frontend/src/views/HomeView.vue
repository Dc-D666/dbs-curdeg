<template>
  <main class="home">
    <header class="home-header">
      <h1 class="brand">SDUdiscord</h1>
      <nav v-if="auth.user" class="nav">
        <router-link to="/me" class="nav-link">
          {{ auth.user.nickname || auth.user.username }}
        </router-link>
        <t-button variant="text" size="small" @click="onLogout">退出</t-button>
      </nav>
      <nav v-else class="nav">
        <router-link to="/login" class="nav-link">登录</router-link>
        <router-link to="/register" class="nav-link">注册</router-link>
      </nav>
    </header>

    <section class="hero">
      <h2 class="hero-title">仿腾讯频道 · 私域社区</h2>
      <p class="hero-desc">频道 → 版块 → 帖子 → 评论，构建你的兴趣社区</p>
      <div class="hero-actions">
        <t-button theme="primary" size="large" @click="router.push('/discover')">浏览频道</t-button>
      </div>
    </section>

    <section class="feed-section">
      <div class="feed-head">
        <h3 class="feed-title">最新帖子</h3>
        <t-radio-group v-model="sort" variant="default-filled" size="small" @change="switchSort">
          <t-radio-button value="latest">最新</t-radio-button>
          <t-radio-button value="hot">热门</t-radio-button>
        </t-radio-group>
      </div>

      <SkeletonFeed v-if="loading && items.length === 0" :count="3" />
      <EmptyState v-else-if="items.length === 0" text="还没有帖子" action-text="浏览频道" to="/discover" />
      <div v-else class="feed-list">
        <FeedCard v-for="p in items" :key="p.id" :post="p" show-community />
      </div>
      <t-button v-if="hasMore" variant="outline" block class="load-more" :loading="loading" @click="loadMore()">
        {{ loading ? '加载中…' : '加载更多' }}
      </t-button>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import FeedCard from '@/components/FeedCard.vue'
import SkeletonFeed from '@/components/SkeletonFeed.vue'
import EmptyState from '@/components/EmptyState.vue'
import { postApi, type PostItem } from '@/api/post'
import { useAuthStore } from '@/stores/auth'
import { toast } from '@/utils/toast'

const auth = useAuthStore()
const router = useRouter()

const items = ref<PostItem[]>([])
const sort = ref<'latest' | 'hot'>('latest')
const cursor = ref<string | null>(null)
const hasMore = ref(false)
const loading = ref(false)

onMounted(() => {
  auth.fetchMe()
  loadMore()
})

async function loadMore() {
  if (loading.value) return
  loading.value = true
  try {
    const data = await postApi.globalFeed(sort.value, cursor.value)
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

function switchSort(s: 'latest' | 'hot') {
  if (sort.value === s) return
  sort.value = s
  items.value = []
  cursor.value = null
  loadMore()
}

function onLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.home {
  max-width: var(--page-max);
  margin: 0 auto;
  padding: 0 var(--sp-4) var(--sp-6);
}
.home-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--nav-height);
  border-bottom: 1px solid var(--border);
}
.brand {
  margin: 0;
  font-size: var(--fs-page);
  font-weight: 700;
  color: var(--brand);
}
.nav {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}
.nav-link {
  color: var(--text-1);
  font-size: var(--fs-body);
}
.hero {
  padding: var(--sp-5) 0;
}
.hero-title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
}
.hero-desc {
  margin: var(--sp-2) 0 0;
  color: var(--text-2);
  font-size: var(--fs-body);
}
.hero-actions {
  margin-top: var(--sp-4);
}
.feed-section {
  margin-top: var(--sp-2);
}
.feed-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-3);
}
.feed-title {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
}
.feed-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.load-more {
  margin-top: var(--sp-3);
}
</style>
