// ============================================================
// 项目管理 API
// ============================================================
import { http } from './http'
import type { Project, CreateProjectRequest, UpdateProjectRequest } from '@/types'

export const projectApi = {
  list(include_archived = false) {
    return http.get<Project[]>('/projects', { include_archived })
  },
  create(data: CreateProjectRequest) {
    return http.post<Project>('/projects', data)
  },
  detail(id: string) {
    return http.get<Project>(`/projects/${id}`)
  },
  update(id: string, data: UpdateProjectRequest) {
    return http.patch<Project>(`/projects/${id}`, data)
  },
  remove(id: string) {
    return http.delete<void>(`/projects/${id}`)
  },
}
