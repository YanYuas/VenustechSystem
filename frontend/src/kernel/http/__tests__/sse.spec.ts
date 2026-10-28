// ============================================================
// kernel/http/sse —— SSE 流式请求解析单元测试
//
// 覆盖：`data: ` 行解析 / 跨 chunk 半包 / 非法 JSON 跳过 / 非 2xx /
// 无响应流 / 网络失败 / 外部中止。全部用桩 Response，不真连 LLM 后端。
// ============================================================
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, sseRequest } from '..'
import { ApiErrorCode } from '../types'
import type { SseEvent } from '../types'

type FetchArgs = [RequestInfo | URL, RequestInit | undefined]

/** 用自定义 reader 模拟 SSE 流（无需 ReadableStream 实现） */
function sseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder()
  let index = 0
  return {
    ok: true,
    status: 200,
    statusText: 'OK',
    body: {
      getReader: () => ({
        read: async () => {
          if (index < chunks.length) {
            const value = encoder.encode(chunks[index])
            index += 1
            return { done: false, value }
          }
          return { done: true, value: undefined }
        },
        releaseLock: () => undefined,
      }),
    },
  } as unknown as Response
}

function stubFetch(impl: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>) {
  const mock = vi.fn(impl)
  vi.stubGlobal('fetch', mock)
  return mock
}

function collect() {
  const events: SseEvent[] = []
  return { events, onMessage: (e: SseEvent) => events.push(e) }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('sseRequest：正常流解析', () => {
  it('逐条解析 data: JSON，并按 POST + application/json 发出请求', async () => {
    const fetchMock = stubFetch(async () =>
      sseResponse([
        'data: {"type":"content","content":"你"}\n',
        '\n',
        'data: {"type":"done","tokens":2}\n\n',
      ]),
    )
    const { events, onMessage } = collect()

    await sseRequest('/conversations/1/messages', { content: '你好' }, onMessage)

    expect(events).toEqual([
      { type: 'content', content: '你' },
      { type: 'done', tokens: 2 },
    ])

    const [url, init] = fetchMock.mock.calls[0] as unknown as FetchArgs
    expect(String(url)).toContain('/conversations/1/messages')
    expect(init?.method).toBe('POST')
    expect((init?.headers as Record<string, string>)['Content-Type']).toBe('application/json')
    expect(init?.body).toBe(JSON.stringify({ content: '你好' }))
  })

  it('JSON 被拆到两个 chunk 时仍能拼回完整事件（半包处理）', async () => {
    stubFetch(async () => sseResponse(['data: {"type":"cont', 'ent","content":"ok"}\n']))
    const { events, onMessage } = collect()

    await sseRequest('/stream', {}, onMessage)

    expect(events).toEqual([{ type: 'content', content: 'ok' }])
  })

  it('非法 JSON 行被跳过，不影响后续事件', async () => {
    stubFetch(async () => sseResponse(['data: not-json\n', 'data: {"type":"done"}\n']))
    const { events, onMessage } = collect()

    await sseRequest('/stream', {}, onMessage)

    expect(events).toEqual([{ type: 'done' }])
  })
})

describe('sseRequest：错误分支', () => {
  it('非 2xx 响应 → ApiError(SERVER_ERROR)，message 含 HTTP 状态', async () => {
    stubFetch(
      async () =>
        ({
          ok: false,
          status: 500,
          statusText: 'Internal Server Error',
        }) as unknown as Response,
    )

    const err = (await sseRequest('/stream', {}, () => undefined).catch(
      (e: unknown) => e,
    )) as ApiError
    expect(err).toBeInstanceOf(ApiError)
    expect(err.code).toBe(ApiErrorCode.SERVER_ERROR)
    expect(err.message).toBe('HTTP 500: Internal Server Error')
  })

  it('响应没有 body → ApiError(“无响应流”)', async () => {
    stubFetch(
      async () => ({ ok: true, status: 200, statusText: 'OK', body: null }) as unknown as Response,
    )

    const err = (await sseRequest('/stream', {}, () => undefined).catch(
      (e: unknown) => e,
    )) as ApiError
    expect(err).toBeInstanceOf(ApiError)
    expect(err.message).toBe('无响应流')
  })

  it('网络失败（fetch TypeError）→ ApiError(“网络请求失败”)', async () => {
    stubFetch(async () => {
      throw new TypeError('Failed to fetch')
    })

    const err = (await sseRequest('/stream', {}, () => undefined).catch(
      (e: unknown) => e,
    )) as ApiError
    expect(err).toBeInstanceOf(ApiError)
    expect(err.message).toBe('网络请求失败')
  })

  it('外部 signal 已中止时请求立即带 aborted signal 发出并报“超时或已取消”', async () => {
    const controller = new AbortController()
    controller.abort()
    let sawAbortedSignal = false
    stubFetch(async (_input, init) => {
      sawAbortedSignal = Boolean(init?.signal?.aborted)
      throw new DOMException('The operation was aborted.', 'AbortError')
    })

    const err = (await sseRequest('/stream', {}, () => undefined, controller.signal).catch(
      (e: unknown) => e,
    )) as ApiError
    expect(sawAbortedSignal).toBe(true)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.message).toBe('请求超时或已取消')
  })
})
