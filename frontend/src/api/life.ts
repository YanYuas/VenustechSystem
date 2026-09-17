// ============================================================
// 生活记录 API（二期 M9 P0）
// 习惯打卡 + 心情记录 + 日记
// ============================================================
import { http } from './http'
import type { Habit, HabitCheckin, MoodLog, Diary, PaginatedData } from '@/types'

export const lifeApi = {
  // ==================== 习惯追踪 ====================
  listHabits(params?: { page?: number; page_size?: number }) {
    return http.get<PaginatedData<Habit & { checked_today: boolean; current_streak: number }>>('/life/habits', params as Record<string, unknown>)
  },
  createHabit(data: Partial<Habit>) {
    return http.post<Habit>('/life/habits', data)
  },
  updateHabit(id: string, data: Partial<Habit>) {
    return http.patch<Habit>(`/life/habits/${id}`, data)
  },
  deleteHabit(id: string) {
    return http.delete<void>(`/life/habits/${id}`)
  },
  checkinHabit(id: string, checkinDate?: string) {
    const qs = checkinDate ? `?checkin_date=${checkinDate}` : ''
    return http.post<HabitCheckin>(`/life/habits/${id}/checkin${qs}`)
  },
  uncheckHabit(id: string, checkinDate?: string) {
    const qs = checkinDate ? `?checkin_date=${checkinDate}` : ''
    return http.delete<void>(`/life/habits/${id}/checkin${qs}`)
  },
  habitCalendar(id: string, year: number, month: number) {
    return http.get<{
      habit_id: string; year: number; month: number;
      calendar: ({ day: number; date: string; checked: boolean; is_today: boolean } | null)[];
      current_streak: number; total_checkins: number;
    }>('/life/habits/' + id + '/calendar', { year, month })
  },

  // ==================== 心情记录 ====================
  listMoods(params?: { page?: number; page_size?: number }) {
    return http.get<PaginatedData<MoodLog>>('/life/moods', params as Record<string, unknown>)
  },
  createMood(data: Partial<MoodLog>) {
    return http.post<MoodLog>('/life/moods', data)
  },
  deleteMood(id: string) {
    return http.delete<void>(`/life/moods/${id}`)
  },
  moodStats(days = 30) {
    return http.get<{
      avg_score: number; count: number;
      distribution: Record<string, number>;
      daily: { date: string; score: number }[];
      trend: 'up' | 'down' | 'stable'; days: number;
    }>('/life/moods/stats', { days })
  },

  // ==================== 日记 ====================
  listDiaries(params?: { page?: number; page_size?: number }) {
    return http.get<PaginatedData<Diary>>('/life/diaries', params as Record<string, unknown>)
  },
  getDiary(id: string) {
    return http.get<Diary>(`/life/diaries/${id}`)
  },
  createDiary(data: Partial<Diary>) {
    return http.post<Diary>('/life/diaries', data)
  },
  updateDiary(id: string, data: Partial<Diary>) {
    return http.patch<Diary>(`/life/diaries/${id}`, data)
  },
  deleteDiary(id: string) {
    return http.delete<void>(`/life/diaries/${id}`)
  },
}
