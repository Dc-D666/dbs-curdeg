/** 帖子/评论/点赞/关注 API（阶段 3）。 */
import { request, type Page } from './http'

export interface SegStyle {
  bold?: boolean
  italic?: boolean
  strike?: boolean
  code?: boolean
  color?: string
  bg?: string
  size?: string
}

export interface RichSegment {
  type: number
  text?: string
  style?: SegStyle
  url?: string
  display_text?: string
  url_type?: number
  at_user?: { id: number; nick: string }
  emoji?: { id: string; pattern_id?: string; char: string }
  topic?: { topic_id: number; topic_name: string }
}

export interface PostItem {
  id: number
  community_id: number
  board_id: number
  author_id: number
  title: string
  post_type: number
  topic_id: number | null
  rich_content: RichSegment[]
  source_markdown: string
  images: string[]
  like_count: number
  comment_count: number
  view_count: number
  favorite_count: number
  share_count: number
  is_top: boolean
  is_essence: boolean
  status: number
  created_at: string
  author_nickname: string
  author_avatar: string
  community_name: string
  board_name: string
  is_liked: boolean
  is_favorited: boolean
  is_followed: boolean
  is_member: boolean
}

export interface FeedResult {
  items: PostItem[]
  next_cursor: string | null
  has_more: boolean
}

export interface CommentItem {
  id: number
  post_id: number
  author_id: number
  parent_id: number | null
  reply_to_user_id: number | null
  content: string
  like_count: number
  status: number
  created_at: string
  author_nickname: string
  author_avatar: string
  reply_to_nickname: string
  is_liked: boolean
}

export const postApi = {
  // 帖子流
  globalFeed(sort: 'latest' | 'hot' = 'latest', cursor?: string | null, pageSize = 20) {
    return request<FeedResult>({
      url: '/feed',
      params: { sort, cursor: cursor ?? undefined, page_size: pageSize },
    })
  },
  feed(cid: number, sort: 'latest' | 'hot' = 'latest', cursor?: string | null, pageSize = 20, boardId?: number | null) {
    return request<FeedResult>({
      url: `/communities/${cid}/feed`,
      params: { sort, board_id: boardId ?? undefined, cursor: cursor ?? undefined, page_size: pageSize },
    })
  },
  meFeed(cursor?: string | null, pageSize = 20) {
    return request<FeedResult>({ url: '/me/feed', params: { cursor: cursor ?? undefined, page_size: pageSize } })
  },
  myJoinedFeed(cursor?: string | null, pageSize = 20) {
    return request<FeedResult>({ url: '/me/joined-feed', params: { cursor: cursor ?? undefined, page_size: pageSize } })
  },
  // 他人主页「TA 的帖子」
  userPosts(userId: number, cursor?: string | null, pageSize = 20) {
    return request<FeedResult>({ url: `/users/${userId}/posts`, params: { cursor: cursor ?? undefined, page_size: pageSize } })
  },
  // 帖子
  get(id: number) {
    return request<PostItem>({ url: `/posts/${id}` })
  },
  create(cid: number, bid: number, data: { title: string; content?: string; rich_content?: RichSegment[]; images?: string[]; topic_id?: number }) {
    return request<PostItem>({ url: `/communities/${cid}/boards/${bid}/posts`, method: 'POST', data })
  },
  update(id: number, data: { title?: string; content?: string; rich_content?: RichSegment[]; images?: string[]; topic_id?: number }) {
    return request<PostItem>({ url: `/posts/${id}`, method: 'PUT', data })
  },
  remove(id: number) {
    return request<null>({ url: `/posts/${id}`, method: 'DELETE' })
  },
  setTop(id: number, isTop = true) {
    return request<PostItem>({ url: `/posts/${id}/top`, method: 'POST', params: { is_top: isTop } })
  },
  setEssence(id: number, isEssence = true) {
    return request<PostItem>({ url: `/posts/${id}/essence`, method: 'POST', params: { is_essence: isEssence } })
  },
  // 评论
  comments(postId: number, page = 1, pageSize = 20) {
    return request<Page<CommentItem>>({ url: `/posts/${postId}/comments`, params: { page, page_size: pageSize } })
  },
  createComment(postId: number, content: string) {
    return request<CommentItem>({ url: `/posts/${postId}/comments`, method: 'POST', data: { content } })
  },
  replies(commentId: number, page = 1, pageSize = 20) {
    return request<Page<CommentItem>>({ url: `/comments/${commentId}/replies`, params: { page, page_size: pageSize } })
  },
  createReply(commentId: number, content: string, replyToUserId?: number) {
    return request<CommentItem>({
      url: `/comments/${commentId}/replies`,
      method: 'POST',
      data: { content, ...(replyToUserId ? { reply_to_user_id: replyToUserId } : {}) },
    })
  },
  deleteComment(commentId: number) {
    return request<null>({ url: `/comments/${commentId}`, method: 'DELETE' })
  },
  // 点赞 / 关注
  like(postId?: number, commentId?: number) {
    return request<{ liked: boolean; count: number }>({ url: '/likes', method: 'POST', data: { post_id: postId, comment_id: commentId } })
  },
  unlike(postId?: number, commentId?: number) {
    return request<{ liked: boolean; count: number }>({ url: '/likes', method: 'DELETE', params: { post_id: postId, comment_id: commentId } })
  },
  follow(communityId: number) {
    return request<{ followed: boolean }>({ url: '/follows', method: 'POST', data: { community_id: communityId } })
  },
  unfollow(communityId: number) {
    return request<{ followed: boolean }>({ url: '/follows', method: 'DELETE', params: { community_id: communityId } })
  },
  // 收藏（P0）
  favorite(postId: number) {
    return request<{ favorited: boolean; count: number }>({ url: `/posts/${postId}/favorite`, method: 'POST', data: { group_name: '默认' } })
  },
  unfavorite(postId: number) {
    return request<{ favorited: boolean; count: number }>({ url: `/posts/${postId}/favorite`, method: 'DELETE' })
  },
  myFavorites(page = 1, pageSize = 20) {
    return request<Page<FavoriteItem>>({ url: '/me/favorites', params: { page, page_size: pageSize } })
  },
  // 附件（P0）
  attachments(postId: number) {
    return request<AttachmentItem[]>({ url: `/posts/${postId}/attachments` })
  },
  uploadAttachment(postId: number, file: File) {
    const fd = new FormData()
    fd.append('file', file)
    return request<AttachmentItem>({ url: `/posts/${postId}/attachments/upload`, method: 'POST', data: fd })
  },
  deleteAttachment(attachmentId: number) {
    return request<null>({ url: `/attachments/${attachmentId}`, method: 'DELETE' })
  },
  // 举报（P0）
  report(data: { target_type: number; target_id: number; reason_type?: string; detail?: string }) {
    return request<{ id: number }>({ url: '/reports', method: 'POST', data })
  },
  // AI 摘要（P0）
  aiSummary(postId: number) {
    return request<{ summary: string }>({ url: '/ai/summary', method: 'POST', data: { post_id: postId } })
  },
  // 我的审核记录 + 申诉（文档⑪：AI 驳回可申诉复审）
  myReviews(page = 1, pageSize = 20) {
    return request<Page<ReviewItem>>({ url: '/ai/reviews/me', params: { page, page_size: pageSize } })
  },
  appealReview(reviewId: number) {
    return request<ReviewItem>({ url: `/ai/reviews/${reviewId}/appeal`, method: 'POST' })
  },
  // 我的短链（文档⑭记录查询/失效）
  myShares(page = 1, pageSize = 20) {
    return request<Page<ShareItem>>({ url: '/shares', params: { page, page_size: pageSize } })
  },
  invalidateShare(code: string) {
    return request<null>({ url: `/shares/${code}`, method: 'DELETE' })
  },
}

export interface ReviewItem {
  id: number
  content_type: number // 1帖子 2评论
  content_id: number
  status: number // 0待审 1通过 2驳回 3转人工
  violation_type: string
  violation_detail: string
  review_method: number // 0AI快审 1AI复审 2人工
  appeal_at: string | null
  result: string
  reviewed_at: string | null
  created_at: string | null
}

export interface ShareItem {
  code: string
  target_type: number // 1频道 2帖子 3用户
  target_id: number
  creator_id: number
  visit_count: number
  expires_at: string | null
  created_at: string | null
}

export interface FavoriteItem {
  favorite_id: number
  group_name: string
  created_at: string | null
  post_id: number
  post_title: string
  post_status: number
}

export interface AttachmentItem {
  id: number
  post_id: number
  media_type: number
  url: string
  thumb_url: string
  width: number
  height: number
  file_size: number
  duration: number
  sort_order: number
}
