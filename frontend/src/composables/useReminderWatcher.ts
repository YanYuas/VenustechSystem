// ============================================================
// useReminderWatcher —— 提醒到期监控
// 定期检查提醒，到期时触发桌面通知 + 应用内通知
// ============================================================
import { ref, onMounted, onUnmounted } from 'vue'
import { panelApi, notificationApi } from '@/api'
import { toast } from './useToast'

const CHECK_INTERVAL = 30000 // 30秒检查一次
const notifiedIds = new Set<string>() // 已通知过的提醒ID，避免重复

let timer: ReturnType<typeof setInterval> | null = null
let running = false

export function useReminderWatcher() {
  const supported = ref(false)

  // 请求桌面通知权限
  async function requestPermission() {
    if (!('Notification' in window)) {
      supported.value = false
      return false
    }
    if (Notification.permission === 'granted') {
      supported.value = true
      return true
    }
    if (Notification.permission !== 'denied') {
      const result = await Notification.requestPermission()
      supported.value = result === 'granted'
      return supported.value
    }
    return false
  }

  // 显示桌面通知
  function showDesktopNotification(title: string, body: string) {
    if (!supported.value || !('Notification' in window)) return
    try {
      const n = new Notification(title, {
        body,
        icon: '/favicon.ico',
        tag: 'venustech-reminder',
      })
      n.onclick = () => {
        window.focus()
        n.close()
      }
    } catch { /* ignore */ }
  }

  // 检查到期提醒
  async function checkReminders() {
    try {
      const reminders = await panelApi.listReminders()
      const now = Date.now()

      for (const r of reminders) {
        if (r.dismissed || !r.remind_at) continue
        if (notifiedIds.has(r.id)) continue

        const remindTime = new Date(r.remind_at).getTime()
        // 提醒时间已到（且在过去1小时内，避免太旧的提醒）
        if (remindTime <= now && now - remindTime < 3600000) {
          notifiedIds.add(r.id)

          // 1. 桌面通知
          showDesktopNotification(r.title, r.description ?? '启明星提醒')

          // 2. 应用内toast
          toast.warning(r.title, r.description ?? '时间到了')

          // 3. 创建系统通知（出现在顶部通知栏）
          try {
            await notificationApi.create({
              title: r.title,
              content: r.description ?? '提醒时间到',
              type: 'warning',
              source_type: 'reminder',
              source_id: r.id,
            })
          } catch { /* ignore */ }

          // 4. 标记提醒为已触发（dismissed）
          try {
            await panelApi.updateReminder(r.id, { dismissed: true })
          } catch { /* ignore */ }
        }
      }
    } catch {
      // 静默失败，不影响用户
    }
  }

  // 启动监控
  function start() {
    if (running) return
    running = true
    requestPermission()
    // 启动后先检查一次
    checkReminders()
    // 定期检查
    timer = setInterval(checkReminders, CHECK_INTERVAL)
  }

  // 停止监控
  function stop() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    running = false
  }

  onMounted(() => {
    start()
  })

  onUnmounted(() => {
    stop()
  })

  return {
    supported,
    requestPermission,
    checkReminders,
    start,
    stop,
  }
}
