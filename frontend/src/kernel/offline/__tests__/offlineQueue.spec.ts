// ============================================================
// kernel/offline/offlineQueue —— 离线队列 Store 单元测试
//
// Store 的职责是"把核心队列接到 Pinia + 浏览器事件 + 原生 fetch 重放"，
// 因此这里：mock IndexedDB 适配层（注入内存 storage）、stub fetch、
// 用 vi.resetModules() 每个用例拿一份全新的 store 模块（store 内有模块级
// manager 缓存），不碰真实 IndexedDB/网络。
// ============================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { QueueEntry, QueueStorage } from '../offlineQueueCore'

const holder = vi.hoisted(() => ({ factory: undefined as undefined | (() => unknown) }))

vi.mock('../offlineQueueIdb', () => ({
  createIndexedDbStorage: () => holder.factory!() as QueueStorage,
}))

/** 内存版 QueueStorage（与 IndexedDB 适配层同语义：返回副本） */
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

function preload(storage: QueueStorage, patch: Partial<QueueEntry> = {}): Promise<number> {
  return storage.add({
    path: '/tasks',
    method: 'POST',
    body: { title: '离线任务' },
    label: '任务',
    createdAt: 1,
    retries: 0,
    ...patch,
  })
}

type FetchArgs = [RequestInfo | URL, RequestInit | undefined]
function stubFetch(impl: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>) {
  const mock = vi.fn(impl)
  vi.stubGlobal('fetch', mock)
  return mock
}
function okJson(data: unknown = {}): Response {
  return {
    ok: true,
    status: 200,
    statusText: 'OK',
    json: async () => data,
  } as unknown as Response
}
function failJson(status: number, message?: string): Response {
  return {
    ok: false,
    status,
    statusText: 'ERR',
    json: async () => (message ? { message } : {}),
  } as unknown as Response
}

let storage!: ReturnType<typeof makeStorage>
let details: Array<Record<string, unknown>> = []
function collectEvent(e: Event) {
  details.push((e as CustomEvent).detail as Record<string, unknown>)
}
let store!: Awaited<ReturnType<typeof freshStore>>

/** 本文件创建过的 store：afterEach 统一 dispose，避免上一个用例注册的 window 监听在后续用例里触发重放 */
const createdStores: Array<{ dispose: () => void }> = []

/** 拿一份全新的 store 模块（模块内有 manager 缓存，必须 resetModules） */
async function freshStore() {
  vi.resetModules()
  const { createPinia, setActivePinia } = await import('pinia')
  setActivePinia(createPinia())
  const mod = await import('../offlineQueue')
  const instance = mod.useOfflineQueueStore()
  createdStores.push({ dispose: () => instance.dispose() })
  return { store: instance, eventName: mod.OFFLINE_QUEUE_EVENT }
}

function emittedDetails(): Array<Record<string, unknown>> {
  return details
}

beforeEach(async () => {
  vi.clearAllMocks()
  localStorage.clear()
  storage = makeStorage()
  holder.factory = () => storage
  vi.stubGlobal('indexedDB', {})
  details = []
  window.addEventListener('qm-offline-queue', collectEvent)
  store = await freshStore()
})

afterEach(() => {
  // 先摘掉各 store 注册的 online/offline 监听（否则旧 store 会在后续用例里重复重放）
  createdStores.splice(0).forEach((s) => s.dispose())
  window.removeEventListener('qm-offline-queue', collectEvent)
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('offlineQueue store：初始化与计数', () => {
  it('init 载入存量条目/计数，并注册 online/offline 监听', async () => {
    await preload(storage)
    await preload(storage, { path: '/documents', retries: 3 })
    const addSpy = vi.spyOn(window, 'addEventListener')

    await store.store.init()

    expect(store.store.pending).toBe(2)
    expect(store.store.failed).toBe(1)
    expect(store.store.items).toHaveLength(2)
    expect(addSpy).toHaveBeenCalledWith('online', expect.any(Function))
    expect(addSpy).toHaveBeenCalledWith('offline', expect.any(Function))
  })

  it('hasPending / badgeText 随 pending、failed 变化（失败时带感叹号）', async () => {
    expect(store.store.hasPending).toBe(false)
    expect(store.store.badgeText).toBe('0')

    await preload(storage)
    await store.store.init()
    expect(store.store.hasPending).toBe(true)
    expect(store.store.badgeText).toBe('1')

    // 再造一条终态失败
    await storage.update({ ...(await storage.all())[0], retries: 3 })
    await store.store.flush()
    expect(store.store.badgeText).toBe('1!')
  })

  it('init 在无 IndexedDB 环境下静默返回（SSR/单测）', async () => {
    vi.stubGlobal('indexedDB', undefined)
    const fresh = await freshStore()
    await expect(fresh.store.init()).resolves.toBeUndefined()
    expect(fresh.store.pending).toBe(0)
  })
})

describe('offlineQueue store：网络事件', () => {
  it('offline 事件把 online 置 false 并广播 offline', async () => {
    await store.store.init()
    window.dispatchEvent(new Event('offline'))

    expect(store.store.online).toBe(false)
    expect(emittedDetails()).toContainEqual(expect.objectContaining({ kind: 'offline' }))
  })

  it('online 事件把 online 置 true、自动重放并广播 flushed', async () => {
    await preload(storage)
    const fetchMock = stubFetch(async () => okJson())
    await store.store.init()

    window.dispatchEvent(new Event('online'))
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

    expect(store.store.online).toBe(true)
    expect(store.store.pending).toBe(0)
    const kinds = emittedDetails().map((d) => d.kind)
    expect(kinds).toContain('online')
    expect(kinds).toContain('flushed')
  })

  it('重复 init 不会叠加 online/offline 监听（D-28 幂等）', async () => {
    const addSpy = vi.spyOn(window, 'addEventListener')
    await store.store.init()
    await store.store.init()
    await store.store.init()

    const onlineCalls = addSpy.mock.calls.filter((c) => c[0] === 'online')
    const offlineCalls = addSpy.mock.calls.filter((c) => c[0] === 'offline')
    expect(onlineCalls).toHaveLength(1)
    expect(offlineCalls).toHaveLength(1)
  })

  it('dispose 之后可以重新 init 并重新注册监听（D-28）', async () => {
    const addSpy = vi.spyOn(window, 'addEventListener')
    const removeSpy = vi.spyOn(window, 'removeEventListener')
    await store.store.init()

    store.store.dispose()
    expect(removeSpy.mock.calls.filter((c) => c[0] === 'online')).toHaveLength(1)

    await store.store.init()
    expect(addSpy.mock.calls.filter((c) => c[0] === 'online')).toHaveLength(2)
  })

  it('dispose 移除 online/offline 监听', async () => {
    await store.store.init()
    const removeSpy = vi.spyOn(window, 'removeEventListener')

    store.store.dispose()

    expect(removeSpy).toHaveBeenCalledWith('online', expect.any(Function))
    expect(removeSpy).toHaveBeenCalledWith('offline', expect.any(Function))
  })
})

describe('offlineQueue store：入队', () => {
  it('enqueue 写入条目、更新 pending 并广播 enqueued（带 label）', async () => {
    await store.store.init()

    await store.store.enqueue('/tasks', 'POST', { title: '离线任务' }, '任务')

    expect(storage.entries).toHaveLength(1)
    expect(store.store.pending).toBe(1)
    expect(store.store.items[0].path).toBe('/tasks')
    expect(emittedDetails()).toContainEqual(
      expect.objectContaining({ kind: 'enqueued', label: '任务' }),
    )
  })

  it('无 IndexedDB 时 enqueue 抛出可读错误（UI 可提示）', async () => {
    vi.stubGlobal('indexedDB', undefined)
    const fresh = await freshStore()

    await expect(fresh.store.enqueue('/tasks', 'POST', {})).rejects.toThrow(
      '离线队列不可用（无 IndexedDB）',
    )
  })
})

describe('offlineQueue store：重放与修复', () => {
  it('flush 用原生 fetch 重放：带 token 头、正确 baseURL/body，成功后出队', async () => {
    localStorage.setItem('qm-star-token', 'tok-9')
    await preload(storage)
    const fetchMock = stubFetch(async () => okJson({ ok: true }))
    await store.store.init()

    const result = await store.store.flush()

    expect(result).toEqual({ sent: 1, failed: 0, stopped: false })
    expect(store.store.pending).toBe(0)
    const [url, init] = fetchMock.mock.calls[0] as unknown as FetchArgs
    expect(String(url)).toContain('/api/v1/tasks')
    expect(init?.method).toBe('POST')
    expect((init?.headers as Record<string, string>)['X-API-Token']).toBe('tok-9')
    expect(init?.body).toBe(JSON.stringify({ title: '离线任务' }))
    expect(emittedDetails()).toContainEqual(expect.objectContaining({ kind: 'flushed', sent: 1 }))
  })

  it('flush 失败时保留条目并广播 item-failed（带后端 message）', async () => {
    await preload(storage)
    stubFetch(async () => failJson(500, 'server busy'))
    await store.store.init()

    const result = await store.store.flush()

    expect(result.sent).toBe(0)
    expect(store.store.pending).toBe(1)
    expect(store.store.items[0].retries).toBe(1)
    expect(emittedDetails()).toContainEqual(
      expect.objectContaining({ kind: 'item-failed', error: 'server busy' }),
    )
  })

  it('flushing 期间再次 flush 直接返回空结果（并发守卫）', async () => {
    await store.store.init()
    store.store.flushing = true

    await expect(store.store.flush()).resolves.toEqual({ sent: 0, failed: 0, stopped: false })
  })

  it('无 manager 时 flush 返回空结果、clearFailed 返回 0', async () => {
    vi.stubGlobal('indexedDB', undefined)
    const fresh = await freshStore()

    await expect(fresh.store.flush()).resolves.toEqual({ sent: 0, failed: 0, stopped: false })
    await expect(fresh.store.clearFailed()).resolves.toBe(0)
    await expect(fresh.store.retryAll()).resolves.toEqual({
      sent: 0,
      failed: 0,
      stopped: false,
    })
  })

  it('retryAll 把终态失败条目清零后重放成功', async () => {
    await preload(storage, { retries: 3 })
    const fetchMock = stubFetch(async () => okJson())
    await store.store.init()
    expect(store.store.failed).toBe(1)

    const result = await store.store.retryAll()

    expect(result.sent).toBe(1)
    expect(store.store.pending).toBe(0)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('clearFailed 删除终态失败条目并返回数量', async () => {
    await preload(storage, { path: '/dead', retries: 3 })
    await preload(storage, { path: '/alive' })
    await store.store.init()

    const removed = await store.store.clearFailed()

    expect(removed).toBe(1)
    expect(store.store.pending).toBe(1)
    expect(store.store.failed).toBe(0)
  })
})
