// ============================================================
// 学习成长 composable（二期 M8）
// ============================================================
import { ref } from 'vue'
import { learningApi } from '@/api'
import type { StudyPlan, Flashcard } from '@/types'

export function useLearning() {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const plans = ref<StudyPlan[]>([])
  const cards = ref<Flashcard[]>([])
  const todayReviewCards = ref<Flashcard[]>([])
  const timeStats = ref<{ total_minutes: number; daily: any[] }>({ total_minutes: 0, daily: [] })

  async function fetchPlans() {
    loading.value = true
    try { plans.value = await learningApi.listPlans() }
    catch (e: any) { error.value = e.message }
    finally { loading.value = false }
  }

  async function fetchTodayReview() {
    loading.value = true
    try { todayReviewCards.value = await learningApi.todayReview() }
    catch (e: any) { error.value = e.message }
    finally { loading.value = false }
  }

  async function submitReview(cardId: string, quality: number) {
    return await learningApi.submitReview(cardId, quality)
  }

  async function fetchTimeStats(days = 30) {
    try { timeStats.value = await learningApi.timeStats(days) }
    catch (e: any) { error.value = e.message }
  }
  return { loading, error, plans, cards, todayReviewCards, timeStats, fetchPlans, fetchTodayReview, submitReview, fetchTimeStats }
}
