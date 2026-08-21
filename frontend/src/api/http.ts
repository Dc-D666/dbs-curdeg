import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosResponse } from 'axios'

/** 后端统一响应结构（见 详细开发方案.md §5.1） */
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
}

/** 分页结构 */
export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

const TOKEN_KEY = 'sdu_access_token'
const REFRESH_KEY = 'sdu_refresh_token'

export const tokenStore = {
  get access(): string | null {
    return localStorage.getItem(TOKEN_KEY)
  },
  set access(v: string | null) {
    v ? localStorage.setItem(TOKEN_KEY, v) : localStorage.removeItem(TOKEN_KEY)
  },
  get refresh(): string | null {
    return localStorage.getItem(REFRESH_KEY)
  },
  set refresh(v: string | null) {
    v ? localStorage.setItem(REFRESH_KEY, v) : localStorage.removeItem(REFRESH_KEY)
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

const http: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 60000, // AI 问答/帮写走 LLM，冷启动 + embedding 可能在 15s 外；放宽到 60s
})

http.interceptors.request.use((config) => {
  const token = tokenStore.access
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 401 单飞（single-flight）：并发 401 只发一次 refresh，其余请求排队等待
let refreshing: Promise<string | null> | null = null
const pending: Array<(token: string | null) => void> = []

function refreshToken(): Promise<string | null> {
  if (!refreshing) {
    refreshing = axios
      .post<ApiResponse<{ access_token: string }>>('/api/v1/auth/refresh', {
        refresh_token: tokenStore.refresh,
      })
      .then((res) => {
        const token = res.data?.data?.access_token ?? null
        tokenStore.access = token
        return token
      })
      .catch(() => {
        tokenStore.clear()
        return null
      })
      .finally(() => {
        refreshing = null
      })
  }
  return refreshing
}

http.interceptors.response.use(
  (res: AxiosResponse) => res,
  async (error) => {
    const { response, config } = error
    if (response?.status === 401) {
      // 未登录（无 refresh token）或刷新失败：清登录态并跳登录页
      if (!tokenStore.refresh || config._retried) {
        tokenStore.clear()
        if (window.location.pathname !== '/login') {
          window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`
        }
        return Promise.reject(error)
      }
      config._retried = true
      const token = await refreshToken()
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
        return http(config)
      }
      tokenStore.clear()
      if (window.location.pathname !== '/login') {
        window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`
      }
    }
    return Promise.reject(error)
  },
)

/** 统一解包：非 0 code 抛出业务错误；HTTP 错误时提取后端 message。FormData 由浏览器自动分配带 boundary 的 multipart 类型，勿手动设头。 */
export async function request<T>(config: AxiosRequestConfig): Promise<T> {
  try {
    const res = await http.request<ApiResponse<T>>(config)
    const body = res.data
    if (body.code !== 0) {
      throw new Error(body.message || `业务错误 code=${body.code}`)
    }
    return body.data
  } catch (e) {
    // axios HTTP 错误：优先提取后端统一响应里的 message
    if (axios.isAxiosError(e)) {
      const data = e.response?.data as ApiResponse | undefined
      if (data && typeof data.message === 'string') {
        throw new Error(data.message)
      }
    }
    throw e
  }
}

export default http
