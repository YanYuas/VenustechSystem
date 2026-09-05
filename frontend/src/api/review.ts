// ============================================================
// 复盘模块 API
// 对应 PRD §13.6
// ============================================================
import { http } from './http'
import type {
  Review, ReviewListQuery, UpsertReviewRequest, AutoFillData, ConvertTaskRequest, PaginatedData,
} from '@/types'

export const reviewApi = {
  list(params?: ReviewListQuery) {
    return http.get<PaginatedData<Review>>('/reviews', params as Record<string, unknown>)
  },
  get(date: string, type: string = 'daily') {
    return http.get<Review>(`/reviews/${date}`, { type })
  },
  upsert(data: UpsertReviewRequest) {
    return http.put<Review>('/reviews', data)
  },
  remove(id: string) {
    return http.delete<void>(`/reviews/${id}`)
  },
  autoFill(date: string, type: string = 'daily') {
    return http.get<AutoFillData>(`/reviews/${date}/auto-fill`, { type })
  },
  convertTask(id: string, data: ConvertTaskRequest) {
    return http.post<{ task_id: string }>(`/reviews/${id}/convert-task`, data)
  },
}
