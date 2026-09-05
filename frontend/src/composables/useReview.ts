// ============================================================
// useReview —— 复盘模块业务逻辑
// ============================================================
import { ref } from 'vue'
import { reviewApi } from '@/api'
import { useAsync } from './useAsync'
import type { Review, ReviewType, ReviewData, AutoFillData } from '@/types'

export function useReview() {
  const reviews = ref<Review[]>([])
  const currentReview = ref<Review | null>(null)
  const autoFillData = ref<AutoFillData | null>(null)

  const { loading, execute: fetchReviews } = useAsync(
    async (type: ReviewType = 'daily') => {
      const res = await reviewApi.list({ type, page: 1, page_size: 30 })
      reviews.value = res.list
      return res
    },
  )

  const { execute: fetchReview } = useAsync(
    async (date: string, type: ReviewType = 'daily') => {
      currentReview.value = await reviewApi.get(date, type)
      return currentReview.value
    },
  )

  const { execute: fetchAutoFill } = useAsync(
    async (date: string, type: ReviewType = 'daily') => {
      autoFillData.value = await reviewApi.autoFill(date, type)
      return autoFillData.value
    },
  )

  const { execute: saveReview } = useAsync(
    async (data: { type: ReviewType; date: string; data: ReviewData }) => {
      currentReview.value = await reviewApi.upsert(data)
      return currentReview.value
    },
  )

  const { execute: convertToTask } = useAsync(
    async (id: string, content: string) => reviewApi.convertTask(id, { content }),
  )

  return {
    reviews,
    currentReview,
    autoFillData,
    loading,
    fetchReviews,
    fetchReview,
    fetchAutoFill,
    saveReview,
    convertToTask,
  }
}
