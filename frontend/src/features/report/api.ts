// ============================================================
// 人生报告 API（S6-5）
// ============================================================
import { http } from '@/kernel/http'
import type { ReportData } from './model'

export const reportApi = {
  /** 三轴聚合 JSON（身份×成长×档案 + 近期经历） */
  get() {
    return http.get<ReportData>('/report')
  },
}
