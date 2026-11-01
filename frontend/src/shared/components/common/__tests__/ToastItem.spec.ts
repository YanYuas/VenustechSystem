// ============================================================
// ToastItem —— 单条 toast 容器测试
//
// 覆盖：文案/类型样式/图标映射、到点自动移除、手动关闭、
// hover 暂停（deadline + remaining 语义）、duration=0 立即移除、卸载清理。
// 计时在组件层，因此全部用例使用 fake timers 并在 afterEach 复位。
// ============================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import { toast } from '@/kernel/ui/toast'
import type { ToastItem as ToastItemModel } from '@/shared/types/common'
import ToastItem from '../ToastItem.vue'

function makeItem(patch: Partial<ToastItemModel> = {}): ToastItemModel {
  return {
    id: 7,
    type: 'info',
    title: '标题',
    message: '正文',
    duration: 3000,
    ...patch,
  } as ToastItemModel
}

const mounted: Array<{ unmount: () => void }> = []
function mountItem(patch: Partial<ToastItemModel> = {}) {
  const wrapper = mount(ToastItem, { props: { item: makeItem(patch) } })
  mounted.push(wrapper)
  return wrapper
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.spyOn(toast, 'remove').mockImplementation(() => undefined)
})

afterEach(() => {
  mounted.splice(0).forEach((w) => w.unmount())
  vi.useRealTimers()
})

describe('ToastItem：渲染', () => {
  it('渲染标题与正文；无 message 时不渲染正文行', () => {
    const withMsg = mountItem()
    expect(withMsg.find('.toast-item__title').text()).toBe('标题')
    expect(withMsg.find('.toast-item__msg').text()).toBe('正文')

    const noMsg = mountItem({ message: undefined })
    expect(noMsg.find('.toast-item__msg').exists()).toBe(false)
  })

  it.each(['info', 'success', 'warning', 'error'])('类型 %s 映射到对应 class', (type) => {
    const wrapper = mountItem({ type: type as ToastItemModel['type'] })

    expect(wrapper.find('.toast-item').classes()).toContain(`toast-item--${type}`)
  })

  it('图标映射：info=2 条路径、success=1 条（check）、warning/error=3 条（warning）', () => {
    // 注意限定在图标容器内：关闭按钮也有自己的 AppIcon（close=2 path），不能用全局 findAll('path')
    const iconPaths = (type: string) =>
      mountItem({ type: type as never }).findAll('.toast-item__icon path')

    expect(iconPaths('info')).toHaveLength(2)
    expect(iconPaths('success')).toHaveLength(1)
    expect(iconPaths('warning')).toHaveLength(3)
    expect(iconPaths('error')).toHaveLength(3)
  })
})

describe('ToastItem：自动过期与手动关闭', () => {
  it('到达 duration 后调用 toast.remove(id)', async () => {
    mountItem({ id: 11, duration: 3000 })

    await vi.advanceTimersByTimeAsync(2999)
    expect(toast.remove).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1)
    expect(toast.remove).toHaveBeenCalledWith(11)
  })

  it('duration=0 时挂载即移除（不留下永不消失的 toast）', () => {
    mountItem({ id: 12, duration: 0 })

    expect(toast.remove).toHaveBeenCalledWith(12)
  })

  it('点击关闭按钮立即 remove(id)', async () => {
    const wrapper = mountItem({ id: 13 })

    await wrapper.find('.toast-item__close').trigger('click')

    expect(toast.remove).toHaveBeenCalledWith(13)
  })
})

describe('ToastItem：hover 暂停', () => {
  it('hover 暂停计时，移出后按剩余时间继续，最终移除', async () => {
    const wrapper = mountItem({ id: 14, duration: 3000 })

    await vi.advanceTimersByTimeAsync(2000)
    await wrapper.find('.toast-item').trigger('mouseenter')
    // 暂停期间大幅推进不触发移除
    await vi.advanceTimersByTimeAsync(10_000)
    expect(toast.remove).not.toHaveBeenCalled()

    await wrapper.find('.toast-item').trigger('mouseleave')
    await vi.advanceTimersByTimeAsync(999)
    expect(toast.remove).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1)
    expect(toast.remove).toHaveBeenCalledWith(14)
  })

  it('未暂停时 mouseleave 不影响原计时', async () => {
    const wrapper = mountItem({ id: 15, duration: 2000 })

    await wrapper.find('.toast-item').trigger('mouseleave')
    await vi.advanceTimersByTimeAsync(2000)

    expect(toast.remove).toHaveBeenCalledWith(15)
  })

  it('卸载时清理计时器：之后不再移除', async () => {
    const wrapper = mountItem({ id: 16, duration: 1000 })
    wrapper.unmount()
    mounted.splice(0)

    await vi.advanceTimersByTimeAsync(5000)

    expect(toast.remove).not.toHaveBeenCalled()
  })
})
