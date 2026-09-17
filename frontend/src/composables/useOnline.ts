// ============================================================
// useOnline —— 网络状态检测
// 对应 PRD §19.3 / US-09 / G-07
// 断网时AI功能提示，工具功能正常；网络恢复自动恢复
// ============================================================
import { ref, onMounted, onUnmounted } from 'vue'

const isOnline = ref(navigator.onLine)
const listeners = new Set<(online: boolean) => void>()

function handleOnline() {
  isOnline.value = true
  listeners.forEach((fn) => fn(true))
}

function handleOffline() {
  isOnline.value = false
  listeners.forEach((fn) => fn(false))
}

let initialized = false

export function useOnline() {
  onMounted(() => {
    if (!initialized) {
      window.addEventListener('online', handleOnline)
      window.addEventListener('offline', handleOffline)
      initialized = true
    }
  })

  onUnmounted(() => {
    // 不移除全局监听器，因为其他组件可能还在用
    // 监听器在应用生命周期内保持
  })

  function onChange(fn: (online: boolean) => void) {
    listeners.add(fn)
    return () => listeners.delete(fn)
  }

  return {
    isOnline,
    onChange,
  }
}
