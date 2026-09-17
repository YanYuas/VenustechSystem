// ============================================================
// 人生报告 API（S6-5）
// ============================================================
import { http } from './http'
import type { ReportData } from '@/types'

export const reportApi = {
  /** 三轴聚合 JSON（身份×成长×档案 + 近期经历） */
  get() {
    return http.get<ReportData>('/report')
  },
}
