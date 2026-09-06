// ============================================================
// 项目模块类型（M06 深度开发：里程碑 + 统计 + 详情聚合）
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

// ---------- 里程碑（M06 F03） ----------

export interface Milestone {
  id: string
  project_id: string
  name: string
  description: string | null
  target_date: string | null
  completed: boolean
  completed_at: string | null
  task_ids: string[]
  sort_order: number
  created_at: string
  updated_at: string
}

export interface MilestoneCreateRequest {
  name: string
  description?: string
  target_date?: string
  task_ids?: string[]
  sort_order?: number
}

export interface MilestoneUpdateRequest {
  name?: string
  description?: string
  target_date?: string
  completed?: boolean
  task_ids?: string[]
  sort_order?: number
}

// ---------- 项目统计（M06 F02） ----------

export interface ProjectStats {
  task_count: number
  completed_count: number
  progress: number
  status_distribution: Record<string, number>
  weekly_trend: Array<{ date: string; completed: number }>
  overdue_count: number
  milestone_count: number
  milestone_completed: number
  health: 'good' | 'warning' | 'risk'
}

// ---------- 项目详情聚合（M06 F01） ----------

export interface ProjectDetailTask {
  id: string
  title: string
  status: string
  priority: string
  due_date: string | null
  is_focus: boolean
  completed_at: string | null
  created_at: string | null
}

export interface ProjectDetailDocument {
  id: string
  title: string
  updated_at: string | null
  tags: string[]
  word_count: number
}

export interface ProjectDetailConversation {
  id: string
  title: string
  updated_at: string | null
}

export interface ProjectDetailReview {
  id: string
  type: string
  review_date: string
  mood: number | null
  summary: string
}

export interface ProjectDetail extends Project {
  tasks: ProjectDetailTask[]
  documents: ProjectDetailDocument[]
  conversations: ProjectDetailConversation[]
  reviews: ProjectDetailReview[]
  milestones: Milestone[]
}
