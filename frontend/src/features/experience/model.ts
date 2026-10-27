// ============================================================
// 经历视图类型（S6-4 · 只读聚合，不建表）
// ============================================================

export type ExperienceSource = 'diary' | 'review' | 'avatar_memory' | 'project_memory'

export interface ExperienceItem {
  id: string
  source: ExperienceSource
  source_label: string
  title: string
  snippet: string | null
  identity_id: string | null
  occurred_at: string
}

export interface ExperienceOut {
  items: ExperienceItem[]
  total: number
  page: number
  page_size: number
  source_counts: Partial<Record<ExperienceSource, number>>
}
