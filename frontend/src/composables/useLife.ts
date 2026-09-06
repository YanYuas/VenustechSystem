// ============================================================
// 生活记录 composable（二期 M9 P0）
// ============================================================
import { ref } from 'vue'
import { useDataCache } from './useDataCache'
import { lifeApi } from '@/api'
import type { Habit, MoodLog, Diary } from '@/types'

export function useLife() {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const { cachedFetch } = useDataCache()
  const habits = ref<(Habit & { checked_today: boolean; current_streak: number })[]>([])
  const moods = ref<MoodLog[]>([])
  const diaries = ref<Diary[]>([])

  async function fetchHabits() {
    loading.value = true
    try {
      const data = await cachedFetch('life:habits', () => lifeApi.listHabits({ page: 1, page_size: 50 }))
      habits.value = data.list
    } catch (e: unknown) { error.value = e instanceof Error ? e.message : String(e) }
    finally { loading.value = false }
  }

  async function fetchMoods() {
    loading.value = true
    try {
      const data = await lifeApi.listMoods({ page: 1, page_size: 20 })
      moods.value = data.list
    } catch (e: unknown) { error.value = e instanceof Error ? e.message : String(e) }
    finally { loading.value = false }
  }

  async function fetchDiaries() {
    loading.value = true
    try {
      const data = await lifeApi.listDiaries({ page: 1, page_size: 50 })
      diaries.value = data.list
    } catch (e: unknown) { error.value = e instanceof Error ? e.message : String(e) }
    finally { loading.value = false }
  }

  return { loading, error, habits, moods, diaries, fetchHabits, fetchMoods, fetchDiaries }
}
