// ============================================================
// 通用 API 响应类型
// 对应 PRD §13.1 统一响应格式
// ============================================================

export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
  /** 服务端时间戳（毫秒），可选 */
  timestamp?: number
}

export interface PaginatedData<T> {
  list: T[]
  total: number
  page: number
  page_size: number
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
