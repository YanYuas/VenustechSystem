// ============================================================
// 左侧信息面板类型（对齐后端 schemas/panel.py）
// 对应参考UI左侧：日期卡片 + 今日状态 + 待办事项 + 系统提醒
// ============================================================

/** 今日状态统计 */
export interface LeftPanelStats {
  focus_task: number
  must_do: number
  in_progress: number
  waiting: number
  completed_today: number
}

/** 快速待办 */
export interface QuickTodo {
  id: string
  title: string
  completed: boolean
  sort_order: number
  created_at: string
  completed_at: string | null
}

/** 系统提醒 */
export interface Reminder {
  id: string
  title: string
  description: string | null
  remind_at: string | null
  type: string
  dismissed: boolean
  repeat: string | null
  created_at: string
}

/** 左侧面板聚合数据 */
export interface LeftPanelData {
  greeting: string
  date_str: string
  weekday: string
  stats: LeftPanelStats
  quick_todos: QuickTodo[]
  reminders: Reminder[]
}

/** 创建快速待办 */
export interface CreateQuickTodoRequest {
  title: string
}

/** 更新快速待办 */
export interface UpdateQuickTodoRequest {
  title?: string
  completed?: boolean
}

/** 创建系统提醒 */
export interface CreateReminderRequest {
  title: string
  description?: string
  remind_at?: string
  type?: string
  repeat?: string
}

/** 更新系统提醒 */
export interface UpdateReminderRequest {
  title?: string
  description?: string
  remind_at?: string
  type?: string
  dismissed?: boolean
  repeat?: string
}
