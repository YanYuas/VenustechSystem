// ============================================================
// 长期资产库 API（二期 M10）
// ============================================================
import { http } from './http'
import type { SOP, PromptTemplate, Skill, ProjectMemory } from '@/types'

export const assetApi = {
  // SOP
  listSOPs(category?: string) {
    return http.get<SOP[]>('/asset/sops', category ? { category } : {})
  },
  createSOP(data: Partial<SOP>) {
    return http.post<SOP>('/asset/sops', data)
  },
  updateSOP(id: string, data: Partial<SOP>) {
    return http.patch<SOP>(`/asset/sops/${id}`, data)
  },
  // Prompt模板
  listPrompts(category?: string) {
    return http.get<PromptTemplate[]>('/asset/prompts', category ? { category } : {})
  },
  createPrompt(data: Partial<PromptTemplate>) {
    return http.post<PromptTemplate>('/asset/prompts', data)
  },
  // Skill
  listSkills() {
    return http.get<Skill[]>('/asset/skills')
  },
  createSkill(data: Partial<Skill>) {
    return http.post<Skill>('/asset/skills', data)
  },
  // 项目记忆
  listMemories(projectId?: string) {
    return http.get<ProjectMemory[]>('/asset/memories', projectId ? { project_id: projectId } : {})
  },
  createMemory(data: Partial<ProjectMemory>) {
    return http.post<ProjectMemory>('/asset/memories', data)
  },
}
