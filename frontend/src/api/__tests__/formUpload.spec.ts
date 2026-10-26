// ============================================================
// FormData 上传路径 —— 纯逻辑单元测试（P0-3：备份导入 100% 失败）
//
// 修前缺陷：`backupApi.import` 构造 FormData 后调 `http.post`，
// post 内部 `JSON.stringify(form)` → body 变成 "{}"，且
// Content-Type 被写成 application/json；后端 `/backup/import` 要求
// `UploadFile = File(...)`（multipart）→ 必然 422。
//
// 这里不启动浏览器/网络，只盯三条不会再退化的约束：
//   ① FormData 原样进 fetch（没被 JSON.stringify 换成字符串）
//   ② 请求头里没有 Content-Type（boundary 必须由运行时自己写）
//   ③ 上传失败不进离线队列（FormData 无法序列化重放）
// 同时留一条 http.post 的对照断言，证明两条路径确实被区分开了。
// ============================================================
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiUnreachableError, http, OfflineQueuedError, setOfflineQueueHandler } from '../http'
import { markReachable } from '../connectivity'

/** 最小可用的 ApiResponse 桩（不依赖 jsdom 是否实现 Response） */
function okJson(data: unknown): Response {
  return {
    ok: true,
    status: 200,
    statusText: 'OK',
    json: async () => ({ code: 0, message: 'success', data, timestamp: 1 }),
  } as unknown as Response
}

type FetchArgs = [RequestInfo | URL, RequestInit | undefined]

/** 造一个和 backupApi.import 完全一致的 multipart body */
function makeBackupForm(): FormData {
  const form = new FormData()
  form.append('file', new Blob(['PK\u0003\u0004zip-bytes'], { type: 'application/zip' }), 'backup.zip')
  return form
}

function stubFetch(impl: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>) {
  const mock = vi.fn(impl)
  vi.stubGlobal('fetch', mock)
  return mock
}

afterEach(() => {
  setOfflineQueueHandler(null)
  vi.unstubAllGlobals()
  markReachable()
})

describe('http.postForm：FormData 直传', () => {
  it('body 原样交给 fetch（未被 JSON.stringify），且不手写 Content-Type', async () => {
    const fetchMock = stubFetch(async () => okJson({ success: true }))
    const stringifySpy = vi.spyOn(JSON, 'stringify')
    const form = makeBackupForm()

    await expect(http.postForm<{ success: boolean }>('/backup/import', form)).resolves.toEqual({
      success: true,
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as unknown as FetchArgs
    expect(url).toContain('/backup/import')
    expect(init?.method).toBe('POST')

    // ① 同一引用 → 没有被序列化成字符串 "{}"
    expect(init?.body).toBe(form)
    expect(typeof init?.body).not.toBe('string')

    // ② 没有 Content-Type 头 → 浏览器/运行时会自动补 multipart/form-data; boundary=...
    const headerNames = Object.keys((init?.headers ?? {}) as Record<string, string>).map((k) =>
      k.toLowerCase(),
    )
    expect(headerNames).not.toContain('content-type')

    // ③ 整个调用过程中，FormData 一次都没被 JSON.stringify 碰过
    const serializedForm = stringifySpy.mock.calls.filter((call) => call[0] === form)
    expect(serializedForm).toHaveLength(0)
  })

  it('对照：http.post 仍然 JSON.stringify + application/json（两条路径确实不同）', async () => {
    const fetchMock = stubFetch(async () => okJson({ id: 't1' }))
    const payload = { title: '写周报' }

    await http.post('/tasks', payload)

    const [, init] = fetchMock.mock.calls[0] as unknown as FetchArgs
    expect(init?.body).toBe(JSON.stringify(payload))
    expect((init?.headers as Record<string, string>)['Content-Type']).toBe('application/json')
  })
})

describe('http.postForm：离线队列语义', () => {
  it('网络失败时不入离线队列（FormData 无法重放），直接抛不可达错误', async () => {
    const enqueued = vi.fn(async () => { /* noop */ })
    setOfflineQueueHandler(enqueued)
    stubFetch(async () => {
      throw new TypeError('Failed to fetch')
    })

    await expect(http.postForm('/backup/import', makeBackupForm())).rejects.toBeInstanceOf(
      ApiUnreachableError,
    )
    expect(enqueued).not.toHaveBeenCalled()
  })

  it('对照：普通 http.post 网络失败仍会进离线队列（既有语义不变）', async () => {
    const enqueued = vi.fn(async () => { /* noop */ })
    setOfflineQueueHandler(enqueued)
    stubFetch(async () => {
      throw new TypeError('Failed to fetch')
    })

    await expect(http.post('/tasks', { title: '离线任务' })).rejects.toBeInstanceOf(
      OfflineQueuedError,
    )
    expect(enqueued).toHaveBeenCalledTimes(1)
    expect(enqueued.mock.calls[0]).toEqual(['/tasks', 'POST', { title: '离线任务' }, '任务'])
  })
})
