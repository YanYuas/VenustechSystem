// ============================================================
// features/aihot/model.ts —— aihot 领域模型（迁移批次 P3，ADR-0007）
// ============================================================

// ---------- 从 api.ts 收编的内联类型 ----------
export interface AihotItem {
  title: string
  summary?: string
  category?: string
  publishedAt?: string
  discoveredAt?: string
  links?: { aihot?: string; original?: string }
}

export interface AihotEnvelope<T = unknown> {
  ok: boolean
  source?: 'live' | 'cache' | 'mock'
  degraded?: boolean
  error?: string
  data: T
}
