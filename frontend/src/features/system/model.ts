// ============================================================
// features/system/model.ts —— system 领域模型（迁移批次 P3，ADR-0007）
// ============================================================

// ---------- 从 api.ts 收编的内联类型 ----------
/** 加密存储状态 */
export interface EncryptionStatus {
  available: boolean
  [key: string]: unknown
}

/** 日志文件条目 */
export interface LogFile {
  name: string
  size_kb: number
  modified: number
  modified_str: string
}

export interface LogList {
  files: LogFile[]
  dir: string
}

export interface LogContent {
  filename: string
  total_lines: number
  content: string
}

export interface ClearLogsResult {
  cleared: number
  failed: string[]
}

/** 事件统计：事件名 → 次数 / 成功 / 失败 */
export interface EventStatItem {
  count: number
  success: number
  failed: number
  failed_handlers?: string[]
  consecutive_failures?: number
  failure_rate_1m?: number | null
  alert?: boolean
}

export type EventStats = Record<string, EventStatItem>

export interface EventRecord {
  event: string
  time?: string
  kwargs?: Record<string, unknown>
  handlers_called?: number
  handlers?: number
  success?: boolean
  failed_handlers?: string[]
  timestamp?: number
}

export interface RuleDomainCount {
  builtin_count: number
  user_count: number
  domains: Array<{ key: string; name: string; source: string; patterns: string[]; units: number }>
}

export interface RulePreviewResult {
  matched: boolean
  fallback?: boolean
  domain_key: string | null
  domain_name: string | null
  matched_patterns?: string[]
  plans: Array<{ unit: string; task: string; duration: string; acceptance?: string }>
  plan_count?: number
}

export interface RuleReloadResult {
  builtin: number
  user: number
  total: number
  skipped: Array<{ file: string; reason: string }>
}

export interface EventTypes {
  events: string[]
  count: number
}

export interface PluginItem {
  id: string
  name: string
  version: string
  enabled: boolean
  description?: string
  author?: string
}
