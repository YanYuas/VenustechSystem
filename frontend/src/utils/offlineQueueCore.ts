// ============================================================
// 离线队列核心（mod-tools F4.3）
//
// 设计要点：
// - **纯逻辑**：存储与发送都通过接口注入，因此可脱离浏览器单测
//   （见 frontend/scripts/test-offline-queue.mjs）
// - FIFO 重放，每条之间留间隔（默认 500ms，避免瞬间洪峰）
// - 失败重试计数，达到 maxRetries 后标记 failed 并停止（不静默丢弃）
// - 冲突策略：本期"最后写入胜出"（P2 再做手动选择）
// ============================================================

// 状态语义（测试与 UI 都依赖，不要混用）：
//   pending  —— 队列中全部条目
//   retrying —— 曾失败但未达上限（retries > 0 且 < maxRetries）：等待自动重试
//   failed   —— 已达重试上限（retries >= maxRetries）：终态失败，需人工"重试全部"或"清空失败"
// 注意：一次失败不会立刻计入 failed（那是"本轮失败次数"，不是终态），
// 因此 flush 返回的 failed 表示"本轮结束时处于终态失败的条目数"。
export interface QueueEntry {
  id?: number
  path: string
  method: 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  /** 入队时间（毫秒时间戳） */
  createdAt: number
  /** 已重试次数 */
  retries: number
  /** 最近一次失败原因 */
  lastError?: string
  /** 本地标签，仅用于面板展示（如「助理 apply」） */
  label?: string
}

export interface QueueStorage {
  add(entry: QueueEntry): Promise<number>
  all(): Promise<QueueEntry[]>
  update(entry: QueueEntry): Promise<void>
  remove(id: number): Promise<void>
  /** 清空所有失败条目，返回清除条数 */
  removeFailed(maxRetries: number): Promise<number>
}

export type FlushState = 'idle' | 'flushing' | 'done' | 'failed'

export interface QueueManagerOptions {
  storage: QueueStorage
  /** 发送器：成功 resolve，失败 reject */
  send: (entry: QueueEntry) => Promise<unknown>
  /** 每条之间的间隔毫秒（默认 500） */
  intervalMs?: number
  /** 最大重试次数（默认 3） */
  maxRetries?: number
  onStateChange?: (state: FlushState, info: { pending: number; failed: number }) => void
  /** 单条重放失败时的回调（便于 UI 提示） */
  onItemFailed?: (entry: QueueEntry, error: string) => void
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

export function createQueueManager(opts: QueueManagerOptions) {
  const intervalMs = opts.intervalMs ?? 500
  const maxRetries = opts.maxRetries ?? 3
  let flushing = false

  async function counts() {
    const items = await opts.storage.all()
    return {
      pending: items.length,
      failed: items.filter((i) => i.retries >= maxRetries).length,
    }
  }

  async function notify(state: FlushState) {
    const c = await counts()
    opts.onStateChange?.(state, c)
  }

  return {
    intervalMs,
    maxRetries,

    /** 入队一条写操作 */
    async enqueue(entry: Omit<QueueEntry, 'createdAt' | 'retries'>): Promise<number> {
      const id = await opts.storage.add({ ...entry, createdAt: Date.now(), retries: 0 })
      await notify('idle')
      return id
    },

    /** 待同步条数 */
    pending: async () => (await counts()).pending,

    /** 失败条数（达到重试上限） */
    failed: async () => (await counts()).failed,

    /**
     * 按 FIFO 重放队列。
     * - 成功 → 出队
     * - 失败 → retries+1；达到 maxRetries 则保留为失败态并**停止本轮**
     *   （避免后续条目在同一个坏端点上空转）
     */
    async flush(): Promise<{ sent: number; failed: number; stopped: boolean }> {
      if (flushing) return { sent: 0, failed: 0, stopped: false }
      flushing = true
      let sent = 0
      let failed = 0
      let stopped = false
      try {
        await notify('flushing')
        const items = (await opts.storage.all()).sort(
          (a, b) => a.createdAt - b.createdAt || (a.id ?? 0) - (b.id ?? 0),
        )
        for (let i = 0; i < items.length; i++) {
          const entry = items[i]
          if (entry.id === undefined) continue
          if (entry.retries >= maxRetries) {
            // 已达上限的条目不自动重放（需手动「重试全部」）
            failed += 1
            continue
          }
          try {
            await opts.send(entry)
            await opts.storage.remove(entry.id)
            sent += 1
            await notify('flushing')
            if (i < items.length - 1) await sleep(intervalMs)
          } catch (e) {
            const msg = e instanceof Error ? e.message : String(e)
            entry.retries += 1
            entry.lastError = msg
            await opts.storage.update(entry)
            opts.onItemFailed?.(entry, msg)
            if (entry.retries >= maxRetries) {
              failed += 1
              stopped = true
              break
            }
          }
        }
        const state: FlushState = failed > 0 ? 'failed' : 'done'
        await notify(state)
        return { sent, failed, stopped }
      } finally {
        flushing = false
      }
    },

    /** 手动「重试全部」：把失败条目的重试计数清零后重放 */
    async retryAll(): Promise<{ sent: number; failed: number; stopped: boolean }> {
      const items = await opts.storage.all()
      for (const it of items) {
        if (it.retries >= maxRetries) {
          it.retries = 0
          it.lastError = undefined
          await opts.storage.update(it)
        }
      }
      return this.flush()
    },

    /** 手动「清空失败」 */
    async clearFailed(): Promise<number> {
      const n = await opts.storage.removeFailed(maxRetries)
      await notify('idle')
      return n
    },

    /** 面板数据 */
    list: async () => (await opts.storage.all()).sort(
      (a, b) => a.createdAt - b.createdAt || (a.id ?? 0) - (b.id ?? 0),
    ),
  }
}

export type QueueManager = ReturnType<typeof createQueueManager>
