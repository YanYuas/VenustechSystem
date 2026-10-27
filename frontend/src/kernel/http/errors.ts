// ============================================================
// kernel/http/errors.ts —— 错误类型与分类
//
// 从原 kernel/http/index.ts 拆出（P4，ADR-0007）。行为零变化：
// 类名 / 错误码 / name / 标志位 / instanceof 语义逐字保留。
// ============================================================
import { ApiErrorCode } from './types'

export class ApiError extends Error {
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

/** 写操作被离线队列接管时抛出的错误（UI 可据此显示"已加入队列"） */
export class OfflineQueuedError extends Error {
  readonly queued = true
  constructor(message = '已离线，操作已加入同步队列') {
    super(message)
    this.name = 'OfflineQueuedError'
  }
}

/**
 * 网络层失败（不是业务错误）：fetch 抛 TypeError / 超时 abort / 502 网关等。
 * 注意 ApiUnreachableError 必须先判 —— 它继承了 ApiError。
 */
export function isNetworkFailure(err: unknown): boolean {
  if (err instanceof ApiUnreachableError) return true
  if (err instanceof ApiError) return false
  if (err instanceof DOMException && err.name === 'AbortError') return true
  if (err instanceof TypeError) return true
  const msg = err instanceof Error ? err.message : String(err)
  return /Failed to fetch|NetworkError|请求超时|timeout|aborted/i.test(msg)
}
