// ============================================================
// app/router/index —— 路由表 / 懒加载 / 守卫 / 滚动行为 测试
//
// 该文件是应用装配层：路由表错误（路径/命名/懒加载失效）只会在用户点击时
// 才暴露。这里用真实 createRouter 实例断言：表结构完整性、懒加载边界、
// 动态 import 路径可解析、根重定向/unknown 兜底、beforeEach 恢复上次路由、
// afterEach 标题与最后路由记录、scrollBehavior 三种分支。
// ============================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { RouteRecordRaw, Router } from 'vue-router'

import router from '../index'

const LAST_ROUTE_KEY = 'qm-star-last-route'

type MetaLike = { title?: string; crumbs?: string[]; hidden?: boolean; icon?: string }
type ScrollBehavior = (
  to: { hash: string },
  from: unknown,
  saved?: { left: number; top: number } | null,
) => unknown

/** 每个用例拿一份全新 router（beforeEach/afterEach 守卫与模块级 restored 都是新实例） */
async function loadRouter(): Promise<Router> {
  vi.resetModules()
  const mod = await import('../index')
  return mod.default
}

function rootRoute(r: Router): RouteRecordRaw {
  const root = r.options.routes.find((route) => route.path === '/')
  if (!root) throw new Error('根路由不存在')
  return root
}

function childRoutes(r: Router): RouteRecordRaw[] {
  return (rootRoute(r).children ?? []) as RouteRecordRaw[]
}

function metaOf(route: RouteRecordRaw): MetaLike {
  return (route.meta ?? {}) as MetaLike
}

beforeEach(() => {
  localStorage.clear()
  document.title = ''
})

afterEach(() => {
  localStorage.clear()
})

describe('路由表完整性', () => {
  it('根路由：DefaultLayout 同步布局 + 重定向 /dashboard + 子路由挂载', async () => {
    const r = await loadRouter()
    const root = rootRoute(r)

    expect(root.redirect).toBe('/dashboard')
    expect(root.component).toBeTruthy()
    expect(typeof root.component).not.toBe('function') // 同步布局，不是懒加载函数
    expect(childRoutes(r).length).toBeGreaterThanOrEqual(20)
  })

  it('每个子路由 name 非空且全局唯一', async () => {
    const r = await loadRouter()
    const names = childRoutes(r).map((c) => c.name)

    for (const name of names) expect(name).toBeTruthy()
    expect(new Set(names).size).toBe(names.length)
  })

  it('每个子路由 path 非空、相对路径且唯一', async () => {
    const r = await loadRouter()
    const paths = childRoutes(r).map((c) => c.path)

    for (const path of paths) {
      expect(path).toBeTruthy()
      expect(path.startsWith('/')).toBe(false)
    }
    expect(new Set(paths).size).toBe(paths.length)
  })

  it('每个子路由都有非空 meta.title 与 meta.icon', async () => {
    const r = await loadRouter()

    for (const child of childRoutes(r)) {
      const meta = metaOf(child)
      expect(typeof meta.title).toBe('string')
      expect((meta.title ?? '').length).toBeGreaterThan(0)
      expect((meta.icon ?? '').length).toBeGreaterThan(0)
    }
  })

  it('每个子路由的 meta.crumbs 是非空字符串数组（面包屑可用）', async () => {
    const r = await loadRouter()

    for (const child of childRoutes(r)) {
      const crumbs = metaOf(child).crumbs
      expect(Array.isArray(crumbs)).toBe(true)
      expect((crumbs ?? []).length).toBeGreaterThan(0)
      for (const crumb of crumbs ?? []) expect(crumb.length).toBeGreaterThan(0)
    }
  })

  it('导航可见的只有 6 个主维度页面，其余 hidden 不进静态导航', async () => {
    const r = await loadRouter()
    const children = childRoutes(r)
    const visible = children.filter((c) => !metaOf(c).hidden).map((c) => String(c.name))
    const hidden = children.filter((c) => metaOf(c).hidden)

    expect(visible).toEqual([
      'dashboard',
      'projects',
      'tasks',
      'documents',
      'conversation',
      'review',
    ])
    expect(hidden.length).toBeGreaterThan(visible.length)
  })

  it('详情/设置类页面被显式 hidden（防止误入一级导航）', async () => {
    const r = await loadRouter()
    const hiddenNames = childRoutes(r)
      .filter((c) => metaOf(c).hidden)
      .map((c) => String(c.name))

    expect(hiddenNames).toContain('project-detail')
    expect(hiddenNames).toContain('workspace-setup')
    expect(hiddenNames).toContain('settings')
    expect(hiddenNames).toContain('vault')
  })

  it('子页面组件全部是懒加载函数（路由级分包），404 也是懒加载', async () => {
    const r = await loadRouter()

    for (const child of childRoutes(r)) {
      expect(typeof child.component).toBe('function')
    }
    const notFound = r.options.routes.find((route) => route.name === 'not-found')
    expect(notFound).toBeTruthy()
    expect(typeof notFound?.component).toBe('function')
  })

  it('全部懒加载 import() 路径都可解析（逐个真实加载，防重构后路径失效）', async () => {
    const r = await loadRouter()
    const loaders = [
      ...childRoutes(r).map((c) => c.component as () => Promise<unknown>),
      r.options.routes.find((route) => route.name === 'not-found')
        ?.component as () => Promise<unknown>,
    ]

    for (const loader of loaders) {
      const resolved = await loader()
      expect(resolved).toBeTruthy()
    }
  }, 120_000)
})

describe('路径解析与 404 兜底', () => {
  it('精确路由与动态参数解析正确', async () => {
    const r = await loadRouter()

    expect(r.resolve('/tasks').name).toBe('tasks')
    expect(r.resolve('/dashboard').name).toBe('dashboard')
    const detail = r.resolve('/projects/42')
    expect(detail.name).toBe('project-detail')
    expect(detail.params.id).toBe('42')
  })

  it('未知/深层未知路径都落到 not-found', async () => {
    const r = await loadRouter()

    expect(r.resolve('/nope').name).toBe('not-found')
    expect(r.resolve('/a/b/c/d').name).toBe('not-found')
    expect(r.resolve('/tasks/extra/deep').name).toBe('not-found')
  })

  it('根路径重定向到 /dashboard', async () => {
    const r = await loadRouter()

    await r.push('/')

    expect(r.currentRoute.value.path).toBe('/dashboard')
    expect(r.currentRoute.value.name).toBe('dashboard')
  })
})

describe('beforeEach：恢复最后访问路由', () => {
  it('首次进入 /dashboard 时跳回本地记录的最后路由', async () => {
    localStorage.setItem(LAST_ROUTE_KEY, '/tasks')
    const r = await loadRouter()

    await r.push('/dashboard')

    expect(r.currentRoute.value.path).toBe('/tasks')
  })

  it('只恢复一次：后续再进 /dashboard 不再被拉走', async () => {
    localStorage.setItem(LAST_ROUTE_KEY, '/tasks')
    const r = await loadRouter()

    await r.push('/dashboard')
    expect(r.currentRoute.value.path).toBe('/tasks')

    await r.push('/dashboard')
    expect(r.currentRoute.value.path).toBe('/dashboard')
  })

  it('记录值与 /dashboard 相同时不触发二次导航', async () => {
    localStorage.setItem(LAST_ROUTE_KEY, '/dashboard')
    const r = await loadRouter()

    await r.push('/dashboard')

    expect(r.currentRoute.value.path).toBe('/dashboard')
  })

  it('localStorage 读取异常时静默降级，照常进入 /dashboard', async () => {
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('storage denied')
    })
    const r = await loadRouter()

    await r.push('/dashboard')
    expect(r.currentRoute.value.path).toBe('/dashboard')
    spy.mockRestore()
  })
})

describe('afterEach：标题与最后路由记录', () => {
  it('按 meta.title 设置 document.title', async () => {
    const r = await loadRouter()

    await r.push('/tasks')
    expect(document.title).toBe('任务 · 启明星')

    await r.push('/settings')
    expect(document.title).toBe('设置 · 启明星')

    await r.push('/definitely-missing')
    expect(document.title).toBe('页面未找到 · 启明星')
  })

  it('把最近访问的 fullPath 写入 localStorage', async () => {
    const r = await loadRouter()

    await r.push('/tasks')
    expect(localStorage.getItem(LAST_ROUTE_KEY)).toBe('/tasks')

    await r.push('/projects/7')
    expect(localStorage.getItem(LAST_ROUTE_KEY)).toBe('/projects/7')
  })
})

describe('scrollBehavior', () => {
  it('有 savedPosition 时还原位置；有 hash 时平滑滚动；否则回到顶部', async () => {
    const r = await loadRouter()
    const scroll = r.options.scrollBehavior as ScrollBehavior
    expect(typeof scroll).toBe('function')

    expect(scroll({ hash: '#section' }, {}, null)).toEqual({ el: '#section', behavior: 'smooth' })
    expect(scroll({ hash: '' }, {}, { left: 0, top: 120 })).toEqual({ left: 0, top: 120 })
    expect(scroll({ hash: '' }, {}, null)).toEqual({ top: 0 })
  })
})

describe('默认导出', () => {
  it('导出的是可用 router 实例（含 beforeEach/afterEach 与 resolve）', () => {
    expect(router).toBeTruthy()
    expect(typeof router.push).toBe('function')
    expect(typeof router.resolve).toBe('function')
    expect(typeof router.beforeEach).toBe('function')
    expect(typeof router.afterEach).toBe('function')
  })
})
