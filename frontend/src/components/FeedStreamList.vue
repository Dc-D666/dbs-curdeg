<template>
  <div>
    <SkeletonFeed v-if="loading && items.length === 0" :count="3" />
    <div v-else-if="loadError && items.length === 0" class="feed-error">
      <p class="feed-error-text">{{ loadError }}</p>
      <t-button variant="outline" size="small" @click="retryLoad">重试</t-button>
    </div>
    <EmptyState
      v-else-if="items.length === 0 && !loading"
      :text="emptyText"
      :action-text="emptyActionText"
      :to="emptyActionTo"
    />
    <div v-else class="feed-list">
      <FeedCard v-for="p in items" :key="p.id" :post="p" show-community />
    </div>
    <t-button v-if="hasMore" variant="outline" block class="load-more" :loading="loading" @click="loadMore()">
      {{ loading ? '加载中…' : '加载更多' }}
    </t-button>
    <p v-else-if="items.length > 0 && !loading" class="feed-end">已经到底啦，没有更多帖子了</p>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import FeedCard from '@/components/FeedCard.vue'
import SkeletonFeed from '@/components/SkeletonFeed.vue'
import EmptyState from '@/components/EmptyState.vue'
import { postApi, type PostItem } from '@/api/post'
import { toast } from '@/utils/toast'

const props = withDefaults(
  defineProps<{
    view: 'all' | 'hot' | 'mine' | 'joined'
    emptyText?: string
    emptyActionText?: string
    emptyActionTo?: string
  }>(),
  { emptyText: '', emptyActionText: '', emptyActionTo: '' },
)

const emptyText = computed(
  () =>
    props.emptyText ||
    (props.view === 'mine' || props.view === 'joined'
      ? '你加入/关注的频道还没有新动态，去发现更多好内容吧！'
      : '这里还没有任何讨论，成为第一个开帖分享的人吧！'),
)
const emptyActionText = computed(() => props.emptyActionText || '去发现频道')
const emptyActionTo = computed(() => props.emptyActionTo || '/discover')

const items = ref<PostItem[]>([])
const cursor = ref<string | null>(null)
const hasMore = ref(false)
const loading = ref(false)
const loadError = ref('')

onMounted(() => {
  loadMore()
  window.addEventListener('live:refresh', onLiveRefresh)
})
onBeforeUnmount(() => {
  window.removeEventListener('live:refresh', onLiveRefresh)
})

/** P1 ③：收到「新讨论」药丸的查看请求 → 重置并重拉首屏。 */
function onLiveRefresh() {
  items.value = []
  cursor.value = null
  hasMore.value = false
  loadMore()
}

function currentFeed(cursorValue: string | null, pageSize = 20) {
  if (props.view === 'hot') return postApi.globalFeed('hot', cursorValue, pageSize)
  if (props.view === 'mine') return postApi.meFeed(cursorValue, pageSize)
  if (props.view === 'joined') return postApi.myJoinedFeed(cursorValue, pageSize)
  return postApi.globalFeed('latest', cursorValue, pageSize)
}

async function loadMore() {
  if (loading.value) return
  loading.value = true
  loadError.value = ''
  try {
    // 置顶帖每页重复返回，去重后可能整页 0 新条目：此时自动续拉下一页（#55），
    // 否则点「加载更多」列表毫无变化，用户以为卡死。上限 5 页防服务端异常时死循环。
    for (let attempt = 0; attempt < 5; attempt++) {
      const data = await currentFeed(cursor.value)
      const seen = new Set(items.value.map((p) => p.id))
      const fresh = data.items.filter((p) => !seen.has(p.id))
      items.value = [...items.value, ...fresh]
      cursor.value = data.next_cursor
      hasMore.value = data.has_more
      if (fresh.length > 0 || !hasMore.value) break
    }
  } catch (e) {
    if (items.value.length === 0) {
      loadError.value = e instanceof Error ? e.message : '加载失败，请稍后重试'
    } else {
      toast(e instanceof Error ? e.message : '加载失败', 'error')
    }
  } finally {
    loading.value = false
  }
}

function retryLoad() {
  items.value = []
  cursor.value = null
  hasMore.value = false
  loadError.value = ''
  loadMore()
}
</script>

<style scoped>
.feed-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.load-more {
  margin-top: var(--sp-3);
}
.feed-end {
  margin: var(--sp-4) 0 0;
  text-align: center;
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.feed-error {
  padding: var(--sp-6) 0;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-3);
}
.feed-error-text {
  margin: 0;
  color: var(--text-3);
  font-size: var(--fs-body);
}
</style>