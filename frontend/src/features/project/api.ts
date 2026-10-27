// ============================================================
// 项目管理 API（M06 深度开发：CRUD + 归档恢复 + 统计 + 里程碑 + 详情）
// ============================================================
import { http } from '@/kernel/http'
import type {
  CreateProjectRequest,
  Milestone,
  MilestoneCreateRequest,
  MilestoneUpdateRequest,
  Project,
  ProjectDetail,
  ProjectStats,
  UpdateProjectRequest,
} from './model'

/** 项目导出包（M06 F07）：后端返回原始实体集合，前端负责打包 ZIP */
export interface ProjectExportPayload {
  project: Project
  tasks: Array<{ id?: string; title?: string; [k: string]: unknown }>
  documents: Array<{ title?: string; content?: string; [k: string]: unknown }>
  conversations: Array<Record<string, unknown>>
  reviews: Array<{ title?: string; content?: string; [k: string]: unknown }>
  exported_at: string
}

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
  timeline(id: string) {
    return http.get<Array<{ type: string; title: string; time: string; icon: string }>>(
      `/projects/${id}/timeline`,
    )
  },
  exportData(id: string) {
    return http.get<ProjectExportPayload>(`/projects/${id}/export`)
  },
}
