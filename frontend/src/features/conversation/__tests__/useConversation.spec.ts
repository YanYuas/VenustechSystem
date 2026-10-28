// ============================================================
// features/conversation/composables/useConversation —— 业务编排单元测试
//
// 该 composable 是"第二分身"的编排层：规则降级 / SSE 流式 / 会话 CRUD。
// 全部 mock 领域 api + SSE 回调，不连真实 LLM 后端；规则模式的打字机用真实
// 定时器即可（每次 ~0.6s），避免 fake timer 与 watch/await 链互相干扰。
// ============================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, type EffectScope } from 'vue'

import { STORAGE_KEYS } from '@/shared/constants'
import { toast } from '@/kernel/ui/toast'
import type { GeneratedPlan } from '@/features/learning'
import { aiApi, conversationApi } from '../api'
import { learningApi } from '@/features/learning'
import { useConversation } from '../composables/useConversation'
import type { Conversation, Message } from '../model'

vi.mock('../api', () => ({
  conversationApi: {
    list: vi.fn(),
    messages: vi.fn(),
    create: vi.fn(),
    remove: vi.fn(),
    sendStream: vi.fn(),
  },
  aiApi: { summarize: vi.fn(), suggestTags: vi.fn(), inspiration: vi.fn() },
}))

vi.mock('@/features/learning', () => ({
  learningApi: { generatePlan: vi.fn() },
}))

vi.mock('@/kernel/ui/toast', () => ({
  toast: { error: vi.fn(), success: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

const list = vi.mocked(conversationApi.list)
const messagesApi = vi.mocked(conversationApi.messages)
const create = vi.mocked(conversationApi.create)
const remove = vi.mocked(conversationApi.remove)
const sendStream = vi.mocked(conversationApi.sendStream)
const generatePlan = vi.mocked(learningApi.generatePlan)
const toastError = vi.mocked(toast.error)

function makeConversation(id: string, title = '对话'): Conversation {
  return {
    id,
    title,
    created_at: '2026-01-01T00:00:00',
    updated_at: '2026-01-01T00:00:00',
  } as unknown as Conversation
}

function makeMessage(patch: Partial<Message> = {}): Message {
  return {
    id: 'm1',
    conversation_id: 'c1',
    role: 'assistant',
    content: '服务端消息',
    tokens: null,
    referenced_doc_ids: [],
    created_at: '2026-01-01T00:00:00',
    ...patch,
  } as unknown as Message
}

function makePlan(patch: Partial<GeneratedPlan> = {}): GeneratedPlan {
  return {
    matched: true,
    domain_name: '雅思',
    skill_name: '雅思',
    total_days: 30,
    units: [{ name: '听力', task_count: 3, goal: '', acceptance: '' }],
    items: [{ title: '第1天', task: '背单词', duration: '30 分钟', acceptance: '完成 50 词' }],
    verify_task: '完成一次模考',
    ...patch,
  } as unknown as GeneratedPlan
}

/** 无 API Key 的本地模式：规则降级路径（真实定时器模拟打字机） */
function setLocalMode(nickname = '小明') {
  localStorage.setItem(
    STORAGE_KEYS.userConfig,
    JSON.stringify({ api_key_configured: false, nickname }),
  )
}

/** 有 API Key：走 SSE 流式路径 */
function setAiMode() {
  localStorage.setItem(STORAGE_KEYS.userConfig, JSON.stringify({ api_key_configured: true }))
}

let scope: EffectScope | null = null
function setup() {
  scope = effectScope()
  return scope.run(() => useConversation())!
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  list.mockResolvedValue([makeConversation('c1')])
  messagesApi.mockResolvedValue([makeMessage()])
  create.mockResolvedValue(makeConversation('c-new'))
  remove.mockResolvedValue(undefined)
  sendStream.mockResolvedValue(undefined)
  generatePlan.mockResolvedValue(makePlan())
  vi.mocked(aiApi.summarize).mockResolvedValue({ summary: 'S' } as never)
  vi.mocked(aiApi.suggestTags).mockResolvedValue({ tags: ['a'] } as never)
  vi.mocked(aiApi.inspiration).mockResolvedValue({ questions: ['q'] } as never)
})

afterEach(() => {
  scope?.stop()
  scope = null
  localStorage.clear()
  vi.useRealTimers()
})

describe('useConversation：本地规则模式（无 API Key）', () => {
  it('问候语命中规则回复，包含配置里的昵称，并落地 user+assistant 两条消息', async () => {
    setLocalMode('小明')
    const api = setup()
    api.currentId.value = 'c1'

    await api.sendMessage({ content: '你好' })

    expect(api.messages.value).toHaveLength(2)
    expect(api.messages.value[0].role).toBe('user')
    expect(api.messages.value[1].role).toBe('assistant')
    expect(api.messages.value[1].content).toContain('小明')
    expect(api.streaming.value).toBe(false)
    expect(api.streamContent.value).toBe('')
    expect(sendStream).not.toHaveBeenCalled()
  })

  it('未命中任何关键词时回退默认话术，且不丢用户原文', async () => {
    setLocalMode()
    const api = setup()
    api.currentId.value = 'c1'
    vi.spyOn(Math, 'random').mockReturnValue(0)

    await api.sendMessage({ content: '随便聊聊天气' })

    expect(api.messages.value[1].content).toContain('随便聊聊天气')
  })

  it('学习意图交给领域规则引擎：解析出 30 天 / 每天 2 小时', async () => {
    setLocalMode()
    const api = setup()
    api.currentId.value = 'c1'

    await api.sendMessage({ content: '我想学雅思，30 天，每天 2 小时' })

    expect(generatePlan).toHaveBeenCalledWith({
      goal: '我想学雅思，30 天，每天 2 小时',
      total_days: 30,
      minutes_per_day: 120,
    })
    expect(api.messages.value[1].content).toContain('能力拆解')
  })

  it('规则引擎异常时回退话术（降级路径本身不能变成新的失败点）', async () => {
    setLocalMode()
    const api = setup()
    api.currentId.value = 'c1'
    vi.spyOn(Math, 'random').mockReturnValue(0)
    generatePlan.mockRejectedValueOnce(new Error('engine down'))

    await api.sendMessage({ content: '我想学吉他，30 天' })

    expect(api.messages.value[1].content).toContain('我想学吉他')
    expect(api.messages.value[1].content).not.toContain('能力拆解')
  })

  it('计划命中领域库时渲染领域名 / 前 5 天 / 最终验证任务', async () => {
    setLocalMode()
    const api = setup()
    api.currentId.value = 'c1'
    generatePlan.mockResolvedValueOnce(
      makePlan({
        items: Array.from({ length: 7 }, (_, i) => ({
          title: `第${i + 1}天`,
          task: '练习',
          duration: '30 分钟',
          acceptance: '达标',
        })) as unknown as GeneratedPlan['items'],
      }),
    )

    await api.sendMessage({ content: '我想学雅思 30 天' })

    const reply = api.messages.value[1].content
    expect(reply).toContain('雅思')
    expect(reply).toContain('共 7 项')
    expect(reply).toContain('最终验证任务')
  })

  it('计划未命中领域库时说明使用通用四阶段法', async () => {
    setLocalMode()
    const api = setup()
    api.currentId.value = 'c1'
    generatePlan.mockResolvedValueOnce(
      makePlan({ matched: false, domain_name: null, skill_name: '手碟', items: [] }),
    )

    await api.sendMessage({ content: '我想学手碟 10 天' })

    expect(api.messages.value[1].content).toContain('通用四阶段法')
  })

  it('hasApiKey 反映本地配置（true/false/坏 JSON 都不抛）', () => {
    const api = setup()
    expect(api.hasApiKey()).toBe(false)

    setAiMode()
    expect(api.hasApiKey()).toBe(true)

    localStorage.setItem(STORAGE_KEYS.userConfig, '{bad json')
    expect(api.hasApiKey()).toBe(false)
  })

  it('stopStreaming 中断规则模式打字机：保留已输出的部分内容', async () => {
    setLocalMode()
    const api = setup()
    api.currentId.value = 'c1'

    const pending = api.sendMessage({ content: '你好' })
    await new Promise((r) => setTimeout(r, 30))
    api.stopStreaming()
    await pending

    const assistant = api.messages.value[1]
    expect(assistant.role).toBe('assistant')
    expect(assistant.content.length).toBeGreaterThan(0)
    expect(api.streaming.value).toBe(false)
  })
})

describe('useConversation：SSE 流式模式（有 API Key）', () => {
  it('正常流：累积内容后刷新消息列表，流结束复位状态', async () => {
    setAiMode()
    const api = setup()
    api.currentId.value = 'c1'
    sendStream.mockImplementationOnce(async (_id, _data, onMessage) => {
      onMessage({ type: 'content', content: '你' })
      onMessage({ type: 'content', content: '好' })
      onMessage({ type: 'done', tokens: 2 })
    })
    messagesApi.mockResolvedValueOnce([makeMessage({ content: '你好' })])

    await api.sendMessage({ content: '在吗' })

    expect(sendStream).toHaveBeenCalledTimes(1)
    expect(messagesApi).toHaveBeenCalledWith('c1')
    expect(api.messages.value).toEqual([makeMessage({ content: '你好' })])
    expect(api.streaming.value).toBe(false)
    expect(api.streamContent.value).toBe('')
    expect(toastError).not.toHaveBeenCalled()
  })

  it('流内错误帧：toast 报错且不刷新消息（避免把半截内容当成功）', async () => {
    setAiMode()
    const api = setup()
    api.currentId.value = 'c1'
    sendStream.mockImplementationOnce(async (_id, _data, onMessage) => {
      onMessage({ type: 'error', error: '会话不存在' })
    })

    await api.sendMessage({ content: 'hi' })

    expect(toastError).toHaveBeenCalledWith('分身响应失败', '会话不存在')
    expect(messagesApi).not.toHaveBeenCalled()
    expect(api.messages.value).toHaveLength(1) // 只有本地 user 消息
  })

  it('流失败时保留已生成内容为兜底消息，并 toast 提示', async () => {
    setAiMode()
    const api = setup()
    api.currentId.value = 'c1'
    sendStream.mockImplementationOnce(async (_id, _data, onMessage) => {
      onMessage({ type: 'content', content: '半截回复' })
      throw new Error('network reset')
    })

    await api.sendMessage({ content: 'hi' })

    expect(toastError).toHaveBeenCalledWith('分身响应失败', 'network reset')
    const fallback = api.messages.value[api.messages.value.length - 1]
    expect(fallback.role).toBe('assistant')
    expect(fallback.content).toBe('半截回复')
  })

  it('主动 stopStreaming 中止时不再 toast（用户主动取消不算失败）', async () => {
    setAiMode()
    const api = setup()
    api.currentId.value = 'c1'
    sendStream.mockImplementationOnce(
      (_id, _data, _onMessage, signal) =>
        new Promise<void>((_resolve, reject) => {
          signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
        }),
    )

    const pending = api.sendMessage({ content: 'hi' })
    await vi.waitFor(() => expect(sendStream).toHaveBeenCalledTimes(1))
    api.stopStreaming()
    await pending

    expect(toastError).not.toHaveBeenCalled()
    expect(api.streaming.value).toBe(false)
  })

  it('并发保护：流式进行中再次 sendMessage 直接返回，不重复发起请求', async () => {
    setAiMode()
    const api = setup()
    api.currentId.value = 'c1'
    let resolveStream: (() => void) | undefined
    sendStream.mockImplementationOnce(
      () =>
        new Promise<void>((resolve) => {
          resolveStream = resolve
        }),
    )

    const first = api.sendMessage({ content: '第一条' })
    await vi.waitFor(() => expect(sendStream).toHaveBeenCalledTimes(1))

    await api.sendMessage({ content: '第二条' })
    expect(sendStream).toHaveBeenCalledTimes(1)
    expect(api.messages.value.filter((m) => m.role === 'user')).toHaveLength(1)

    resolveStream?.()
    await first
  })

  it('没有当前会话时 sendMessage 不动作', async () => {
    setAiMode()
    const api = setup()

    await api.sendMessage({ content: 'hi' })

    expect(api.messages.value).toHaveLength(0)
    expect(sendStream).not.toHaveBeenCalled()
  })
})

describe('useConversation：会话 CRUD 与 AI 文档能力', () => {
  it('fetchConversations 写入列表；失败时向上抛', async () => {
    const api = setup()
    await api.fetchConversations()
    expect(api.conversations.value.map((c) => c.id)).toEqual(['c1'])

    list.mockRejectedValueOnce(new Error('list down'))
    await expect(api.fetchConversations()).rejects.toThrow('list down')
  })

  it('fetchMessages 同时设置 currentId 与消息列表', async () => {
    const api = setup()
    await api.fetchMessages('c9')
    expect(api.currentId.value).toBe('c9')
    expect(api.messages.value).toHaveLength(1)
  })

  it('createConversation 设置当前会话并刷新列表', async () => {
    const api = setup()
    await api.createConversation('新对话')
    expect(create).toHaveBeenCalledWith('新对话')
    expect(api.currentId.value).toBe('c-new')
    expect(list).toHaveBeenCalledTimes(1)
  })

  it('deleteConversation：删除当前会话时清空 currentId 与消息', async () => {
    const api = setup()
    await api.fetchConversations()
    api.currentId.value = 'c1'
    api.messages.value = [makeMessage()]

    await api.deleteConversation('c1')

    expect(remove).toHaveBeenCalledWith('c1')
    expect(api.conversations.value).toHaveLength(0)
    expect(api.currentId.value).toBeNull()
    expect(api.messages.value).toHaveLength(0)
  })

  it('deleteConversation：删除非当前会话时保留当前上下文', async () => {
    const api = setup()
    api.conversations.value = [makeConversation('c1'), makeConversation('c2')]
    api.currentId.value = 'c1'
    api.messages.value = [makeMessage()]

    await api.deleteConversation('c2')

    expect(api.currentId.value).toBe('c1')
    expect(api.messages.value).toHaveLength(1)
  })

  it('summarize / suggestTags / getInspiration 委托 aiApi', async () => {
    const api = setup()
    await api.summarize('d1')
    await api.suggestTags('d1')
    await api.getInspiration('d1')

    expect(aiApi.summarize).toHaveBeenCalledWith('d1')
    expect(aiApi.suggestTags).toHaveBeenCalledWith('d1')
    expect(aiApi.inspiration).toHaveBeenCalledWith('d1')
  })
})
