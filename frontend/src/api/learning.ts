// ============================================================
// 学习成长 API（二期 M8 P0）
// 学习计划 + 知识卡片(SM-2) + 学习时长
// ============================================================
import { http } from './http'
import type { StudyPlan, Flashcard, StudyTimeLog, PaginatedData } from '@/types'

export const learningApi = {
  // ==================== 学习计划 ====================
  listPlans(params?: { page?: number; page_size?: number }) {
    return http.get<PaginatedData<StudyPlan>>('/learning/plans', params as Record<string, unknown>)
  },
  createPlan(data: Partial<StudyPlan>) {
    return http.post<StudyPlan>('/learning/plans', data)
  },
  updatePlan(id: string, data: Partial<StudyPlan>) {
    return http.patch<StudyPlan>(`/learning/plans/${id}`, data)
  },
  deletePlan(id: string) {
    return http.delete<void>(`/learning/plans/${id}`)
  },

  // ==================== 知识卡片 ====================
  listCards(params?: { plan_id?: string; page?: number; page_size?: number }) {
    return http.get<PaginatedData<Flashcard>>('/learning/cards', params as Record<string, unknown>)
  },
  createCard(data: Partial<Flashcard>) {
    return http.post<Flashcard>('/learning/cards', data)
  },
  updateCard(id: string, data: Partial<Flashcard>) {
    return http.patch<Flashcard>(`/learning/cards/${id}`, data)
  },
  deleteCard(id: string) {
    return http.delete<void>(`/learning/cards/${id}`)
  },

  // ==================== SM-2 复习 ====================
  todayReview() {
    return http.get<{ list: Flashcard[]; total: number; date: string }>('/learning/review/today')
  },
  submitReview(cardId: string, quality: number) {
    return http.post<{
      card_id: string; quality: number; ef: number;
      repetition: number; interval: number; next_review: string;
    }>(`/learning/cards/${cardId}/review`, { quality })
  },

  // ==================== 学习时长 ====================
  logStudyTime(data: Partial<StudyTimeLog>) {
    return http.post<StudyTimeLog>('/learning/time/log', data)
  },
  timeStats(days = 30) {
    return http.get<{
      total_minutes: number; avg_minutes: number;
      daily: { date: string; minutes: number }[];
      trend: 'up' | 'down' | 'stable'; days: number;
    }>('/learning/time/stats', { days })
  },
}
