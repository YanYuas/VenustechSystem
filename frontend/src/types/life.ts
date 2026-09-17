// ============================================================
// 生活记录类型定义（二期 M9）
// ============================================================

export interface Habit {
  id: string
  name: string
  icon: string | null
  color: string | null
  frequency: 'daily' | 'weekly' | 'custom'
  target_per_week: number
  reminder_time: string | null
  goal_days: number | null
  status: 'active' | 'paused' | 'archived'
  created_at: string
  updated_at: string
}

export interface HabitCheckin {
  id: string
  habit_id: string
  checkin_date: string
  note: string | null
  created_at: string
}

export interface MoodLog {
  id: string
  score: number  // 1-5
  tags: string[]
  content: string | null
  logged_date: string
  created_at: string
}

export interface Diary {
  id: string
  dimension: string | null  // 生活/学习/工作/情感
  title: string | null
  content: string | null
  diary_date: string
  tags: string[]
  created_at: string
  updated_at: string
}
