// ============================================================
// 全局错误处理
// - 捕获未处理的 Promise rejection
// - 捕获 Vue 组件渲染错误
// - 离线状态检测与提示
// - 统一错误上报（一期仅本地日志，二期可接入上报）
// ============================================================
import type { App } from 'vue'
import { toast } from '@/composables/useToast'

let isOffline = false

export function setupErrorHandler(app: App) {
  // Vue 组件错误
  app.config.errorHandler = (err, _instance, info) => {
    console.error('[Vue Error]', err, info)
    if (import.meta.env.DEV) {
      toast.error('组件异常', String(err))
    }
  }

  // 未处理的 Promise rejection
  window.addEventListener('unhandledrejection', (event) => {
    console.error('[Unhandled Rejection]', event.reason)
    const reason = event.reason
    // ApiError 已在 http 层提示，这里不重复提示
    if (reason?.name === 'ApiError') return
    if (import.meta.env.DEV) {
      toast.error('未处理异常', String(reason?.message || reason))
    }
  })

  // 全局 JS 错误
  window.addEventListener('error', (event) => {
    console.error('[Global Error]', event.message, event.filename, event.lineno)
  })

  // 离线/在线状态检测
  window.addEventListener('offline', () => {
    isOffline = true
    toast.warning('网络已断开', '当前处于离线状态，部分功能可能不可用')
  })

  window.addEventListener('online', () => {
    if (isOffline) {
      isOffline = false
      toast.success('网络已恢复', '连接已恢复正常')
    }
  })
}

export function checkOnline(): boolean {
  return navigator.onLine
}
