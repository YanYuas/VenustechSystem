// ============================================================
// shared/constants/dimensions —— 六维度导航配置纯数据/纯函数测试
//
// 这些常量驱动顶部导航与"当前维度"高亮，属于高扇出的纯数据：
// 一旦键值/路由映射被改坏，导航会静默错位。这里做全量快照式断言
// （逐项，不用 DOM 快照）与路由解析边界测试。
// ============================================================
import { describe, expect, it } from 'vitest'

import { DIMENSIONS, MAIN_NAV_ITEMS, ROUTE_TO_DIMENSION, getDimensionByRoute } from '../dimensions'

describe('DIMENSIONS：六维度全量', () => {
  it('id/顺序/标签与产品定义一致', () => {
    expect(DIMENSIONS.map((d) => d.id)).toEqual([
      'dashboard',
      'execution',
      'knowledge',
      'life',
      'asset',
      'companion',
    ])
    expect(DIMENSIONS.map((d) => d.label)).toEqual(['首页', '执行', '知识', '人生', '资产', '伙伴'])
  })

  it('每个维度都有非空 icon 与绝对路径 defaultRoute', () => {
    for (const d of DIMENSIONS) {
      expect(d.icon).toBeTruthy()
      expect(d.defaultRoute.startsWith('/')).toBe(true)
    }
  })

  it('首页无 tab，其余维度都有 tab', () => {
    expect(DIMENSIONS.find((d) => d.id === 'dashboard')?.tabs).toEqual([])
    for (const d of DIMENSIONS.filter((x) => x.id !== 'dashboard')) {
      expect(d.tabs.length).toBeGreaterThan(0)
    }
  })

  it('tab id 全局唯一（导航 key 不能撞）', () => {
    const ids = DIMENSIONS.flatMap((d) => d.tabs.map((t) => t.id))
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('每个 tab 的 route 以 / 开头，且 optional 仅用于工作区', () => {
    for (const tab of DIMENSIONS.flatMap((d) => d.tabs)) {
      expect(tab.route.startsWith('/')).toBe(true)
      if (tab.optional) expect(tab.id).toBe('workspace')
    }
    const optionalTabs = DIMENSIONS.flatMap((d) => d.tabs).filter((t) => t.optional)
    expect(optionalTabs.map((t) => t.id)).toEqual(['workspace'])
  })
})

describe('ROUTE_TO_DIMENSION：路由映射完整性', () => {
  it('每个 tab 的 route 都能映射回它所属的维度', () => {
    for (const d of DIMENSIONS) {
      for (const tab of d.tabs) {
        expect(ROUTE_TO_DIMENSION[tab.route]).toBe(d.id)
      }
    }
  })

  it('每个维度的 defaultRoute 都在映射表里', () => {
    for (const d of DIMENSIONS) {
      expect(ROUTE_TO_DIMENSION[d.defaultRoute]).toBe(d.id)
    }
  })

  it('映射值都是合法 DimensionId', () => {
    const valid = new Set(DIMENSIONS.map((d) => d.id))
    for (const dimId of Object.values(ROUTE_TO_DIMENSION)) {
      expect(valid.has(dimId)).toBe(true)
    }
  })
})

describe('getDimensionByRoute：精确 / 前缀 / 未命中', () => {
  it('精确命中：/tasks → execution，/dashboard → dashboard', () => {
    expect(getDimensionByRoute('/tasks')?.id).toBe('execution')
    expect(getDimensionByRoute('/dashboard')?.id).toBe('dashboard')
  })

  it('子路径前缀命中：/tasks/123、/documents/a/b 各自归属正确维度', () => {
    expect(getDimensionByRoute('/tasks/123')?.id).toBe('execution')
    expect(getDimensionByRoute('/documents/a/b')?.id).toBe('knowledge')
    expect(getDimensionByRoute('/assistant/thread/9')?.id).toBe('companion')
  })

  it('未命中返回 undefined：未知路由、根路径、相似但非子路径', () => {
    expect(getDimensionByRoute('/nope')).toBeUndefined()
    expect(getDimensionByRoute('/')).toBeUndefined()
    // 前缀匹配要求 "route + /"，/task 不应被 /tasks 吞掉
    expect(getDimensionByRoute('/task')).toBeUndefined()
    expect(getDimensionByRoute('/document/1')).toBeUndefined()
  })

  it('/avatar 是映射表里存在但无 tab 的独立路由，解析到伙伴维度', () => {
    expect(getDimensionByRoute('/avatar')?.id).toBe('companion')
    expect(getDimensionByRoute('/avatar/1')?.id).toBe('companion')
  })
})

describe('MAIN_NAV_ITEMS', () => {
  it('与 DIMENSIONS 一一对应且顺序一致', () => {
    expect(MAIN_NAV_ITEMS).toHaveLength(DIMENSIONS.length)
    MAIN_NAV_ITEMS.forEach((item, i) => {
      const dim = DIMENSIONS[i]
      expect(item.id).toBe(dim.id)
      expect(item.label).toBe(dim.label)
      expect(item.icon).toBe(dim.icon)
      expect(item.route).toBe(dim.defaultRoute)
    })
  })

  it('每个导航项都有可跳转的绝对 route 与非空 id', () => {
    for (const item of MAIN_NAV_ITEMS) {
      expect(item.id).toBeTruthy()
      expect((item.route ?? '').startsWith('/')).toBe(true)
    }
  })
})
