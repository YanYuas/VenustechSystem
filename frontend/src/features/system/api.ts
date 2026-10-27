// ============================================================
// 系统诊断 API（加密 / 日志 / 事件总线 / 插件）
//
// 这四个模块后端早已写好，但前端既没有封装也没有界面 —— 能力被埋没。
// 本文件只是把它们**接出来**，不新增任何后端能力。
// ============================================================
import { http } from '@/kernel/http'
import type {
  EncryptionStatus,
  LogList,
  LogContent,
  ClearLogsResult,
  EventStats,
  EventRecord,
  RuleDomainCount,
  RulePreviewResult,
  RuleReloadResult,
  EventTypes,
  PluginItem,
} from './model'

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
  eventHistory(limit = 50, event?: string) {
    return http.get<EventRecord[]>('/events/history', { limit, event })
  },
  eventTypes() {
    return http.get<EventTypes>('/events/types')
  },
  clearEventHistory() {
    return http.post<{ cleared: boolean }>('/events/clear-history')
  },
  eventSubscriptions() {
    return http.get<{ sync: Record<string, string[]>; async: Record<string, string[]> }>(
      '/events/subscriptions',
    )
  },

  // ---------- 规则引擎（O6 · F4.1/F4.3） ----------
  ruleDomains() {
    return http.get<RuleDomainCount>('/rules/domains')
  },
  ruleReload() {
    return http.post<RuleReloadResult>('/rules/reload')
  },
  rulePreview(text: string) {
    return http.post<RulePreviewResult>('/rules/preview', { text })
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
