// ============================================================
// 生活记录 composable（二期 M9）
// ============================================================
import { ref } from 'vue'
import { useDataCache } from './useDataCache'
import { lifeApi } from '@/api'
import type { Habit, MoodLog, Diary } from '@/types'

export function useLife() {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const { cachedFetch } = useDataCache()
  const habits = ref<Habit[]>([])
  const moods = ref<MoodLog[]>([])
  const diaries = ref<Diary[]>([])
  const moodTrend = ref<{ avg_score: number; distribution: Record<number, number> }>({ avg_score: 0, distribution: {} })

  async function fetchHabits() {
    loading.value = true
    try { habits.value = await cachedFetch('life:habits', () => lifeApi.listHabits()) }
    catch (e: unknown) { error.value = e instanceof Error ? e.message : String(e) }
    finally { loading.value = false }
  }

  async function checkinHabit(habitId: string, note?: string) {
    return await lifeApi.checkinHabit(habitId, note)
  }

  async function fetchMoodTrend(days = 30) {
    try { moodTrend.value = await lifeApi.moodTrend(days) }
    catch (e: unknown) { error.value = e instanceof Error ? e.message : String(e) }
  }

  async function fetchDiaries(dimension?: string) {
    loading.value = true
    try { diaries.value = await lifeApi.listDiaries(dimension) }
    catch (e: unknown) { error.value = e instanceof Error ? e.message : String(e) }
    finally { loading.value = false }
  }
  return { loading, error, habits, moods, diaries, moodTrend, fetchHabits, checkinHabit, fetchMoodTrend, fetchDiaries }
}
