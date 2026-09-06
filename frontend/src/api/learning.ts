// ============================================================
// 学习成长 API（二期 M8）
// ============================================================
import { http } from './http'
import type { StudyPlan, Flashcard, StudyTimeLog, ReviewResult } from '@/types'

export const learningApi = {
  // 学习计划
  listPlans() {
    return http.get<StudyPlan[]>('/learning/plans')
  },
  createPlan(data: Partial<StudyPlan>) {
    return http.post<StudyPlan>('/learning/plans', data)
  },
  updatePlan(id: string, data: Partial<StudyPlan>) {
    return http.patch<StudyPlan>(`/learning/plans/${id}`, data)
  },
  // 知识卡片
  listCards(planId?: string) {
    return http.get<Flashcard[]>('/learning/cards', planId ? { plan_id: planId } : {})
  },
  createCard(data: Partial<Flashcard>) {
    return http.post<Flashcard>('/learning/cards', data)
  },
  // SM-2 复习
  todayReview() {
    return http.get<Flashcard[]>('/learning/review/today')
  },
  submitReview(cardId: string, quality: number) {
    return http.post<ReviewResult>(`/learning/cards/${cardId}/review`, { quality })
  },
  // 学习时长
  logStudyTime(data: Partial<StudyTimeLog>) {
    return http.post<StudyTimeLog>('/learning/time/log', data)
  },
  timeStats(days = 30) {
    return http.get<{ total_minutes: number; daily: { date: string; minutes: number }[] }>('/learning/time/stats', { days })
  },
}
