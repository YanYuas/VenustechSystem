// ============================================================
// 复盘模块类型
// 对应 PRD §13.6 复盘模块 + §15.10 reviews表
// ============================================================

export type ReviewType = 'daily' | 'weekly' | 'monthly'

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
  type: ReviewType
  date: string
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
  content: string
  priority?: string
  due_date?: string
}
