// ============================================================
// features/pet/api.ts —— 桌宠领域接口（迁移批次 P2，ADR-0007）
// 原 `api/pet.ts`。配置 + 形象管理 + 状态感知 + 四维陪伴数值。
//
// 依赖规则：领域 api 只依赖 kernel（HTTP 单点漏斗），类型取自 ./model。
// 跨域使用请从 `@/features/pet` 导入。
// ============================================================
import { http } from '@/kernel/http'
import type { PetConfig, PetAvatar, PetState, PetStats, PetStatsDelta } from './model'

export const petApi = {
  // 配置
  getConfig() {
    return http.get<PetConfig>('/pet/config')
  },
  updateConfig(data: Partial<PetConfig>) {
    return http.patch<PetConfig>('/pet/config', data)
  },

  // 形象
  listAvatars() {
    return http.get<PetAvatar[]>('/pet/avatars')
  },
  createAvatar(data: Partial<PetAvatar>) {
    return http.post<PetAvatar>('/pet/avatars', data)
  },
  updateAvatar(id: string, data: Partial<PetAvatar>) {
    return http.patch<PetAvatar>(`/pet/avatars/${id}`, data)
  },
  deleteAvatar(id: string) {
    return http.delete<void>(`/pet/avatars/${id}`)
  },
  activateAvatar(id: string) {
    return http.post<PetConfig>(`/pet/avatars/${id}/activate`)
  },

  // 状态感知
  getState() {
    return http.get<PetState>('/pet/state')
  },

  // 四维陪伴数值（S6-2：从 localStorage 迁入数据库）
  getStats() {
    return http.get<PetStats>('/pet/stats')
  },
  updateStats(delta: PetStatsDelta) {
    return http.put<PetStats>('/pet/stats', delta)
  },
}
