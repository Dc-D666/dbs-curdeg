import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosResponse } from 'axios'

/** 后端统一响应结构（见 详细开发方案.md §5.1） */
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
}

/** 带 HTTP 状态的错误。
 *
 * 视图据此区分「目标确实不存在（404）」与「网络/服务端故障」——
 * 二者此前都显示成「不存在」，会把断网误报成内容被删、且不给重试入口。
 * 继承 Error，因此所有 `e instanceof Error` 的旧判断不受影响。
 */
// 自定义请求配置：axios 原生类型里没有这两个字段，做模块增强以便类型检查
declare module 'axios' {
  interface AxiosRequestConfig<D = any, P = any> {
    /** 401 时不要强制跳登录页。
     *
     * 用于「只是探测一下登录态」的请求（如 GET /users/me）。这类请求 401 是预期结果之一，
     * 一旦跟着全局跳转，游客访问首页就会被直接弹到登录页。
     */
    skipAuthRedirect?: boolean
    /** 内部标记：已用新 token 重试过一次，避免 401 死循环。 */
    _retried?: boolean
  }
}

export class ApiError extends Error {
  status: number
  code: number
  constructor(message: string, status = 0, code = 0) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
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

/** 跳登录页并带上来源地址，登录后自动回来。 */
function redirectToLogin() {
  window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`
}

http.interceptors.response.use(
  (res: AxiosResponse) => res,
  async (error) => {
    const { response, config } = error
    const canRedirect = !config?.skipAuthRedirect && window.location.pathname !== '/login'
    if (response?.status === 401) {
      // 未登录（无 refresh token）或刷新失败：清登录态并跳登录页
      if (!tokenStore.refresh || config._retried) {
        tokenStore.clear()
        if (canRedirect) redirectToLogin()
        return Promise.reject(error)
      }
      // 仍有 refresh token：先尝试静默续期（skipAuthRedirect 的请求也走续期，只是失败时不跳页）
      config._retried = true
      const token = await refreshToken()
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
        return http(config)
      }
      tokenStore.clear()
      if (canRedirect) redirectToLogin()
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
      throw new ApiError(body.message || `业务错误 code=${body.code}`, res.status, body.code)
    }
    return body.data
  } catch (e) {
    // axios HTTP 错误：优先提取后端统一响应里的 message，并带上 HTTP 状态码
    if (axios.isAxiosError(e)) {
      const data = e.response?.data as ApiResponse | undefined
      throw new ApiError(
        data?.message || e.message || '网络请求失败',
        e.response?.status ?? 0,
        data?.code ?? 0,
      )
    }
    throw e
  }
}

export default http
