// ============================================================
// 左侧信息面板 API
// 对应后端 /api/v1/panel + /quick-todos + /reminders
// ============================================================
import { http } from './http'
import type {
  LeftPanelData,
  QuickTodo,
  Reminder,
  CreateQuickTodoRequest,
  UpdateQuickTodoRequest,
  CreateReminderRequest,
  UpdateReminderRequest,
} from '@/types'

export const panelApi = {
  /** 左侧面板聚合数据 */
  get() {
    return http.get<LeftPanelData>('/panel')
  },

  /** 快速待办列表 */
  listTodos() {
    return http.get<QuickTodo[]>('/quick-todos')
  },
  createTodo(data: CreateQuickTodoRequest) {
    return http.post<QuickTodo>('/quick-todos', data)
  },
  updateTodo(id: string, data: UpdateQuickTodoRequest) {
    return http.patch<QuickTodo>(`/quick-todos/${id}`, data)
  },
  deleteTodo(id: string) {
    return http.delete<void>(`/quick-todos/${id}`)
  },

  /** 系统提醒列表 */
  listReminders() {
    return http.get<Reminder[]>('/reminders')
  },
  createReminder(data: CreateReminderRequest) {
    return http.post<Reminder>('/reminders', data)
  },
  updateReminder(id: string, data: UpdateReminderRequest) {
    return http.patch<Reminder>(`/reminders/${id}`, data)
  },
  deleteReminder(id: string) {
    return http.delete<void>(`/reminders/${id}`)
  },
}
