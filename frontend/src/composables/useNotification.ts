// ============================================================
// 通知服务 —— 统一通知中心状态管理
// 用法: const { unreadCount, notifications, fetchList, markRead, markAllRead } = useNotification()
// ============================================================
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { notificationApi } from '@/api'
import type { Notification } from '@/types'
import { toast } from './useToast'

const notifications = ref<Notification[]>([])
const unreadCount = ref(0)
const loading = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null
let initialized = false

async function fetchStats() {
  try {
    const stats = await notificationApi.stats()
    unreadCount.value = stats.unread
  } catch { /* 静默失败 */ }
}

async function fetchList(unreadOnly = false, page = 1, pageSize = 20) {
  loading.value = true
  try {
    const res = await notificationApi.list({ unread_only: unreadOnly, page, page_size: pageSize })
    notifications.value = res.list
    unreadCount.value = res.list.filter((n) => !n.is_read).length
  } catch (err) {
    console.error('[Notification] fetch list failed', err)
  } finally {
    loading.value = false
  }
}

async function markRead(id: string, read = true) {
  try {
    await notificationApi.markRead(id, read)
    const item = notifications.value.find((n) => n.id === id)
    if (item) {
      item.is_read = read
      if (read) unreadCount.value = Math.max(0, unreadCount.value - 1)
      else unreadCount.value += 1
    }
  } catch (err) {
    toast.error('操作失败', String(err))
  }
}

async function markAllRead() {
  try {
    await notificationApi.markAllRead()
    notifications.value.forEach((n) => { n.is_read = true })
    unreadCount.value = 0
    toast.success('已全部标记为已读')
  } catch (err) {
    toast.error('操作失败', String(err))
  }
}

function startPolling(intervalMs = 30000) {
  if (pollTimer) return
  // 页面不可见时跳过轮询（Electron 最小化/切后台时不再空转打后端）
  pollTimer = setInterval(() => {
    if (!document.hidden) fetchStats()
  }, intervalMs)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

export function useNotification() {
  onMounted(() => {
    if (!initialized) {
      initialized = true
      fetchStats()
      startPolling()
    }
  })
  onUnmounted(() => {
    // 全局服务不停止轮询，由应用生命周期管理
  })

  return {
    notifications: computed(() => notifications.value),
    unreadCount: computed(() => unreadCount.value),
    loading: computed(() => loading.value),
    fetchList,
    fetchStats,
    markRead,
    markAllRead,
    startPolling,
    stopPolling,
  }
}
