// ============================================================
// 仪表盘 & 备份 API
// 对应 PRD §13.7 / §13.8
// ============================================================
import { http } from './http'
import type { DashboardData } from '@/types'

export const dashboardApi = {
  get() {
    return http.get<DashboardData>('/dashboard')
  },
}

export const backupApi = {
  export() {
    return http.post<{ path: string }>('/backup/export')
  },
  import(file: File) {
    const form = new FormData()
    form.append('file', file)
    return http.post<{ success: boolean }>('/backup/import', form)
  },
  stats() {
    return http.get<{ documents: number; tasks: number; tags: number; conversations: number }>('/data/stats')
  },
}
