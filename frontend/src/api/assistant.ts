// ============================================================
// AI 行程助理 API（移动端方案 M2/M3）
// parse 只产建议；apply 是用户确认后的白名单落库
// ============================================================
import { http } from './http'

export interface AssistantSuggestion {
  kind: 'task' | 'reminder' | 'note'
  title: string
  deadline: string | null
  people: string[]
  location: string | null
  priority: 'high' | 'medium' | 'low'
  notes: string | null
  /** 前端确认态（是否加入） */
  checked?: boolean
}

export interface AssistantParseResult {
  ok: boolean
  source: 'deepseek' | 'local'
  degraded?: boolean
  items: AssistantSuggestion[]
  clarifications: string[]
}

export const assistantApi = {
  status() {
    return http.get<{ configured: boolean; model: string }>('/assistant/status')
  },
  configure(apiKey: string) {
    return http.put<{ configured: boolean; model: string }>('/assistant/config', { api_key: apiKey })
  },
  parse(text: string) {
    return http.post<AssistantParseResult>('/assistant/parse', { text })
  },
  apply(items: AssistantSuggestion[]) {
    return http.post<{ applied: number; by_kind: Record<string, number> }>(
      '/assistant/apply',
      { items: items.map(({ checked, ...rest }) => rest) },
    )
  },
}
