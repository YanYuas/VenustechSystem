// ============================================================
// 仪表盘聚合类型（对齐后端 schemas/dashboard.py）
// 对应 PRD §13.7 + 参考UI模块丰富度
// ============================================================
import type { FocusTask, TodayStats } from './task'

/** 模块开发状态 */
export type ModuleStatus = 'ready' | 'beta' | 'planned'

export interface ModuleStatusItem {
  id: string
  name: string
  status: ModuleStatus
  description: string
}

/** 今日执行分组 */
export interface ExecutionGroup {
  status: string
  label: string
  count: number
  tasks: Array<{
    id: string
    title: string
    priority: string
    due_date: string | null
  }>
}

export interface TodayExecution {
  groups: ExecutionGroup[]
  total: number
}

/** 当前项目 */
export interface ProjectItem {
  id: string
  name: string
  progress: number
  task_count: number
  completed_count: number
  status: ModuleStatus
}

export interface ProjectsSection {
  items: ProjectItem[]
  status: ModuleStatus
}

/** 资源中心 */
export interface ResourceCategory {
  id: string
  name: string
  count: number
  icon: string
}

export interface ResourceCenter {
  categories: ResourceCategory[]
  status: ModuleStatus
}

/** 学习与成长 */
export interface LearningItem {
  id: string
  title: string
  progress: number
  type: string
}

export interface LearningSection {
  today_study: LearningItem | null
  plans: LearningItem[]
  cards_count: number
  status: ModuleStatus
}

/** 最近文档 */
export interface RecentDocument {
  id: string
  title: string
  updated_at: string
  tags: string[]
}

/** 生活与自我 */
export interface LifeCategory {
  id: string
  name: string
  value: string
  icon: string
}

export interface LifeSection {
  categories: LifeCategory[]
  status: ModuleStatus
}

/** 快速入口 */
export interface QuickAction {
  id: string
  name: string
  icon: string
  action: string
  status: ModuleStatus
}

export interface QuickActions {
  items: QuickAction[]
}

/** AI助手状态 */
export interface AIAssistantStatus {
  enabled: boolean
  model: string
  status: ModuleStatus
  quick_prompts: string[]
}

/** 长期资产库 */
export interface AssetCategory {
  id: string
  name: string
  count: number
  icon: string
}

export interface AssetsSection {
  categories: AssetCategory[]
  status: ModuleStatus
}

/** 本周进度环（M01 F04） */
export interface WeekProgress {
  completed: number
  total: number
  percentage: number
}

/** 连续打卡徽章（M01 F05） */
export interface StreakData {
  days: number
  week_checkins: boolean[]
}
/** 用户信息 */
export interface DashboardUser {
  nickname: string
  greeting: string
}

/** 完整 Dashboard 数据 */
export interface DashboardData {
  // 已实现
  focus_task: FocusTask | null
  today_stats: TodayStats
  recent_documents: RecentDocument[]
  user: DashboardUser

  // 今日执行（已实现）
  today_execution: TodayExecution

  // 当前项目（beta）
  projects: ProjectsSection

  // 待开发模块
  resource_center: ResourceCenter
  learning: LearningSection
  life: LifeSection
  assets: AssetsSection

  // 全局
  quick_actions: QuickActions
  ai_assistant: AIAssistantStatus
  modules_status: ModuleStatusItem[]
}
