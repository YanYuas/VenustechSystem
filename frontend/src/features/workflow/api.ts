// ============================================================
// 工作流 API（二期 P1）
// ============================================================
import { http } from '@/kernel/http'
import type { PaginatedData } from '@/kernel/http/types'
import type { Workflow, WorkflowApplication } from './model'

export const workflowApi = {
  listPresets() {
    return http.get<{ list: Workflow[]; total: number }>('/workflows/presets')
  },
  listWorkflows(params?: { category?: string; page?: number; page_size?: number }) {
    return http.get<PaginatedData<Workflow>>('/workflows', params as Record<string, unknown>)
  },
  getWorkflow(id: string) {
    return http.get<Workflow>(`/workflows/${id}`)
  },
  createWorkflow(data: Partial<Workflow>) {
    return http.post<Workflow>('/workflows', data)
  },
  updateWorkflow(id: string, data: Partial<Workflow>) {
    return http.patch<Workflow>(`/workflows/${id}`, data)
  },
  deleteWorkflow(id: string) {
    return http.delete<void>(`/workflows/${id}`)
  },
  applyWorkflow(id: string, params: Record<string, unknown> = {}) {
    return http.post<{
      workflow_name: string
      tags_created: number
      templates_created: number
      tasks_created: number
      domains_created: number
      summary: string
      application_id: string
    }>(`/workflows/${id}/apply`, { params })
  },
  listApplications(params?: { page?: number; page_size?: number }) {
    return http.get<PaginatedData<WorkflowApplication>>(
      '/workflows/applications/history',
      params as Record<string, unknown>,
    )
  },
}
