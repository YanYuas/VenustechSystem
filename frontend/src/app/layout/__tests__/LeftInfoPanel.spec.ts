// ============================================================
// LeftInfoPanel —— 左侧信息面板壳层测试
//
// mock panelApi / vue-router / useToast，覆盖：加载三态（骨架→数据→失败降级）、
// 日期/状态/待办/提醒渲染、快捷入口跳转、新增待办（空值守卫/成功/失败）、
// 勾选乐观更新与回滚、删除、Esc 收起输入框。
// ============================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import { panelApi } from '@/features/panel'
import type { LeftPanelData, QuickTodo } from '@/features/panel'
import LeftInfoPanel from '../LeftInfoPanel.vue'

const h = vi.hoisted(() => ({
  push: vi.fn(),
  toast: { error: vi.fn(), success: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

vi.mock('vue-router', () => ({ useRouter: () => ({ push: h.push }) }))
vi.mock('@/features/panel', () => ({
  panelApi: { get: vi.fn(), createTodo: vi.fn(), updateTodo: vi.fn(), deleteTodo: vi.fn() },
}))
vi.mock('@/kernel/ui/toast', () => ({
  useToast: () => h.toast,
  toast: h.toast,
}))

// 通过 mock 模块拿回 api 引用（与组件使用同一模块实例）
const api = panelApi as unknown as {
  get: ReturnType<typeof vi.fn>
  createTodo: ReturnType<typeof vi.fn>
  updateTodo: ReturnType<typeof vi.fn>
  deleteTodo: ReturnType<typeof vi.fn>
}
const toastError = h.toast.error

function todo(patch: Partial<QuickTodo> = {}): QuickTodo {
  return {
    id: 't1',
    title: '买牛奶',
    completed: false,
    sort_order: 0,
    created_at: '2026-10-31T08:00:00',
    ...patch,
  } as QuickTodo
}

function makePanelData(patch: Partial<LeftPanelData> = {}): LeftPanelData {
  return {
    greeting: '早上好',
    date_str: '2026年10月31日',
    weekday: '星期六',
    stats: { focus_task: 2, must_do: 3, in_progress: 1, waiting: 4, completed_today: 5 },
    quick_todos: [todo()],
    reminders: [{ id: 'r1', title: '10 点开会', remind_at: '10:00' }],
    ...patch,
  } as unknown as LeftPanelData
}

const mounted: Array<{ unmount: () => void }> = []
function mountPanel() {
  const wrapper = mount(LeftInfoPanel)
  mounted.push(wrapper)
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  api.get.mockResolvedValue(makePanelData())
  api.createTodo.mockResolvedValue(todo())
  api.updateTodo.mockResolvedValue(todo({ completed: true }))
  api.deleteTodo.mockResolvedValue(undefined)
})

afterEach(() => {
  mounted.splice(0).forEach((w) => w.unmount())
})

describe('LeftInfoPanel：加载三态', () => {
  it('加载中：显示骨架屏与日期占位，不渲染数据列表', async () => {
    api.get.mockReturnValue(new Promise(() => undefined))
    const wrapper = mountPanel()
    await wrapper.vm.$nextTick()

    expect(wrapper.findAll('.panel-skeleton').length).toBe(3)
    expect(wrapper.text()).toContain('----年--月--日')
    expect(wrapper.text()).toContain('星期--')
    expect(wrapper.find('.stat-list').exists()).toBe(false)
  })

  it('加载成功：骨架消失，日期/星期/问候与 5 项今日状态渲染', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.findAll('.panel-skeleton')).toHaveLength(0)
    expect(wrapper.text()).toContain('2026年10月31日')
    expect(wrapper.text()).toContain('星期六')
    expect(wrapper.text()).toContain('早上好，启明星！')

    const stats = wrapper.findAll('.stat-item')
    expect(stats).toHaveLength(5)
    expect(stats[0].text()).toContain('今日最重要')
    expect(stats[0].text()).toContain('2项')
    expect(stats[4].text()).toContain('今日完成')
    expect(stats[4].text()).toContain('5项')
  })

  it('加载失败：toast 报错并降级为空列表（loading 结束）', async () => {
    api.get.mockRejectedValue(new Error('panel down'))
    const wrapper = mountPanel()
    await flushPromises()

    expect(toastError).toHaveBeenCalledWith('加载失败', '左侧面板数据加载失败')
    expect(wrapper.findAll('.panel-skeleton')).toHaveLength(0)
    expect(wrapper.text()).toContain('暂无待办，点击 + 添加')
    expect(wrapper.text()).toContain('暂无提醒')
  })

  it('状态字段缺失时回退显示 0 项', async () => {
    api.get.mockResolvedValue(
      makePanelData({ stats: { focus_task: 1 } as unknown as LeftPanelData['stats'] }),
    )
    const wrapper = mountPanel()
    await flushPromises()

    const stats = wrapper.findAll('.stat-item')
    expect(stats[0].text()).toContain('1项')
    expect(stats[4].text()).toContain('0项')
  })
})

describe('LeftInfoPanel：快捷入口', () => {
  it('点击状态项、查看全部、底部设置按钮各自跳转', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    await wrapper.find('.stat-item').trigger('click')
    expect(h.push).toHaveBeenLastCalledWith('/tasks')

    await wrapper.find('.panel-section__more').trigger('click')
    expect(h.push).toHaveBeenLastCalledWith('/tasks')

    const settingBtn = wrapper.findAll('.panel-footer__btn')[2]
    await settingBtn.trigger('click')
    expect(h.push).toHaveBeenLastCalledWith('/settings')
  })
})

describe('LeftInfoPanel：待办 CRUD', () => {
  it('渲染待办标题与完成态；无待办时显示空提示', async () => {
    api.get.mockResolvedValueOnce(
      makePanelData({
        quick_todos: [todo({ id: 'a', title: '已完成', completed: true }), todo({ id: 'b' })],
      }),
    )
    const wrapper = mountPanel()
    await flushPromises()

    const titles = wrapper.findAll('.todo-item__title')
    expect(titles[0].text()).toBe('已完成')
    expect(titles[0].classes()).toContain('is-done')
    expect(titles[1].classes()).not.toContain('is-done')
  })

  it('无待办时显示空提示', async () => {
    api.get.mockResolvedValueOnce(makePanelData({ quick_todos: [] }))
    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.text()).toContain('暂无待办，点击 + 添加')
  })

  it('点击 + 展开输入框；空白输入回车不创建', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    await wrapper.find('.panel-section__add').trigger('click')
    const input = wrapper.find('.todo-input__field')
    expect(input.exists()).toBe(true)

    await input.setValue('   ')
    await input.trigger('keyup.enter')
    await flushPromises()
    expect(api.createTodo).not.toHaveBeenCalled()
  })

  it('新增待办成功：trim 后提交、清空并收起输入框、重新加载面板', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.find('.panel-section__add').trigger('click')

    const input = wrapper.find('.todo-input__field')
    await input.setValue('  买牛奶  ')
    await input.trigger('keyup.enter')
    await flushPromises()

    expect(api.createTodo).toHaveBeenCalledWith({ title: '买牛奶' })
    expect(api.get).toHaveBeenCalledTimes(2) // 初次加载 + 新增后 reload
    expect(wrapper.find('.todo-input').exists()).toBe(false)
  })

  it('新增待办失败：toast 报错，输入内容保留', async () => {
    api.createTodo.mockRejectedValueOnce(new Error('create down'))
    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.find('.panel-section__add').trigger('click')
    const input = wrapper.find('.todo-input__field')
    await input.setValue('买牛奶')

    await input.trigger('keyup.enter')
    await flushPromises()

    expect(toastError).toHaveBeenCalledWith('创建失败', '待办创建失败')
    expect((wrapper.find('.todo-input__field').element as HTMLInputElement).value).toBe('买牛奶')
    expect(wrapper.find('.todo-input').exists()).toBe(true)
  })

  it('Esc 收起待办输入框', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.find('.panel-section__add').trigger('click')

    await wrapper.find('.todo-input__field').trigger('keyup.esc')

    expect(wrapper.find('.todo-input').exists()).toBe(false)
  })

  it('勾选待办：先乐观更新并调用接口', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    await wrapper.find('.todo-item__check input').trigger('change')

    expect(api.updateTodo).toHaveBeenCalledWith('t1', { completed: true })
    expect(wrapper.find('.todo-item__title').classes()).toContain('is-done')
  })

  it('勾选失败：回滚本地状态并 toast 报错', async () => {
    api.updateTodo.mockRejectedValueOnce(new Error('patch down'))
    const wrapper = mountPanel()
    await flushPromises()

    await wrapper.find('.todo-item__check input').trigger('change')
    await flushPromises()

    expect(toastError).toHaveBeenCalledWith('操作失败', '待办状态更新失败')
    expect(wrapper.find('.todo-item__title').classes()).not.toContain('is-done')
  })

  it('删除待办：成功后重新加载；失败 toast 报错', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    await wrapper.find('.todo-item__delete').trigger('click')
    await flushPromises()
    expect(api.deleteTodo).toHaveBeenCalledWith('t1')
    expect(api.get).toHaveBeenCalledTimes(2)

    api.deleteTodo.mockRejectedValueOnce(new Error('del down'))
    await wrapper.find('.todo-item__delete').trigger('click')
    await flushPromises()
    expect(toastError).toHaveBeenCalledWith('删除失败', '待办删除失败')
  })
})

describe('LeftInfoPanel：系统提醒', () => {
  it('渲染提醒标题与时间；无提醒时显示空提示', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    const reminder = wrapper.find('.reminder-item')
    expect(reminder.text()).toContain('10 点开会')
    expect(reminder.text()).toContain('10:00')

    api.get.mockResolvedValueOnce(makePanelData({ reminders: [] }))
    const empty = mountPanel()
    await flushPromises()
    expect(empty.text()).toContain('暂无提醒')
  })
})
