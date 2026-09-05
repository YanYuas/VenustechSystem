// ============================================================
// useAutoSave —— 文档自动保存
// 对应 PRD M3-01 / §21：每30秒或失焦时自动保存，延迟≤1秒
// 用法: const { save, dirty, lastSaved } = useAutoSave((data) => api.save(data))
// ============================================================
import { ref, onMounted, onUnmounted } from 'vue'

interface UseAutoSaveOptions<T> {
  /** 保存函数 */
  onSave: (data: T) => Promise<void>
  /** 防抖间隔（ms），默认1000ms（PRD要求≤1秒） */
  debounce?: number
  /** 自动保存间隔（ms），默认30000ms（PRD要求30秒） */
  interval?: number
  /** 是否启用自动保存 */
  enabled?: boolean
}

export function useAutoSave<T>(data: () => T, options: UseAutoSaveOptions<T>) {
  const { onSave, debounce = 1000, interval = 30000, enabled = true } = options
  const dirty = ref(false)
  const saving = ref(false)
  const lastSaved = ref<Date | null>(null)
  const error = ref<Error | null>(null)

  let debounceTimer: number | null = null
  let intervalTimer: number | null = null

  async function save() {
    if (saving.value) return
    saving.value = true
    error.value = null
    try {
      await onSave(data())
      dirty.value = false
      lastSaved.value = new Date()
    } catch (err) {
      error.value = err instanceof Error ? err : new Error(String(err))
    } finally {
      saving.value = false
    }
  }

  function scheduleSave() {
    if (!enabled) return
    dirty.value = true
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = window.setTimeout(() => save(), debounce)
  }

  function onVisibilityChange() {
    if (document.hidden && dirty.value) {
      // 失焦/切后台时立即保存
      if (debounceTimer) clearTimeout(debounceTimer)
      save()
    }
  }

  function onBeforeUnload(e: BeforeUnloadEvent) {
    if (dirty.value) {
      e.preventDefault()
      e.returnValue = ''
    }
  }

  onMounted(() => {
    if (enabled) {
      intervalTimer = window.setInterval(() => {
        if (dirty.value) save()
      }, interval)
      document.addEventListener('visibilitychange', onVisibilityChange)
      window.addEventListener('beforeunload', onBeforeUnload)
    }
  })

  onUnmounted(() => {
    if (debounceTimer) clearTimeout(debounceTimer)
    if (intervalTimer) clearInterval(intervalTimer)
    document.removeEventListener('visibilitychange', onVisibilityChange)
    window.removeEventListener('beforeunload', onBeforeUnload)
    // 卸载时如有未保存数据，静默提交（绕过 save() 状态更新，避免写入已卸载组件）
    if (dirty.value) {
      onSave(data()).catch(() => { /* 卸载后忽略错误 */ })
    }
  })

  return {
    dirty,
    saving,
    lastSaved,
    error,
    save,
    scheduleSave,
  }
}
