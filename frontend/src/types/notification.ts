// ============================================================
// 通知模块类型
// 对应 PRD §12.4 统一通知
// ============================================================

export type NotificationType = 'info' | 'success' | 'warning' | 'error'

export interface Notification {
  id: string
  type: NotificationType
  title: string
  content: string | null
  is_read: boolean
  read_at: string | null
  source_type: string | null
  source_id: string | null
  created_at: string
  updated_at: string
}

export interface NotificationListQuery {
  unread_only?: boolean
  page?: number
  page_size?: number
}

export interface CreateNotificationRequest {
  type?: NotificationType
  title: string
  content?: string
  source_type?: string
  source_id?: string
}

export interface NotificationStats {
  total: number
  unread: number
}
