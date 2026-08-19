/** 帖子/评论/点赞/关注 API（阶段 3）。 */
import { request, type Page } from './http'

export interface PostItem {
  id: number
  community_id: number
  board_id: number
  author_id: number
  title: string
  rich_content: Array<{ type: number; text?: string; url?: string; display_text?: string }>
  source_markdown: string
  images: string[]
  like_count: number
  comment_count: number
  is_top: boolean
  is_essence: boolean
  status: number
  created_at: string
  author_nickname: string
  author_avatar: string
  community_name: string
  board_name: string
  is_liked: boolean
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
  feed(cid: number, sort: 'latest' | 'hot' = 'latest', cursor?: string | null, pageSize = 20) {
    return request<FeedResult>({
      url: `/communities/${cid}/feed`,
      params: { sort, cursor: cursor ?? undefined, page_size: pageSize },
    })
  },
  meFeed(cursor?: string | null, pageSize = 20) {
    return request<FeedResult>({ url: '/me/feed', params: { cursor: cursor ?? undefined, page_size: pageSize } })
  },
  // 帖子
  get(id: number) {
    return request<PostItem>({ url: `/posts/${id}` })
  },
  create(cid: number, bid: number, data: { title: string; content: string; images?: string[] }) {
    return request<PostItem>({ url: `/communities/${cid}/boards/${bid}/posts`, method: 'POST', data })
  },
  update(id: number, data: { title?: string; content?: string; images?: string[] }) {
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
  createReply(commentId: number, content: string) {
    return request<CommentItem>({ url: `/comments/${commentId}/replies`, method: 'POST', data: { content } })
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
}
