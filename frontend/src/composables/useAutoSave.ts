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
  /** 保存期间又有新编辑，需要在途保存完成后补存 */
  let pendingSave = false
  /** 保存完成后是否仍有未落盘数据（防止 in-flight 期间 dirty 被误清） */
  let hasPendingData = false
  /** 保存链：卸载时的兜底提交挂到链尾，避免并发 PATCH 相互覆盖 */
  let saveChain: Promise<void> = Promise.resolve()

  async function save() {
    if (saving.value) {
      pendingSave = true
      return
    }
    saving.value = true
    hasPendingData = false
    error.value = null
    const snapshot = data()
    try {
      await onSave(snapshot)
      lastSaved.value = new Date()
    } catch (err) {
      error.value = err instanceof Error ? err : new Error(String(err))
    } finally {
      saving.value = false
      // 快照对比：保存期间用户继续输入 → 补存，杜绝并发 PATCH
      if (pendingSave || hasPendingData || JSON.stringify(data()) !== JSON.stringify(snapshot)) {
        pendingSave = false
        void save()
      } else {
        dirty.value = false
      }
    }
  }

  function scheduleSave() {
    if (!enabled) return
    dirty.value = true
    hasPendingData = true
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = window.setTimeout(() => save(), debounce)
  }

  function onVisibilityChange() {
    if (document.hidden && dirty.value) {
      // 失焦/切后台时立即保存（在途保存由 save() 内部串行补存，不会丢）
      if (debounceTimer) clearTimeout(debounceTimer)
      void save()
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
    // 卸载时如有未保存数据，挂到保存链尾串行提交（避免与在途保存并发 PATCH 相互覆盖）
    if (dirty.value) {
      const snapshot = data()
      saveChain = saveChain
        .then(() => (saving.value ? saveChain : onSave(snapshot)))
        .catch(() => { /* 卸载后忽略错误 */ })
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
