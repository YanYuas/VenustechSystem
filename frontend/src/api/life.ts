// ============================================================
// 生活记录 API（二期 M9）
// ============================================================
import { http } from './http'
import type { Habit, MoodLog, Diary } from '@/types'

export const lifeApi = {
  // 习惯
  listHabits() {
    return http.get<Habit[]>('/life/habits')
  },
  createHabit(data: Partial<Habit>) {
    return http.post<Habit>('/life/habits', data)
  },
  checkinHabit(habitId: string, note?: string) {
    return http.post<{ habit_id: string; date: string; status: string }>(`/life/habits/${habitId}/checkin`, { note })
  },
  habitStreak(habitId: string) {
    return http.get<{ current_streak: number; longest_streak: number }>(`/life/habits/${habitId}/streak`)
  },
  // 心情
  logMood(data: Partial<MoodLog>) {
    return http.post<MoodLog>('/life/moods', data)
  },
  moodTrend(days = 30) {
    return http.get<{ avg_score: number; distribution: Record<number, number> }>('/life/moods/trend', { days })
  },
  // 日记
  listDiaries(dimension?: string) {
    return http.get<Diary[]>('/life/diaries', dimension ? { dimension } : {})
  },
  createDiary(data: Partial<Diary>) {
    return http.post<Diary>('/life/diaries', data)
  },
}
