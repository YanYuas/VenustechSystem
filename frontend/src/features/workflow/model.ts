// ============================================================
// features/workflow/model.ts —— workflow 领域模型（迁移批次 P3，ADR-0007）
// ============================================================

// ---------- 从 api.ts 收编的内联类型 ----------
export interface Workflow {
  id: string
  name: string
  description: string | null
  icon: string | null
  category: string | null
  scenario: string | null
  config: Record<string, unknown>
  is_preset: boolean
  is_active: boolean
  use_count: number
  created_at: string
  updated_at: string
}

export interface WorkflowApplication {
  id: string
  workflow_id: string
  user_id: string
  params: Record<string, unknown>
  status: string
  result_summary: string | null
  applied_at: string
}
