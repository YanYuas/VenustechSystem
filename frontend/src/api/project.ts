// ============================================================
// 项目管理 API（M06 深度开发：CRUD + 归档恢复 + 统计 + 里程碑 + 详情）
// ============================================================
import { http } from './http'
import type {
  CreateProjectRequest,
  Milestone,
  MilestoneCreateRequest,
  MilestoneUpdateRequest,
  Project,
  ProjectDetail,
  ProjectStats,
  UpdateProjectRequest,
} from '@/types'

export const projectApi = {
  list(include_archived = false) {
    return http.get<Project[]>('/projects', { include_archived })
  },
  create(data: CreateProjectRequest) {
    return http.post<Project>('/projects', data)
  },
  /** M06 F01：详情聚合（基础信息 + 任务/文档/对话/复盘/里程碑） */
  detail(id: string) {
    return http.get<ProjectDetail>(`/projects/${id}`)
  },
  update(id: string, data: UpdateProjectRequest) {
    return http.patch<Project>(`/projects/${id}`, data)
  },
  remove(id: string) {
    return http.delete<void>(`/projects/${id}`)
  },
  // ---------- 归档 / 恢复（M06 F04） ----------
  archive(id: string) {
    return http.post<Project>(`/projects/${id}/archive`)
  },
  restore(id: string) {
    return http.post<Project>(`/projects/${id}/restore`)
  },
  // ---------- 统计（M06 F02） ----------
  stats(id: string) {
    return http.get<ProjectStats>(`/projects/${id}/stats`)
  },
  // ---------- 里程碑（M06 F03） ----------
  listMilestones(projectId: string) {
    return http.get<Milestone[]>(`/projects/${projectId}/milestones`)
  },
  createMilestone(projectId: string, data: MilestoneCreateRequest) {
    return http.post<Milestone>(`/projects/${projectId}/milestones`, data)
  },
  updateMilestone(milestoneId: string, data: MilestoneUpdateRequest) {
    return http.patch<Milestone>(`/projects/milestones/${milestoneId}`, data)
  },
  removeMilestone(milestoneId: string) {
    return http.delete<void>(`/projects/milestones/${milestoneId}`)
  },
}
