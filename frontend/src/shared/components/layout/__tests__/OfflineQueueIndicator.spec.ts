// ============================================================
// OfflineQueueIndicator —— 离线队列角标/面板测试
//
// 组件依赖 offlineQueue store（mock 成受控对象）、connectivity 真实 ref
// （用 markUnreachable/markReachable 切换"未连接"标记）、toast（mock）与
// 全局 qm-offline-queue CustomEvent 广播。Teleport 用 stub 拉平断言。
// ============================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { mount } from '@vue/test-utils'

import { markReachable, markUnreachable } from '@/kernel/http/connectivity'
import OfflineQueueIndicator from '../OfflineQueueIndicator.vue'

const queueStore = vi.hoisted(() => ({
  pending: 0,
  failed: 0,
  flushing: false,
  hasPending: false,
  items: [] as Array<Record<string, unknown>>,
  retryAll: vi.fn(),
  clearFailed: vi.fn(),
}))

vi.mock('@/kernel/offline/offlineQueue', () => ({
  useOfflineQueueStore: () => queueStore,
  OFFLINE_QUEUE_EVENT: 'qm-offline-queue',
}))

const toastMock = vi.hoisted(() => ({
  error: vi.fn(),
  success: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
}))
vi.mock('@/kernel/ui/toast', () => ({ toast: toastMock }))

const toastSuccess = toastMock.success
const toastError = toastMock.error

const mounted: Array<{ unmount: () => void }> = []
function mountIndicator() {
  const wrapper = mount(OfflineQueueIndicator, {
    global: { stubs: { teleport: true } },
    attachTo: document.body,
  })
  mounted.push(wrapper)
  return wrapper
}

function emitQueueEvent(detail: Record<string, unknown>) {
  window.dispatchEvent(new CustomEvent('qm-offline-queue', { detail }))
}

function buttonByText(wrapper: ReturnType<typeof mountIndicator>, text: string) {
  const found = wrapper.findAll('button').find((b) => b.text().includes(text))
  if (!found) throw new Error(`未找到按钮：${text}`)
  return found
}

beforeEach(() => {
  vi.clearAllMocks()
  queueStore.pending = 0
  queueStore.failed = 0
  queueStore.flushing = false
  queueStore.hasPending = false
  queueStore.items = []
  queueStore.retryAll.mockResolvedValue({ sent: 0, failed: 0, stopped: false })
  queueStore.clearFailed.mockResolvedValue(0)
  markReachable()
  document.body.style.overflow = ''
})

afterEach(() => {
  mounted.splice(0).forEach((w) => w.unmount())
  markReachable()
})

describe('OfflineQueueIndicator：角标', () => {
  it('无待同步且未同步中时不渲染角标', () => {
    const wrapper = mountIndicator()

    expect(wrapper.find('.offline-queue__badge').exists()).toBe(false)
  })

  it('有待同步条目时显示数字角标与 title', () => {
    queueStore.pending = 3
    queueStore.hasPending = true
    const wrapper = mountIndicator()

    const badge = wrapper.find('.offline-queue__badge')
    expect(badge.text()).toBe('3')
    expect(badge.attributes('title')).toBe('3 条待同步')
  })

  it('pending 超过 99 显示 99+', () => {
    queueStore.pending = 120
    queueStore.hasPending = true

    expect(mountIndicator().find('.offline-queue__badge').text()).toBe('99+')
  })

  it('存在失败条目时角标带 is-failed', () => {
    queueStore.pending = 1
    queueStore.hasPending = true
    queueStore.failed = 2

    expect(mountIndicator().find('.offline-queue__badge').classes()).toContain('is-failed')
  })

  it('同步中：显示 is-syncing 且 title 为「同步中…」', () => {
    queueStore.flushing = true
    const wrapper = mountIndicator()

    const badge = wrapper.find('.offline-queue__badge')
    expect(badge.classes()).toContain('is-syncing')
    expect(badge.attributes('title')).toBe('同步中…')
  })
})

describe('OfflineQueueIndicator：队列面板', () => {
  it('点击角标打开面板，标题显示待同步与失败数', async () => {
    queueStore.pending = 2
    queueStore.hasPending = true
    queueStore.failed = 1
    const wrapper = mountIndicator()

    await wrapper.find('.offline-queue__badge').trigger('click')

    expect(wrapper.find('.offline-queue__sheet').exists()).toBe(true)
    expect(wrapper.text()).toContain('待同步队列')
    expect(wrapper.text()).toContain('2 条 · 失败 1')
  })

  it('队列为空时显示空态', async () => {
    queueStore.pending = 1
    queueStore.hasPending = true
    const wrapper = mountIndicator()

    await wrapper.find('.offline-queue__badge').trigger('click')

    expect(wrapper.find('.offline-queue__empty').text()).toBe('队列为空')
  })

  it('条目渲染标签/方法/时间/重试次数/失败原因与失败标记', async () => {
    queueStore.pending = 2
    queueStore.hasPending = true
    queueStore.items = [
      {
        id: 'q1',
        path: '/tasks',
        method: 'POST',
        label: '任务',
        createdAt: new Date(2026, 9, 30, 10, 5).getTime(),
        retries: 1,
        lastError: 'boom',
      },
      {
        id: 'q2',
        path: '/documents',
        method: 'PATCH',
        createdAt: new Date(2026, 9, 30, 11, 0).getTime(),
        retries: 3,
      },
    ]
    const wrapper = mountIndicator()

    await wrapper.find('.offline-queue__badge').trigger('click')

    const items = wrapper.findAll('.offline-queue__item')
    expect(items).toHaveLength(2)
    expect(items[0].text()).toContain('任务')
    expect(items[0].text()).toContain('POST')
    expect(items[0].text()).toContain('10-30 10:05')
    expect(items[0].text()).toContain('重试 1/3')
    expect(items[0].text()).toContain('boom')
    // 无 label 回落到 path；重试达 3 次标失败
    expect(items[1].text()).toContain('/documents')
    expect(items[1].classes()).toContain('is-failed')
    expect(items[1].find('.offline-queue__tag').text()).toBe('失败')
  })

  it('关闭按钮 / 遮罩点击都能关闭面板', async () => {
    queueStore.pending = 1
    queueStore.hasPending = true
    const wrapper = mountIndicator()

    await wrapper.find('.offline-queue__badge').trigger('click')
    await wrapper.find('.offline-queue__close').trigger('click')
    expect(wrapper.find('.offline-queue__sheet').exists()).toBe(false)

    await wrapper.find('.offline-queue__badge').trigger('click')
    await wrapper.find('.offline-queue__mask').trigger('click')
    expect(wrapper.find('.offline-queue__sheet').exists()).toBe(false)
  })
})

describe('OfflineQueueIndicator：重试全部 / 清空失败', () => {
  async function openPanel() {
    queueStore.pending = 1
    queueStore.hasPending = true
    const wrapper = mountIndicator()
    await wrapper.find('.offline-queue__badge').trigger('click')
    return wrapper
  }

  it('重试全部：成功时 toast 同步条数', async () => {
    queueStore.retryAll.mockResolvedValue({ sent: 2, failed: 0, stopped: false })
    const wrapper = await openPanel()

    await buttonByText(wrapper, '重试全部').trigger('click')

    expect(queueStore.retryAll).toHaveBeenCalledTimes(1)
    expect(toastSuccess).toHaveBeenCalledWith('已同步 2 条')
  })

  it('重试全部：仍有失败时 toast 失败条数', async () => {
    queueStore.retryAll.mockResolvedValue({ sent: 0, failed: 3, stopped: true })
    const wrapper = await openPanel()

    await buttonByText(wrapper, '重试全部').trigger('click')

    expect(toastError).toHaveBeenCalledWith('仍有 3 条同步失败')
  })

  it('重试全部：没有任何变化时不打扰用户', async () => {
    const wrapper = await openPanel()

    await buttonByText(wrapper, '重试全部').trigger('click')

    expect(toastSuccess).not.toHaveBeenCalled()
    expect(toastError).not.toHaveBeenCalled()
  })

  it('清空失败：有记录时提示清空数量，无记录时提示没有失败记录', async () => {
    queueStore.clearFailed.mockResolvedValueOnce(2)
    const wrapper = await openPanel()

    await buttonByText(wrapper, '清空失败').trigger('click')
    expect(toastSuccess).toHaveBeenCalledWith('已清空 2 条失败记录')

    queueStore.clearFailed.mockResolvedValueOnce(0)
    await buttonByText(wrapper, '清空失败').trigger('click')
    expect(toastSuccess).toHaveBeenCalledWith('没有失败记录')
  })
})

describe('OfflineQueueIndicator：连不上后端提示', () => {
  it('backendUnreachable=false 时不显示「未连接」', () => {
    const wrapper = mountIndicator()

    expect(wrapper.find('.offline-queue__offline').exists()).toBe(false)
  })

  it('标记不可达后显示「未连接」，点击打开排查说明并可关闭', async () => {
    const wrapper = mountIndicator()
    markUnreachable()
    await nextTick()

    const chip = wrapper.find('.offline-queue__offline')
    expect(chip.exists()).toBe(true)
    expect(chip.text()).toContain('未连接')

    await chip.trigger('click')
    expect(wrapper.text()).toContain('连不上后端服务')
    expect(wrapper.findAll('.offline-queue__help li')).toHaveLength(4)

    await wrapper.find('.offline-queue__close').trigger('click')
    expect(wrapper.text()).not.toContain('连不上后端服务')
  })
})

describe('OfflineQueueIndicator：事件广播 toast', () => {
  it('offline 广播提示已离线', () => {
    mountIndicator()

    emitQueueEvent({ kind: 'offline', pending: 1 })

    expect(toastError).toHaveBeenCalledWith('已离线', '写操作将进入同步队列')
  })

  it('flushed 广播按 sent/failed 分别提示', () => {
    mountIndicator()

    emitQueueEvent({ kind: 'flushed', pending: 0, sent: 2, failed: 0 })
    expect(toastSuccess).toHaveBeenCalledWith('2 条操作已同步')

    emitQueueEvent({ kind: 'flushed', pending: 3, sent: 0, failed: 3 })
    expect(toastError).toHaveBeenCalledWith('3 条同步失败', '可在队列面板手动重试')
  })

  it('item-failed 广播带 label 与错误原因', () => {
    mountIndicator()

    emitQueueEvent({ kind: 'item-failed', pending: 1, label: '任务', error: 'boom' })
    expect(toastError).toHaveBeenCalledWith('同步失败：任务', 'boom')

    emitQueueEvent({ kind: 'item-failed', pending: 1, error: 'no label' })
    expect(toastError).toHaveBeenCalledWith('同步失败：写操作', 'no label')
  })

  it('未知 kind / 缺 error 的 item-failed 不 toast', () => {
    mountIndicator()

    emitQueueEvent({ kind: 'unknown', pending: 0 })
    emitQueueEvent({ kind: 'item-failed', pending: 1 })

    expect(toastError).not.toHaveBeenCalled()
    expect(toastSuccess).not.toHaveBeenCalled()
  })

  it('卸载后移除事件监听：不再 toast', () => {
    const wrapper = mountIndicator()
    wrapper.unmount()
    mounted.splice(0)

    emitQueueEvent({ kind: 'offline', pending: 1 })

    expect(toastError).not.toHaveBeenCalled()
  })
})
