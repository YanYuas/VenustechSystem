// ============================================================
// 长期资产库 API（二期 M10 P0）
// SOP + Prompt模板 + Skill技能 + 项目记忆
// ============================================================
import { http } from './http'
import type { SOP, PromptTemplate, Skill, ProjectMemory, PaginatedData } from '@/types'

export const assetApi = {
  // ==================== SOP 流程 ====================
  listSOPs(params?: { category?: string; page?: number; page_size?: number }) {
    return http.get<PaginatedData<SOP>>('/assets/sops', params as Record<string, unknown>)
  },
  getSOP(id: string) {
    return http.get<SOP>(`/assets/sops/${id}`)
  },
  createSOP(data: Partial<SOP>) {
    return http.post<SOP>('/assets/sops', data)
  },
  updateSOP(id: string, data: Partial<SOP>, changeNote?: string) {
    const qs = changeNote ? `?change_note=${encodeURIComponent(changeNote)}` : ''
    return http.patch<SOP>(`/assets/sops/${id}${qs}`, data)
  },
  deleteSOP(id: string) {
    return http.delete<void>(`/assets/sops/${id}`)
  },
  useSOP(id: string) {
    return http.post<SOP>(`/assets/sops/${id}/use`)
  },
  listSOPVersions(id: string) {
    return http.get<{ sop_id: string; versions: { id: string; version: number; content: Record<string, unknown>; change_note: string | null; created_at: string }[] }>(`/assets/sops/${id}/versions`)
  },

  // ==================== Prompt 模板 ====================
  listPrompts(params?: { category?: string; page?: number; page_size?: number }) {
    return http.get<PaginatedData<PromptTemplate>>('/assets/prompts', params as Record<string, unknown>)
  },
  getPrompt(id: string) {
    return http.get<PromptTemplate>(`/assets/prompts/${id}`)
  },
  createPrompt(data: Partial<PromptTemplate>) {
    return http.post<PromptTemplate>('/assets/prompts', data)
  },
  updatePrompt(id: string, data: Partial<PromptTemplate>) {
    return http.patch<PromptTemplate>(`/assets/prompts/${id}`, data)
  },
  deletePrompt(id: string) {
    return http.delete<void>(`/assets/prompts/${id}`)
  },
  applyPrompt(id: string, variables: Record<string, string>) {
    return http.post<{ prompt_id: string; rendered: string; variables_used: string[]; use_count: number }>(`/assets/prompts/${id}/apply`, variables)
  },
  ratePrompt(id: string, rating: number) {
    return http.post<PromptTemplate>(`/assets/prompts/${id}/rate?rating=${rating}`)
  },

  // ==================== Skill 技能库 ====================
  listSkills(params?: { category?: string; page?: number; page_size?: number }) {
    return http.get<PaginatedData<Skill>>('/assets/skills', params as Record<string, unknown>)
  },
  createSkill(data: Partial<Skill>) {
    return http.post<Skill>('/assets/skills', data)
  },
  updateSkill(id: string, data: Partial<Skill>) {
    return http.patch<Skill>(`/assets/skills/${id}`, data)
  },
  deleteSkill(id: string) {
    return http.delete<void>(`/assets/skills/${id}`)
  },
  useSkill(id: string) {
    return http.post<Skill>(`/assets/skills/${id}/use`)
  },

  // ==================== 项目记忆 ====================
  listMemories(params?: { project_id?: string; page?: number; page_size?: number }) {
    return http.get<PaginatedData<ProjectMemory>>('/assets/memories', params as Record<string, unknown>)
  },
  getMemory(id: string) {
    return http.get<ProjectMemory>(`/assets/memories/${id}`)
  },
  createMemory(data: Partial<ProjectMemory>) {
    return http.post<ProjectMemory>('/assets/memories', data)
  },
  updateMemory(id: string, data: Partial<ProjectMemory>) {
    return http.patch<ProjectMemory>(`/assets/memories/${id}`, data)
  },
  deleteMemory(id: string) {
    return http.delete<void>(`/assets/memories/${id}`)
  },
}
