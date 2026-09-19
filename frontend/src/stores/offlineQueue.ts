// ============================================================
// 离线队列 Store（mod-tools F4.3）
//
// 职责：
// - 持有队列管理器（核心逻辑在 utils/offlineQueueCore，存储用 IndexedDB）
// - 监听 online/offline，联网时自动 FIFO 重放
// - 暴露给 UI：pending / failed / flushing / items
// - 离线入队与重放结果通过 window CustomEvent 广播，由角标组件弹 toast
//   （store 里不直接调 toast，避免脱离组件上下文）
// ============================================================
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  createQueueManager,
  type QueueEntry,
  type QueueManager,
} from '@/utils/offlineQueueCore'
import { createIndexedDbStorage } from '@/utils/offlineQueueIdb'
import { getApiBase, getApiToken } from '@/api/http'

export const OFFLINE_QUEUE_EVENT = 'qm-offline-queue'

interface QueueEventDetail {
  kind: 'enqueued' | 'flushed' | 'item-failed' | 'offline' | 'online'
  pending: number
  sent?: number
  failed?: number
  stopped?: boolean
  label?: string
  error?: string
}

function emit(detail: QueueEventDetail) {
  try {
    window.dispatchEvent(new CustomEvent(OFFLINE_QUEUE_EVENT, { detail }))
  } catch {
    /* 非浏览器环境（单测）忽略 */
  }
}

let manager: QueueManager | null = null

export const useOfflineQueueStore = defineStore('offlineQueue', () => {
  const pending = ref(0)
  const failed = ref(0)
  const flushing = ref(false)
  const items = ref<QueueEntry[]>([])
  const online = ref(typeof navigator === 'undefined' ? true : navigator.onLine)

  const hasPending = computed(() => pending.value > 0)
  const badgeText = computed(() => (failed.value > 0 ? `${pending.value}!` : `${pending.value}`))

  function getManager(): QueueManager | null {
    if (typeof indexedDB === 'undefined') return null // 单测/SSR 环境
    if (manager) return manager
    manager = createQueueManager({
      storage: createIndexedDbStorage(),
      send: async (entry) => {
        // 用原生 fetch 重放：绕开 http.ts（避免再次入队造成死循环）
        const headers: Record<string, string> = { 'Content-Type': 'application/json' }
        const token = getApiToken()
        if (token) headers['X-API-Token'] = token
        const res = await fetch(`${getApiBase()}${entry.path}`, {
          method: entry.method,
          headers,
          body: entry.body === undefined ? undefined : JSON.stringify(entry.body),
        })
        if (!res.ok) {
          let msg = `HTTP ${res.status}`
          try {
            const j = await res.json()
            if (j?.message) msg = j.message
          } catch {
            /* ignore */
          }
          throw new Error(msg)
        }
        return res.json().catch(() => ({}))
      },
      onStateChange: async (_state, info) => {
        pending.value = info.pending
        failed.value = info.failed
        flushing.value = _state === 'flushing'
        items.value = ((await manager?.list()) ?? []).slice()
      },
      onItemFailed: (entry, error) => {
        emit({ kind: 'item-failed', pending: pending.value, label: entry.label, error })
      },
    })
    return manager
  }

  /** 应用启动时调用一次：载入存量队列并挂上网络监听 */
  async function init() {
    const m = getManager()
    if (!m) return
    items.value = await m.list()
    pending.value = await m.pending()
    failed.value = await m.failed()
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
  }

  function dispose() {
    window.removeEventListener('online', onOnline)
    window.removeEventListener('offline', onOffline)
  }

  function onOnline() {
    online.value = true
    emit({ kind: 'online', pending: pending.value })
    void flush()
  }

  function onOffline() {
    online.value = false
    emit({ kind: 'offline', pending: pending.value })
  }

  /** 拦截到离线写操作时调用 */
  async function enqueue(path: string, method: QueueEntry['method'], body?: unknown, label?: string) {
    const m = getManager()
    if (!m) throw new Error('离线队列不可用（无 IndexedDB）')
    await m.enqueue({ path, method, body, label })
    items.value = await m.list()
    pending.value = await m.pending()
    failed.value = await m.failed()
    emit({ kind: 'enqueued', pending: pending.value, label })
  }

  /** 自动重放（联网触发；也可手动点「立即同步」） */
  async function flush() {
    const m = getManager()
    if (!m || flushing.value) return { sent: 0, failed: 0, stopped: false }
    flushing.value = true
    const r = await m.flush()
    flushing.value = false
    items.value = await m.list()
    pending.value = await m.pending()
    failed.value = await m.failed()
    emit({ kind: 'flushed', pending: pending.value, ...r })
    return r
  }

  async function retryAll() {
    const m = getManager()
    if (!m) return { sent: 0, failed: 0, stopped: false }
    flushing.value = true
    const r = await m.retryAll()
    flushing.value = false
    items.value = await m.list()
    pending.value = await m.pending()
    failed.value = await m.failed()
    emit({ kind: 'flushed', pending: pending.value, ...r })
    return r
  }

  async function clearFailed() {
    const m = getManager()
    if (!m) return 0
    const n = await m.clearFailed()
    items.value = await m.list()
    pending.value = await m.pending()
    failed.value = await m.failed()
    return n
  }

  return {
    pending, failed, flushing, items, online, hasPending, badgeText,
    init, dispose, enqueue, flush, retryAll, clearFailed,
  }
})
