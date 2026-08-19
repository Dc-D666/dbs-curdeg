<template>
  <main class="detail-page">
    <header class="page-header">
      <router-link :to="`/c/${post?.community_id ?? ''}`" class="back">← 返回</router-link>
      <h1 class="page-title">帖子</h1>
    </header>

    <div v-if="loading" class="state">加载中…</div>

    <template v-else-if="post">
      <section class="panel post-panel">
        <div class="post-head">
          <h2 class="post-title">
            {{ post.title }}
            <span v-if="post.is_top" class="tag tag-top">置顶</span>
            <span v-if="post.is_essence" class="tag tag-essence">精华</span>
          </h2>
          <div class="post-meta">
            <span class="author">{{ post.author_nickname }}</span>
            <span>{{ post.community_name }} · {{ post.board_name }}</span>
            <span>{{ post.created_at.slice(0, 16) }}</span>
          </div>
        </div>

        <div class="post-body">
          <p v-for="(seg, i) in textSegments" :key="i" class="post-text">{{ seg }}</p>
          <div v-if="post.images.length" class="post-images">
            <img v-for="(img, i) in post.images" :key="img" :src="img" alt="" @click="previewIndex = i" />
          </div>
        </div>

        <div class="post-actions">
          <button class="btn-ghost" :class="{ liked: post.is_liked }" @click="toggleLike">
            {{ post.is_liked ? '已赞' : '点赞' }} {{ post.like_count }}
          </button>
          <button class="btn-ghost" :class="{ followed: post.is_followed }" @click="toggleFollow">
            {{ post.is_followed ? '已关注' : '关注频道' }}
          </button>
          <span class="action-note">{{ post.comment_count }} 评论</span>
        </div>

        <div v-if="canManage" class="manage-row">
          <button class="btn-ghost btn-sm" @click="onToggleTop">{{ post.is_top ? '取消置顶' : '置顶' }}</button>
          <button class="btn-ghost btn-sm" @click="onToggleEssence">{{ post.is_essence ? '取消精华' : '设精华' }}</button>
          <button class="btn-ghost btn-sm danger" @click="onDeletePost">删除帖子</button>
        </div>
      </section>

      <section class="panel comment-panel">
        <h3 class="panel-title">评论</h3>

        <div v-if="replyTarget" class="reply-banner">
          回复 {{ replyTarget.nickname }}
          <button class="reply-cancel" @click="replyTarget = null">取消</button>
        </div>
        <div class="comment-input-row">
          <input
            v-model="commentInput"
            class="input"
            :placeholder="replyTarget ? `回复 ${replyTarget.nickname}…` : '写下你的评论…'"
            maxlength="2000"
            @keyup.enter="submitComment"
          />
          <button class="btn-primary btn-sm" :disabled="sending" @click="submitComment">发送</button>
        </div>

        <p v-if="commentsLoading && comments.length === 0" class="state">加载中…</p>
        <p v-else-if="comments.length === 0" class="state">暂无评论</p>

        <ul v-else class="comment-list">
          <li v-for="c in comments" :key="c.id" class="comment-item">
            <div class="comment-head">
              <span class="author">{{ c.author_nickname }}</span>
              <span class="comment-time">{{ c.created_at.slice(5, 16) }}</span>
              <button v-if="canDeleteComment(c)" class="comment-del" @click="deleteComment(c.id)">删除</button>
            </div>
            <p class="comment-content">{{ c.content }}</p>
            <div class="comment-ops">
              <button class="op-btn" :class="{ liked: c.is_liked }" @click="toggleCommentLike(c)">
                {{ c.is_liked ? '已赞' : '赞' }} {{ c.like_count }}
              </button>
              <button class="op-btn" @click="setReplyTarget(c)">回复</button>
              <button class="op-btn" @click="toggleReplies(c)">
                {{ replyMap.get(c.id)?.expanded ? '收起' : `楼中楼${replyMap.get(c.id)?.total ? ' ' + replyMap.get(c.id)?.total : ''}` }}
              </button>
            </div>

            <div v-if="replyMap.get(c.id)?.expanded" class="replies">
              <div v-for="r in replyMap.get(c.id)?.items ?? []" :key="r.id" class="reply-item">
                <span class="reply-author">{{ r.author_nickname }}</span>
                <span v-if="r.reply_to_nickname" class="reply-to">回复 {{ r.reply_to_nickname }}</span>
                <span class="reply-content">{{ r.content }}</span>
                <button v-if="canDeleteComment(r)" class="comment-del" @click="deleteComment(r.id)">删除</button>
                <span class="reply-time">{{ r.created_at.slice(5, 16) }}</span>
              </div>
              <button
                v-if="(replyMap.get(c.id)?.items.length ?? 0) < (replyMap.get(c.id)?.total ?? 0)"
                class="op-btn"
                @click="loadMoreReplies(c)"
              >加载更多回复</button>
            </div>
          </li>
        </ul>

        <button
          v-if="comments.length < commentTotal"
          class="btn-ghost load-more"
          :disabled="commentsLoading"
          @click="loadComments(commentPage + 1)"
        >{{ commentsLoading ? '加载中…' : '加载更多评论' }}</button>
      </section>

      <div v-if="previewIndex !== null && post.images[previewIndex]" class="preview-mask" @click="previewIndex = null">
        <img :src="post.images[previewIndex]" alt="" />
      </div>
    </template>

    <div v-else class="state">帖子不存在</div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { communityApi } from '@/api/community'
import { postApi, type CommentItem, type PostItem } from '@/api/post'
import { tokenStore } from '@/api/http'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const pid = Number(route.params.id)
const auth = useAuthStore()

const post = ref<PostItem | null>(null)
const loading = ref(true)
const myMemberType = ref<number | null>(null)
const previewIndex = ref<number | null>(null)

// 评论
const comments = ref<CommentItem[]>([])
const commentPage = ref(0)
const commentTotal = ref(0)
const commentsLoading = ref(false)
const commentInput = ref('')
const sending = ref(false)
const replyTarget = ref<{ id: number; nickname: string } | null>(null)

interface ReplyState {
  items: CommentItem[]
  page: number
  total: number
  loading: boolean
  expanded: boolean
}
const replyMap = ref(new Map<number, ReplyState>())

const textSegments = computed(() =>
  (post.value?.rich_content ?? [])
    .filter((s) => s.type === 1 && s.text)
    .map((s) => s.text as string),
)
const canManage = computed(() => {
  const p = post.value
  if (!p) return false
  if (!tokenStore.access) return false
  return p.author_id === auth.user?.id || myMemberType.value === 0
})

onMounted(async () => {
  try {
    post.value = await postApi.get(pid)
    const me = tokenStore.access ? await communityApi.get(post.value.community_id).catch(() => null) : null
    myMemberType.value = me?.my_member_type ?? null
  } catch (e) {
    post.value = null
  } finally {
    loading.value = false
  }
  loadComments(1)
})

async function loadComments(page: number) {
  if (commentsLoading.value) return
  commentsLoading.value = true
  try {
    const data = await postApi.comments(pid, page)
    comments.value = page === 1 ? data.items : [...comments.value, ...data.items]
    commentPage.value = page
    commentTotal.value = data.total
  } catch (e) {
    alert(e instanceof Error ? e.message : '加载评论失败')
  } finally {
    commentsLoading.value = false
  }
}

function requireLogin(): boolean {
  if (tokenStore.access) return true
  window.location.href = '/login'
  return false
}

async function toggleLike() {
  if (!post.value || !requireLogin()) return
  const p = post.value
  if (p.is_liked) {
    const r = await postApi.unlike(p.id)
    p.is_liked = false
    p.like_count = r.count
  } else {
    const r = await postApi.like(p.id)
    p.is_liked = true
    p.like_count = r.count
  }
}

async function toggleFollow() {
  if (!post.value || !requireLogin()) return
  const p = post.value
  if (p.is_followed) {
    await postApi.unfollow(p.community_id)
    p.is_followed = false
  } else {
    await postApi.follow(p.community_id)
    p.is_followed = true
  }
}

async function submitComment() {
  if (!post.value || !requireLogin()) return
  const text = commentInput.value.trim()
  if (!text) return
  if (sending.value) return
  sending.value = true
  try {
    if (replyTarget.value) {
      await postApi.createReply(replyTarget.value.id, text)
      const c = comments.value.find((x) => x.id === replyTarget.value!.id)
      if (c) {
        const st = ensureReplyState(c)
        st.total += 1
        await refreshReplies(c)
        st.expanded = true
      }
    } else {
      await postApi.createComment(pid, text)
      if (post.value) post.value.comment_count += 1
      await loadComments(1)
    }
    commentInput.value = ''
    replyTarget.value = null
  } catch (e) {
    alert(e instanceof Error ? e.message : '发送失败')
  } finally {
    sending.value = false
  }
}

function setReplyTarget(c: CommentItem) {
  if (!requireLogin()) return
  replyTarget.value = { id: c.id, nickname: c.author_nickname }
}

function ensureReplyState(c: CommentItem): ReplyState {
  let st = replyMap.value.get(c.id)
  if (!st) {
    st = { items: [], page: 0, total: 0, loading: false, expanded: false }
    replyMap.value.set(c.id, st)
  }
  return st
}

async function refreshReplies(c: CommentItem) {
  const st = ensureReplyState(c)
  const data = await postApi.replies(c.id, 1)
  st.items = data.items
  st.page = 1
  st.total = data.total
}

async function toggleReplies(c: CommentItem) {
  const st = ensureReplyState(c)
  st.expanded = !st.expanded
  if (st.expanded && st.items.length === 0) {
    st.loading = true
    try {
      await refreshReplies(c)
    } finally {
      st.loading = false
    }
  }
}

async function loadMoreReplies(c: CommentItem) {
  const st = ensureReplyState(c)
  if (st.loading) return
  st.loading = true
  try {
    const data = await postApi.replies(c.id, st.page + 1)
    st.items = [...st.items, ...data.items]
    st.page += 1
    st.total = data.total
  } catch (e) {
    alert(e instanceof Error ? e.message : '加载失败')
  } finally {
    st.loading = false
  }
}

async function toggleCommentLike(c: CommentItem) {
  if (!requireLogin()) return
  if (c.is_liked) {
    const r = await postApi.unlike(undefined, c.id)
    c.is_liked = false
    c.like_count = r.count
  } else {
    const r = await postApi.like(undefined, c.id)
    c.is_liked = true
    c.like_count = r.count
  }
}

function canDeleteComment(c: CommentItem): boolean {
  if (!tokenStore.access) return false
  return c.author_id === auth.user?.id || myMemberType.value === 0
}

async function deleteComment(commentId: number) {
  if (!confirm('确定删除该评论？')) return
  try {
    await postApi.deleteComment(commentId)
    if (post.value) post.value.comment_count = Math.max(0, post.value.comment_count - 1)
    await loadComments(1)
  } catch (e) {
    alert(e instanceof Error ? e.message : '删除失败')
  }
}

async function onToggleTop() {
  if (!post.value) return
  post.value = await postApi.setTop(post.value.id, !post.value.is_top)
}

async function onToggleEssence() {
  if (!post.value) return
  post.value = await postApi.setEssence(post.value.id, !post.value.is_essence)
}

async function onDeletePost() {
  if (!post.value || !confirm('确定删除该帖子？')) return
  try {
    await postApi.remove(post.value.id)
    router.push(`/c/${post.value.community_id}`)
  } catch (e) {
    alert(e instanceof Error ? e.message : '删除失败')
  }
}
</script>

<style scoped>
.detail-page {
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
.panel {
  margin-top: var(--sp-4);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: var(--sp-4);
}
.post-title {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
  line-height: 1.4;
}
.post-meta {
  margin-top: var(--sp-2);
  display: flex;
  gap: var(--sp-3);
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.author {
  color: var(--brand);
}
.post-body {
  margin-top: var(--sp-4);
}
.post-text {
  margin: 0 0 var(--sp-2);
  font-size: var(--fs-body);
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}
.post-images {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
  margin-top: var(--sp-2);
}
.post-images img {
  max-width: 100%;
  max-height: 320px;
  border-radius: var(--radius-btn);
  cursor: zoom-in;
}
.post-actions {
  margin-top: var(--sp-4);
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.action-note {
  margin-left: auto;
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.manage-row {
  margin-top: var(--sp-3);
  display: flex;
  gap: var(--sp-2);
  border-top: 1px solid var(--border);
  padding-top: var(--sp-3);
}
.btn-ghost {
  height: 36px;
  padding: 0 var(--sp-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-btn);
  background: var(--bg-card);
  color: var(--text-1);
  font-size: var(--fs-body);
  cursor: pointer;
}
.btn-ghost.liked {
  color: var(--brand);
  border-color: var(--brand);
}
.btn-ghost.followed {
  color: var(--brand);
  border-color: var(--brand);
}
.btn-ghost.danger {
  color: var(--danger);
  border-color: var(--danger);
}
.btn-sm {
  height: 30px;
  font-size: var(--fs-caption);
}
.btn-primary {
  height: 36px;
  padding: 0 var(--sp-3);
  border: none;
  border-radius: var(--radius-btn);
  background: var(--brand);
  color: #fff;
  font-size: var(--fs-body);
  cursor: pointer;
}
.btn-primary:disabled {
  background: var(--text-3);
  cursor: not-allowed;
}
.tag {
  font-size: var(--fs-caption);
  border-radius: 4px;
  padding: 1px 6px;
  margin-left: var(--sp-1);
}
.tag-top {
  color: var(--danger);
  border: 1px solid var(--danger);
}
.tag-essence {
  color: #b8860b;
  border: 1px solid #b8860b;
}
.comment-panel .panel-title {
  margin: 0 0 var(--sp-3);
  font-size: var(--fs-title);
  font-weight: 600;
}
.reply-banner {
  margin-bottom: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-btn);
  background: var(--brand-weak);
  color: var(--brand);
  font-size: var(--fs-caption);
}
.reply-cancel {
  margin-left: var(--sp-2);
  border: none;
  background: none;
  color: var(--text-3);
  cursor: pointer;
}
.comment-input-row {
  display: flex;
  gap: var(--sp-2);
}
.comment-input-row .input {
  flex: 1;
  height: 36px;
  padding: 0 var(--sp-3);
  font-size: var(--fs-body);
  color: var(--text-1);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-btn);
  outline: none;
}
.comment-input-row .input:focus {
  border-color: var(--brand);
}
.comment-list {
  margin: var(--sp-3) 0 0;
  padding: 0;
  list-style: none;
}
.comment-item {
  padding: var(--sp-3) 0;
  border-bottom: 1px solid var(--border);
}
.comment-item:last-child {
  border-bottom: none;
}
.comment-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  font-size: var(--fs-caption);
}
.comment-time {
  color: var(--text-3);
}
.comment-del {
  margin-left: auto;
  border: none;
  background: none;
  color: var(--danger);
  font-size: var(--fs-caption);
  cursor: pointer;
}
.comment-content {
  margin: var(--sp-1) 0 0;
  font-size: var(--fs-body);
  line-height: 1.6;
  word-break: break-word;
}
.comment-ops {
  margin-top: var(--sp-1);
  display: flex;
  gap: var(--sp-3);
}
.op-btn {
  border: none;
  background: none;
  color: var(--text-3);
  font-size: var(--fs-caption);
  cursor: pointer;
}
.op-btn.liked {
  color: var(--brand);
}
.replies {
  margin: var(--sp-2) 0 0 var(--sp-4);
  padding: var(--sp-2) var(--sp-3);
  border-left: 2px solid var(--border);
  background: var(--bg-2, #f7f8fa);
  border-radius: 0 var(--radius-btn) var(--radius-btn) 0;
}
.reply-item {
  padding: var(--sp-1) 0;
  font-size: var(--fs-caption);
  line-height: 1.5;
  word-break: break-word;
}
.reply-author {
  color: var(--brand);
}
.reply-to {
  color: var(--text-3);
}
.reply-time {
  margin-left: var(--sp-2);
  color: var(--text-3);
}
.load-more {
  margin-top: var(--sp-3);
  width: 100%;
  justify-content: center;
}
.preview-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  cursor: zoom-out;
}
.preview-mask img {
  max-width: 92vw;
  max-height: 92vh;
  border-radius: var(--radius-btn);
}
</style>
