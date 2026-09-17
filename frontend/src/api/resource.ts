// ============================================================
// 资源中心 API（二期 M7 P0）
// 收集箱 + 模板库 + 领域库 完整CRUD
// ============================================================
import { http } from './http'
import type { InboxItem, Template, Domain, PaginatedData } from '@/types'

export const resourceApi = {
  // ==================== 收集箱 ====================
  listInbox(params?: { status?: string; page?: number; page_size?: number }) {
    return http.get<PaginatedData<InboxItem>>('/resource/inbox', params as Record<string, unknown>)
  },
  getInboxItem(id: string) {
    return http.get<InboxItem>(`/resource/inbox/${id}`)
  },
  createInboxItem(data: Partial<InboxItem>) {
    return http.post<InboxItem>('/resource/inbox', data)
  },
  updateInboxItem(id: string, data: Partial<InboxItem>) {
    return http.patch<InboxItem>(`/resource/inbox/${id}`, data)
  },
  deleteInboxItem(id: string) {
    return http.delete<void>(`/resource/inbox/${id}`)
  },
  processInboxItem(id: string, action: 'archive' | 'delete' | 'convert_task' | 'convert_doc', targetId?: string) {
    const qs = new URLSearchParams({ action })
    if (targetId) qs.set('target_id', targetId)
    return http.post<{ item_id: string; action: string; status: string }>(`/resource/inbox/${id}/process?${qs.toString()}`)
  },
  batchProcessInbox(itemIds: string[], action: string) {
    return http.post<{ total: number; success: number; failed: number }>('/resource/inbox/batch-process', { item_ids: itemIds, action })
  },

  // ==================== 模板库 ====================
  listTemplates(params?: { category?: string; page?: number; page_size?: number }) {
    return http.get<PaginatedData<Template>>('/resource/templates', params as Record<string, unknown>)
  },
  createTemplate(data: Partial<Template>) {
    return http.post<Template>('/resource/templates', data)
  },
  updateTemplate(id: string, data: Partial<Template>) {
    return http.patch<Template>(`/resource/templates/${id}`, data)
  },
  deleteTemplate(id: string) {
    return http.delete<void>(`/resource/templates/${id}`)
  },
  applyTemplate(id: string, variables: Record<string, string>) {
    return http.post<{ template_id: string; rendered: string; variables_used: string[] }>(`/resource/templates/${id}/apply`, variables)
  },

  // ==================== 领域库 ====================
  listDomains() {
    return http.get<Domain[]>('/resource/domains')
  },
  createDomain(data: Partial<Domain>) {
    return http.post<Domain>('/resource/domains', data)
  },
  updateDomain(id: string, data: Partial<Domain>) {
    return http.patch<Domain>(`/resource/domains/${id}`, data)
  },
  deleteDomain(id: string) {
    return http.delete<void>(`/resource/domains/${id}`)
  },
}
