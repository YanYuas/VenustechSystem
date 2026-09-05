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
  due_date: string | null
  is_focus: boolean
  progress: number
  subtasks_count: number
  subtasks_completed: number
  completed_at: string | null
  created_at: string
  updated_at: string
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
  page?: number
  page_size?: number
  sort?: string
}

export interface CreateTaskRequest {
  title: string
  description?: string
  priority?: TaskPriority
  status?: TaskStatus
  project_tag?: string
  project_id?: string
  due_date?: string
}

export interface UpdateTaskRequest {
  title?: string
  description?: string
  status?: TaskStatus
  priority?: TaskPriority
  project_tag?: string
  project_id?: string
  due_date?: string
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
