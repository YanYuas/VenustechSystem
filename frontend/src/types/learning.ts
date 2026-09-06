// ============================================================
// 学习成长类型定义（二期 M8）
// ============================================================

export interface StudyPlan {
  id: string
  name: string
  description: string | null
  target_date: string | null
  estimated_hours: number | null
  progress: number
  status: 'active' | 'paused' | 'completed'
  config: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface Flashcard {
  id: string
  plan_id: string | null
  front: string
  back: string
  card_type: 'qa' | 'cloze' | 'image'
  category: string | null
  tags: string[]
  difficulty: number  // 1-5
  ef: number  // SM-2 难度因子，下限1.3
  interval: number  // 天
  repetition: number
  next_review: string | null
  last_reviewed_at: string | null
  review_count: number
  created_at: string
  updated_at: string
}

export interface StudyTimeLog {
  id: string
  plan_id: string | null
  subject: string | null
  duration: number  // 分钟
  note: string | null
  source: 'manual' | 'timer' | 'auto'
  logged_date: string
  created_at: string
}

export interface ReviewResult {
  card_id: string
  quality: number  // 0-5
  next_interval: number
  next_review: string
}
