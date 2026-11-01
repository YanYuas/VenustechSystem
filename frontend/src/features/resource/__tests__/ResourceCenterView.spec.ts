// ============================================================
// ResourceCenterView —— ?tab= 深链测试（Phase21 D-69 首页资源卡联动）
//
// 覆盖：query 初始 tab、首页分类单数 id 别名、缺省/非法回收集箱、
// 同一路由内 query 变化（首页连点不同资源卡）触发切换、数组 query 取首值。
// 用真实 memory router（组件只依赖 useRoute，无需 mock vue-router）；
// ../api 只 mock 用到的接口。
// ============================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

vi.mock('../api', () => ({
  resourceApi: {
    listInbox: vi.fn(),
    listTemplates: vi.fn(),
    listDomains: vi.fn(),
    createInboxItem: vi.fn(),
    processInboxItem: vi.fn(),
    createTemplate: vi.fn(),
    createDomain: vi.fn(),
    deleteDomain: vi.fn(),
  },
}))

import { resourceApi } from '../api'
import ResourceCenterView from '../views/ResourceCenterView.vue'

const api = resourceApi as unknown as Record<string, ReturnType<typeof vi.fn>>

const mounted: Array<{ unmount: () => void }> = []

async function mountAt(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/resource-center', component: ResourceCenterView }],
  })
  await router.push(path)
  await router.isReady()
  const wrapper = mount(ResourceCenterView, { global: { plugins: [router] } })
  mounted.push(wrapper)
  await flushPromises()
  return { wrapper, router }
}

function activeTabText(wrapper: ReturnType<typeof mount>): string {
  const active = wrapper.find('.tab-btn.active')
  return active.exists() ? active.text() : ''
}

beforeEach(() => {
  vi.clearAllMocks()
  api.listInbox.mockResolvedValue({ list: [], total: 0 })
  api.listTemplates.mockResolvedValue({ list: [], total: 0 })
  api.listDomains.mockResolvedValue([])
})

afterEach(() => {
  mounted.splice(0).forEach((w) => w.unmount())
})

describe('ResourceCenterView：?tab= 深链', () => {
  it('?tab=templates 初始进入模板库，只拉模板', async () => {
    const { wrapper } = await mountAt('/resource-center?tab=templates')

    expect(activeTabText(wrapper)).toContain('模板库')
    expect(api.listTemplates).toHaveBeenCalledTimes(1)
    expect(api.listInbox).not.toHaveBeenCalled()
  })

  it('?tab=template（首页资源分类单数 id）映射到模板库', async () => {
    const { wrapper } = await mountAt('/resource-center?tab=template')

    expect(activeTabText(wrapper)).toContain('模板库')
    expect(api.listTemplates).toHaveBeenCalledTimes(1)
  })

  it.each(['domains', 'domain'])('?tab=%s 进入领域库', async (tab) => {
    const { wrapper } = await mountAt(`/resource-center?tab=${tab}`)

    expect(activeTabText(wrapper)).toContain('领域库')
    expect(api.listDomains).toHaveBeenCalledTimes(1)
  })

  it('无 query 或非法值回收集箱（保持原行为）', async () => {
    const noQuery = await mountAt('/resource-center')
    expect(activeTabText(noQuery.wrapper)).toContain('收集箱')
    expect(api.listInbox).toHaveBeenCalledTimes(1)

    const invalid = await mountAt('/resource-center?tab=not-a-tab')
    expect(activeTabText(invalid.wrapper)).toContain('收集箱')
  })

  it('同一路由内 query 变化会切换 tab（首页连点不同资源卡）', async () => {
    const { wrapper, router } = await mountAt('/resource-center?tab=inbox')
    expect(activeTabText(wrapper)).toContain('收集箱')

    await router.push('/resource-center?tab=templates')
    await flushPromises()

    expect(activeTabText(wrapper)).toContain('模板库')
    expect(api.listTemplates).toHaveBeenCalledTimes(1)
  })

  it('query 为数组时取第一个值（vue-router 重复参数）', async () => {
    const { wrapper } = await mountAt('/resource-center?tab=domains&tab=inbox')

    expect(activeTabText(wrapper)).toContain('领域库')
  })
})
