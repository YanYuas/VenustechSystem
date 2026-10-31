// ============================================================
// TopNav —— 顶部导航壳层测试
//
// mock vue-router（useRoute/useRouter）与 useNotification，stub 掉离线角标；
// 覆盖：六维度导航渲染与高亮、点击跳转、搜索/头像 emit、
// 通知面板开合与 fetchList、未读红点、通知点击已读+按类型跳转、时间格式化。
// ============================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import TopNav from '../TopNav.vue'

const h = vi.hoisted(() => ({
  route: { path: '/dashboard' },
  push: vi.fn(),
  notif: {
    notifications: [] as Array<Record<string, unknown>>,
    unreadCount: 0,
    fetchList: vi.fn(),
    markRead: vi.fn(),
    markAllRead: vi.fn(),
  },
}))

vi.mock('vue-router', () => ({
  useRoute: () => h.route,
  useRouter: () => ({ push: h.push }),
}))
vi.mock('@/features/notification', () => ({
  useNotification: () => h.notif,
}))

const mounted: Array<{ unmount: () => void }> = []
function mountNav(path = '/dashboard') {
  h.route.path = path
  const wrapper = mount(TopNav, {
    global: { stubs: { OfflineQueueIndicator: true } },
  })
  mounted.push(wrapper)
  return wrapper
}

function minutesAgo(min: number): string {
  return new Date(Date.now() - min * 60_000).toISOString()
}

function makeNotif(patch: Record<string, unknown> = {}) {
  return {
    id: 'n1',
    title: '任务到期',
    content: '记得提交',
    type: 'task',
    is_read: false,
    created_at: minutesAgo(0.1),
    ...patch,
  }
}

function openNotifPanel(wrapper: ReturnType<typeof mountNav>) {
  return wrapper.find('.topnav__icon-btn').trigger('click')
}

beforeEach(() => {
  vi.clearAllMocks()
  h.route.path = '/dashboard'
  h.notif.notifications = []
  h.notif.unreadCount = 0
})

afterEach(() => {
  mounted.splice(0).forEach((w) => w.unmount())
})

describe('TopNav：六维度导航', () => {
  it('渲染品牌与 6 个导航项（顺序与维度配置一致）', () => {
    const wrapper = mountNav()

    expect(wrapper.text()).toContain('Venustech System')
    const labels = wrapper.findAll('.topnav__item').map((b) => b.text())
    expect(labels).toEqual(['首页', '执行', '知识', '人生', '资产', '伙伴'])
  })

  it.each([
    ['/dashboard', '首页'],
    ['/tasks', '执行'],
    ['/documents', '知识'],
    ['/identities', '人生'],
    ['/learning', '资产'],
    ['/settings', '伙伴'],
  ])('当前路由 %s 时高亮「%s」且只高亮一个', (path, label) => {
    const wrapper = mountNav(path)

    const active = wrapper.findAll('.topnav__item.is-active')
    expect(active).toHaveLength(1)
    expect(active[0].text()).toBe(label)
  })

  it('子路径前缀也归属对应维度（/projects/42 → 执行）', () => {
    const wrapper = mountNav('/projects/42')

    expect(wrapper.find('.topnav__item.is-active').text()).toBe('执行')
  })

  it('未知路由不高亮任何维度', () => {
    const wrapper = mountNav('/unknown')

    expect(wrapper.findAll('.topnav__item.is-active')).toHaveLength(0)
  })

  it('点击导航项跳转到对应路由', async () => {
    const wrapper = mountNav()

    await wrapper.findAll('.topnav__item')[1].trigger('click')
    expect(h.push).toHaveBeenCalledWith('/tasks')

    await wrapper.findAll('.topnav__item')[5].trigger('click')
    expect(h.push).toHaveBeenCalledWith('/conversation')
  })

  it('搜索与头像按钮分别 emit open-search / open-user-menu', async () => {
    const wrapper = mountNav()

    await wrapper.find('.topnav__search').trigger('click')
    await wrapper.find('.topnav__avatar').trigger('click')

    expect(wrapper.emitted('open-search')).toHaveLength(1)
    expect(wrapper.emitted('open-user-menu')).toHaveLength(1)
  })
})

describe('TopNav：通知面板', () => {
  it('打开面板时拉取通知列表；关闭再打开会再次拉取', async () => {
    const wrapper = mountNav()

    await openNotifPanel(wrapper)
    await flushPromises()
    expect(h.notif.fetchList).toHaveBeenCalledTimes(1)
    expect(h.notif.fetchList).toHaveBeenCalledWith(false, 1, 20)

    await openNotifPanel(wrapper) // 关闭
    expect(wrapper.find('.topnav__notif-panel').exists()).toBe(false)

    await openNotifPanel(wrapper) // 再开
    await flushPromises()
    expect(h.notif.fetchList).toHaveBeenCalledTimes(2)
  })

  it('有未读时显示红点与「全部已读」；无未读则都不显示', async () => {
    h.notif.unreadCount = 3
    const withUnread = mountNav()
    await openNotifPanel(withUnread)
    expect(withUnread.find('.topnav__badge').exists()).toBe(true)
    expect(withUnread.find('.topnav__notif-readall').exists()).toBe(true)

    // 组件在 setup 时快照 useNotification() 的返回值；共享 mock 对象必须先重置再挂载
    h.notif.unreadCount = 0
    const noUnread = mountNav()
    await openNotifPanel(noUnread)
    expect(noUnread.find('.topnav__badge').exists()).toBe(false)
    expect(noUnread.find('.topnav__notif-readall').exists()).toBe(false)
  })

  it('无通知时显示空态；「全部已读」触发 markAllRead', async () => {
    h.notif.unreadCount = 1
    const wrapper = mountNav()
    await openNotifPanel(wrapper)
    expect(wrapper.text()).toContain('暂无通知')

    await wrapper.find('.topnav__notif-readall').trigger('click')
    expect(h.notif.markAllRead).toHaveBeenCalledTimes(1)
  })

  it('通知条目渲染标题/内容，并按时间显示「刚刚/N分钟前/N小时前/N天前」', async () => {
    h.notif.notifications = [
      makeNotif({ id: 'n1', title: '刚刚的', created_at: minutesAgo(0) }),
      makeNotif({ id: 'n2', title: '30分钟', created_at: minutesAgo(30.5) }),
      makeNotif({ id: 'n3', title: '5小时', created_at: minutesAgo(5 * 60 + 1) }),
      makeNotif({ id: 'n4', title: '3天', created_at: minutesAgo(3 * 24 * 60 + 5) }),
    ]
    const wrapper = mountNav()
    await openNotifPanel(wrapper)

    const items = wrapper.findAll('.topnav__notif-item')
    expect(items).toHaveLength(4)
    expect(items[0].find('.topnav__notif-time').text()).toBe('刚刚')
    expect(items[1].find('.topnav__notif-time').text()).toBe('30分钟前')
    expect(items[2].find('.topnav__notif-time').text()).toBe('5小时前')
    expect(items[3].find('.topnav__notif-time').text()).toBe('3天前')
    expect(items[0].text()).toContain('记得提交')
  })

  it('已读条目带 is-read 样式', async () => {
    h.notif.notifications = [makeNotif({ is_read: true })]
    const wrapper = mountNav()
    await openNotifPanel(wrapper)

    expect(wrapper.find('.topnav__notif-item').classes()).toContain('is-read')
  })

  it('点击未读通知：标记已读 + 关闭面板 + 按类型跳转', async () => {
    h.notif.notifications = [makeNotif({ id: 'n9', type: 'task', is_read: false })]
    const wrapper = mountNav()
    await openNotifPanel(wrapper)

    await wrapper.find('.topnav__notif-item').trigger('click')

    expect(h.notif.markRead).toHaveBeenCalledWith('n9', true)
    expect(h.push).toHaveBeenCalledWith('/tasks')
    expect(wrapper.find('.topnav__notif-panel').exists()).toBe(false)
  })

  it('点击已读通知：不再标记已读，但仍跳转', async () => {
    h.notif.notifications = [makeNotif({ id: 'n10', type: 'document', is_read: true })]
    const wrapper = mountNav()
    await openNotifPanel(wrapper)

    await wrapper.find('.topnav__notif-item').trigger('click')

    expect(h.notif.markRead).not.toHaveBeenCalled()
    expect(h.push).toHaveBeenCalledWith('/documents')
  })

  it('未知通知类型：只关闭面板，不跳转', async () => {
    h.notif.notifications = [makeNotif({ id: 'n11', type: 'other', is_read: true })]
    const wrapper = mountNav()
    await openNotifPanel(wrapper)

    await wrapper.find('.topnav__notif-item').trigger('click')

    expect(h.push).not.toHaveBeenCalled()
    expect(wrapper.find('.topnav__notif-panel').exists()).toBe(false)
  })
})
