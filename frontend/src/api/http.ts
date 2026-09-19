// ============================================================
// HTTP 客户端封装
// - 统一 baseURL / 超时 / 错误处理
// - 统一响应格式解包 (ApiResponse<T> → T)
// - SSE 流式响应支持
// ============================================================
import { ApiErrorCode, type ApiResponse } from '@/types/api'
import type { SseEvent } from '@/types/conversation'
import { toast } from '@/composables/useToast'
import {
  CONNECTIVITY_TOAST_TITLE,
  isBackendUnreachable,
  markReachable,
  markUnreachable,
  shouldNotifyUnreachable,
} from './connectivity'

const ENV_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8765/api/v1'
// 运行时可覆盖（Capacitor App 壳里指向 PC 的 Tailscale 地址；localStorage 持久）
const API_BASE_KEY = 'qm-star-api-base'

export function getApiBase(): string {
  try {
    return localStorage.getItem(API_BASE_KEY) || ENV_BASE
  } catch {
    return ENV_BASE
  }
}

export function getApiToken(): string {
  try {
    return localStorage.getItem('qm-star-token') || ''
  } catch {
    return ''
  }
}

export function setApiToken(token: string): void {
  try {
    localStorage.setItem('qm-star-token', token.trim())
  } catch { /* ignore */ }
}

export function setApiBase(url: string): void {
  let clean = url.trim().replace(/\/+$/, '')
  // 防呆：服务器地址漏带 /api/v1 时自动补全（头号连接故障源）
  if (clean && !clean.endsWith('/api/v1')) clean = `${clean}/api/v1`
  if (clean) localStorage.setItem(API_BASE_KEY, clean)
  else localStorage.removeItem(API_BASE_KEY)
}
/** 常规请求超时 */
const TIMEOUT = 15000
/**
 * 已判定后端不可达时的探活超时。
 * 15s 的常规超时用在"服务根本没开"的场景上，会让每个页面都干等 15 秒；
 * 降到 4s 既能让 UI 快速给出结论，也不影响服务恢复后的正常请求。
 */
const FAST_FAIL_TIMEOUT = 4000
/** SSE 首包超时：LLM 冷启动/长 prompt 时首包可能远超 15s */
const SSE_TIMEOUT = 60000
/** 网络错误自动重试次数（PRD §21：重试1次，间隔2秒） */
const RETRY_COUNT = 1
const RETRY_DELAY = 2000
/** 仅幂等方法允许自动重试：POST 重试可能造成重复创建 */
const IDEMPOTENT_METHODS = new Set(['GET', 'HEAD', 'PUT', 'DELETE'])

class ApiError extends Error {
  code: number
  constructor(code: number, message: string) {
    super(message)
    this.code = code
    this.name = 'ApiError'
  }
}

/**
 * 网络级失败（连不上 / 超时）—— 与业务错误严格区分。
 *
 * 为什么必须单独建类：原先网络失败也被包成普通 ApiError，
 * 于是 isNetworkFailure() 一律返回 false，
 *   - 离线队列的"服务不可达即入队"分支永不生效（写操作直接报错）
 *   - request() 的重试分支变成死代码
 * 继承 ApiError 以保证既有 `instanceof ApiError` 判定与错误码处理不受影响。
 */
export class ApiUnreachableError extends ApiError {
  readonly unreachable = true
  constructor(message: string) {
    super(ApiErrorCode.SERVER_ERROR, message)
    this.name = 'ApiUnreachableError'
  }
}


// ---------- 离线队列接入（mod-tools F4.3） ----------
// 用注册钩子而非直接 import store：store 需要 getApiBase/getApiToken，
// 直接互相 import 会形成循环依赖。
export type OfflineEnqueueHandler = (
  path: string,
  method: 'POST' | 'PATCH' | 'PUT' | 'DELETE',
  body?: unknown,
  label?: string,
) => Promise<void>

let offlineEnqueueHandler: OfflineEnqueueHandler | null = null

export function setOfflineQueueHandler(handler: OfflineEnqueueHandler | null): void {
  offlineEnqueueHandler = handler
}

/** 写操作被离线队列接管时抛出的错误（UI 可据此显示"已加入队列"） */
export class OfflineQueuedError extends Error {
  readonly queued = true
  constructor(message = '已离线，操作已加入同步队列') {
    super(message)
    this.name = 'OfflineQueuedError'
  }
}

const WRITE_METHODS = new Set(['POST', 'PATCH', 'PUT', 'DELETE'])

function isOffline(): boolean {
  try {
    return typeof navigator !== 'undefined' && navigator.onLine === false
  } catch {
    return false
  }
}

/**
 * 网络层失败（不是业务错误）：fetch 抛 TypeError / 超时 abort / 502 网关等。
 * 注意 ApiUnreachableError 必须先判 —— 它继承了 ApiError。
 */
function isNetworkFailure(err: unknown): boolean {
  if (err instanceof ApiUnreachableError) return true
  if (err instanceof ApiError) return false
  if (err instanceof DOMException && err.name === 'AbortError') return true
  if (err instanceof TypeError) return true
  const msg = err instanceof Error ? err.message : String(err)
  return /Failed to fetch|NetworkError|请求超时|timeout|aborted/i.test(msg)
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { ...(options.headers as Record<string, string>) }
  const token = getApiToken()
  if (token) headers['X-API-Token'] = token
  options = { ...options, headers }
  let lastError: unknown
  const method = (options.method ?? 'GET').toUpperCase()
  // 已判定不可达时不再重试：重试只会让用户多等一个往返
  const retryable = IDEMPOTENT_METHODS.has(method) && !isBackendUnreachable()
  const maxAttempts = retryable ? RETRY_COUNT : 0
  for (let attempt = 0; attempt <= maxAttempts; attempt++) {
    try {
      return await doRequest<T>(path, options)
    } catch (err) {
      lastError = err
      // 只重试网络级失败；业务错误（参数错/未授权/404…）重试无意义
      if (!isNetworkFailure(err)) throw err
      // 最后一次重试失败，抛出错误
      if (attempt === maxAttempts) break
      // 重试间隔
      await new Promise((r) => setTimeout(r, RETRY_DELAY))
    }
  }
  // 写操作 + （离线 或 网络失败）→ 交给离线队列，而不是直接失败
  if (WRITE_METHODS.has(method) && offlineEnqueueHandler) {
    if (isOffline() || isNetworkFailure(lastError)) {
      try {
        const body = typeof options.body === 'string' ? JSON.parse(options.body) : undefined
        await offlineEnqueueHandler(
          path,
          method as 'POST' | 'PATCH' | 'PUT' | 'DELETE',
          body,
          offlineLabel(path),
        )
        throw new OfflineQueuedError()
      } catch (e) {
        if (e instanceof OfflineQueuedError) throw e
        // 入队本身失败（如 IndexedDB 不可用）→ 保留原始错误
      }
    }
  }
  throw lastError
}

/** 给队列条目一个可读标签（面板展示用；未知路径回退为方法+路径） */
function offlineLabel(path: string): string {
  if (path.includes('/assistant/apply')) return 'AI 助理 · 加入待办'
  if (path.startsWith('/workspace/roots')) return '工作区 · 根目录'
  if (path.startsWith('/workspace/scan')) return '工作区 · 扫描'
  if (path.startsWith('/vault/items')) return '保险箱 · 凭据'
  if (path.startsWith('/tasks')) return '任务'
  if (path.startsWith('/documents')) return '文档'
  if (path.startsWith('/reviews')) return '复盘'
  if (path.startsWith('/diaries')) return '日记'
  return path
}

/**
 * 按运行环境给出可操作的排查指引。
 * App 壳（Capacitor）里后端在电脑上，用户需要的是检查地址；
 * 浏览器/开发环境里通常就是"服务没启动"。
 */
function HINT_SUFFIX(): string {
  try {
    const native = Boolean((window as unknown as { Capacitor?: { isNativePlatform?: () => boolean } })
      .Capacitor?.isNativePlatform?.())
    if (native) return '，请确认电脑端服务已启动、设置里的服务器地址与访问令牌正确'
  } catch { /* 非 Capacitor 环境 */ }
  return '，请先启动后端服务（双击「启动移动服务.bat」，或运行 node server.js）'
}

async function doRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${getApiBase()}${path}`
  const controller = new AbortController()
  // 已知不可达 → 用短超时快速失败（否则每个页面都要干等 15s）
  const effectiveTimeout = isBackendUnreachable() ? FAST_FAIL_TIMEOUT : TIMEOUT
  const timer = setTimeout(() => controller.abort(), effectiveTimeout)

  // FormData 上传时不手动设置 Content-Type（让浏览器自动设置 boundary）
  const isFormData = options.body instanceof FormData
  const headers = isFormData
    ? { ...options.headers }
    : { 'Content-Type': 'application/json', ...options.headers }

  try {
    const res = await fetch(url, {
      ...options,
      headers,
      signal: controller.signal,
    })
    clearTimeout(timer)
    if (!res.ok) {
      // 尝试解析后端错误信息
      let message = `HTTP ${res.status}: ${res.statusText}`
      try {
        const errBody = await res.json()
        if (errBody?.message) message = errBody.message
      } catch { /* ignore */ }
      if (res.status === 401) {
        throw new ApiError(ApiErrorCode.AUTH_ERROR, message || '未授权，请重新初始化')
      }
      if (res.status === 422) {
        throw new ApiError(ApiErrorCode.VALIDATION_ERROR, message || '参数校验失败')
      }
      if (res.status === 404) {
        throw new ApiError(ApiErrorCode.NOT_FOUND, message || '资源不存在')
      }
      throw new ApiError(ApiErrorCode.SERVER_ERROR, message)
    }
    const body: ApiResponse<T> = await res.json()
    if (body.code !== ApiErrorCode.SUCCESS) {
      throw new ApiError(body.code, body.message)
    }
    // 请求成功 → 连通性自愈（提示立即恢复正常，无需用户手动操作）
    markReachable()
    return body.data
  } catch (err) {
    clearTimeout(timer)
    if (err instanceof ApiUnreachableError) {
      // 统一提示（节流 8s）：不可达期间几十个组件会同时失败，
      // 逐个提示只会刷屏 —— 真正的原因只有一个
      if (shouldNotifyUnreachable()) {
        toast.error(CONNECTIVITY_TOAST_TITLE, err.message, 8000)
      }
      throw err
    }
    if (err instanceof ApiError) {
      // 按错误码分类提示
      if (err.code === ApiErrorCode.AI_ERROR) toast.error('AI服务异常', err.message)
      else if (err.code === ApiErrorCode.AUTH_ERROR) toast.error('认证失败', err.message)
      else if (err.code === ApiErrorCode.VALIDATION_ERROR) toast.error('参数错误', err.message)
      else if (err.code === ApiErrorCode.NOT_FOUND) toast.error('资源不存在', err.message)
      else if (err.code >= 5000) toast.error('服务异常', err.message)
      throw err
    }
    // AbortError → 超时
    if (err instanceof DOMException && err.name === 'AbortError') {
      markUnreachable()
      throw new ApiUnreachableError(`请求超时（${effectiveTimeout / 1000} 秒无响应）${HINT_SUFFIX()}`)
    }
    // 网络错误（fetch 失败：后端未启动 / 地址不对 / 不在同一网络）
    if (err instanceof TypeError) {
      markUnreachable()
      throw new ApiUnreachableError(`无法连接服务器${HINT_SUFFIX()}`)
    }
    throw new ApiError(ApiErrorCode.SERVER_ERROR, '网络请求失败')
  }
}

export const http = {
  get<T>(path: string, params?: Record<string, unknown>) {
    const clean = params ? Object.fromEntries(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''),
    ) : {}
    const query = Object.keys(clean).length
      ? '?' + new URLSearchParams(clean as Record<string, string>).toString()
      : ''
    return request<T>(`${path}${query}`, { method: 'GET' })
  },
  post<T>(path: string, body?: unknown) {
    return request<T>(path, { method: 'POST', body: JSON.stringify(body) })
  },
  patch<T>(path: string, body?: unknown) {
    return request<T>(path, { method: 'PATCH', body: JSON.stringify(body) })
  },
  put<T>(path: string, body?: unknown) {
    return request<T>(path, { method: 'PUT', body: JSON.stringify(body) })
  },
  delete<T>(path: string) {
    return request<T>(path, { method: 'DELETE' })
  },
}

export async function sseRequest(
  path: string,
  body: unknown,
  onMessage: (event: SseEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  // 合并外部 signal 与内部超时 signal
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), SSE_TIMEOUT)
  if (signal) {
    if (signal.aborted) controller.abort()
    else signal.addEventListener('abort', () => controller.abort(), { once: true })
  }

  try {
    const res = await fetch(`${getApiBase()}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    })
    clearTimeout(timer)
    if (!res.ok) {
      throw new ApiError(ApiErrorCode.SERVER_ERROR, `HTTP ${res.status}: ${res.statusText}`)
    }
    if (!res.body) throw new ApiError(ApiErrorCode.SERVER_ERROR, '无响应流')
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try { onMessage(JSON.parse(line.slice(6))) } catch { /* ignore malformed */ }
          }
        }
      }
    } finally {
      reader.releaseLock()
    }
  } catch (err) {
    clearTimeout(timer)
    if (err instanceof ApiError) throw err
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiError(ApiErrorCode.SERVER_ERROR, '请求超时或已取消')
    }
    throw new ApiError(ApiErrorCode.SERVER_ERROR, '网络请求失败')
  }
}

export { ApiError }
