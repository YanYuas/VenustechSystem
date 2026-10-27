// ============================================================
// kernel/http/request.ts —— 请求执行：信封解包 / 错误映射 / 重试 / 离线入队
//
// 从原 kernel/http/index.ts 拆出（P4，ADR-0007）。行为零变化：
// 超时选择、重试次数与间隔、错误文案、离线队列语义逐字保留。
// ============================================================
import { ApiErrorCode, type ApiResponse } from './types'
import {
  FAST_FAIL_TIMEOUT,
  HINT_SUFFIX,
  IDEMPOTENT_METHODS,
  RETRY_COUNT,
  RETRY_DELAY,
  TIMEOUT,
  WRITE_METHODS,
  getApiBase,
  getApiToken,
} from './client'
import { ApiError, ApiUnreachableError, OfflineQueuedError, isNetworkFailure } from './errors'
import {
  CONNECTIVITY_TOAST_TITLE,
  isBackendUnreachable,
  markReachable,
  markUnreachable,
  shouldNotifyUnreachable,
} from './connectivity'
import { toast } from '../ui/toast'

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

/**
 * request() 的额外控制项（不属于 fetch 的 RequestInit，故单列一个参数）。
 */
interface RequestControls {
  /**
   * 网络失败 / 离线时是否允许把请求交给离线队列重放（默认 true，保持既有语义）。
   *
   * 只有 JSON 字符串请求体可重放（队列里存的就是可序列化的 body）；
   * FormData / Blob 这类二进制体无法序列化进 IndexedDB，
   * 上传类请求必须显式关闭，否则队列里会留下一条永远重放不了的「空请求」。
   */
  allowOfflineQueue?: boolean
}

function isOffline(): boolean {
  try {
    return typeof navigator !== 'undefined' && navigator.onLine === false
  } catch {
    return false
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  controls: RequestControls = {},
): Promise<T> {
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
  // allowOfflineQueue === false 的请求（FormData 上传）跳过：二进制体无法重放
  if (WRITE_METHODS.has(method) && offlineEnqueueHandler && controls.allowOfflineQueue !== false) {
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
      } catch {
        /* ignore */
      }
      if (res.status === 401) {
        throw new ApiError(ApiErrorCode.AUTH_ERROR, message || '未授权，请重新初始化')
      }
      if (res.status === 422) {
        throw new ApiError(ApiErrorCode.VALIDATION_ERROR, message || '参数校验失败')
      }
      if (res.status === 404) {
        throw new ApiError(ApiErrorCode.NOT_FOUND, message || '资源不存在')
      }
      // 网关层错误码 = 后端不可达（server.js 在代理失败时返回 502）。
      // 归入 ApiUnreachableError 而非普通服务端错误，这样：
      //   - 提示走统一的「连不上后端服务」可操作文案，而不是含糊的"服务异常"
      //   - 写操作会被离线队列接管（服务不可达期间不该让用户白填一遍）
      if (res.status === 502 || res.status === 503 || res.status === 504) {
        markUnreachable()
        throw new ApiUnreachableError(message || '后端服务不可达')
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
      throw new ApiUnreachableError(
        `请求超时（${effectiveTimeout / 1000} 秒无响应）${HINT_SUFFIX()}`,
      )
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
    const clean = params
      ? Object.fromEntries(
          Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''),
        )
      : {}
    const query = Object.keys(clean).length
      ? '?' + new URLSearchParams(clean as Record<string, string>).toString()
      : ''
    return request<T>(`${path}${query}`, { method: 'GET' })
  },
  post<T>(path: string, body?: unknown) {
    return request<T>(path, { method: 'POST', body: JSON.stringify(body) })
  },
  /**
   * 表单上传（multipart/form-data）—— 文件 / 备份包等二进制体专用。
   *
   * 与 post() 的三点关键差异（都是「备份导入必失败」P0-3 的根因，别改回去）：
   *  1. body 原样交给 fetch，**绝不 JSON.stringify**：FormData 一旦被序列化就变成
   *     字符串 "{}"，后端只看得到一个空对象；
   *  2. **不手动设置 Content-Type**：multipart 必须由浏览器/运行时自己写
   *     `multipart/form-data; boundary=...`；手写头会丢掉 boundary，FastAPI 的
   *     `UploadFile = File(...)` 仍然 422（doRequest 里已按 FormData 跳过 Content-Type）；
   *  3. **不进离线队列**：队列只能重放 JSON，二进制体无法序列化。
   *
   * 超时 / token / 错误处理 / 连通性提示全部复用 request() → doRequest()，与普通请求一致。
   */
  postForm<T>(path: string, form: FormData) {
    return request<T>(path, { method: 'POST', body: form }, { allowOfflineQueue: false })
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
