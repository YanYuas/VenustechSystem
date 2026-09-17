// ============================================================
// 通知模块 API
// 对应 PRD §12.4 统一通知
// ============================================================
import { http } from './http'
import type {
  Notification,
  NotificationListQuery,
  CreateNotificationRequest,
  NotificationStats,
  PaginatedData,
} from '@/types'

export const notificationApi = {
  list(params?: NotificationListQuery) {
    return http.get<PaginatedData<Notification>>('/notifications', params as Record<string, unknown>)
  },
  stats() {
    return http.get<NotificationStats>('/notifications/stats')
  },
  create(data: CreateNotificationRequest) {
    return http.post<Notification>('/notifications', data)
  },
  markRead(id: string, read = true) {
    return http.patch<Notification>(`/notifications/${id}/read`, { read })
  },
  markAllRead() {
    return http.post<{ success: boolean }>('/notifications/read-all')
  },
}
