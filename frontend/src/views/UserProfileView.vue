<template>
  <main class="profile">
    <header class="page-header">
      <t-button variant="text" @click="goBack">
        <ArrowLeftIcon class="back-icon" /> 返回
      </t-button>
      <h1 class="page-title">用户主页</h1>
    </header>

    <div v-if="loading" class="state">
      <t-skeleton :row="3" :loading="true" animation="gradient" />
    </div>

    <section v-else-if="user" class="panel">
      <div class="profile-row">
        <t-avatar :image="user.avatar_url || undefined" size="64px">
          <template #icon>{{ initial }}</template>
        </t-avatar>
        <div class="profile-main">
          <p class="nickname">{{ user.nickname || user.username }}</p>
          <p class="meta">@{{ user.username }} · 注册于 {{ createdDate }}</p>
        </div>
        <t-button
          v-if="auth.user && auth.user.id !== uid"
          variant="outline"
          :class="{ 't-active': following }"
          :loading="followBusy"
          @click="toggleFollow"
        >{{ following ? '已关注' : '关注' }}</t-button>
      </div>
      <p v-if="user.bio" class="bio">{{ user.bio }}</p>
      <p v-else class="bio empty">这个人很懒，什么都没写</p>
      <p v-if="user.province || user.city" class="location">
        📍 {{ user.province }} {{ user.city }}
      </p>
      <p class="follow-stats">关注 <b>{{ followCount }}</b> 人</p>

      <t-tabs v-model="profileTab" class="profile-tabs" lazy>
        <t-tab-panel value="posts" label="TA 的帖子">
          <div v-if="postsLoading" class="state">加载中…</div>
          <EmptyState v-else-if="posts.length === 0" text="TA 还没有发布帖子" />
          <div v-else class="post-list">
            <FeedCard v-for="p in posts" :key="p.id" :post="p" show-community @updated="reloadPosts" />
          </div>
          <t-button
            v-if="postsHasMore"
            variant="outline"
            block
            class="load-more"
            :loading="postsLoading"
            @click="loadMorePosts()"
          >{{ postsLoading ? '加载中…' : '加载更多帖子' }}</t-button>
        </t-tab-panel>
      </t-tabs>
    </section>

    <!-- 加载失败：区分「用户确实不存在」与「网络/服务端故障（可重试）」 -->
    <ErrorState
      v-else
      :text="loadError"
      :retryable="!notFound"
      @retry="retryLoad"
    >
      <router-link v-if="notFound" to="/discover" class="state-link">去发现频道</router-link>
    </ErrorState>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeftIcon } from 'tdesign-icons-vue-next'
import { userApi, type PublicUser } from '@/api/user'
import { postApi, type PostItem } from '@/api/post'
import { useAuthStore } from '@/stores/auth'
import { tokenStore } from '@/api/http'
import FeedCard from '@/components/FeedCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import { toast } from '@/utils/toast'
import { loadErrorMessage } from '@/utils/error'

const route = useRoute()
const router = useRouter()
const uid = Number(route.params.id)
const auth = useAuthStore()
const user = ref<PublicUser | null>(null)
const loading = ref(true)
const loadError = ref('')
const notFound = ref(false)

/** 返回：有上一页就回上一页；分享链接/新标签页直接进入时兜底到「发现」。
 *
 * 兜底选「发现」而不是首页：用户主页多半是从频道/帖子流里的作者名点进来的，
 * 回到「发现」比回到个人工作台更符合来路预期。
 */
function goBack() {
  const back = window.history.state?.back
  if (typeof back === 'string' && back) router.back()
  else router.push('/discover')
}
const following = ref(false)
const followBusy = ref(false)
const followCount = ref(0)

// TA 的帖子
const profileTab = ref<'posts'>('posts')
const posts = ref<PostItem[]>([])
const postsLoading = ref(false)
const postsCursor = ref<string | null>(null)
const postsHasMore = ref(false)

const initial = computed(() => (user.value?.nickname || user.value?.username || 'U').slice(0, 1).toUpperCase())
const createdDate = computed(() => (user.value?.created_at || '').slice(0, 10))

async function loadPosts(reset = false) {
  if (postsLoading.value) return
  if (reset) {
    posts.value = []
    postsCursor.value = null
    postsHasMore.value = false
  }
  postsLoading.value = true
  try {
    const data = await postApi.userPosts(uid, postsCursor.value, 20)
    const seen = new Set(posts.value.map((p) => p.id))
    posts.value = reset
      ? data.items
      : [...posts.value, ...data.items.filter((p) => !seen.has(p.id))]
    postsCursor.value = data.next_cursor
    postsHasMore.value = data.has_more
  } catch (e) {
    toast(e instanceof Error ? e.message : '加载帖子失败', 'error')
  } finally {
    postsLoading.value = false
  }
}

function loadMorePosts() {
  loadPosts(false)
}

async function reloadPosts() {
  await loadPosts(true)
}

onMounted(async () => {
  await loadUser()
  // 用户资料都加载失败就不要再请求帖子，否则叠加一条「加载帖子失败」的报错 toast
  if (!user.value) return
  loadPosts(true)
  if (tokenStore.access && auth.user?.id !== uid) {
    userApi.followStatus(uid).then((r) => (following.value = r.following)).catch(() => {})
  }
})

async function loadUser() {
  loading.value = true
  loadError.value = ''
  notFound.value = false
  try {
    user.value = await userApi.get(uid)
  } catch (e) {
    user.value = null
    const r = loadErrorMessage(e, '用户', '用户不存在')
    notFound.value = r.notFound
    loadError.value = r.text
  } finally {
    loading.value = false
  }
}

function retryLoad() {
  loadUser().then(() => {
    if (user.value) loadPosts(true)
  })
}

async function toggleFollow() {
  if (!tokenStore.access) {
    router.push(`/login?redirect=${encodeURIComponent(route.fullPath)}`)
    return
  }
  if (followBusy.value) return
  followBusy.value = true
  try {
    if (following.value) {
      const r = await userApi.unfollow(uid)
      following.value = false
      followCount.value = r.count
    } else {
      const r = await userApi.follow(uid)
      following.value = true
      followCount.value = r.count
      toast('已关注', 'success')
    }
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  } finally {
    followBusy.value = false
  }
}
</script>

<style scoped>
.profile {
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
.page-title {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
}
.state {
  padding: var(--sp-6) 0;
  text-align: center;
  color: var(--text-3);
}
.panel {
  margin-top: var(--sp-4);
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-component-border);
  border-radius: var(--td-radius-large);
  padding: var(--sp-4);
}
.profile-row {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
}
.back-icon {
  width: 16px;
  height: 16px;
  vertical-align: -2px;
}
.nickname {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
}
.meta {
  margin: var(--sp-1) 0 0;
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.bio {
  margin: var(--sp-4) 0 0;
  font-size: var(--fs-body);
  color: var(--text-1);
  line-height: 1.6;
}
.bio.empty {
  color: var(--text-3);
}
.location {
  margin: var(--sp-2) 0 0;
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.follow-stats {
  margin: var(--sp-2) 0 0;
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.profile-tabs {
  margin-top: var(--sp-4);
}
.profile-tabs :deep(.t-tabs__panel) {
  padding: 0;
}
.post-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.load-more {
  margin-top: var(--sp-3);
}
.t-active {
  color: var(--td-brand-color);
  border-color: var(--td-brand-color);
}
</style>
