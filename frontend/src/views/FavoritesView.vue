<template>
  <main class="favorites">
    <header class="page-header">
      <router-link to="/me" class="back">
        <ArrowLeftIcon class="back-icon" /> 返回
      </router-link>
      <h1 class="page-title">我的收藏</h1>
    </header>

    <div v-if="loading && items.length === 0" class="state"><t-skeleton :row="3" animation="gradient" /></div>
    <ErrorState
      v-else-if="loadError && items.length === 0"
      :text="loadError"
      @retry="retry"
    />
    <EmptyState v-else-if="items.length === 0" text="暂无收藏" />

    <ul v-else class="list">
      <li v-for="f in items" :key="f.favorite_id" class="item">
        <router-link v-if="f.post_status === 0" :to="`/p/${f.post_id}`" class="item-main">
          <span class="item-title">{{ f.post_title || `帖子 #${f.post_id}` }}</span>
          <span class="item-time"><StarIcon class="item-time-icon" /> {{ f.group_name }} · {{ (f.created_at || '').slice(0, 10) }}</span>
        </router-link>
        <div v-else class="item-main">
          <span class="item-title">{{ f.post_title || `帖子 #${f.post_id}` }}</span>
          <span class="item-time">内容不可见</span>
        </div>
        <t-button variant="text" size="small" theme="danger" @click="remove(f)">
          <template #icon><DeleteIcon /></template> 取消收藏
        </t-button>
      </li>
    </ul>

    <t-button v-if="items.length < total" variant="outline" block class="load-more" :loading="loading" @click="load(page + 1)">
      {{ loading ? '加载中…' : '加载更多' }}
    </t-button>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ArrowLeftIcon, DeleteIcon, StarIcon } from 'tdesign-icons-vue-next'
import { postApi, type FavoriteItem } from '@/api/post'
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import { toast } from '@/utils/toast'
import { errMessage } from '@/utils/error'

// 显式组件名：供 App.vue 的 <keep-alive :include> 匹配（返回本页保留列表状态，#37）
defineOptions({ name: 'FavoritesView' })

const items = ref<FavoriteItem[]>([])
const page = ref(0)
const total = ref(0)
const loading = ref(false)
// 首屏失败要落到错误态，否则空列表会被误读成「暂无收藏」
const loadError = ref('')

async function load(p: number) {
  if (loading.value) return
  loading.value = true
  loadError.value = ''
  try {
    const data = await postApi.myFavorites(p)
    items.value = p === 1 ? data.items : [...items.value, ...data.items]
    page.value = p
    total.value = data.total
  } catch (e) {
    const msg = errMessage(e, '加载失败')
    if (p === 1 && items.value.length === 0) loadError.value = msg
    else toast(msg, 'error')
  } finally {
    loading.value = false
  }
}

function retry() {
  page.value = 0
  load(1)
}

async function remove(f: FavoriteItem) {
  try {
    await postApi.unfavorite(f.post_id)
    items.value = items.value.filter((x) => x.favorite_id !== f.favorite_id)
    toast('已取消收藏')
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

onMounted(() => load(1))
</script>

<style scoped>
.favorites {
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
.list {
  margin: var(--sp-4) 0 0;
  padding: 0;
  list-style: none;
}
.item {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-3);
  margin-bottom: var(--sp-2);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  transition: border-color 0.15s, box-shadow 0.2s;
}
.item:hover {
  border-color: var(--brand);
  box-shadow: var(--shadow-sm);
}
.item-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: var(--text-1);
  text-decoration: none;
}
.item-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--fs-body);
}
.item-time {
  font-size: var(--fs-caption);
  color: var(--text-3);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.item-time-icon {
  width: 12px;
  height: 12px;
}
.load-more {
  margin-top: var(--sp-3);
}
</style>
