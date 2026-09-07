// ============================================================
// 第二分身 API（二期 P1）
// 长期记忆 + 灵感工作流 + 五档配置
// ============================================================
import { http } from './http'
import type { PaginatedData } from '@/types'

export interface AvatarMemory {
  id: string
  user_id: string
  memory_type: 'profile' | 'knowledge' | 'event' | 'relation'
  category: string | null
  title: string
  content: string | null
  tags: string[]
  source: string | null
  confidence: number
  is_verified: boolean
  importance: number
  created_at: string
  updated_at: string
}

export interface AvatarInspiration {
  id: string
  user_id: string
  title: string
  description: string | null
  domain: string | null
  estimated_value: string | null
  prompt: string | null
  result: string | null
  status: 'generated' | 'selected' | 'executing' | 'completed' | 'discarded'
  feedback: string | null
  batch_id: string | null
  source_type: string
  created_at: string
  updated_at: string
}

export interface AvatarConfig {
  id: string
  user_id: string
  automation_level: string
  local_model_enabled: boolean
  local_model_provider: string | null
  local_model_name: string | null
  local_model_url: string | null
  cloud_model_enabled: boolean
  cloud_model_provider: string | null
  cloud_model_name: string | null
  persona_name: string
  persona_setting: string | null
  inspiration_enabled: boolean
  inspiration_frequency: string
  inspiration_domains: string[]
  reply_length: string
  language_style: string
  creativity: number
  operation_overrides: Record<string, unknown>
  updated_at: string
}

export const avatarApi = {
  // 记忆
  listMemories(params?: { memory_type?: string; page?: number; page_size?: number }) {
    return http.get<PaginatedData<AvatarMemory>>('/avatar/memories', params as Record<string, unknown>)
  },
  memoryStats() {
    return http.get<{ profile: number; knowledge: number; event: number; relation: number; total: number; verified: number }>('/avatar/memories/stats')
  },
  createMemory(data: Partial<AvatarMemory>) {
    return http.post<AvatarMemory>('/avatar/memories', data)
  },
  updateMemory(id: string, data: Partial<AvatarMemory>) {
    return http.patch<AvatarMemory>(`/avatar/memories/${id}`, data)
  },
  deleteMemory(id: string) {
    return http.delete<void>(`/avatar/memories/${id}`)
  },
  verifyMemory(id: string, verified = true) {
    return http.post<AvatarMemory>(`/avatar/memories/${id}/verify?verified=${verified}`)
  },

  // 灵感
  generateInspirations(data: { domain?: string; count?: number; source_type?: string }) {
    return http.post<{ batch_id: string; inspirations: AvatarInspiration[]; count: number }>('/avatar/inspirations/generate', data)
  },
  listInspirations(params?: { status?: string; page?: number; page_size?: number }) {
    return http.get<PaginatedData<AvatarInspiration>>('/avatar/inspirations', params as Record<string, unknown>)
  },
  selectInspiration(id: string) {
    return http.post<AvatarInspiration>(`/avatar/inspirations/${id}/select`)
  },
  executeInspiration(id: string, result?: string) {
    const qs = result ? `?result=${encodeURIComponent(result)}` : ''
    return http.post<AvatarInspiration>(`/avatar/inspirations/${id}/execute${qs}`)
  },
  feedbackInspiration(id: string, feedback: string) {
    return http.post<AvatarInspiration>(`/avatar/inspirations/${id}/feedback?feedback=${feedback}`)
  },
  discardInspiration(id: string) {
    return http.post<AvatarInspiration>(`/avatar/inspirations/${id}/discard`)
  },

  // 配置
  getConfig() {
    return http.get<AvatarConfig>('/avatar/config')
  },
  updateConfig(data: Partial<AvatarConfig>) {
    return http.patch<AvatarConfig>('/avatar/config', data)
  },
}
