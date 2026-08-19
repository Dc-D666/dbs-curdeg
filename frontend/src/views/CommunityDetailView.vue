<template>
  <main class="detail">
    <header class="page-header">
      <router-link to="/discover" class="back">← 发现</router-link>
      <h1 class="page-title">{{ community?.name || '频道' }}</h1>
      <span v-if="community?.is_member" class="tag tag-member">已加入</span>
    </header>

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="community">
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
            <button v-if="community.my_member_type !== 0" class="btn-ghost" @click="onLeave">退出频道</button>
          </template>
          <button v-else class="btn-primary" :disabled="joining" @click="onJoin">
            {{ joining ? '处理中…' : '加入频道' }}
          </button>
        </div>
      </section>

      <section class="panel">
        <div class="board-tabs" role="tablist">
          <button
            v-for="b in community.boards"
            :key="b.id"
            class="tab"
            :class="{ active: activeBoard === b.id }"
            @click="activeBoard = b.id"
          >
            {{ b.name }}
          </button>
          <span v-if="community.boards.length === 0" class="no-board">暂无版块</span>
        </div>
        <div v-if="activeBoardInfo" class="board-desc">{{ activeBoardInfo.description || '暂无版块描述' }}</div>
        <div v-else-if="community.boards.length === 0" class="empty-block">
          <p class="state">版块还未创建</p>
        </div>
      </section>

      <section v-if="activeBoardInfo" class="panel feed-panel">
        <div class="feed-toolbar">
          <div class="feed-tabs" role="tablist">
            <button class="tab" :class="{ active: feedSort === 'latest' }" @click="switchSort('latest')">最新</button>
            <button class="tab" :class="{ active: feedSort === 'hot' }" @click="switchSort('hot')">热门</button>
          </div>
          <router-link
            v-if="community.is_member"
            :to="`/c/${cid}/boards/${activeBoard}/post/new`"
            class="btn-primary btn-sm"
          >发帖</router-link>
        </div>

        <p v-if="feedLoading && feedItems.length === 0" class="state">加载中…</p>
        <p v-else-if="feedItems.length === 0" class="state">暂无帖子，来发第一帖吧</p>
        <div v-else class="feed-list">
          <FeedCard v-for="p in feedItems" :key="p.id" :post="p" />
        </div>
        <button v-if="feedHasMore" class="btn-ghost load-more" :disabled="feedLoading" @click="loadFeed()">
          {{ feedLoading ? '加载中…' : '加载更多' }}
        </button>
      </section>

      <section v-if="community.my_member_type === 0" class="panel owner-panel">
        <h3 class="panel-title">频道管理</h3>

        <div class="owner-row">
          <span class="owner-label">头像 / 封面</span>
          <label class="btn-ghost btn-sm">
            上传图片
            <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" @change="onCoverUpload" hidden />
          </label>
          <span class="owner-hint">同时设为头像与封面</span>
        </div>

        <div class="owner-row">
          <span class="owner-label">频道状态</span>
          <select v-model.number="statusForm.status" class="input status-select">
            <option :value="0">正常</option>
            <option :value="1">关闭</option>
          </select>
          <button class="btn-ghost btn-sm" @click="onStatusSave">保存</button>
        </div>

        <div class="owner-row">
          <span class="owner-label">创建版块</span>
          <input v-model.trim="boardForm.name" class="input board-input" placeholder="版块名称" maxlength="64" />
          <input v-model.trim="boardForm.description" class="input board-input" placeholder="简介（可选）" maxlength="255" />
          <button class="btn-ghost btn-sm" :disabled="boardCreating" @click="onCreateBoard">创建</button>
        </div>

        <div class="owner-row">
          <span class="owner-label">成员列表</span>
          <button class="btn-ghost btn-sm" @click="toggleMembers">{{ membersOpen ? '收起' : `${community.member_count} 人` }}</button>
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
          <button class="btn-ghost btn-sm" @click="toggleRequests">{{ requestsOpen ? '收起' : `${requests.length} 条待审` }}</button>
        </div>
        <div v-if="requestsOpen" class="manage-list">
          <div v-for="r in requests" :key="r.id" class="manage-item">
            <span class="manage-name">{{ r.user_nickname || r.username }}</span>
            <span class="manage-time">{{ r.created_at.slice(5, 16) }}</span>
            <button class="btn-ghost btn-sm" @click="handleRequest(r, true)">通过</button>
            <button class="btn-ghost btn-sm danger" @click="handleRequest(r, false)">驳回</button>
          </div>
          <p v-if="requests.length === 0" class="manage-empty">暂无待审申请</p>
        </div>

        <div class="owner-row">
          <span class="owner-label">解散频道</span>
          <button class="btn-ghost btn-sm danger" @click="onDissolve">解散</button>
        </div>

        <p v-if="ownerMsg" class="msg">{{ ownerMsg }}</p>
      </section>
    </div>
    <div v-else class="state">频道不存在</div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { communityApi, type Community, type JoinRequestItem, type Member } from '@/api/community'
import { postApi, type PostItem } from '@/api/post'
import FeedCard from '@/components/FeedCard.vue'
import { request, tokenStore } from '@/api/http'

const route = useRoute()
const router = useRouter()
const cid = Number(route.params.id)
const community = ref<Community | null>(null)
const loading = ref(true)
const joining = ref(false)
const activeBoard = ref<number | null>(null)
const ownerMsg = ref('')
const statusForm = reactive({ status: 0 })

// 管理面板
const boardForm = reactive({ name: '', description: '' })
const boardCreating = ref(false)
const membersOpen = ref(false)
const members = ref<Member[]>([])
const requestsOpen = ref(false)
const requests = ref<JoinRequestItem[]>([])

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
    alert(e instanceof Error ? e.message : '加载失败')
  } finally {
    feedLoading.value = false
  }
}

function switchSort(sort: 'latest' | 'hot') {
  if (feedSort.value === sort) return
  feedSort.value = sort
  loadFeed(true)
}

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
  } finally {
    loading.value = false
  }
})

async function onJoin() {
  if (!tokenStore.access) {
    window.location.href = `/login?redirect=${encodeURIComponent(route.fullPath)}`
    return
  }
  if (joining.value) return
  joining.value = true
  try {
    await communityApi.join(cid)
    community.value = await communityApi.get(cid)
  } catch (e) {
    alert(e instanceof Error ? e.message : '操作失败')
  } finally {
    joining.value = false
  }
}

async function onLeave() {
  if (!confirm('确定退出该频道？')) return
  try {
    await communityApi.leave(cid)
    community.value = await communityApi.get(cid)
  } catch (e) {
    alert(e instanceof Error ? e.message : '操作失败')
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
      alert(e instanceof Error ? e.message : '加载成员失败')
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
    alert(e instanceof Error ? e.message : '加载申请失败')
  }
}

async function handleRequest(r: JoinRequestItem, approve: boolean) {
  try {
    await communityApi.handleJoinRequest(cid, r.id, approve)
    requests.value = requests.value.filter((x) => x.id !== r.id)
    community.value = await communityApi.get(cid)
    ownerMsg.value = approve ? '已通过申请' : '已驳回申请'
  } catch (e) {
    alert(e instanceof Error ? e.message : '操作失败')
  }
}

function memberTypeName(t: number): string {
  return t === 0 ? '频道主' : t === 1 ? '管理员' : '成员'
}

async function onDissolve() {
  if (!confirm('确定解散该频道？此操作不可撤销！')) return
  try {
    await communityApi.dissolve(cid)
    router.push('/discover')
  } catch (e) {
    alert(e instanceof Error ? e.message : '解散失败')
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
.tab {
  height: 34px;
  padding: 0 var(--sp-4);
  border: 1px solid var(--border);
  border-radius: var(--radius-btn);
  background: var(--bg-card);
  color: var(--text-2);
  font-size: var(--fs-body);
  cursor: pointer;
  transition: all 0.15s;
}
.tab.active {
  border-color: var(--brand);
  color: var(--brand);
  background: var(--brand-weak);
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
.btn-primary {
  height: 36px;
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
  height: 36px;
  padding: 0 var(--sp-4);
  border: 1px solid var(--border);
  border-radius: var(--radius-btn);
  background: var(--bg-card);
  color: var(--text-1);
  font-size: var(--fs-body);
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  cursor: pointer;
}
.btn-sm {
  height: 32px;
  padding: 0 var(--sp-3);
  font-size: var(--fs-caption);
}
.owner-panel .panel-title {
  margin: 0 0 var(--sp-3);
  font-size: var(--fs-title);
  font-weight: 600;
}
.owner-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-2) 0;
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
  height: 32px;
  padding: 0 var(--sp-2);
  font-size: var(--fs-caption);
}
.msg {
  margin: var(--sp-2) 0 0;
  font-size: var(--fs-caption);
  color: var(--success);
}
.board-input {
  flex: 1;
  min-width: 0;
  height: 32px;
  padding: 0 var(--sp-2);
  font-size: var(--fs-caption);
  border: 1px solid var(--border);
  border-radius: var(--radius-btn);
  outline: none;
}
.board-input:focus {
  border-color: var(--brand);
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
.btn-ghost.danger {
  color: var(--danger);
  border-color: var(--danger);
}
.feed-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
}
.feed-tabs {
  display: flex;
  gap: var(--sp-2);
}
.feed-list {
  margin: var(--sp-3) 0 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.feed-item {
  padding: var(--sp-3) 0;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
}
.feed-item:last-child {
  border-bottom: none;
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
.tag-top {
  color: var(--danger);
  border-color: var(--danger);
}
.tag-essence {
  color: #b8860b;
  border-color: #b8860b;
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
  gap: var(--sp-3);
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.feed-time {
  margin-left: auto;
}
.load-more {
  margin-top: var(--sp-3);
  width: 100%;
  justify-content: center;
}
</style>
