// ============================================================
// 成长体系 API（S6-2）
// ============================================================
import { http } from './http'
import type { GrowthEventItem, GrowthMeta, GrowthState, SkillNode } from '@/types'

export const growthApi = {
  /** 成长状态（经验值 / 等级 / 升级进度） */
  state() {
    return http.get<GrowthState>('/growth/state')
  },
  /** EXP 流水（最近 N 条） */
  events(limit = 20) {
    return http.get<{ list: GrowthEventItem[] }>('/growth/events', { limit })
  },
  /** 技能树（只包含有计数的分类） */
  skills() {
    return http.get<{ list: SkillNode[] }>('/growth/skills')
  },
  /** 静态元数据：等级门槛表 + EXP 规则 + 全部技能分类 */
  meta() {
    return http.get<GrowthMeta>('/growth/levels')
  },
}
