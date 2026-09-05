// ============================================================
// 项目模块类型
// ============================================================

export type ProjectStatus = 'active' | 'archived' | 'completed'

export interface Project {
  id: string
  user_id: string
  name: string
  description: string | null
  color: string
  status: ProjectStatus
  due_date: string | null
  sort_order: number
  task_count: number
  completed_count: number
  progress: number
  created_at: string
  updated_at: string
}

export interface CreateProjectRequest {
  name: string
  description?: string
  color?: string
  status?: ProjectStatus
  due_date?: string
}

export interface UpdateProjectRequest {
  name?: string
  description?: string
  color?: string
  status?: ProjectStatus
  due_date?: string
  sort_order?: number
}
