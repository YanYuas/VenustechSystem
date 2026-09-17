// ============================================================
// 任务模块 API（M02 深度开发：批量操作 + 番茄钟 + 子任务排序）
// 对应 PRD §13.3
// ============================================================
import { http } from './http'
import type {
  Task, Subtask, TaskListQuery, CreateTaskRequest, UpdateTaskRequest,
  TodayStats, FocusTask, PaginatedData,
  BatchTaskRequest, BatchTaskResult, FocusSession,
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
  updateSubtask(taskId: string, subId: string, data: { title?: string; completed?: boolean; sort_order?: number }) {
    return http.patch<Subtask>(`/tasks/${taskId}/subtasks/${subId}`, data)
  },
  removeSubtask(taskId: string, subId: string) {
    return http.delete<void>(`/tasks/${taskId}/subtasks/${subId}`)
  },
  // ---------- 批量操作（M02 F07） ----------
  batch(data: BatchTaskRequest) {
    return http.post<BatchTaskResult>('/tasks/batch', data)
  },
  // ---------- 番茄钟（M02 F08） ----------
  focusStart(taskId: string) {
    return http.post<FocusSession>(`/tasks/${taskId}/focus-sessions/start`)
  },
  focusStop(sessionId: string) {
    return http.post<FocusSession>(`/tasks/focus-sessions/${sessionId}/stop`)
  },
  focusSessions(taskId: string) {
    return http.get<FocusSession[]>(`/tasks/${taskId}/focus-sessions`)
  },
}
