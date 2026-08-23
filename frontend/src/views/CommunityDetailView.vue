<template>
  <main class="detail" :class="{ wb: isWide }">
    <header class="page-header">
      <router-link to="/discover" class="back">
        <ArrowLeftIcon class="back-icon" /> 发现
      </router-link>
      <h1 class="page-title">{{ community?.name || '频道' }}</h1>
      <span v-if="community?.is_member" class="tag tag-member">已加入</span>
    </header>

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="community">
      <template v-if="!isWide">
      <section class="panel head-panel">
        <div v-if="community.cover_url" class="cover" :style="{ backgroundImage: `url('${community.cover_url}')` }"></div>
        <div class="head-title-row">
          <img v-if="community.avatar_url" :src="community.avatar_url" class="head-avatar" alt="" />
          <h1 class="head-name">{{ community.name }}</h1>
        </div>
        <p class="profile">{{ community.profile || '暂无简介' }}</p>
        <div class="meta">
          <span>{{ community.member_count }} 成员</span>
          <span>{{ community.boards.length }} 个版块</span>
          <span>#{{ community.number }}</span>
        </div>
        <div class="actions">
          <template v-if="community.is_member">
            <t-button v-if="community.my_member_type !== 0" variant="outline" @click="onLeave">退出频道</t-button>
          </template>
          <t-button v-else theme="primary" :loading="joining" @click="onJoin">
            {{ joining ? '处理中…' : '加入频道' }}
          </t-button>
        </div>
      </section>

      <section class="panel">
        <t-radio-group v-model="activeBoard" variant="default-filled" size="small" class="board-tabs">
          <t-radio-button v-for="b in community.boards" :key="b.id" :value="b.id">
            {{ b.name }}
          </t-radio-button>
        </t-radio-group>
        <p v-if="community.boards.length === 0" class="no-board">暂无版块</p>
        <div v-if="activeBoardInfo" class="board-desc">{{ activeBoardInfo.description || '暂无版块描述' }}</div>
      </section>

      <!-- 话题（P0） -->
      <section class="panel topic-panel">
        <div class="panel-title-row">
          <h3 class="panel-title">话题</h3>
          <div class="topic-toolbar">
            <t-radio-group v-model="topicSort" variant="default-filled" size="small">
              <t-radio-button value="hot">热度</t-radio-button>
              <t-radio-button value="latest">最新</t-radio-button>
            </t-radio-group>
            <t-button v-if="community.is_member" variant="outline" size="small" @click="openTopicDialog()">+ 新建</t-button>
          </div>
        </div>
        <div v-if="topics.length" class="topic-list">
          <div v-for="t in topics" :key="t.id" class="topic-item">
            <span class="topic-name">#{{ t.name }}</span>
            <span class="topic-count">{{ t.post_count }} 帖 · 热度 {{ t.heat_value }}</span>
            <div v-if="community.my_member_type === 0 || community.my_member_type === 1" class="topic-ops">
              <t-button variant="text" size="small" @click="openTopicDialog(t)">编辑</t-button>
              <t-button variant="text" size="small" theme="danger" @click="removeTopic(t)">删除</t-button>
            </div>
          </div>
        </div>
        <p v-else class="no-board">暂无话题</p>
      </section>

      <section v-if="activeBoardInfo" class="panel feed-panel">
        <QuickComposer
          v-if="community.is_member"
          :cid="cid"
          :bid="activeBoard ?? 0"
          @posted="onQuickPosted"
        />
        <div class="feed-toolbar">
          <t-radio-group v-model="feedSort" variant="default-filled" size="small">
            <t-radio-button value="latest">最新</t-radio-button>
            <t-radio-button value="hot">热门</t-radio-button>
          </t-radio-group>
          <t-button
            v-if="community.is_member"
            theme="primary"
            size="small"
            @click="router.push(`/c/${cid}/boards/${activeBoard}/post/new`)"
          >发帖</t-button>
        </div>

        <SkeletonFeed v-if="feedLoading && feedItems.length === 0" :count="2" />
        <EmptyState v-else-if="feedItems.length === 0" text="这里还没有任何讨论，成为第一个开帖分享的人吧！" />
        <div v-else class="feed-list">
          <FeedCard v-for="p in feedItems" :key="p.id" :post="p" />
        </div>
        <t-button v-if="feedHasMore" variant="outline" block class="load-more" :loading="feedLoading" @click="loadFeed()">
          {{ feedLoading ? '加载中…' : '加载更多' }}
        </t-button>
      </section>

      <section v-if="community.my_member_type === 0 || community.my_member_type === 1" class="panel owner-panel">
        <div class="panel-title-row">
          <h3 class="panel-title">频道管理</h3>
          <t-button variant="outline" size="small" @click="router.push(`/c/${cid}/admin`)">管理后台</t-button>
        </div>

        <div class="owner-row">
          <span class="owner-label">头像 / 封面</span>
          <label class="btn-ghost btn-sm upload-label">
            上传图片
            <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" @change="onCoverUpload" hidden />
          </label>
          <span class="owner-hint">同时设为头像与封面</span>
        </div>

        <div class="owner-row">
          <span class="owner-label">频道状态</span>
          <t-select v-model="statusForm.status" class="status-select">
            <t-option :value="0" label="正常" />
            <t-option :value="1" label="关闭" />
          </t-select>
          <t-button variant="outline" size="small" @click="onStatusSave">保存</t-button>
        </div>

        <div class="owner-row">
          <span class="owner-label">创建版块</span>
          <t-input v-model.trim="boardForm.name" class="board-input" placeholder="版块名称" maxlength="64" clearable />
          <t-input v-model.trim="boardForm.description" class="board-input" placeholder="简介（可选）" maxlength="255" clearable />
          <t-button variant="outline" size="small" :loading="boardCreating" @click="onCreateBoard">创建</t-button>
        </div>

        <div class="owner-row">
          <span class="owner-label">成员列表</span>
          <t-button variant="outline" size="small" @click="toggleMembers">{{ membersOpen ? '收起' : `${community.member_count} 人` }}</t-button>
        </div>
        <div v-if="membersOpen" class="manage-list">
          <div v-for="m in members" :key="m.id" class="manage-item">
            <span class="manage-name">{{ m.user_nickname || m.nickname }}</span>
            <span class="manage-type">{{ memberTypeName(m.member_type) }}</span>
          </div>
          <p v-if="members.length === 0" class="manage-empty">暂无成员</p>
        </div>

        <div v-if="community.join_setting === 1" class="owner-row">
          <span class="owner-label">加入审核</span>
          <t-button variant="outline" size="small" @click="toggleRequests">{{ requestsOpen ? '收起' : `${requests.length} 条待审` }}</t-button>
        </div>
        <div v-if="requestsOpen" class="manage-list">
          <div v-for="r in requests" :key="r.id" class="manage-item">
            <span class="manage-name">{{ r.user_nickname || r.username }}</span>
            <span class="manage-time">{{ formatTime(r.created_at) }}</span>
            <t-button variant="outline" size="small" @click="handleRequest(r, true)">通过</t-button>
            <t-button variant="outline" size="small" theme="danger" @click="handleRequest(r, false)">驳回</t-button>
          </div>
          <p v-if="requests.length === 0" class="manage-empty">暂无待审申请</p>
        </div>

        <div class="owner-row">
          <span class="owner-label">解散频道</span>
          <t-button variant="outline" size="small" theme="danger" @click="onDissolve">解散</t-button>
        </div>

        <p v-if="ownerMsg" class="msg">{{ ownerMsg }}</p>
      </section>
      </template>

      <!-- 三栏宽屏工作台（桌面 ≥1024px） -->
      <template v-else>
        <div class="wb">
          <!-- 左栏：社区切换 + 版块树 -->
          <aside class="wb-left">
            <div class="wb-rail-title">我的频道</div>
            <div class="wb-channels">
              <router-link v-for="c in myChannels" :key="c.id" :to="`/c/${c.id}`" class="wb-channel" :class="{ active: c.id === cid }">
                <UserAvatar :name="c.name" :src="c.avatar_url" :size="24" />
                <span class="wb-channel-name">{{ c.name }}</span>
              </router-link>
            </div>
            <div class="wb-rail-title">版块</div>
            <nav class="wb-boards">
              <button v-for="b in community.boards" :key="b.id" class="wb-board" :class="{ active: b.id === activeBoard }" @click="activeBoard = b.id">
                <span class="wb-board-hash">#</span>{{ b.name }}
              </button>
              <p v-if="community.boards.length === 0" class="wb-empty">暂无版块</p>
            </nav>
          </aside>

          <!-- 中栏：频道头 + 内联发帖 + 信息流 + 管理入口 -->
          <section class="wb-main">
            <div class="wb-channel-head">
              <img v-if="community.avatar_url" :src="community.avatar_url" class="wb-avatar" alt="" />
              <div class="wb-head-main">
                <div class="wb-head-name">{{ community.name }}<span v-if="community.is_member" class="tag tag-member">已加入</span></div>
                <p class="wb-profile">{{ community.profile || '暂无简介' }}</p>
                <div class="wb-meta">{{ community.member_count }} 成员 · {{ community.boards.length }} 版块 · #{{ community.number }}</div>
              </div>
              <div class="wb-actions">
                <t-button v-if="community.is_member && community.my_member_type !== 0" variant="outline" size="small" @click="onLeave">退出</t-button>
                <t-button v-else-if="!community.is_member" theme="primary" size="small" :loading="joining" @click="onJoin">加入</t-button>
              </div>
            </div>

            <QuickComposer v-if="community.is_member" :cid="cid" :bid="activeBoard ?? 0" @posted="onQuickPosted" />

            <div v-if="activeBoardInfo" class="wb-feed">
              <div class="feed-toolbar">
                <t-radio-group v-model="feedSort" variant="default-filled" size="small">
                  <t-radio-button value="latest">最新</t-radio-button>
                  <t-radio-button value="hot">热门</t-radio-button>
                </t-radio-group>
                <t-button
                  v-if="community.is_member"
                  theme="primary"
                  size="small"
                  @click="router.push(`/c/${cid}/boards/${activeBoard}/post/new`)"
                >发帖</t-button>
              </div>
              <SkeletonFeed v-if="feedLoading && feedItems.length === 0" :count="2" />
              <EmptyState v-else-if="feedItems.length === 0" text="这里还没有任何讨论，成为第一个开帖分享的人吧！" />
              <div v-else class="feed-list">
                <FeedCard v-for="p in feedItems" :key="p.id" :post="p" />
              </div>
              <t-button v-if="feedHasMore" variant="outline" block class="load-more" :loading="feedLoading" @click="loadFeed()">
                {{ feedLoading ? '加载中…' : '加载更多' }}
              </t-button>
            </div>

            <section v-if="community.my_member_type === 0 || community.my_member_type === 1" class="panel owner-panel">
              <div class="panel-title-row">
                <h3 class="panel-title">频道管理</h3>
                <t-button variant="outline" size="small" @click="router.push(`/c/${cid}/admin`)">管理后台</t-button>
              </div>
              <p class="owner-hint">头像/封面、频道状态、版块、成员与违规管理请前往管理后台。</p>
            </section>
          </section>

          <!-- 右栏：话题 + 今日热议 -->
          <aside class="wb-right">
            <div class="wb-panel">
              <div class="wb-rail-title">话题</div>
              <div class="topic-toolbar">
                <t-radio-group v-model="topicSort" variant="default-filled" size="small">
                  <t-radio-button value="hot">热度</t-radio-button>
                  <t-radio-button value="latest">最新</t-radio-button>
                </t-radio-group>
                <t-button v-if="community.is_member" variant="outline" size="small" @click="openTopicDialog()">+ 新建</t-button>
              </div>
              <div v-if="topics.length" class="topic-list">
                <div v-for="t in topics" :key="t.id" class="topic-item">
                  <span class="topic-name">#{{ t.name }}</span>
                  <span class="topic-count">{{ t.post_count }} 帖 · 热度 {{ t.heat_value }}</span>
                  <div v-if="community.my_member_type === 0 || community.my_member_type === 1" class="topic-ops">
                    <t-button variant="text" size="small" @click="openTopicDialog(t)">编辑</t-button>
                    <t-button variant="text" size="small" theme="danger" @click="removeTopic(t)">删除</t-button>
                  </div>
                </div>
              </div>
              <p v-else class="wb-empty">暂无话题</p>
            </div>

            <div class="wb-panel">
              <div class="wb-rail-title">今日热议</div>
              <div v-if="hotPosts.length" class="hot-list">
                <button v-for="p in hotPosts" :key="p.id" class="hot-item" @click="openHotPost(p.id)">
                  <span class="hot-title">{{ p.title }}</span>
                  <span class="hot-meta">{{ p.like_count }} 赞 · {{ p.comment_count }} 评</span>
                </button>
              </div>
              <p v-else class="wb-empty">暂无热门</p>
            </div>
          </aside>
        </div>
      </template>
    </div>
    <div v-else class="state">频道不存在</div>

    <!-- 话题编辑弹窗 -->
    <t-dialog
      v-model:visible="topicDialog"
      :header="topicForm.id ? '编辑话题' : '新建话题'"
      :confirm-btn="{ content: topicForm.id ? '保存' : '创建', theme: 'primary', loading: topicSaving }"
      cancel-btn="取消"
      @confirm="saveTopic"
    >
      <div class="topic-form">
        <t-input v-model="topicForm.name" placeholder="话题名称（不带 #）" maxlength="32" class="topic-input" />
        <t-input v-model="topicForm.description" placeholder="话题描述（选填）" maxlength="255" class="topic-input" />
        <t-textarea v-model="topicForm.rules" :autosize="{ minRows: 2, maxRows: 4 }" placeholder="话题规则（选填）" maxlength="500" />
      </div>
    </t-dialog>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeftIcon } from 'tdesign-icons-vue-next'
import { communityApi, type Community, type JoinRequestItem, type Member, type TopicItem } from '@/api/community'
import { postApi, type PostItem } from '@/api/post'
import FeedCard from '@/components/FeedCard.vue'
import QuickComposer from '@/components/QuickComposer.vue'
import UserAvatar from '@/components/UserAvatar.vue'
import SkeletonFeed from '@/components/SkeletonFeed.vue'
import EmptyState from '@/components/EmptyState.vue'
import { usePostDrawer } from '@/stores/postDrawer'
import { request, tokenStore } from '@/api/http'
import { toast } from '@/utils/toast'
import { confirmDialog } from '@/utils/confirm'
import { formatTime } from '@/utils/time'

const route = useRoute()
const router = useRouter()
const cid = Number(route.params.id)
const community = ref<Community | null>(null)
const loading = ref(true)
const joining = ref(false)
const activeBoard = ref<number | null>(null)
const ownerMsg = ref('')
const statusForm = reactive({ status: 0 })

// 桌面三栏工作台判定（≥1024px）+ 社区切换器（我的频道）
const isWide = ref(window.innerWidth >= 1024)
function onResize() {
  isWide.value = window.innerWidth >= 1024
}
const myChannels = ref<Community[]>([])
async function loadMyChannels() {
  if (!tokenStore.access) return
  try {
    const m = await communityApi.mine()
    const seen = new Set<number>()
    myChannels.value = [...m.owned, ...m.managed, ...m.joined].filter((c) => {
      if (seen.has(c.id)) return false
      seen.add(c.id)
      return true
    })
  } catch {
    /* ignore */
  }
}
// 右栏「今日热议」：取频道热门 Top5
const hotPosts = ref<PostItem[]>([])
async function loadHotPosts() {
  try {
    const data = await postApi.feed(cid, 'hot', null, 5)
    hotPosts.value = data.items
  } catch {
    /* ignore */
  }
}

// 管理面板
const boardForm = reactive({ name: '', description: '' })
const boardCreating = ref(false)
const membersOpen = ref(false)
const members = ref<Member[]>([])
const requestsOpen = ref(false)
const requests = ref<JoinRequestItem[]>([])

// 话题（P0）
const topics = ref<TopicItem[]>([])
const topicSort = ref<'hot' | 'latest'>('hot')
const topicDialog = ref(false)
const topicSaving = ref(false)
const topicForm = reactive({ id: 0, name: '', description: '', rules: '' })

async function loadTopics() {
  try {
    topics.value = await communityApi.topics(cid, topicSort.value)
  } catch (e) {
    toast(e instanceof Error ? e.message : '加载话题失败', 'error')
  }
}

watch(topicSort, () => loadTopics())

function openTopicDialog(t?: TopicItem) {
  topicForm.id = t?.id ?? 0
  topicForm.name = t?.name ?? ''
  topicForm.description = t?.description ?? ''
  topicForm.rules = t?.rules ?? ''
  topicDialog.value = true
}

async function saveTopic() {
  if (!topicForm.name.trim()) {
    toast('请填写话题名称', 'error')
    return
  }
  topicSaving.value = true
  try {
    if (topicForm.id) {
      await communityApi.updateTopic(cid, topicForm.id, {
        name: topicForm.name,
        description: topicForm.description,
        rules: topicForm.rules,
      })
      toast('话题已更新')
    } else {
      await communityApi.createTopic(cid, {
        name: topicForm.name,
        description: topicForm.description,
        rules: topicForm.rules,
      })
      toast('话题已创建')
    }
    topicDialog.value = false
    await loadTopics()
  } catch (e) {
    toast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    topicSaving.value = false
  }
}

async function removeTopic(t: TopicItem) {
  if (!(await confirmDialog('删除话题', `确定删除话题「${t.name}」？`))) return
  try {
    await communityApi.deleteTopic(cid, t.id)
    await loadTopics()
    toast('话题已删除')
  } catch (e) {
    toast(e instanceof Error ? e.message : '删除失败', 'error')
  }
}

const activeBoardInfo = computed(
  () => community.value?.boards.find((b) => b.id === activeBoard.value) ?? null,
)

// ---------- 帖子流 ----------
const feedItems = ref<PostItem[]>([])
const feedSort = ref<'latest' | 'hot'>('latest')
const feedCursor = ref<string | null>(null)
const feedHasMore = ref(false)
const feedLoading = ref(false)

async function loadFeed(reset = false) {
  if (!activeBoard.value || feedLoading.value) return
  if (reset) {
    feedItems.value = []
    feedCursor.value = null
    feedHasMore.value = false
  }
  feedLoading.value = true
  try {
    const data = await postApi.feed(cid, feedSort.value, feedCursor.value, 20, activeBoard.value)
    // 按 id 去重：置顶帖每页都会返回，避免"加载更多"后重复
    const seen = new Set(feedItems.value.map((p) => p.id))
    const merged = reset
      ? data.items
      : [...feedItems.value, ...data.items.filter((p) => !seen.has(p.id))]
    feedItems.value = merged
    feedCursor.value = data.next_cursor
    feedHasMore.value = data.has_more
  } catch (e) {
    toast(e instanceof Error ? e.message : '加载失败', 'error')
  } finally {
    feedLoading.value = false
  }
}

// Quick Composer 发布成功后重拉当前版块首屏
function onQuickPosted() {
  loadFeed(true)
}

// 右栏「今日热议」点击：桌面打开抽屉，移动端整页跳转
const postDrawer = usePostDrawer()
function openHotPost(id: number) {
  if (window.innerWidth >= 1024) postDrawer.open(id)
  else router.push(`/p/${id}`)
}

function switchSort(sort: 'latest' | 'hot') {
  if (feedSort.value === sort) return
  feedSort.value = sort
  loadFeed(true)
}

watch(feedSort, (s) => {
  loadFeed(true)
})

watch(activeBoard, (bid) => {
  if (bid) loadFeed(true)
})

onMounted(async () => {
  try {
    community.value = await communityApi.get(cid)
    if (community.value.boards.length > 0) {
      activeBoard.value = community.value.boards[0].id
    }
    statusForm.status = community.value.status
    loadTopics()
  } finally {
    loading.value = false
  }
})

// P1 ③：收到「新讨论」药丸的查看请求 → 重拉当前版块首屏
function onLiveRefresh() {
  if (activeBoard.value) loadFeed(true)
}
onMounted(() => {
  window.addEventListener('live:refresh', onLiveRefresh)
  window.addEventListener('resize', onResize)
  loadMyChannels()
  loadHotPosts()
})
onBeforeUnmount(() => {
  window.removeEventListener('live:refresh', onLiveRefresh)
  window.removeEventListener('resize', onResize)
})

async function onJoin() {
  if (!tokenStore.access) {
    router.push(`/login?redirect=${encodeURIComponent(route.fullPath)}`)
    return
  }
  if (joining.value) return
  joining.value = true
  try {
    await communityApi.join(cid)
    community.value = await communityApi.get(cid)
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  } finally {
    joining.value = false
  }
}

async function onLeave() {
  if (!(await confirmDialog('退出频道', '确定退出该频道？'))) return
  try {
    await communityApi.leave(cid)
    community.value = await communityApi.get(cid)
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

async function onCoverUpload(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  ownerMsg.value = '上传中…'
  const fd = new FormData()
  fd.append('file', file)
  try {
    const up = await request<{ url: string }>({ url: '/uploads', method: 'POST', data: fd })
    community.value = await communityApi.update(cid, { avatar_url: up.url, cover_url: up.url })
    ownerMsg.value = '图片已更新'
  } catch (err) {
    ownerMsg.value = err instanceof Error ? err.message : '上传失败'
  }
}

async function onStatusSave() {
  ownerMsg.value = ''
  try {
    community.value = await communityApi.updateStatus(cid, statusForm.status)
    ownerMsg.value = '状态已保存'
  } catch (err) {
    ownerMsg.value = err instanceof Error ? err.message : '保存失败'
  }
}

async function onCreateBoard() {
  if (!boardForm.name) {
    ownerMsg.value = '请填写版块名称'
    return
  }
  boardCreating.value = true
  ownerMsg.value = ''
  try {
    await communityApi.createBoard(cid, { name: boardForm.name, description: boardForm.description })
    boardForm.name = ''
    boardForm.description = ''
    community.value = await communityApi.get(cid)
    if (activeBoard.value === null && community.value.boards.length > 0) {
      activeBoard.value = community.value.boards[0].id
    }
    ownerMsg.value = '版块已创建'
  } catch (err) {
    ownerMsg.value = err instanceof Error ? err.message : '创建失败'
  } finally {
    boardCreating.value = false
  }
}

async function toggleMembers() {
  membersOpen.value = !membersOpen.value
  if (membersOpen.value && members.value.length === 0) {
    try {
      const data = await communityApi.members(cid, 1, 50)
      members.value = data.items
    } catch (e) {
      toast(e instanceof Error ? e.message : '加载成员失败', 'error')
    }
  }
}

async function toggleRequests() {
  requestsOpen.value = !requestsOpen.value
  if (requestsOpen.value && requests.value.length === 0) {
    await loadRequests()
  }
}

async function loadRequests() {
  try {
    const data = await communityApi.joinRequests(cid, 1, 50)
    requests.value = data.items
  } catch (e) {
    toast(e instanceof Error ? e.message : '加载申请失败', 'error')
  }
}

async function handleRequest(r: JoinRequestItem, approve: boolean) {
  try {
    await communityApi.handleJoinRequest(cid, r.id, approve)
    requests.value = requests.value.filter((x) => x.id !== r.id)
    community.value = await communityApi.get(cid)
    ownerMsg.value = approve ? '已通过申请' : '已驳回申请'
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

function memberTypeName(t: number): string {
  return t === 0 ? '频道主' : t === 1 ? '管理员' : '成员'
}

async function onDissolve() {
  if (!(await confirmDialog('解散频道', '确定解散该频道？此操作不可撤销！'))) return
  try {
    await communityApi.dissolve(cid)
    router.push('/discover')
  } catch (e) {
    toast(e instanceof Error ? e.message : '解散失败', 'error')
  }
}
</script>

<style scoped>
.detail {
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
.state {
  padding: var(--sp-6) 0;
  text-align: center;
  color: var(--text-3);
}
.panel {
  margin-top: var(--sp-4);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: var(--sp-4);
}
.head-panel .profile {
  margin: 0;
  color: var(--text-2);
}
.cover {
  height: 110px;
  border-radius: var(--radius-card);
  background-size: cover;
  background-position: center;
  margin: calc(-1 * var(--sp-4)) calc(-1 * var(--sp-4)) var(--sp-4);
}
.head-title-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  margin-bottom: var(--sp-2);
}
.head-avatar {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  object-fit: cover;
  border: 1px solid var(--border);
}
.head-name {
  margin: 0;
  font-size: var(--fs-page);
  font-weight: 600;
}
.meta {
  margin-top: var(--sp-3);
  display: flex;
  gap: var(--sp-4);
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.actions {
  margin-top: var(--sp-4);
  display: flex;
  gap: var(--sp-2);
}
.board-tabs {
  display: flex;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
.no-board {
  color: var(--text-3);
  font-size: var(--fs-caption);
}
.board-desc {
  margin-top: var(--sp-3);
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.empty-block {
  margin-top: var(--sp-3);
}
.owner-panel .panel-title {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
}
.panel-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-3);
}
.owner-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-2) 0;
  flex-wrap: wrap;
}
.owner-label {
  width: 72px;
  font-size: var(--fs-caption);
  color: var(--text-2);
}
.owner-hint {
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.status-select {
  width: 120px;
}
.msg {
  margin: var(--sp-2) 0 0;
  font-size: var(--fs-caption);
  color: var(--success);
}
.board-input {
  flex: 1;
  min-width: 120px;
}
.upload-label {
  display: inline-flex;
  align-items: center;
  height: 32px;
  padding: 0 var(--sp-3);
  border: 1px solid var(--td-component-border);
  border-radius: var(--td-radius-default);
  background: var(--td-bg-color-container);
  color: var(--td-text-color-primary);
  font-size: var(--fs-caption);
  cursor: pointer;
}
.upload-label:hover {
  border-color: var(--td-brand-color);
  color: var(--td-brand-color);
}
.manage-list {
  margin: var(--sp-1) 0 var(--sp-2) 96px;
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}
.manage-item {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-1) 0;
  font-size: var(--fs-caption);
  border-bottom: 1px dashed var(--border);
}
.manage-item:last-child {
  border-bottom: none;
}
.manage-name {
  font-weight: 600;
}
.manage-type,
.manage-time {
  color: var(--text-3);
}
.manage-empty {
  color: var(--text-3);
  font-size: var(--fs-caption);
}
.feed-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
}
.feed-list {
  margin: var(--sp-3) 0 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.load-more {
  margin-top: var(--sp-3);
}
.topic-panel .panel-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-2);
}
.topic-panel .panel-title {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
}
.topic-toolbar {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.topic-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}
.topic-item {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) 0;
  border-bottom: 1px dashed var(--border);
}
.topic-item:last-child {
  border-bottom: none;
}
.topic-name {
  color: #8a6d1a;
  background: #fff7e6;
  border-radius: 4px;
  padding: 2px 8px;
  font-size: var(--fs-body);
}
.topic-count {
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.topic-ops {
  margin-left: auto;
  display: flex;
  gap: var(--sp-1);
}
.topic-form {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
/* ===== 三栏宽屏工作台（桌面 ≥1024px） ===== */
.detail.wb {
  max-width: none;
  margin: 0;
  padding: 0;
}
.wb {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr) 300px;
  height: calc(100vh - var(--nav-height));
  min-height: 0;
  border-top: 1px solid var(--border);
}
.wb-left {
  border-right: 1px solid var(--border);
  background: var(--surface-2);
  overflow-y: auto;
  padding: var(--sp-3);
}
.wb-main {
  overflow-y: auto;
  padding: var(--sp-4);
}
.wb-right {
  border-left: 1px solid var(--border);
  background: var(--surface-2);
  overflow-y: auto;
  padding: var(--sp-3);
}
.wb-rail-title {
  font-size: var(--fs-caption);
  color: var(--text-3);
  font-weight: 600;
  letter-spacing: 0.05em;
  margin: var(--sp-3) 0 var(--sp-2);
}
.wb-rail-title:first-child {
  margin-top: 0;
}
.wb-channels {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.wb-channel {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: var(--radius-control);
  color: var(--text-2);
  text-decoration: none;
}
.wb-channel:hover {
  background: var(--surface);
}
.wb-channel.active {
  background: var(--brand-weak);
  color: var(--brand);
  font-weight: 600;
}
.wb-channel-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.wb-boards {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.wb-board {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 8px;
  border: none;
  background: transparent;
  color: var(--text-2);
  border-radius: var(--radius-control);
  text-align: left;
  cursor: pointer;
}
.wb-board:hover {
  background: var(--surface);
}
.wb-board.active {
  background: var(--brand-weak);
  color: var(--brand);
  font-weight: 600;
}
.wb-board-hash {
  opacity: 0.5;
}
.wb-channel-head {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-3);
  margin-bottom: var(--sp-4);
}
.wb-avatar {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-control);
  object-fit: cover;
}
.wb-head-main {
  flex: 1;
  min-width: 0;
}
.wb-head-name {
  font-size: var(--fs-page);
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.wb-profile {
  margin: 4px 0 0;
  color: var(--text-2);
  line-height: 1.6;
}
.wb-meta {
  margin-top: 4px;
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.wb-actions {
  display: flex;
  gap: var(--sp-2);
}
.wb-feed .feed-toolbar {
  margin-bottom: var(--sp-3);
}
.wb-panel {
  padding: var(--sp-2) 0;
}
.wb-empty {
  color: var(--text-3);
  font-size: var(--fs-caption);
}
.hot-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.hot-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  text-align: left;
  padding: 8px;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-control);
  background: var(--surface);
  cursor: pointer;
}
.hot-item:hover {
  border-color: var(--brand);
}
.hot-title {
  font-size: var(--fs-body);
  color: var(--text-1);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.hot-meta {
  font-size: var(--fs-caption);
  color: var(--text-3);
}
</style>
