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

describe('toast：容量上限（D-61）', () => {
  it('超过 50 条时只保留最新 50 条，最旧的被淘汰', () => {
    for (let i = 0; i < 60; i += 1) toast.info('批量', `#${i}`)

    expect(toast.items).toHaveLength(50)
    expect(toast.items[0].message).toBe('#10')
    expect(toast.items[49].message).toBe('#59')
  })

  it('恰好 50 条时不淘汰', () => {
    for (let i = 0; i < 50; i += 1) toast.info('批量', `#${i}`)

    expect(toast.items).toHaveLength(50)
    expect(toast.items[0].message).toBe('#0')
  })

  it('淘汰后继续入队仍维持上限', () => {
    for (let i = 0; i < 60; i += 1) toast.info('批量', `#${i}`)
    toast.info('再来一条', '#new')

    expect(toast.items).toHaveLength(50)
    expect(toast.items[49].message).toBe('#new')
    expect(toast.items.map((x) => x.message)).not.toContain('#10')
  })
})

describe('toast：同内容去重（D-61）', () => {
  it('(type,title,message) 相同 → 只保留 1 条并复用已有 id', () => {
    const first = toast.info('网络异常', '请稍后重试')
    const second = toast.info('网络异常', '请稍后重试')

    expect(second).toBe(first)
    expect(toast.items).toHaveLength(1)
  })

  it('去重不刷新展示时长（duration 保持首次入队时的值）', () => {
    toast.info('去重', '正文', 1234)
    toast.info('去重', '正文', 9999)

    expect(toast.items).toHaveLength(1)
    expect(toast.items[0].duration).toBe(1234)
  })

  it('type 或 message 不同则不去重；title+message 相同但 type 不同也各自入队', () => {
    toast.info('同名', '同文')
    toast.info('同名', '不同文')
    toast.success('同名', '同文')
    toast.warning('同名')

    expect(toast.items).toHaveLength(4)
  })
})

describe('toast：计时归属（不变）', () => {
  it('store 不做自动过期：入队后推进 10s 条目仍在（计时由 ToastItem 负责）', async () => {
    vi.useFakeTimers()
    toast.info('常驻')

    await vi.advanceTimersByTimeAsync(10_000)

    expect(toast.items).toHaveLength(1)
  })
})
