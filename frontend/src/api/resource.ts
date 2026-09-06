// ============================================================
// 资源中心 API（二期 M7）
// ============================================================
import { http } from './http'
import type { InboxItem, Template, Domain } from '@/types'

export const resourceApi = {
  // 收集箱
  listInbox(status?: string) {
    return http.get<InboxItem[]>('/resource/inbox', status ? { status } : {})
  },
  createInboxItem(data: Partial<InboxItem>) {
    return http.post<InboxItem>('/resource/inbox', data)
  },
  updateInboxItem(id: string, data: Partial<InboxItem>) {
    return http.patch<InboxItem>(`/resource/inbox/${id}`, data)
  },
  processInboxItem(id: string, action: string, targetId?: string) {
    return http.post<void>(`/resource/inbox/${id}/process`, { action, targetId })
  },
  // 模板库
  listTemplates(category?: string) {
    return http.get<Template[]>('/resource/templates', category ? { category } : {})
  },
  createTemplate(data: Partial<Template>) {
    return http.post<Template>('/resource/templates', data)
  },
  applyTemplate(id: string, variables: Record<string, string>) {
    return http.post<{ rendered: string }>(`/resource/templates/${id}/apply`, { variables })
  },
  // 领域库
  listDomains() {
    return http.get<Domain[]>('/resource/domains')
  },
  createDomain(data: Partial<Domain>) {
    return http.post<Domain>('/resource/domains', data)
  },
}
