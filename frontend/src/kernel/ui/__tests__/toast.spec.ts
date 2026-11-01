// ============================================================
// kernel/ui/toast —— Toast store 逻辑测试
//
// 该模块是命令式提示的唯一入口：入队/移除/清空/按类型默认时长/后端不可达抑制。
// 注意：自动过期计时在 ToastItem 组件层（支持 hover 暂停），store 只负责入队 ——
// 相关语义在本文件显式固定，避免以后误把计时搬进 store。
// ============================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  CONNECTIVITY_TOAST_TITLE,
  markReachable,
  markUnreachable,
} from '@/kernel/http/connectivity'
import { toast, useToast } from '../toast'

beforeEach(() => {
  toast.clear()
  markReachable()
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
})

afterEach(() => {
  toast.clear()
  markReachable()
  vi.useRealTimers()
})

describe('toast：入队与类型', () => {
  it('success 入队并返回递增 id，字段与默认时长正确', () => {
    const id1 = toast.success('已保存', '数据已写入')
    const id2 = toast.success('再一条')

    expect(id2).toBeGreaterThan(id1)
    expect(toast.items).toHaveLength(2)
    expect(toast.items[0]).toMatchObject({
      id: id1,
      type: 'success',
      title: '已保存',
      message: '数据已写入',
      duration: 3000,
    })
  })

  it('默认时长按类型：info/success 3s，warning/error 5s', () => {
    toast.info('i')
    toast.success('s')
    toast.warning('w')
    toast.error('e')

    const durations = toast.items.map((t) => t.duration)
    expect(durations).toEqual([3000, 3000, 5000, 5000])
  })

  it('自定义 duration 覆盖默认值', () => {
    toast.info('i', undefined, 1234)
    expect(toast.items[0].duration).toBe(1234)
  })

  it('show() 默认 info 类型且可指定 type', () => {
    toast.show('默认')
    toast.show('警告', '正文', 'warning')

    expect(toast.items[0]).toMatchObject({ type: 'info', title: '默认' })
    expect(toast.items[1]).toMatchObject({ type: 'warning', title: '警告', message: '正文' })
  })
})

describe('toast：移除/清空/单例', () => {
  it('remove(id) 只删指定条目；不存在的 id 无副作用', () => {
    const a = toast.info('a')
    const b = toast.info('b')

    toast.remove(a)
    expect(toast.items.map((t) => t.id)).toEqual([b])

    toast.remove(999)
    expect(toast.items.map((t) => t.id)).toEqual([b])
  })

  it('clear() 清空全部；items 引用保持同一数组（容器可持续订阅）', () => {
    const itemsRef = toast.items
    toast.info('a')
    toast.info('b')

    toast.clear()

    expect(toast.items).toHaveLength(0)
    expect(toast.items).toBe(itemsRef)
  })

  it('useToast() 返回同一单例（组件与服务共享同一个队列）', () => {
    const a = useToast()
    const b = useToast()

    expect(a).toBe(b)
    a.info('共享')
    expect(b.items).toHaveLength(1)
  })

  it('setReady()/isReady 反映容器就绪状态', () => {
    expect(toast.isReady).toBe(false)
    toast.setReady()
    expect(toast.isReady).toBe(true)
  })
})

describe('toast：后端不可达抑制', () => {
  it('error 在后端不可达且非连通性标题时被抑制（返回 0、不入队、记 console.warn）', () => {
    markUnreachable()

    const id = toast.error('加载失败', '列表请求失败')

    expect(id).toBe(0)
    expect(toast.items).toHaveLength(0)
    expect(console.warn).toHaveBeenCalled()
  })

  it('连通性自身标题不被抑制；warning/info/success 也不受抑制', () => {
    markUnreachable()

    const id = toast.error(CONNECTIVITY_TOAST_TITLE, '请检查服务')
    toast.warning('本地校验')
    toast.success('已保存')

    expect(id).toBeGreaterThan(0)
    expect(toast.items.map((t) => t.type)).toEqual(['error', 'warning', 'success'])
  })

  it('后端恢复后 error 正常入队', () => {
    markUnreachable()
    toast.error('被抑制')
    markReachable()

    const id = toast.error('恢复后')

    expect(id).toBeGreaterThan(0)
    expect(toast.items).toHaveLength(1)
  })
})

describe('toast：已知边界（记录当前实现，非本轮修复）', () => {
  it('store 不做自动过期：入队后推进 10s 条目仍在（计时由 ToastItem 负责）', async () => {
    vi.useFakeTimers()
    toast.info('常驻')

    await vi.advanceTimersByTimeAsync(10_000)

    expect(toast.items).toHaveLength(1)
  })

  it('无容量上限/无同 id 去重：连续同标题入队会全部保留', () => {
    for (let i = 0; i < 120; i += 1) toast.info('重复标题', `#${i}`)

    expect(toast.items).toHaveLength(120)
  })
})
