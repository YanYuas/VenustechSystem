// ============================================================
// 长期资产库类型定义（二期 M10）
// ============================================================

export interface SOP {
  id: string
  name: string
  category: string | null
  description: string | null
  steps: SOPStep[]
  checklist: string[]
  tags: string[]
  use_count: number
  version: number
  created_at: string
  updated_at: string
}

export interface SOPStep {
  title: string
  description: string
  estimated_time: number | null
}

export interface PromptTemplate {
  id: string
  name: string
  category: string | null
  description: string | null
  role_setting: string | null
  task_description: string | null
  constraints: string | null
  output_format: string | null
  variables: string[]
  use_count: number
  rating: number | null
  created_at: string
  updated_at: string
}

export interface Skill {
  id: string
  name: string
  category: string | null
  description: string | null
  methodology: string | null
  proficiency: 'beginner' | 'intermediate' | 'advanced' | 'expert'
  tags: string[]
  use_count: number
  created_at: string
  updated_at: string
}

export interface ProjectMemory {
  id: string
  project_id: string | null
  name: string
  summary: string | null
  successes: string | null
  failures: string | null
  extracted_assets: string[]
  key_metrics: Record<string, unknown>
  tags: string[]
  created_at: string
  updated_at: string
}
