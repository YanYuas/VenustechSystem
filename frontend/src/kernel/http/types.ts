// ============================================================
// 通用 API 响应类型
// 对应 PRD §13.1 统一响应格式
// ============================================================

export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
  /**
   * 服务端时间戳（单位：**秒**，Unix epoch）。
   * 后端 core/response.py:17 `int(time.time())` 总是返回，故这里为必填；
   * 旧注释误写「毫秒」，按毫秒换算会差 1000 倍。
   */
  timestamp: number
}

export interface PaginatedData<T> {
  list: T[]
  total: number
  page: number
  page_size: number
}

// ---------- SSE 流事件（从 types/conversation.ts 收编） ----------
// 为什么放在 kernel/http：这是**传输层**的事件形状，kernel/http 的 sseRequest
// 需要它；而 kernel 不得依赖 features（types/conversation 将迁入 features/conversation）。
export type SseEventType = 'content' | 'done' | 'error'

export interface SseEvent {
  type: SseEventType
  content?: string
  tokens?: number
  error?: string
}

/** 错误码 —— 对应 PRD §13.1 */
export enum ApiErrorCode {
  SUCCESS = 0,
  PARAM_ERROR = 1001,
  NOT_FOUND = 1002,
  VALIDATION_ERROR = 1003,
  UNAUTHORIZED = 2001,
  AUTH_ERROR = 2002,
  BUSINESS_CONFLICT = 3001,
  AI_ERROR = 4001,
  SERVER_ERROR = 5000,
}
