// ============================================================
// 任务模块类型
// 对应 PRD §13.3 任务模块 + §15.2 tasks表
// ============================================================

export type TaskStatus = 'pending' | 'in_progress' | 'waiting' | 'completed'
export type TaskPriority = 'low' | 'medium' | 'high' | 'urgent'

export interface Task {
  id: string
  title: string
  description: string | null
  status: TaskStatus
  priority: TaskPriority
  project_tag: string | null
  project_id: string | null
  project_name: string | null
  /** 身份轴（三期 B）：可空 = 未归类 */
  identity_id: string | null
  due_date: string | null
  is_focus: boolean
  progress: number
  subtasks_count: number
  subtasks_completed: number
  completed_at: string | null
  // ---------- M02 深度开发 ----------
  reminder_time: string | null
  recurrence: RecurrenceRule | null
  focus_duration: number
  // ---------- S6-1 领域规则引擎（backend schemas/task.py:45-46）----------
  /** 预估时长（分钟）：学习计划生成的任务会带上，用于日程排布 */
  estimated_minutes: number | null
  /** 达标标准：对「做完没做完」之外的第二层验收 */
  acceptance_criteria: string | null
  created_at: string
  updated_at: string
}

/** 重复规则（M02 F05）：{type, interval, days} */
export interface RecurrenceRule {
  type: 'daily' | 'weekly' | 'monthly'
  interval?: number
  days?: number[]
}

export interface Subtask {
  id: string
  task_id: string
  title: string
  completed: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

export interface TaskListQuery {
  status?: TaskStatus
  priority?: TaskPriority
  project_tag?: string
  project_id?: string
  due_date?: string
  /** 身份轴（三期 B）：按身份过滤 */
  identity_id?: string
  /** 只看未归类 */
  identity_unassigned?: boolean
  page?: number
  page_size?: number
  sort?: string
}

export interface CreateTaskRequest {
  // ADR-0008：null = 清空该字段，省略 = 不改
  title: string
  description?: string | null
  priority?: TaskPriority | null
  status?: TaskStatus | null
  project_tag?: string | null
  project_id?: string | null
  /** 身份轴（三期 B）：可空 = 未归类 */
  identity_id?: string | null
  due_date?: string | null
  reminder_time?: string | null
  recurrence?: RecurrenceRule | null
}

export interface UpdateTaskRequest {
  // ADR-0008：null = 清空该字段，省略 = 不改
  title?: string | null
  description?: string | null
  status?: TaskStatus | null
  priority?: TaskPriority | null
  project_tag?: string | null
  project_id?: string | null
  /** 身份轴（三期 B）：可空 = 未归类 */
  identity_id?: string | null
  due_date?: string | null
  /** null 表示清除提醒（一次性提醒触发后清除） */
  reminder_time?: string | null
  recurrence?: RecurrenceRule | null
  // S6-1：计划生成的任务会带这两项，允许用户后续自行微调
  // （backend schemas/task.py:82-83，estimated_minutes 有 ge=0 / le=100000 约束）
  estimated_minutes?: number | null
  acceptance_criteria?: string | null
}

// ---------- 批量操作（M02 F07） ----------

export type BatchAction = 'complete' | 'delete' | 'move_project' | 'set_priority'

export interface BatchTaskRequest {
  // ADR-0008：null = 清空该字段，省略 = 不改
  task_ids: string[]
  action: BatchAction
  project_id?: string | null
  priority?: TaskPriority | null
}

export interface BatchTaskResult {
  affected: number
  failed: number
}

// ---------- 番茄钟（M02 F08） ----------

export interface FocusSession {
  id: string
  task_id: string | null
  start_time: string
  end_time: string | null
  duration: number
  note: string | null
  created_at: string
}

export interface TodayStats {
  must_do: number
  in_progress: number
  waiting: number
  completed_today: number
}

export interface FocusTask {
  id: string
  title: string
  project_tag: string | null
  project_id: string | null
  stage: string
  progress: number
  next_step: string
  status: TaskStatus
}
