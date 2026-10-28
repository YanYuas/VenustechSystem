// ============================================================
// kernel/http/request —— 请求执行层单元测试
//
// 覆盖的是"最容易被悄悄改坏"的传输语义（全部用 vi.stubGlobal('fetch') 桩，
// 不访问真实网络/后端）：
//   ① 信封解包：code===0 → 只返回 data；code!==0 → 抛 ApiError 并带后端 message
//   ② HTTP 状态 → 错误码映射：401/422/404/500 与 502/503/504（不可达）
//   ③ 网络失败 ⇒ ApiUnreachableError + 连通性标记；幂等方法重试 1 次、写方法不重试
//   ④ 写操作网络失败 → 离线队列接管（OfflineQueuedError）；入队自身失败则保留原错误
//   ⑤ 运行时配置：get 参数过滤空值、token 头、baseURL 覆盖
// ============================================================
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  ApiError,
  ApiUnreachableError,
  http,
  OfflineQueuedError,
  setOfflineQueueHandler,
  setApiBase,
  setApiToken,
} from '..'
import { getApiBase } from '../client'
import { isBackendUnreachable, markReachable } from '../connectivity'
import { ApiErrorCode } from '../types'

type FetchArgs = [RequestInfo | URL, RequestInit | undefined]

/** 200 + 标准信封 */
function envelope<T>(data: T): Response {
  return {
    ok: true,
    status: 200,
    statusText: 'OK',
    json: async () => ({ code: 0, message: 'success', data, timestamp: 1_700_000_000 }),
  } as unknown as Response
}

/** 非 2xx 响应（body 可带后端 message） */
function httpError(status: number, statusText: string, body: unknown = {}): Response {
  return {
    ok: false,
    status,
    statusText,
    json: async () => body,
  } as unknown as Response
}

/** 2xx 但业务错误码 */
function errorEnvelope(code: number, message: string): Response {
  return {
    ok: true,
    status: 200,
    statusText: 'OK',
    json: async () => ({ code, message, data: null, timestamp: 1_700_000_000 }),
  } as unknown as Response
}

function stubFetch(impl: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>) {
  const mock = vi.fn(impl)
  vi.stubGlobal('fetch', mock)
  return mock
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
  setOfflineQueueHandler(null)
  markReachable()
  localStorage.clear()
})

describe('信封解包', () => {
  it('code===0 时只把 data 返回给调用方（信封不外泄）', async () => {
    stubFetch(async () => envelope({ id: 't1', title: '任务' }))
    await expect(http.get<{ id: string }>('/tasks/t1')).resolves.toEqual({
      id: 't1',
      title: '任务',
    })
  })

  it('code!==0 时抛 ApiError，错误码与后端 message 原样保留', async () => {
    stubFetch(async () => errorEnvelope(ApiErrorCode.AI_ERROR, '模型额度不足'))
    const err = await http.get('/ai/summary').catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).code).toBe(ApiErrorCode.AI_ERROR)
    expect((err as ApiError).message).toBe('模型额度不足')
  })
})

describe('HTTP 状态 → 错误码映射', () => {
  it('401 → AUTH_ERROR，且使用后端 body.message', async () => {
    stubFetch(async () => httpError(401, 'Unauthorized', { message: '令牌无效' }))
    const err = (await http.get('/me').catch((e: unknown) => e)) as ApiError
    expect(err.code).toBe(ApiErrorCode.AUTH_ERROR)
    expect(err.message).toBe('令牌无效')
  })

  it('422 → VALIDATION_ERROR', async () => {
    stubFetch(async () => httpError(422, 'Unprocessable Entity', { message: 'title 不能为空' }))
    const err = (await http.post('/tasks', {}).catch((e: unknown) => e)) as ApiError
    expect(err.code).toBe(ApiErrorCode.VALIDATION_ERROR)
    expect(err.message).toBe('title 不能为空')
  })

  it('404 → NOT_FOUND', async () => {
    stubFetch(async () => httpError(404, 'Not Found'))
    const err = (await http.get('/tasks/missing').catch((e: unknown) => e)) as ApiError
    expect(err.code).toBe(ApiErrorCode.NOT_FOUND)
    expect(err.message).toBe('HTTP 404: Not Found')
  })

  it('500 → SERVER_ERROR（走服务异常提示分支）', async () => {
    stubFetch(async () => httpError(500, 'Internal Server Error', { message: '数据库忙' }))
    const err = (await http.get('/dashboard').catch((e: unknown) => e)) as ApiError
    expect(err.code).toBe(ApiErrorCode.SERVER_ERROR)
    expect(err.message).toBe('数据库忙')
  })

  it('502 网关失败 → ApiUnreachableError，并标记后端不可达', async () => {
    stubFetch(async () => httpError(502, 'Bad Gateway', { message: 'proxy error' }))
    const err = (await http.get('/tasks').catch((e: unknown) => e)) as ApiUnreachableError
    expect(err).toBeInstanceOf(ApiUnreachableError)
    expect(err.unreachable).toBe(true)
    expect(isBackendUnreachable()).toBe(true)
  })
})

describe('网络失败与重试策略', () => {
  it('网络 TypeError → ApiUnreachableError，并标记不可达', async () => {
    stubFetch(async () => {
      throw new TypeError('Failed to fetch')
    })
    const err = (await http
      .post('/tasks', { title: 'x' })
      .catch((e: unknown) => e)) as ApiUnreachableError
    expect(err).toBeInstanceOf(ApiUnreachableError)
    expect(err.message).toContain('无法连接服务器')
    expect(isBackendUnreachable()).toBe(true)
  })

  it('幂等 GET 网络失败会重试 1 次后才失败（共 2 次 fetch）', async () => {
    const fetchMock = stubFetch(async () => {
      throw new TypeError('Failed to fetch')
    })
    vi.useFakeTimers()
    const pending = http.get('/tasks')
    const assertion = expect(pending).rejects.toBeInstanceOf(ApiUnreachableError)
    await vi.advanceTimersByTimeAsync(2500)
    await assertion
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('幂等 GET 第一次网络失败、重试成功时返回数据（重试确实有效）', async () => {
    let calls = 0
    const fetchMock = stubFetch(async () => {
      calls += 1
      if (calls === 1) throw new TypeError('Failed to fetch')
      return envelope({ list: [], total: 0 })
    })
    vi.useFakeTimers()
    const pending = http.get('/tasks')
    const assertion = expect(pending).resolves.toEqual({ list: [], total: 0 })
    await vi.advanceTimersByTimeAsync(2500)
    await assertion
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('写方法 POST 网络失败不重试（避免重复创建）', async () => {
    const fetchMock = stubFetch(async () => {
      throw new TypeError('Failed to fetch')
    })
    await expect(http.post('/tasks', { title: '重复风险' })).rejects.toBeInstanceOf(
      ApiUnreachableError,
    )
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('请求超时（AbortError）→ ApiUnreachableError，文案含“请求超时”', async () => {
    stubFetch(async () => {
      throw new DOMException('The operation was aborted.', 'AbortError')
    })
    const err = (await http
      .post('/tasks', { title: 'x' })
      .catch((e: unknown) => e)) as ApiUnreachableError
    expect(err).toBeInstanceOf(ApiUnreachableError)
    expect(err.message).toContain('请求超时')
    expect(isBackendUnreachable()).toBe(true)
  })
})

describe('离线队列接管（写操作）', () => {
  it('网络失败时把 POST 交给离线队列，并抛 OfflineQueuedError（带可读标签）', async () => {
    const enqueued = vi.fn(async () => undefined)
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

  it('入队自身失败时保留原始网络错误（不会假装已入队）', async () => {
    setOfflineQueueHandler(async () => {
      throw new Error('IndexedDB unavailable')
    })
    stubFetch(async () => {
      throw new TypeError('Failed to fetch')
    })

    await expect(http.post('/tasks', { title: 'x' })).rejects.toBeInstanceOf(ApiUnreachableError)
  })
})

describe('运行时配置（查询串 / token / baseURL）', () => {
  it('GET 参数过滤 undefined/null/空串，只保留有效值', async () => {
    const fetchMock = stubFetch(async () => envelope([]))
    await http.get('/tasks', { page: 1, status: '', tag: undefined, sort: null, q: '周报' })

    const [url] = fetchMock.mock.calls[0] as unknown as FetchArgs
    const parsed = new URL(String(url))
    expect(parsed.searchParams.get('page')).toBe('1')
    expect(parsed.searchParams.get('q')).toBe('周报')
    expect(parsed.searchParams.has('status')).toBe(false)
    expect(parsed.searchParams.has('tag')).toBe(false)
    expect(parsed.searchParams.has('sort')).toBe(false)
  })

  it('已保存 token 时附加 X-API-Token；自定义 baseURL 会自动补 /api/v1', async () => {
    setApiToken('  tok-1  ')
    setApiBase('http://10.0.0.5:3000/')
    expect(getApiBase()).toBe('http://10.0.0.5:3000/api/v1')

    const fetchMock = stubFetch(async () => envelope({ ok: true }))
    await http.get('/health')

    const [url, init] = fetchMock.mock.calls[0] as unknown as FetchArgs
    expect(String(url)).toBe('http://10.0.0.5:3000/api/v1/health')
    expect((init?.headers as Record<string, string>)['X-API-Token']).toBe('tok-1')
  })

  it('setApiBase("") 清除覆盖，回落到默认地址', async () => {
    setApiBase('http://custom:1')
    expect(getApiBase()).toBe('http://custom:1/api/v1')
    setApiBase('')
    expect(getApiBase()).not.toBe('http://custom:1/api/v1')
    expect(getApiBase()).toContain('/api/v1')
  })
})
