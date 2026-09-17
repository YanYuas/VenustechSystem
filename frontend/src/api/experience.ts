// ============================================================
// 经历视图 API（S6-4 · 只读聚合）
// ============================================================
import { http } from './http'
import type { ExperienceOut } from '@/types'

export const experienceApi = {
  /**
   * 经历时间线（日记/复盘/分身记忆/项目记忆 四源归并）
   * identity_id 与 identity_unassigned 都不传 = 全部
   */
  list(params?: { identity_id?: string; identity_unassigned?: boolean; page?: number; page_size?: number }) {
    return http.get<ExperienceOut>('/experience', params as Record<string, unknown>)
  },
}
