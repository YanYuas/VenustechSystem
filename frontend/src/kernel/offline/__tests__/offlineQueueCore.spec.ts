// ============================================================
// kernel/offline/offlineQueueCore —— 离线队列核心逻辑单元测试
//
// 该模块被刻意设计成"纯逻辑 + 依赖注入"（存储/发送器都是接口），
// 这里用内存版 QueueStorage + 可控 send 验证语义（不碰 IndexedDB / IndexedDB 适配层）：
//   - 入队字段与计数
//   - FIFO 重放、成功出队
//   - 失败计数 + 达上限进入 failed 终态并停止本轮
//   - 已达上限的条目不再自动重放（需 retryAll）
//   - retryAll 清零重放 / clearFailed 清空失败
//   - 并发 flush 守卫、onStateChange 状态序列
// ============================================================
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createQueueManager } from '../offlineQueueCore'
import type { FlushState, QueueEntry, QueueStorage } from '../offlineQueueCore'

/** 内存版存储：语义对齐 IndexedDB 适配层（返回副本，避免外部直接改内部对象） */
function makeStorage(): QueueStorage & { entries: QueueEntry[] } {
  const entries: QueueEntry[] = []
  let nextId = 1
  return {
    entries,
    async add(entry) {
      const id = nextId++
      entries.push({ ...entry, id })
      return id
    },
    async all() {
      return entries.map((e) => ({ ...e }))
    },
    async update(entry) {
      const idx = entries.findIndex((e) => e.id === entry.id)
      if (idx >= 0) entries[idx] = { ...entry }
    },
    async remove(id) {
      const idx = entries.findIndex((e) => e.id === id)
      if (idx >= 0) entries.splice(idx, 1)
    },
    async removeFailed(maxRetries) {
      const before = entries.length
      for (let i = entries.length - 1; i >= 0; i--) {
        if (entries[i].retries >= maxRetries) entries.splice(i, 1)
      }
      return before - entries.length
    },
  }
}

function entry(
  path: string,
  extra: Partial<QueueEntry> = {},
): Omit<QueueEntry, 'createdAt' | 'retries'> {
  return { path, method: 'POST', body: { path }, ...extra }
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('入队与查询', () => {
  it('enqueue 写入 createdAt/retries=0 并返回 id，pending 计数正确', async () => {
    const storage = makeStorage()
    const manager = createQueueManager({ storage, send: async () => undefined })

    const id = await manager.enqueue(entry('/tasks', { label: '任务' }))

    expect(id).toBe(1)
    expect(storage.entries).toHaveLength(1)
    expect(storage.entries[0].retries).toBe(0)
    expect(typeof storage.entries[0].createdAt).toBe('number')
    expect(await manager.pending()).toBe(1)
    expect(await manager.failed()).toBe(0)
  })

  it('list 按 createdAt 升序（同一时刻按 id）返回队列，供面板展示', async () => {
    const storage = makeStorage()
    const manager = createQueueManager({ storage, send: async () => undefined })
    await storage.add({ path: '/b', method: 'POST', createdAt: 2000, retries: 0 })
    await storage.add({ path: '/a', method: 'POST', createdAt: 1000, retries: 0 })

    const list = await manager.list()

    expect(list.map((e) => e.path)).toEqual(['/a', '/b'])
  })
})

describe('flush：重放语义', () => {
  it('成功时按 FIFO 逐条发送并出队，返回 sent 计数', async () => {
    const storage = makeStorage()
    const sent: string[] = []
    const manager = createQueueManager({
      storage,
      intervalMs: 0,
      send: async (e) => {
        sent.push(e.path)
      },
    })
    await manager.enqueue(entry('/first'))
    await manager.enqueue(entry('/second'))

    const result = await manager.flush()

    expect(sent).toEqual(['/first', '/second'])
    expect(result).toEqual({ sent: 2, failed: 0, stopped: false })
    expect(await manager.pending()).toBe(0)
  })

  it('失败时 retries+1、记录 lastError、条目保留，并回调 onItemFailed', async () => {
    const storage = makeStorage()
    const onItemFailed = vi.fn()
    const manager = createQueueManager({
      storage,
      intervalMs: 0,
      maxRetries: 3,
      send: async () => {
        throw new Error('boom')
      },
      onItemFailed,
    })
    await manager.enqueue(entry('/tasks'))

    const result = await manager.flush()

    expect(result.sent).toBe(0)
    expect(await manager.pending()).toBe(1)
    expect(storage.entries[0].retries).toBe(1)
    expect(storage.entries[0].lastError).toBe('boom')
    expect(onItemFailed).toHaveBeenCalledTimes(1)
    expect(onItemFailed.mock.calls[0][1]).toBe('boom')
  })

  it('重试达 maxRetries 后进入 failed 终态并停止本轮（stopped=true）', async () => {
    const storage = makeStorage()
    const manager = createQueueManager({
      storage,
      intervalMs: 0,
      maxRetries: 1,
      send: async () => {
        throw new Error('nope')
      },
    })
    await manager.enqueue(entry('/tasks'))

    const result = await manager.flush()

    expect(result).toEqual({ sent: 0, failed: 1, stopped: true })
    expect(await manager.failed()).toBe(1)
  })

  it('已达上限的条目不再自动重放，但同一轮里其它条目仍会发送', async () => {
    const storage = makeStorage()
    const sentPaths: string[] = []
    const manager = createQueueManager({
      storage,
      intervalMs: 0,
      maxRetries: 1,
      send: async (e) => {
        sentPaths.push(e.path)
      },
    })
    // A 已是终态失败，B 待重放
    await storage.add({ path: '/dead', method: 'POST', createdAt: 1, retries: 1 })
    await manager.enqueue(entry('/alive'))

    const result = await manager.flush()

    expect(sentPaths).toEqual(['/alive'])
    expect(result.failed).toBe(1)
    expect(result.sent).toBe(1)
    expect(await manager.pending()).toBe(1)
  })

  it('并发的第二次 flush 直接返回空结果（不会重复发送）', async () => {
    const storage = makeStorage()
    let release: (() => void) | undefined
    const send = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          release = resolve
        }),
    )
    const manager = createQueueManager({ storage, intervalMs: 0, send })
    await manager.enqueue(entry('/slow'))

    const first = manager.flush()
    const second = await manager.flush()
    expect(second).toEqual({ sent: 0, failed: 0, stopped: false })

    // 等第一条真正进入 send 之后再放行，避免依赖微任务时序
    await vi.waitFor(() => expect(send).toHaveBeenCalledTimes(1))
    release?.()
    await first
    expect(send).toHaveBeenCalledTimes(1)
  })

  it('onStateChange 依次上报 flushing → done', async () => {
    const storage = makeStorage()
    const states: FlushState[] = []
    const manager = createQueueManager({
      storage,
      intervalMs: 0,
      send: async () => undefined,
      onStateChange: (state) => states.push(state),
    })
    await manager.enqueue(entry('/tasks'))

    await manager.flush()

    expect(states).toContain('flushing')
    expect(states[states.length - 1]).toBe('done')
  })
})

describe('手动修复：retryAll / clearFailed', () => {
  it('retryAll 清零失败条目重试计数后重放成功', async () => {
    const storage = makeStorage()
    let shouldFail = true
    const manager = createQueueManager({
      storage,
      intervalMs: 0,
      maxRetries: 1,
      send: async () => {
        if (shouldFail) throw new Error('still down')
      },
    })
    await manager.enqueue(entry('/tasks'))
    await manager.flush()
    expect(await manager.failed()).toBe(1)

    shouldFail = false
    const result = await manager.retryAll()

    expect(result.sent).toBe(1)
    expect(await manager.pending()).toBe(0)
    expect(await manager.failed()).toBe(0)
  })

  it('clearFailed 只删除终态失败条目，并返回删除数量', async () => {
    const storage = makeStorage()
    const manager = createQueueManager({
      storage,
      intervalMs: 0,
      maxRetries: 1,
      send: async () => undefined,
    })
    await storage.add({ path: '/dead', method: 'POST', createdAt: 1, retries: 1 })
    await manager.enqueue(entry('/alive'))

    const removed = await manager.clearFailed()

    expect(removed).toBe(1)
    expect(await manager.pending()).toBe(1)
    expect((await manager.list())[0].path).toBe('/alive')
  })
})
