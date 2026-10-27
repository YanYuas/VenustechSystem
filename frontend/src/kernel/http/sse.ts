// ============================================================
// kernel/http/sse.ts —— SSE 流式请求（POST + text/event-stream 逐行解析）
//
// 从原 kernel/http/index.ts 拆出（P4，ADR-0007）。行为零变化：
// 首包超时 60s、data: 前缀解析、错误文案逐字保留。
// ============================================================
import { SSE_TIMEOUT, getApiBase } from './client'
import { ApiError } from './errors'
import { ApiErrorCode, type SseEvent } from './types'

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
            try {
              onMessage(JSON.parse(line.slice(6)))
            } catch {
              /* ignore malformed */
            }
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
