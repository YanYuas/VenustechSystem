// ============================================================
// 任务模块 API
// 对应 PRD §13.3
// ============================================================
import { http } from './http'
import type {
  Task, Subtask, TaskListQuery, CreateTaskRequest, UpdateTaskRequest,
  TodayStats, FocusTask, PaginatedData,
} from '@/types'

export const taskApi = {
  list(params?: TaskListQuery) {
    return http.get<PaginatedData<Task>>('/tasks', params as Record<string, unknown>)
  },
  create(data: CreateTaskRequest) {
    return http.post<Task>('/tasks', data)
  },
  detail(id: string) {
    return http.get<Task & { subtasks: Subtask[] }>(`/tasks/${id}`)
  },
  update(id: string, data: UpdateTaskRequest) {
    return http.patch<Task>(`/tasks/${id}`, data)
  },
  remove(id: string) {
    return http.delete<void>(`/tasks/${id}`)
  },
  setFocus(id: string) {
    return http.post<void>(`/tasks/${id}/focus`)
  },
  cancelFocus(id: string) {
    return http.delete<void>(`/tasks/${id}/focus`)
  },
  todayStats() {
    return http.get<TodayStats>('/tasks/today/stats')
  },
  focus() {
    return http.get<FocusTask | null>('/tasks/focus')
  },
  addSubtask(taskId: string, title: string) {
    return http.post<Subtask>(`/tasks/${taskId}/subtasks`, { title })
  },
  updateSubtask(taskId: string, subId: string, data: { title?: string; completed?: boolean }) {
    return http.patch<Subtask>(`/tasks/${taskId}/subtasks/${subId}`, data)
  },
  removeSubtask(taskId: string, subId: string) {
    return http.delete<void>(`/tasks/${taskId}/subtasks/${subId}`)
  },
}
