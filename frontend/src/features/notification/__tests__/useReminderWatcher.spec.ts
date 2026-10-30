// ============================================================
// useReminderWatcher —— 提醒到期监控单元测试
//
// 该 composable 用模块级 timer/running/notifiedIds（生产单例语义），
// 所以每个用例用唯一提醒 id、并在 afterEach stop()，避免串场。
// 覆盖：通知权限降级、到点提醒（桌面+toast+系统通知+标记已提醒）、
// 去重/未来/过期窗口/已忽略跳过、任务提醒一次性清理、自调度轮询间隔、
// 停止清理与重启、document.hidden 跳过、慢请求不堆叠、异常不中断后续 tick。
// ============================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { panelApi } from '@/features/panel'
import { taskApi } from '@/features/task'
import { notificationApi } from '../api'
import { useReminderWatcher } from '../composables/useReminderWatcher'

vi.mock('@/features/panel', () => ({
  panelApi: { listReminders: vi.fn(), updateReminder: vi.fn() },
}))
vi.mock('../api', () => ({ notificationApi: { create: vi.fn() } }))
vi.mock('@/features/task', () => ({ taskApi: { list: vi.fn(), update: vi.fn() } }))

const toastMock = vi.hoisted(() => ({
  error: vi.fn(),
  success: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
}))
vi.mock('@/kernel/ui/toast', () => ({ toast: toastMock }))

type AnyMock = ReturnType<typeof vi.fn>
const panel = panelApi as unknown as { listReminders: AnyMock; updateReminder: AnyMock }
const task = taskApi as unknown as { list: AnyMock; update: AnyMock }
const notify = notificationApi as unknown as { create: AnyMock }
const toastWarning = toastMock.warning

const NOW = new Date('2026-10-30T10:00:00Z')
const minutesAgo = (m: number) => new Date(NOW.getTime() - m * 60_000).toISOString()

type Api = ReturnType<typeof useReminderWatcher>
let api: Api | undefined

/** 简易 Notification 桩：记录实例、可配置权限、可让构造抛错 */
class FakeNotification {
  static permission: 'default' | 'granted' | 'denied' = 'granted'
  static requestPermission = vi.fn(async () => 'granted' as const)
  static instances: FakeNotification[] = []
  static throwOnConstruct = false
  onclick: (() => void) | null = null
  close = vi.fn()
  constructor(
    public title: string,
    public options?: NotificationOptions,
  ) {
    if (FakeNotification.throwOnConstruct) throw new Error('denied by browser')
    FakeNotification.instances.push(this)
  }
}

function stubNotification(permission: 'default' | 'granted' | 'denied' = 'granted') {
  FakeNotification.permission = permission
  FakeNotification.instances = []
  FakeNotification.throwOnConstruct = false
  FakeNotification.requestPermission = vi.fn(async () => 'granted' as const)
  vi.stubGlobal('Notification', FakeNotification)
  return FakeNotification
}

function setup(): Api {
  api = useReminderWatcher()
  return api
}

function setHidden(hidden: boolean) {
  Object.defineProperty(document, 'hidden', { configurable: true, get: () => hidden })
}

function makeQuickReminder(patch: Record<string, unknown> = {}) {
  return {
    id: 'r1',
    title: '喝水',
    description: '该喝水了',
    remind_at: minutesAgo(5),
    dismissed: false,
    ...patch,
  }
}

function makeTask(patch: Record<string, unknown> = {}) {
  return {
    id: 't1',
    title: '写周报',
    description: '别忘了写周报',
    status: 'pending',
    reminder_time: minutesAgo(5),
    due_date: '2026-10-31',
    ...patch,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers({ now: NOW })
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  panel.listReminders.mockResolvedValue([])
  panel.updateReminder.mockResolvedValue(undefined)
  task.list.mockResolvedValue({ list: [], total: 0, page: 1, page_size: 200 })
  task.update.mockResolvedValue(undefined)
  notify.create.mockResolvedValue(undefined)
})

afterEach(() => {
  api?.stop()
  api = undefined
  delete (document as unknown as Record<string, unknown>).hidden
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('useReminderWatcher：通知权限', () => {
  it('浏览器不支持 Notification：返回 false，supported 保持 false', async () => {
    vi.unstubAllGlobals()
    const w = setup()

    await expect(w.requestPermission()).resolves.toBe(false)
    expect(w.supported.value).toBe(false)
  })

  it('已授权：直接返回 true，不重复请求权限', async () => {
    FakeNotification.permission = 'granted'
    stubNotification('granted')
    const w = setup()

    await expect(w.requestPermission()).resolves.toBe(true)
    expect(w.supported.value).toBe(true)
    expect(FakeNotification.requestPermission).not.toHaveBeenCalled()
  })

  it('默认状态：请求权限，授予后 supported=true', async () => {
    const Stub = stubNotification('default')
    Stub.requestPermission = vi.fn(async () => 'granted' as const)
    const w = setup()

    await expect(w.requestPermission()).resolves.toBe(true)
    expect(Stub.requestPermission).toHaveBeenCalledTimes(1)
    expect(w.supported.value).toBe(true)
  })

  it('用户拒绝：返回 false 且不再请求权限', async () => {
    const Stub = stubNotification('denied')
    const w = setup()

    await expect(w.requestPermission()).resolves.toBe(false)
    expect(Stub.requestPermission).not.toHaveBeenCalled()
    expect(w.supported.value).toBe(false)
  })
})

describe('useReminderWatcher：快速提醒', () => {
  it('到点提醒：桌面通知 + 应用内 toast + 系统通知 + 标记 dismissed', async () => {
    const Stub = stubNotification('granted')
    panel.listReminders.mockResolvedValue([makeQuickReminder({ id: 'r-101' })])
    const w = setup()
    await w.requestPermission()

    await w.checkReminders()

    expect(Stub.instances).toHaveLength(1)
    expect(Stub.instances[0].title).toBe('喝水')
    expect(Stub.instances[0].options).toMatchObject({ body: '该喝水了', tag: 'venustech-reminder' })

    expect(toastWarning).toHaveBeenCalledWith('喝水', '该喝水了')
    expect(notify.create).toHaveBeenCalledWith({
      title: '喝水',
      content: '该喝水了',
      type: 'warning',
      source_type: 'reminder',
      source_id: 'r-101',
    })
    expect(panel.updateReminder).toHaveBeenCalledWith('r-101', { dismissed: true })
  })

  it('同一条提醒只通知一次（跨 tick 去重）', async () => {
    panel.listReminders.mockResolvedValue([makeQuickReminder({ id: 'r-102' })])
    const w = setup()

    await w.checkReminders()
    await w.checkReminders()

    expect(toastWarning).toHaveBeenCalledTimes(1)
    expect(panel.updateReminder).toHaveBeenCalledTimes(1)
  })

  it('未来提醒 / 超过 1 小时旧提醒 / 已 dismissed / 无 remind_at 都跳过', async () => {
    panel.listReminders.mockResolvedValue([
      makeQuickReminder({ id: 'r-201', remind_at: new Date(NOW.getTime() + 60_000).toISOString() }),
      makeQuickReminder({ id: 'r-202', remind_at: minutesAgo(120) }),
      makeQuickReminder({ id: 'r-203', dismissed: true }),
      makeQuickReminder({ id: 'r-204', remind_at: null }),
    ])
    const w = setup()

    await w.checkReminders()

    expect(toastWarning).not.toHaveBeenCalled()
    expect(panel.updateReminder).not.toHaveBeenCalled()
  })

  it('桌面通知构造抛错被吞掉，不影响 toast 与落库', async () => {
    const Stub = stubNotification('granted')
    Stub.throwOnConstruct = true
    panel.listReminders.mockResolvedValue([makeQuickReminder({ id: 'r-301' })])
    const w = setup()
    await w.requestPermission()

    await expect(w.checkReminders()).resolves.toBeUndefined()

    expect(toastWarning).toHaveBeenCalledTimes(1)
    expect(panel.updateReminder).toHaveBeenCalledWith('r-301', { dismissed: true })
  })

  it('点击桌面通知：窗口聚焦并关闭通知', async () => {
    const Stub = stubNotification('granted')
    panel.listReminders.mockResolvedValue([makeQuickReminder({ id: 'r-302' })])
    const focusSpy = vi.spyOn(window, 'focus').mockImplementation(() => undefined)
    const w = setup()
    await w.requestPermission()
    await w.checkReminders()

    const n = Stub.instances[0]
    expect(n.onclick).toBeTypeOf('function')
    n.onclick?.()

    expect(focusSpy).toHaveBeenCalledTimes(1)
    expect(n.close).toHaveBeenCalledTimes(1)
  })

  it('提醒列表接口失败：静默不抛错，任务提醒仍会检查', async () => {
    panel.listReminders.mockRejectedValue(new Error('panel down'))
    const w = setup()

    await expect(w.checkReminders()).resolves.toBeUndefined()

    expect(task.list).toHaveBeenCalledTimes(1)
  })
})

describe('useReminderWatcher：任务提醒', () => {
  it('到期任务：桌面 + toast（带截止日）+ 系统通知 + 清空 reminder_time', async () => {
    const Stub = stubNotification('granted')
    task.list.mockResolvedValue({ list: [makeTask({ id: 't-101' })], total: 1 })
    const w = setup()
    await w.requestPermission()

    await w.checkReminders()

    expect(Stub.instances[0].title).toBe('任务提醒：写周报')
    expect(toastWarning).toHaveBeenCalledWith('任务提醒：写周报', '截止 2026-10-31')
    expect(notify.create).toHaveBeenCalledWith({
      title: '任务提醒：写周报',
      content: '别忘了写周报',
      type: 'warning',
      source_type: 'task',
      source_id: 't-101',
    })
    expect(task.update).toHaveBeenCalledWith('t-101', { reminder_time: null })
  })

  it('已完成任务 / 无 reminder_time / 未来提醒都不触发', async () => {
    task.list.mockResolvedValue({
      list: [
        makeTask({ id: 't-201', status: 'completed' }),
        makeTask({ id: 't-202', reminder_time: null }),
        makeTask({ id: 't-203', reminder_time: new Date(NOW.getTime() + 60_000).toISOString() }),
      ],
      total: 3,
    })
    const w = setup()

    await w.checkReminders()

    expect(toastWarning).not.toHaveBeenCalled()
    expect(task.update).not.toHaveBeenCalled()
  })

  it('任务接口失败：静默降级，不影响快速提醒已完成的部分', async () => {
    task.list.mockRejectedValue(new Error('task down'))
    const w = setup()

    await expect(w.checkReminders()).resolves.toBeUndefined()
  })
})

describe('useReminderWatcher：轮询与生命周期', () => {
  it('start 后立即检查一次，之后每 30s 一次', async () => {
    const w = setup()

    w.start()
    await vi.advanceTimersByTimeAsync(0)
    expect(panel.listReminders).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(30_000)
    expect(panel.listReminders).toHaveBeenCalledTimes(2)

    await vi.advanceTimersByTimeAsync(30_000)
    expect(panel.listReminders).toHaveBeenCalledTimes(3)
  })

  it('stop 清理定时器：之后不再检查；重复 stop 安全', async () => {
    const w = setup()
    w.start()
    await vi.advanceTimersByTimeAsync(0)
    expect(panel.listReminders).toHaveBeenCalledTimes(1)

    w.stop()
    w.stop()
    await vi.advanceTimersByTimeAsync(120_000)

    expect(panel.listReminders).toHaveBeenCalledTimes(1)
  })

  it('stop 后可重新 start（重新进入轮询）', async () => {
    const w = setup()
    w.start()
    await vi.advanceTimersByTimeAsync(0)
    w.stop()

    w.start()
    await vi.advanceTimersByTimeAsync(0)
    expect(panel.listReminders).toHaveBeenCalledTimes(2)

    await vi.advanceTimersByTimeAsync(30_000)
    expect(panel.listReminders).toHaveBeenCalledTimes(3)
  })

  it('document.hidden 时跳过本次检查，但仍继续调度', async () => {
    const w = setup()
    setHidden(true)

    w.start()
    await vi.advanceTimersByTimeAsync(0)
    expect(panel.listReminders).not.toHaveBeenCalled()

    setHidden(false)
    await vi.advanceTimersByTimeAsync(30_000)
    expect(panel.listReminders).toHaveBeenCalledTimes(1)
  })

  it('慢请求不会堆叠：上一次检查未完成前不会发起下一轮', async () => {
    let release: ((v: unknown) => void) | undefined
    panel.listReminders.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          release = resolve
        }),
    )
    const w = setup()

    w.start()
    await vi.advanceTimersByTimeAsync(0)
    expect(panel.listReminders).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(90_000)
    expect(panel.listReminders).toHaveBeenCalledTimes(1) // 仍然只有那一次

    release?.([])
    await vi.advanceTimersByTimeAsync(0)
    await vi.advanceTimersByTimeAsync(30_000)
    expect(panel.listReminders).toHaveBeenCalledTimes(2)
  })
})
