/** 搜索 API（阶段 4）：关键词搜索 + 热门词。 */
import { request } from './http'

export interface SearchResult {
  id: number
  community_id: number
  board_id: number
  author_id: number
  title: string
  highlight_title: string
  snippet: string
  source_markdown: string
  like_count: number
  comment_count: number
  is_top: boolean
  is_essence: boolean
  created_at: string
  author_nickname: string
  community_name: string
  board_name: string
}

export interface SearchPage {
  items: SearchResult[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}

export interface HotKeyword {
  keyword: string
  count: number
}

export const searchApi = {
  posts(q: string, opts: { community_id?: number; page?: number; page_size?: number } = {}) {
    return request<SearchPage>({
      url: '/search/posts',
      params: { q, community_id: opts.community_id, page: opts.page ?? 1, page_size: opts.page_size ?? 20 },
    })
  },
  hot() {
    return request<HotKeyword[]>({ url: '/search/hot' })
  },
}
