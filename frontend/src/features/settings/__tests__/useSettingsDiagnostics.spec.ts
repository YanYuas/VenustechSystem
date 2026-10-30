// ============================================================
// features/settings/composables/useSettingsDiagnostics —— 纯编排单元测试
//
// 该 composable 只做「读后端诊断数据 → 落到响应式状态 + toast/confirm 副作用」。
// 全部 mock 领域 api 与 UI 服务，覆盖：分项失败隔离、事件告警去重、
// 规则预览防抖、日志/插件/密钥操作的成功与失败分支。
// ============================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick } from 'vue'

import { systemApi } from '@/features/system'
import { toast } from '@/kernel/ui/toast'
import type { PluginItem } from '@/features/system'
import { useSettingsDiagnostics } from '../composables/useSettingsDiagnostics'

vi.mock('@/features/system', () => ({
  systemApi: {
    ruleDomains: vi.fn(),
    rulePreview: vi.fn(),
    ruleReload: vi.fn(),
    eventHistory: vi.fn(),
    clearEventHistory: vi.fn(),
    encryptionStatus: vi.fn(),
    listPlugins: vi.fn(),
    eventStats: vi.fn(),
    listLogs: vi.fn(),
    readLog: vi.fn(),
    clearLogs: vi.fn(),
    rotateKey: vi.fn(),
    setPluginEnabled: vi.fn(),
    discoverPlugins: vi.fn(),
  },
}))

const toastMock = vi.hoisted(() => ({
  error: vi.fn(),
  success: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
}))
// 被测 composable 走的是 useToast()（与 toast 同为该模块导出），mock 必须两个都给
vi.mock('@/kernel/ui/toast', () => ({
  toast: toastMock,
  useToast: () => toastMock,
}))

const hoisted = vi.hoisted(() => ({ confirm: vi.fn() }))
const confirm = hoisted.confirm
vi.mock('@/kernel/ui/modal', () => ({
  useModal: () => ({ confirm: hoisted.confirm }),
}))

const api = vi.mocked(systemApi)
const toastError = vi.mocked(toast.error)
const toastSuccess = vi.mocked(toast.success)
const toastWarning = vi.mocked(toast.warning)

function makePlugin(patch: Partial<PluginItem> = {}): PluginItem {
  return {
    id: 'p1',
    name: '插件',
    version: '1.0.0',
    enabled: false,
    ...patch,
  } as unknown as PluginItem
}

const encryptionFixture = { available: true, algorithm: 'fernet' } as never

beforeEach(() => {
  vi.clearAllMocks()
  confirm.mockReset()
  api.ruleDomains.mockResolvedValue({ builtin_count: 3, user_count: 2, domains: [] })
  api.rulePreview.mockResolvedValue({
    matched: true,
    domain_key: 'ielts',
    domain_name: '雅思',
    plans: [],
  })
  api.ruleReload.mockResolvedValue({ builtin: 4, user: 5, total: 9, skipped: [] })
  api.eventHistory.mockResolvedValue([{ event: 'ai.error', time: 't', success: true }])
  api.clearEventHistory.mockResolvedValue({ cleared: true })
  api.encryptionStatus.mockResolvedValue(encryptionFixture)
  api.listPlugins.mockResolvedValue([makePlugin()])
  api.eventStats.mockResolvedValue({
    'task.created': { count: 8, success: 8, failed: 0, failed_handlers: [], alert: false },
    'ai.error': { count: 3, success: 0, failed: 6, failed_handlers: ['h1', 'h2'], alert: true },
  })
  api.listLogs.mockResolvedValue({ files: [{ name: 'app.log', size_kb: 12 }] } as never)
  api.readLog.mockResolvedValue({ content: '日志内容' } as never)
  api.clearLogs.mockResolvedValue({ cleared: 2, failed: [] } as never)
  api.rotateKey.mockResolvedValue(undefined)
  api.setPluginEnabled.mockResolvedValue(undefined)
  api.discoverPlugins.mockResolvedValue([makePlugin({ id: 'p2' })])
})

afterEach(() => {
  vi.useRealTimers()
})

describe('loadDiagnostics：分项加载与告警', () => {
  it('三项独立加载：事件按 count 降序、加密/插件写入状态', async () => {
    // 本用例只验证映射/排序；用未触发告警的统计，避免与"告警只一次"用例交叉断言
    api.eventStats.mockResolvedValueOnce({
      'task.created': { count: 8, success: 8, failed: 0, failed_handlers: [], alert: false },
      'ai.error': { count: 3, success: 3, failed: 0, failed_handlers: [], alert: false },
    })
    const d = useSettingsDiagnostics()
    await d.loadDiagnostics()

    expect(d.encryption.value).toEqual(encryptionFixture)
    expect(d.plugins.value).toHaveLength(1)
    expect(d.eventStats.value.map((e: { name: string }) => e.name)).toEqual([
      'task.created',
      'ai.error',
    ])
    expect(toastError).not.toHaveBeenCalled()
  })

  it('事件连续失败达阈值时告警一次，重复加载不重复打扰', async () => {
    const d = useSettingsDiagnostics()
    await d.loadDiagnostics()
    await d.loadDiagnostics()

    expect(toastError).toHaveBeenCalledTimes(1)
    expect(toastError).toHaveBeenCalledWith('事件 ai.error 持续失败', '请检查插件或服务')
  })

  it('单项失败不连累其它面板（加密挂了，插件与事件仍加载）', async () => {
    api.encryptionStatus.mockRejectedValueOnce(new Error('no key'))
    const d = useSettingsDiagnostics()

    await d.loadDiagnostics()

    expect(d.encryption.value).toBeNull()
    expect(d.plugins.value).toHaveLength(1)
    expect(d.eventStats.value).toHaveLength(2)
  })

  it('eventStats 返回 null 时降级为空数组', async () => {
    api.eventStats.mockResolvedValueOnce(null as never)
    const d = useSettingsDiagnostics()

    await d.loadDiagnostics()

    expect(d.eventStats.value).toEqual([])
  })

  it('failedHandlerSummary 去重后用顿号拼接', async () => {
    const d = useSettingsDiagnostics()
    await d.loadDiagnostics()

    expect(d.failedHandlerSummary.value).toBe('h1、h2')
  })

  it('loadRuleDomains 成功写入领域数；失败保持默认值不抛出', async () => {
    const d = useSettingsDiagnostics()
    await d.loadRuleDomains()
    expect(d.ruleDomains.value).toEqual({ builtin: 3, user: 2 })

    api.ruleDomains.mockRejectedValueOnce(new Error('down'))
    await expect(d.loadRuleDomains()).resolves.toBeUndefined()
    expect(d.ruleDomains.value).toEqual({ builtin: 3, user: 2 })
  })
})

describe('规则引擎预览：防抖与热重载', () => {
  it('输入停止 400ms 后才请求预览（防抖）', async () => {
    vi.useFakeTimers()
    const d = useSettingsDiagnostics()

    d.setRuleText('我想学雅思')
    await nextTick()
    expect(api.rulePreview).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(399)
    expect(api.rulePreview).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1)
    await nextTick()
    expect(api.rulePreview).toHaveBeenCalledWith('我想学雅思')
    expect(d.rulePreview.value).toMatchObject({
      matched: true,
      domain_name: '雅思',
      plans: [],
    })
  })

  it('连续输入只发最后一次预览（清掉前一个定时器）', async () => {
    vi.useFakeTimers()
    const d = useSettingsDiagnostics()

    d.setRuleText('雅')
    await nextTick()
    d.setRuleText('雅思')
    await nextTick()
    await vi.advanceTimersByTimeAsync(400)
    await nextTick()

    expect(api.rulePreview).toHaveBeenCalledTimes(1)
    expect(api.rulePreview).toHaveBeenCalledWith('雅思')
  })

  it('空白输入直接清空预览、不发请求', async () => {
    vi.useFakeTimers()
    const d = useSettingsDiagnostics()
    d.rulePreview.value = { matched: true, domain_name: 'x', plans: [] }

    d.setRuleText('   ')
    await nextTick()
    await vi.advanceTimersByTimeAsync(400)
    await nextTick()

    expect(api.rulePreview).not.toHaveBeenCalled()
    expect(d.rulePreview.value).toBeNull()
  })

  it('预览接口失败时清空预览（不留下过期结果）', async () => {
    vi.useFakeTimers()
    api.rulePreview.mockRejectedValueOnce(new Error('bad'))
    const d = useSettingsDiagnostics()

    d.setRuleText('雅思')
    await nextTick()
    await vi.advanceTimersByTimeAsync(400)
    await nextTick()

    expect(d.rulePreview.value).toBeNull()
  })

  it('作用域销毁（卸载）时清掉 400ms 定时器：之后不再请求预览（D-27）', async () => {
    vi.useFakeTimers()
    const scope = effectScope()
    const d = scope.run(() => useSettingsDiagnostics())!

    d.setRuleText('我想学雅思')
    await nextTick()
    scope.stop()

    await vi.advanceTimersByTimeAsync(600)

    expect(api.rulePreview).not.toHaveBeenCalled()
    expect(d.rulePreview.value).toBeNull()
  })

  it('热重载成功更新领域数并 toast；失败 toast error', async () => {
    const d = useSettingsDiagnostics()
    await d.onReloadDomains()
    expect(d.ruleDomains.value).toEqual({ builtin: 4, user: 5 })
    expect(toastSuccess).toHaveBeenCalledWith('领域库已热重载', '用户扩展 5 个')

    api.ruleReload.mockRejectedValueOnce(new Error('x'))
    await d.onReloadDomains()
    expect(toastError).toHaveBeenCalledWith('热重载失败')
  })
})

describe('事件面板：详情与清空', () => {
  it('toggleEventDetail 首次展开拉取 10 条；再次点击收起', async () => {
    const d = useSettingsDiagnostics()

    await d.toggleEventDetail('ai.error')
    expect(api.eventHistory).toHaveBeenCalledWith(10, 'ai.error')
    expect(d.activeEvent.value).toBe('ai.error')
    expect(d.eventTimeline.value).toHaveLength(1)

    await d.toggleEventDetail('ai.error')
    expect(d.activeEvent.value).toBe('')
  })

  it('历史拉取失败时时间线置空，但事件仍保持展开', async () => {
    api.eventHistory.mockRejectedValueOnce(new Error('down'))
    const d = useSettingsDiagnostics()

    await d.toggleEventDetail('ai.error')

    expect(d.activeEvent.value).toBe('ai.error')
    expect(d.eventTimeline.value).toEqual([])
  })

  it('清空历史：用户取消则不调用接口', async () => {
    confirm.mockResolvedValueOnce(false)
    const d = useSettingsDiagnostics()
    d.eventStats.value = [{ name: 'a', count: 1, failed: 0, failedHandlers: [], alert: false }]

    await d.onClearEvents()

    expect(api.clearEventHistory).not.toHaveBeenCalled()
    expect(d.eventStats.value).toHaveLength(1)
  })

  it('清空历史：确认后清空统计/展开态并 toast', async () => {
    confirm.mockResolvedValueOnce(true)
    const d = useSettingsDiagnostics()
    d.activeEvent.value = 'a'

    await d.onClearEvents()

    expect(api.clearEventHistory).toHaveBeenCalledTimes(1)
    expect(d.eventStats.value).toEqual([])
    expect(d.activeEvent.value).toBe('')
    expect(toastSuccess).toHaveBeenCalledWith('事件历史已清空')
  })
})

describe('日志：列表 / 查看 / 清空', () => {
  it('showLogs 首次展开且列表为空时自动刷新', async () => {
    const d = useSettingsDiagnostics()
    d.toggleShowLogs()
    await nextTick()

    expect(d.showLogs.value).toBe(true)
    await vi.waitFor(() => expect(api.listLogs).toHaveBeenCalledTimes(1))
    expect(d.logFiles.value).toHaveLength(1)
  })

  it('refreshLogs 对 files=null 降级为空数组', async () => {
    api.listLogs.mockResolvedValueOnce({ files: null } as never)
    const d = useSettingsDiagnostics()

    await d.refreshLogs()

    expect(d.logFiles.value).toEqual([])
  })

  it('viewLog 成功写入内容；失败显示“(读取失败)”', async () => {
    const d = useSettingsDiagnostics()
    await d.viewLog('app.log')
    expect(d.activeLog.value).toBe('app.log')
    expect(d.logContent.value).toBe('日志内容')

    api.readLog.mockRejectedValueOnce(new Error('io'))
    await d.viewLog('broken.log')
    expect(d.activeLog.value).toBe('broken.log')
    expect(d.logContent.value).toBe('(读取失败)')
  })

  it('clearLogs 成功 toast 并复位展开内容；部分失败用 warning', async () => {
    const d = useSettingsDiagnostics()
    d.logContent.value = 'x'
    d.activeLog.value = 'app.log'

    await d.clearLogs()
    expect(toastSuccess).toHaveBeenCalledWith('已清空 2 个日志文件')
    expect(d.logContent.value).toBe('')
    expect(d.activeLog.value).toBe('')
    expect(api.listLogs).toHaveBeenCalledTimes(1)

    api.clearLogs.mockResolvedValueOnce({ cleared: 1, failed: ['b.log'] } as never)
    await d.clearLogs()
    expect(toastWarning).toHaveBeenCalledWith('已清空 1 个，1 个失败', 'b.log')
  })

  it('clearLogs 异常时 toast error', async () => {
    api.clearLogs.mockRejectedValueOnce(new Error('io'))
    const d = useSettingsDiagnostics()

    await d.clearLogs()

    expect(toastError).toHaveBeenCalledWith('清空失败', 'Error: io')
  })
})

describe('加密与插件', () => {
  it('rotateKey 成功后重新拉取加密状态', async () => {
    const next = { available: false } as never
    api.encryptionStatus.mockResolvedValueOnce(next)
    const d = useSettingsDiagnostics()

    await d.rotateKey()

    expect(api.rotateKey).toHaveBeenCalledTimes(1)
    expect(d.encryption.value).toEqual(next)
    expect(toastSuccess).toHaveBeenCalledWith('加密密钥已轮换')
  })

  it('rotateKey 失败 toast 且不覆盖已有状态', async () => {
    api.rotateKey.mockRejectedValueOnce(new Error('boom'))
    const d = useSettingsDiagnostics()
    d.encryption.value = encryptionFixture

    await d.rotateKey()

    expect(toastError).toHaveBeenCalledWith('轮换失败', 'Error: boom')
    expect(d.encryption.value).toEqual(encryptionFixture)
  })

  it('togglePlugin 成功后翻转 enabled 并 toast；失败时保持原值', async () => {
    const d = useSettingsDiagnostics()
    const plugin = makePlugin({ enabled: false })

    await d.togglePlugin(plugin)
    expect(api.setPluginEnabled).toHaveBeenCalledWith('p1', true)
    expect(plugin.enabled).toBe(true)
    expect(toastSuccess).toHaveBeenCalledWith('插件已启用')

    api.setPluginEnabled.mockRejectedValueOnce(new Error('x'))
    await d.togglePlugin(makePlugin({ enabled: true }))
    expect(toastError).toHaveBeenCalledWith('操作失败', 'Error: x')
  })

  it('discoverPlugins 成功替换列表并提示数量；失败 toast', async () => {
    const d = useSettingsDiagnostics()
    await d.discoverPlugins()
    expect(d.plugins.value.map((plug: PluginItem) => plug.id)).toEqual(['p2'])
    expect(toastSuccess).toHaveBeenCalledWith('发现 1 个插件')

    api.discoverPlugins.mockRejectedValueOnce(new Error('x'))
    await d.discoverPlugins()
    expect(toastError).toHaveBeenCalledWith('扫描失败', 'Error: x')
  })
})

describe('折叠面板开关', () => {
  it('5 个 toggle 逐个翻转对应状态', () => {
    const d = useSettingsDiagnostics()

    d.toggleShowSecurity()
    d.toggleShowLogs()
    d.toggleShowEvents()
    d.toggleShowRules()
    d.toggleShowPlugins()

    expect([
      d.showSecurity.value,
      d.showLogs.value,
      d.showEvents.value,
      d.showRules.value,
      d.showPlugins.value,
    ]).toEqual([true, true, true, true, true])

    d.toggleShowSecurity()
    expect(d.showSecurity.value).toBe(false)
  })
})
