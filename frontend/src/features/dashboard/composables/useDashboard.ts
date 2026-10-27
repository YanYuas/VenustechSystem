// ============================================================
// useDashboard —— 首页仪表盘聚合数据
// ============================================================
import { ref } from 'vue'
import { dashboardApi } from '../api'
import { useAsync } from '@/kernel/async/useAsync'
import type { DashboardData } from '../model'

export function useDashboard() {
  const data = ref<DashboardData | null>(null)

  const { loading, execute: fetchDashboard } = useAsync(
    async () => {
      data.value = await dashboardApi.get()
      return data.value
    },
    { immediate: true },
  )

  return { data, loading, fetchDashboard }
}
