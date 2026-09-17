// ============================================================
// 身份 API（三期 B · 横切标签）
// ============================================================
import { http } from './http'
import type { Identity, CreateIdentityRequest, UpdateIdentityRequest } from '@/types'

export const identityApi = {
  /** 身份列表（默认含归档，归档的 is_active=false 灰显） */
  list(includeArchived = true) {
    return http.get<Identity[]>('/identities', { include_archived: includeArchived })
  },
  create(data: CreateIdentityRequest) {
    return http.post<Identity>('/identities', data)
  },
  detail(id: string) {
    return http.get<Identity>(`/identities/${id}`)
  },
  update(id: string, data: UpdateIdentityRequest) {
    return http.patch<Identity>(`/identities/${id}`, data)
  },
  remove(id: string) {
    return http.delete<{ deleted: boolean }>(`/identities/${id}`)
  },
}
