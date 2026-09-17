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

// ============================================================
// S6-1 领域规则引擎：从目标生成学习计划
// 全程离线可用，不依赖 API Key
// ============================================================

/** 计划中的一个能力单元（含阶段：1 打基础 / 2 核心练习 / 3 整合实战） */
export interface GeneratedUnit {
  name: string
  phase: number
  task_count: number
}

/** 计划中的一条任务。day 在周模式下表示周序号 */
export interface GeneratedPlanItem {
  unit_id: string
  day: number
  title: string
  task: string
  duration: string
  /** 由 duration 文本归一得到的分钟数（后端已解析，无法识别时为 null） */
  estimated_minutes: number | null
  /** 达标标准：做到什么程度算完成。领域库 90/90 条任务都有 */
  acceptance: string
  is_verify: boolean
}

export interface GeneratedPlan {
  goal: string
  skill_name: string
  /** false 表示未命中领域库，走了「入门准备→基础操作→核心练习→实战产出」通用兜底 */
  matched: boolean
  domain_key: string | null
  domain_name: string | null
  total_days: number
  minutes_per_day: number
  /** true 表示按周排期（周期 > 45 天） */
  weekly_mode: boolean
  verify_task: string
  units: GeneratedUnit[]
  items: GeneratedPlanItem[]
  item_count: number
}

export interface GeneratePlanParams {
  goal: string
  total_days?: number
  minutes_per_day?: number
}

export interface ApplyPlanParams extends GeneratePlanParams {
  plan_name?: string
  project_id?: string
  start_date?: string
}

export interface ApplyPlanResult {
  plan: StudyPlan
  task_count: number
  task_ids: string[]
  preview: GeneratedPlan
}
