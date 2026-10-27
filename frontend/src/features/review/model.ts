// ============================================================
// 复盘模块类型
// 对应 PRD §13.6 复盘模块 + §15.10 reviews表
// ============================================================

// 后端 schemas/review.py 的 type 是自由字符串；前端 UI 提供日/周/月/项目四种，
// 因此 'project' 必须在内（原 union 漏掉，导致项目复盘分支在类型上不可达）。
export type ReviewType = 'daily' | 'weekly' | 'monthly' | 'project'

export interface ReviewData {
  completed_tasks: string
  unfinished_tasks: string
  gains: string
  reflections: Array<{ question: string; answer: string }>
  tomorrow_plan: string
  mood: number
  energy: number
}

export interface Review {
  id: string
  type: ReviewType
  review_date: string
  /** 关联项目（backend schemas/review.py:30） */
  project_id: string | null
  /** 身份轴（三期 B）（backend schemas/review.py:32） */
  identity_id: string | null
  data: ReviewData
  created_at: string
  updated_at: string
}

export interface ReviewListQuery {
  type?: ReviewType
  page?: number
  page_size?: number
}

export interface UpsertReviewRequest {
  /** 后端默认 "daily"（schemas/review.py:39 `type: str = "daily"`） */
  type?: ReviewType
  date: string
  /** 关联项目（backend schemas/review.py:41） */
  project_id?: string | null
  /** 身份轴（三期 B）：可空 = 未归类（backend schemas/review.py:43） */
  identity_id?: string | null
  data: ReviewData
}

export interface AutoFillData {
  completed_tasks: Array<{ id: string; title: string; completed_at: string }>
  unfinished_tasks: Array<{ id: string; title: string; due_date: string | null }>
  documents_created: Array<{ id: string; title: string; created_at: string }>
  stats: {
    tasks_completed: number
    documents_created: number
    tasks_overdue: number
  }
}

export interface ConvertTaskRequest {
  // ADR-0008：null = 清空该字段，省略 = 不改
  content: string
  priority?: string | null
  due_date?: string | null
}
