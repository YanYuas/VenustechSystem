// ============================================================
// features/assistant/model.ts —— assistant 领域模型（迁移批次 P3，ADR-0007）
// ============================================================

// ---------- 从 api.ts 收编的内联类型 ----------
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
