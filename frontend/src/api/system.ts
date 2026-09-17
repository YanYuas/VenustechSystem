// ============================================================
// 系统诊断 API（加密 / 日志 / 事件总线 / 插件）
//
// 这四个模块后端早已写好，但前端既没有封装也没有界面 —— 能力被埋没。
// 本文件只是把它们**接出来**，不新增任何后端能力。
// ============================================================
import { http } from './http'

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
export type EventStats = Record<string, { count: number; success: number; failed: number }>

export interface EventRecord {
  event: string
  kwargs?: Record<string, unknown>
  handlers_called?: number
  success?: boolean
  timestamp?: number
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

export const systemApi = {
  // ---------- 加密 / 安全 ----------
  encryptionStatus() {
    return http.get<EncryptionStatus>('/security/status')
  },
  rotateKey() {
    return http.post<unknown>('/security/key/rotate')
  },

  // ---------- 日志 ----------
  listLogs() {
    return http.get<LogList>('/logs')
  },
  readLog(filename: string, tail = 200) {
    return http.get<LogContent>(`/logs/${filename}`, { tail })
  },
  clearLogs() {
    return http.post<ClearLogsResult>('/logs/clear')
  },

  // ---------- 事件总线 ----------
  eventStats() {
    return http.get<EventStats>('/events/stats')
  },
  eventHistory(limit = 50) {
    return http.get<EventRecord[]>('/events/history', { limit })
  },
  eventTypes() {
    return http.get<EventTypes>('/events/types')
  },
  clearEventHistory() {
    return http.post<{ cleared: boolean }>('/events/clear-history')
  },

  // ---------- 插件 ----------
  listPlugins() {
    return http.get<PluginItem[]>('/plugins')
  },
  discoverPlugins() {
    return http.post<PluginItem[]>('/plugins/discover')
  },
  setPluginEnabled(id: string, enabled: boolean) {
    return enabled
      ? http.post<unknown>(`/plugins/${id}/enable`)
      : http.post<unknown>(`/plugins/${id}/disable`)
  },
  reloadPlugin(id: string) {
    return http.post<unknown>(`/plugins/${id}/reload`)
  },
}
