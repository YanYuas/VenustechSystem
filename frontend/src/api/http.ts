// ============================================================
// HTTP 客户端封装
// - 统一 baseURL / 超时 / 错误处理
// - 统一响应格式解包 (ApiResponse<T> → T)
// - SSE 流式响应支持
// ============================================================
import { ApiErrorCode, type ApiResponse } from '@/types/api'
import type { SseEvent } from '@/types/conversation'
import { toast } from '@/composables/useToast'

const BASE_URL = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8765/api/v1'
const TIMEOUT = 15000
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

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let lastError: unknown
  const method = (options.method ?? 'GET').toUpperCase()
  const retryable = IDEMPOTENT_METHODS.has(method)
  const maxAttempts = retryable ? RETRY_COUNT : 0
  for (let attempt = 0; attempt <= maxAttempts; attempt++) {
    try {
      return await doRequest<T>(path, options)
    } catch (err) {
      lastError = err
      // 只对幂等方法的网络错误重试，业务错误（ApiError）不重试
      if (err instanceof ApiError) throw err
      // 最后一次重试失败，抛出错误
      if (attempt === maxAttempts) break
      // 重试间隔
      await new Promise((r) => setTimeout(r, RETRY_DELAY))
    }
  }
  throw lastError
}

async function doRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${path}`
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT)

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
    return body.data
  } catch (err) {
    clearTimeout(timer)
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
      throw new ApiError(ApiErrorCode.SERVER_ERROR, '请求超时，请检查网络连接')
    }
    // 网络错误（fetch 失败，后端未启动）
    if (err instanceof TypeError && err.message.includes('Failed to fetch')) {
      throw new ApiError(ApiErrorCode.SERVER_ERROR, '无法连接服务器，请确认后端已启动')
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
    const res = await fetch(`${BASE_URL}${path}`, {
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
