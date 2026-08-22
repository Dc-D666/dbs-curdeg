<template>
  <main class="detail-page">
    <header class="page-header">
      <router-link :to="post ? `/c/${post.community_id}` : '/discover'" class="back">
        <ArrowLeftIcon class="back-icon" /> 返回
      </router-link>
      <h1 class="page-title">帖子</h1>
    </header>

    <div v-if="loading" class="state">加载中…</div>

    <template v-else-if="post">
      <section class="panel post-panel">
        <div class="post-head">
          <h2 class="post-title">
            {{ post.title }}
            <t-tag v-if="post.is_top" theme="danger" variant="light" size="small">置顶</t-tag>
            <t-tag v-if="post.is_essence" theme="warning" variant="light" size="small">精华</t-tag>
          </h2>
          <div class="post-meta">
            <router-link :to="`/users/${post.author_id}`" class="author">{{ post.author_nickname }}</router-link>
            <span>{{ post.community_name }} · {{ post.board_name }}</span>
            <span>{{ formatTime(post.created_at) }}</span>
          </div>
        </div>

        <div class="post-body">
          <template v-for="(seg, i) in richSegments" :key="i">
            <!-- 文本分片（含样式） -->
            <p v-if="seg.type === 1 && seg.text" class="post-text" :style="segStyle(seg.style)">
              <template v-for="(piece, j) in splitMarkdown(seg.text)" :key="j">
                <code v-if="piece.code" class="post-code">{{ piece.text }}</code>
                <span v-else :style="piece.style">{{ piece.text }}</span>
              </template>
            </p>
            <!-- @提及 -->
            <span v-else-if="seg.type === 2 && seg.at_user" class="post-at">
              <router-link :to="`/users/${seg.at_user.id}`">@{{ seg.at_user.nick }}</router-link>
            </span>
            <!-- 链接卡片 -->
            <a
              v-else-if="seg.type === 3 && seg.url"
              :href="seg.url"
              target="_blank"
              rel="noopener noreferrer"
              class="post-link"
            >{{ seg.display_text || seg.url }}</a>
            <!-- emoji -->
            <span v-else-if="seg.type === 4 && seg.emoji" class="post-emoji">{{ seg.emoji.char }}</span>
            <!-- 话题 -->
            <router-link
              v-else-if="seg.type === 8 && seg.topic"
              :to="`/c/${post.community_id}`"
              class="post-topic"
            >#{{ seg.topic.topic_name }}</router-link>
          </template>
          <div v-if="post.images.length" class="post-images">
            <img v-for="(img, i) in post.images" :key="img" :src="img" alt="" @click="previewIndex = i" />
          </div>
        </div>

        <div class="post-actions">
          <t-button variant="outline" :class="{ 't-active': post.is_liked }" @click="toggleLike">
            {{ post.is_liked ? '已赞' : '点赞' }} {{ post.like_count }}
          </t-button>
          <t-button variant="outline" :class="{ 't-active': post.is_favorited }" @click="toggleFavorite">
            {{ post.is_favorited ? '已收藏' : '收藏' }} {{ post.favorite_count }}
          </t-button>
          <t-button variant="outline" :class="{ 't-active': post.is_followed }" @click="toggleFollow">
            {{ post.is_followed ? '已关注' : '关注频道' }}
          </t-button>
          <t-button variant="outline" @click="sharePost">分享{{ post.share_count ? ' ' + post.share_count : '' }}</t-button>
          <t-button variant="outline" theme="danger" @click="openReport">举报</t-button>
          <span class="action-note">{{ post.comment_count }} 评论 · {{ post.view_count }} 浏览</span>
        </div>

        <div class="post-extra">
          <t-button v-if="!summary" variant="text" size="small" :loading="summarizing" @click="genSummary">
            <template #icon><AiIcon /></template> AI 摘要
          </t-button>
          <p v-else class="ai-summary"><b>AI 摘要：</b>{{ summary }}</p>
        </div>

        <div v-if="attachments.length" class="attachments">
          <div v-for="att in attachments" :key="att.id" class="attachment">
            <img v-if="att.media_type === 1" :src="att.url" class="att-img" alt="" @click="previewIndex = imagesPreview(att)" />
            <video v-else-if="att.media_type === 2" :src="att.url" class="att-video" controls />
            <a v-else :href="att.url" target="_blank" rel="noopener" class="att-file">📎 {{ attUrlName(att.url) }}</a>
            <t-button v-if="canManage" variant="text" size="small" theme="danger" class="att-del" @click="removeAttachment(att.id)">删除</t-button>
          </div>
        </div>

        <div v-if="canManage" class="manage-row">
          <t-button
            v-if="post.author_id === auth.user?.id"
            variant="outline"
            size="small"
            @click="router.push(`/c/${post.community_id}/boards/${post.board_id}/post/new?edit=${post.id}`)"
          >编辑</t-button>
          <t-button variant="outline" size="small" @click="onToggleTop">{{ post.is_top ? '取消置顶' : '置顶' }}</t-button>
          <t-button variant="outline" size="small" @click="onToggleEssence">{{ post.is_essence ? '取消精华' : '设精华' }}</t-button>
          <t-button variant="outline" size="small" theme="danger" @click="onDeletePost">删除帖子</t-button>
        </div>
      </section>

      <section class="panel comment-panel">
        <h3 class="panel-title">评论</h3>

        <div class="comment-input-row">
          <t-input
            v-model="commentInput"
            placeholder="写下你的评论…"
            maxlength="2000"
            @enter="submitComment"
          />
          <t-button theme="primary" size="small" :loading="sending" @click="submitComment">发送</t-button>
        </div>

        <p v-if="commentsLoading && comments.length === 0" class="state">加载中…</p>
        <EmptyState v-else-if="comments.length === 0" text="暂无评论" />

        <ul v-else class="comment-list">
          <li v-for="c in comments" :key="c.id" class="comment-item" :class="{ 'flash-highlight': flashId === c.id }">
            <div class="comment-head">
              <router-link :to="`/users/${c.author_id}`" class="author">{{ c.author_nickname }}</router-link>
              <span class="comment-time">{{ formatTime(c.created_at) }}</span>
              <t-button v-if="canDeleteComment(c)" variant="text" size="small" theme="danger" class="comment-del" @click="deleteComment(c.id)">删除</t-button>
            </div>
            <p class="comment-content">{{ c.content }}</p>
            <div class="comment-ops">
              <t-button variant="text" size="small" :class="{ 't-active': c.is_liked }" :disabled="interaction.isPending(`clike:${c.id}`)" @click="toggleCommentLike(c)">
                {{ c.is_liked ? '已赞' : '赞' }} {{ c.like_count }}
              </t-button>
              <t-button variant="text" size="small" @click="openReply(c)">回复</t-button>
              <t-button variant="text" size="small" @click="toggleReplies(c)">
                {{ replyMap.get(c.id)?.expanded ? '收起' : `楼中楼${replyMap.get(c.id)?.total ? ' ' + replyMap.get(c.id)?.total : ''}` }}
              </t-button>
            </div>

            <!-- 行内回复框：在对应评论下方就地展开，不打断阅读脉络 -->
            <div v-if="replyTarget?.commentId === c.id" ref="replyBoxEl" class="inline-reply">
              <t-input
                v-model="replyInput"
                :placeholder="`回复 ${replyTarget?.nickname}…`"
                maxlength="2000"
                @enter="submitReply"
              />
              <div class="inline-reply-ops">
                <t-button size="small" variant="text" @click="closeReply">取消</t-button>
                <t-button size="small" theme="primary" :loading="sending" @click="submitReply">发送</t-button>
              </div>
            </div>

            <div v-if="replyMap.get(c.id)?.expanded" class="replies">
              <div v-for="r in replyMap.get(c.id)?.items ?? []" :key="r.id" class="reply-item" :class="{ 'flash-highlight': flashId === r.id }">
                <span class="reply-author">{{ r.author_nickname }}</span>
                <span v-if="r.reply_to_nickname" class="reply-to">回复 {{ r.reply_to_nickname }}</span>
                <span class="reply-content">{{ r.content }}</span>
                <span class="reply-ops">
                  <t-button variant="text" size="small" @click="openReply(c, r)">回复</t-button>
                  <t-button v-if="canDeleteComment(r)" variant="text" size="small" theme="danger" class="comment-del" @click="deleteComment(r.id)">删除</t-button>
                </span>
                <span class="reply-time">{{ formatTime(r.created_at) }}</span>
              </div>
              <t-button
                v-if="(replyMap.get(c.id)?.items.length ?? 0) < (replyMap.get(c.id)?.total ?? 0)"
                variant="text"
                size="small"
                @click="loadMoreReplies(c)"
              >加载更多回复</t-button>
            </div>
          </li>
        </ul>

        <t-button
          v-if="comments.length < commentTotal"
          variant="outline"
          block
          class="load-more"
          :loading="commentsLoading"
          @click="loadComments(commentPage + 1)"
        >{{ commentsLoading ? '加载中…' : '加载更多评论' }}</t-button>
      </section>

      <div v-if="previewIndex !== null && post.images[previewIndex]" class="preview-mask" @click="previewIndex = null">
        <img :src="post.images[previewIndex]" alt="" />
      </div>
    </template>

    <div v-else class="state">帖子不存在</div>

    <!-- 举报弹窗 -->
    <t-dialog
      v-model:visible="reportDialog"
      header="举报内容"
      :confirm-btn="{ content: '提交举报', theme: 'danger', loading: reportSending }"
      cancel-btn="取消"
      @confirm="submitReport"
    >
      <t-select v-model="reportReason" class="report-select">
        <t-option value="违规" label="违规内容" />
        <t-option value="侵权" label="侵权" />
        <t-option value="垃圾信息" label="垃圾信息" />
        <t-option value="其他" label="其他" />
      </t-select>
      <t-textarea
        v-model="reportDetail"
        :autosize="{ minRows: 3, maxRows: 6 }"
        maxlength="500"
        placeholder="补充说明（选填）"
        class="report-detail"
      />
    </t-dialog>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { AiIcon, ArrowLeftIcon } from 'tdesign-icons-vue-next'
import { communityApi } from '@/api/community'
import EmptyState from '@/components/EmptyState.vue'
import { postApi, type AttachmentItem, type CommentItem, type PostItem } from '@/api/post'
import { tokenStore } from '@/api/http'
import { request } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { useInteractionStore } from '@/stores/interaction'
import { toast } from '@/utils/toast'
import { confirmDialog } from '@/utils/confirm'
import { formatTime } from '@/utils/time'

const route = useRoute()
const router = useRouter()
const pid = Number(route.params.id)
const auth = useAuthStore()
const interaction = useInteractionStore()

const post = ref<PostItem | null>(null)
const loading = ref(true)
const myMemberType = ref<number | null>(null)
const previewIndex = ref<number | null>(null)

// 收藏 / 举报 / AI 摘要 / 附件（P0）
const attachments = ref<AttachmentItem[]>([])
const summary = ref('')
const summarizing = ref(false)
const reportDialog = ref(false)
const reportSending = ref(false)
const reportReason = ref('违规')
const reportDetail = ref('')

// 评论
const comments = ref<CommentItem[]>([])
const commentPage = ref(0)
const commentTotal = ref(0)
const commentsLoading = ref(false)
const commentInput = ref('')
const sending = ref(false)
const replyInput = ref('')
// 行内回复目标：commentId 为楼中楼挂载点（顶层评论），replyToUserId 用于「回复 @某人」
const replyTarget = ref<{ commentId: number; nickname: string; replyToUserId?: number } | null>(null)
const replyBoxEl = ref<HTMLDivElement | null>(null)
// 新评论/新回复追加后的闪烁高亮 id
const flashId = ref<number | null>(null)

interface ReplyState {
  items: CommentItem[]
  page: number
  total: number
  loading: boolean
  expanded: boolean
}
const replyMap = ref(new Map<number, ReplyState>())

const richSegments = computed(() => post.value?.rich_content ?? [])

interface SegStyleLike {
  bold?: boolean
  italic?: boolean
  strike?: boolean
  code?: boolean
  color?: string
  bg?: string
  size?: string
}

function segStyle(s?: SegStyleLike): Record<string, string> {
  const css: Record<string, string> = {}
  if (s?.bold) css.fontWeight = 'bold'
  if (s?.italic) css.fontStyle = 'italic'
  if (s?.strike) css.textDecorationLine = 'line-through'
  if (s?.color) css.color = s.color
  if (s?.bg) css.backgroundColor = s.bg
  if (s?.size) css.fontSize = s.size
  return css
}

function splitMarkdown(text: string): Array<{ text: string; code?: boolean; style: Record<string, string> }> {
  // 渲染端解析 markdown 快捷语法（**加粗** *斜体* `代码` ~~删除线~~）
  const parts: Array<{ text: string; code?: boolean; style: Record<string, string> }> = []
  const re = /(\*\*[^*]+\*\*|\*[^*\n]+\*|`[^`]+`|~~[^~]+~~)/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(text))) {
    if (m.index > last) parts.push({ text: text.slice(last, m.index), style: {} })
    const raw = m[0]
    if (raw.startsWith('**')) parts.push({ text: raw.slice(2, -2), style: { fontWeight: 'bold' } })
    else if (raw.startsWith('~~')) parts.push({ text: raw.slice(2, -2), style: { textDecorationLine: 'line-through' } })
    else if (raw.startsWith('`')) parts.push({ text: raw.slice(1, -1), code: true, style: {} })
    else if (raw.startsWith('*')) parts.push({ text: raw.slice(1, -1), style: { fontStyle: 'italic' } })
    last = m.index + raw.length
  }
  if (last < text.length) parts.push({ text: text.slice(last), style: {} })
  return parts
}
const canManage = computed(() => {
  const p = post.value
  if (!p) return false
  if (!tokenStore.access) return false
  return p.author_id === auth.user?.id || myMemberType.value === 0 || myMemberType.value === 1
})

onMounted(async () => {
  try {
    post.value = await postApi.get(pid)
    const me = tokenStore.access ? await communityApi.get(post.value.community_id).catch(() => null) : null
    myMemberType.value = me?.my_member_type ?? null
    postApi.attachments(pid).then((list) => (attachments.value = list)).catch(() => {})
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
    toast(e instanceof Error ? e.message : '加载评论失败', 'error')
  } finally {
    commentsLoading.value = false
  }
}

function requireLogin(): boolean {
  if (tokenStore.access) return true
  router.push(`/login?redirect=${encodeURIComponent(route.fullPath)}`)
  return false
}

async function toggleLike() {
  if (!post.value || !requireLogin()) return
  const p = post.value
  const key = `like:${p.id}`
  if (interaction.isPending(key)) return
  const wasLiked = p.is_liked
  const prevCount = p.like_count
  try {
    await interaction.run(key, {
      apply: () => {
        p.is_liked = !wasLiked
        p.like_count = Math.max(0, prevCount + (wasLiked ? -1 : 1))
      },
      rollback: () => {
        p.is_liked = wasLiked
        p.like_count = prevCount
      },
      request: () => (wasLiked ? postApi.unlike(p.id) : postApi.like(p.id)),
      onSuccess: (r) => {
        p.like_count = r.count
      },
    })
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

async function toggleFollow() {
  if (!post.value || !requireLogin()) return
  const p = post.value
  const key = `follow:${p.community_id}`
  if (interaction.isPending(key)) return
  const wasFollowed = p.is_followed
  try {
    await interaction.run(key, {
      apply: () => {
        p.is_followed = !wasFollowed
      },
      rollback: () => {
        p.is_followed = wasFollowed
      },
      request: () => (wasFollowed ? postApi.unfollow(p.community_id) : postApi.follow(p.community_id)),
      onSuccess: (r) => {
        p.is_followed = r.followed
      },
    })
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

/** 分享：生成短链并复制（阶段 5）。 */
async function sharePost() {
  if (!post.value || !requireLogin()) return
  try {
    const { code } = await request<{ code: string }>({
      url: '/shares',
      method: 'POST',
      data: { target_type: 2, target_id: post.value.id },
    })
    const url = `${window.location.origin}/s/${code}`
    try {
      await navigator.clipboard.writeText(url)
      toast('短链已复制，发送给好友即可打开', 'success')
    } catch {
      // 剪贴板不可用（非 https / 权限）：提示手动复制
      toast(`请手动复制：${url}`, 'info')
    }
  } catch (e) {
    toast(e instanceof Error ? e.message : '生成短链失败', 'error')
  }
}

/** 收藏 / 取消收藏（P0）。 */
async function toggleFavorite() {
  if (!post.value || !requireLogin()) return
  const p = post.value
  const key = `favorite:${p.id}`
  if (interaction.isPending(key)) return
  const wasFavorited = p.is_favorited
  const prevCount = p.favorite_count
  try {
    await interaction.run(key, {
      apply: () => {
        p.is_favorited = !wasFavorited
        p.favorite_count = Math.max(0, prevCount + (wasFavorited ? -1 : 1))
      },
      rollback: () => {
        p.is_favorited = wasFavorited
        p.favorite_count = prevCount
      },
      request: () => (wasFavorited ? postApi.unfavorite(p.id) : postApi.favorite(p.id)),
      onSuccess: (r) => {
        p.favorite_count = r.count
      },
    })
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

/** 打开举报弹窗。 */
function openReport() {
  if (!post.value || !requireLogin()) return
  reportDetail.value = ''
  reportReason.value = '违规'
  reportDialog.value = true
}

async function submitReport() {
  if (!post.value || reportSending.value) return
  reportSending.value = true
  try {
    await postApi.report({
      target_type: 1,
      target_id: post.value.id,
      reason_type: reportReason.value,
      detail: reportDetail.value,
    })
    toast('举报已提交，我们会尽快处理', 'success')
    reportDialog.value = false
  } catch (e) {
    toast(e instanceof Error ? e.message : '提交失败', 'error')
  } finally {
    reportSending.value = false
  }
}

/** AI 摘要（P0）。 */
async function genSummary() {
  if (!post.value || !requireLogin()) return
  summarizing.value = true
  try {
    const r = await postApi.aiSummary(post.value.id)
    summary.value = r.summary
  } catch (e) {
    toast(e instanceof Error ? e.message : '生成摘要失败', 'error')
  } finally {
    summarizing.value = false
  }
}

async function removeAttachment(attachmentId: number) {
  if (!(await confirmDialog('删除附件', '确定删除该附件？'))) return
  try {
    await postApi.deleteAttachment(attachmentId)
    attachments.value = attachments.value.filter((a) => a.id !== attachmentId)
    toast('附件已删除')
  } catch (e) {
    toast(e instanceof Error ? e.message : '删除失败', 'error')
  }
}

function imagesPreview(att: AttachmentItem): number | null {
  // 附件图片点击预览：若在 post.images 中存在则复用索引
  const idx = post.value?.images.indexOf(att.url) ?? -1
  return idx >= 0 ? idx : null
}

function attUrlName(url: string): string {
  const seg = url.split('/')
  return seg[seg.length - 1] || '附件'
}

async function submitComment() {
  if (!post.value || !requireLogin()) return
  const text = commentInput.value.trim()
  if (!text || sending.value) return
  sending.value = true
  try {
    // 顶层评论：无刷新追加 + 高亮闪烁，保持当前阅读位置
    const item = await postApi.createComment(pid, text)
    if (post.value) post.value.comment_count += 1
    commentTotal.value += 1
    comments.value = [...comments.value, item]
    commentInput.value = ''
    flashItem(item.id)
  } catch (e) {
    toast(e instanceof Error ? e.message : '发送失败', 'error')
  } finally {
    sending.value = false
  }
}

/** 行内回复（楼中楼）：在对应评论下方直接发送，成功后无刷新追加并高亮。 */
async function submitReply() {
  if (!post.value || !requireLogin()) return
  const t = replyTarget.value
  const text = replyInput.value.trim()
  if (!t || !text || sending.value) return
  sending.value = true
  try {
    const item = await postApi.createReply(t.commentId, text, t.replyToUserId)
    const c = comments.value.find((x) => x.id === t.commentId)
    if (c) {
      const st = ensureReplyState(c)
      st.items = [...st.items, item]
      st.total += 1
      st.expanded = true // 展开楼中楼让新回复可见
      flashItem(item.id)
    }
    replyInput.value = ''
    closeReply()
  } catch (e) {
    toast(e instanceof Error ? e.message : '发送失败', 'error')
  } finally {
    sending.value = false
  }
}

/** 新评论/回复闪烁高亮（1.6s 后自动移除）。 */
function flashItem(id: number) {
  flashId.value = id
  window.setTimeout(() => {
    if (flashId.value === id) flashId.value = null
  }, 1600)
}

/** 打开行内回复框（r 存在 = 回复楼中楼里的某条回复，默认回复该顶层评论）。 */
function openReply(c: CommentItem, r?: CommentItem) {
  if (!requireLogin()) return
  replyTarget.value = {
    commentId: c.id,
    nickname: r ? r.author_nickname : c.author_nickname,
    replyToUserId: r ? r.author_id : undefined,
  }
  replyInput.value = r ? `@${r.author_nickname} ` : ''
  nextTick(() => {
    replyBoxEl.value?.querySelector('input')?.focus()
  })
}

function closeReply() {
  replyTarget.value = null
  replyInput.value = ''
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
    toast(e instanceof Error ? e.message : '加载失败', 'error')
  } finally {
    st.loading = false
  }
}

async function toggleCommentLike(c: CommentItem) {
  if (!requireLogin()) return
  const key = `clike:${c.id}`
  if (interaction.isPending(key)) return
  const wasLiked = c.is_liked
  const prevCount = c.like_count
  try {
    await interaction.run(key, {
      apply: () => {
        c.is_liked = !wasLiked
        c.like_count = Math.max(0, prevCount + (wasLiked ? -1 : 1))
      },
      rollback: () => {
        c.is_liked = wasLiked
        c.like_count = prevCount
      },
      request: () => (wasLiked ? postApi.unlike(undefined, c.id) : postApi.like(undefined, c.id)),
      onSuccess: (r) => {
        c.like_count = r.count
      },
    })
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

function canDeleteComment(c: CommentItem): boolean {
  if (!tokenStore.access) return false
  return c.author_id === auth.user?.id || myMemberType.value === 0 || myMemberType.value === 1
}

async function deleteComment(commentId: number) {
  if (!(await confirmDialog('删除评论', '确定删除该评论？'))) return
  try {
    await postApi.deleteComment(commentId)
    if (post.value) post.value.comment_count = Math.max(0, post.value.comment_count - 1)
    await loadComments(1)
  } catch (e) {
    toast(e instanceof Error ? e.message : '删除失败', 'error')
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
  if (!post.value || !(await confirmDialog('删除帖子', '确定删除该帖子？'))) return
  try {
    await postApi.remove(post.value.id)
    router.push(`/c/${post.value.community_id}`)
  } catch (e) {
    toast(e instanceof Error ? e.message : '删除失败', 'error')
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
  text-decoration: none;
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
.post-link {
  display: inline-block;
  margin: 0 0 var(--sp-2);
  padding: 6px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-btn);
  background: var(--bg-secondary);
  color: var(--brand);
  font-size: var(--fs-body);
  text-decoration: none;
  transition: border-color var(--anim-duration) var(--anim-ease);
}
.post-link:hover {
  border-color: var(--brand);
}
.post-at {
  margin-right: var(--sp-1);
}
.post-at a {
  color: var(--brand);
  background: var(--brand-weak);
  border-radius: 4px;
  padding: 0 3px;
  text-decoration: none;
}
.post-topic {
  display: inline-block;
  margin: 0 var(--sp-2) var(--sp-2) 0;
  color: #8a6d1a;
  background: #fff7e6;
  border-radius: 4px;
  padding: 0 6px;
  text-decoration: none;
  font-size: var(--fs-body);
}
.post-code {
  font-family: Consolas, Monaco, monospace;
  background: var(--bg-secondary);
  border-radius: 4px;
  padding: 0 4px;
  font-size: 0.92em;
}
.post-emoji {
  font-size: 18px;
  margin-right: 2px;
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
.post-extra {
  margin-top: var(--sp-2);
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-height: 24px;
}
.ai-summary {
  margin: 0;
  padding: 8px 12px;
  background: var(--brand-weak);
  border-radius: var(--radius-btn);
  font-size: var(--fs-caption);
  line-height: 1.6;
  color: var(--text-2);
}
.attachments {
  margin-top: var(--sp-3);
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
}
.attachment {
  position: relative;
  display: inline-flex;
}
.att-img {
  max-width: 180px;
  max-height: 180px;
  border-radius: var(--radius-btn);
  cursor: zoom-in;
}
.att-video {
  max-width: 260px;
  border-radius: var(--radius-btn);
  background: #000;
}
.att-file {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-btn);
  background: var(--bg-secondary);
  color: var(--brand);
  font-size: var(--fs-caption);
  text-decoration: none;
}
.att-del {
  position: absolute;
  top: -6px;
  right: -6px;
}
.report-select {
  width: 100%;
  margin-bottom: var(--sp-3);
}
.report-detail {
  width: 100%;
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
.t-active {
  color: var(--td-brand-color);
  border-color: var(--td-brand-color);
}
.t-active :deep(.t-button__text) {
  color: var(--td-brand-color);
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
.inline-reply {
  margin-top: var(--sp-2);
  padding: var(--sp-2);
  border: 1px solid var(--brand);
  border-radius: var(--radius-btn);
  background: var(--bg-card);
}
.inline-reply-ops {
  margin-top: var(--sp-2);
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-1);
}
.reply-ops {
  margin-left: var(--sp-2);
}
.reply-ops .comment-del {
  margin-left: 0;
}
.flash-highlight {
  animation: flash-bg 1.6s ease;
}
@keyframes flash-bg {
  0% {
    background: var(--brand-weak);
  }
  100% {
    background: transparent;
  }
}
.load-more {
  margin-top: var(--sp-3);
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
