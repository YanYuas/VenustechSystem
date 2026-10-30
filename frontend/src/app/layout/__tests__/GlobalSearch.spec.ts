// ============================================================
// GlobalSearch（Cmd+K 全局搜索）—— 交互组件测试
//
// 覆盖：输入 200ms 防抖、结果分组映射、操作项恒定、空匹配、加载中、
// 请求失败降级、↑↓ 高亮、Enter 选中、Esc/遮罩关闭、搜索历史、
// 过期响应丢弃（竞态）、打开时重置与聚焦、卸载清理防抖。
// 全程 stub documentApi.search，不访问真实后端。
// ============================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'

import type { SearchResult } from '@/features/document'
import { documentApi } from '@/features/document'
import GlobalSearch from '../GlobalSearch.vue'

vi.mock('@/features/document', () => ({
  documentApi: { search: vi.fn() },
}))

const search = vi.mocked(documentApi.search)
const HISTORY_KEY = 'qmx:search-history'

function makeSearch(patch: Partial<SearchResult> = {}): SearchResult {
  return {
    tasks: [],
    documents: [],
    conversations: [],
    ...patch,
  } as unknown as SearchResult
}

const mounted: Array<{ unmount: () => void }> = []

function mountSearch(modelValue = true) {
  const wrapper = mount(GlobalSearch, {
    props: { modelValue },
    global: { stubs: { teleport: true } },
    attachTo: document.body,
  })
  mounted.push(wrapper)
  return wrapper
}

/** fake timers 下只刷微任务（VS VTU 的 flushPromises 内部 setTimeout 不会被推进） */
async function flushMicro() {
  await Promise.resolve()
  await Promise.resolve()
  await Promise.resolve()
  await nextTick()
}

async function typeAndWait(wrapper: ReturnType<typeof mountSearch>, value: string) {
  await wrapper.find('input.gsearch__input').setValue(value)
  await vi.advanceTimersByTimeAsync(200)
  await flushMicro()
}

beforeEach(() => {
  vi.useFakeTimers()
  localStorage.clear()
  search.mockReset()
  search.mockResolvedValue(makeSearch())
})

afterEach(() => {
  mounted.splice(0).forEach((w) => {
    try {
      w.unmount()
    } catch {
      /* 用例内已手动卸载 */
    }
  })
  vi.useRealTimers()
  localStorage.clear()
})

describe('GlobalSearch：搜索防抖与结果', () => {
  it('连续输入只在停止 200ms 后发一次请求（参数为最后输入）', async () => {
    const wrapper = mountSearch()
    const input = wrapper.find('input.gsearch__input')

    await input.setValue('a')
    await input.setValue('ab')
    await input.setValue('abc')
    expect(search).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(199)
    expect(search).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1)
    await flushMicro()
    expect(search).toHaveBeenCalledTimes(1)
    expect(search).toHaveBeenCalledWith('abc')
  })

  it('把后端结果映射成分组条目，并恒带「新建任务/新建文档」两个操作项', async () => {
    search.mockResolvedValueOnce(
      makeSearch({
        tasks: [{ id: 't1', title: '任务A', status: 'todo' }] as never,
        documents: [{ id: 'd1', title: '文档B', snippet: '片段内容' }] as never,
        conversations: [{ id: 'c1', title: '对话C' }] as never,
      }),
    )
    const wrapper = mountSearch()
    await typeAndWait(wrapper, 'A')

    const text = wrapper.text()
    expect(text).toContain('任务A')
    expect(text).toContain('文档B')
    expect(text).toContain('对话C')
    expect(text).toContain('todo')
    expect(text).toContain('片段内容')
    expect(text).toContain('新建任务')
    expect(text).toContain('新建文档')
  })

  it('无匹配时显示引导式空态，且两个操作项仍常驻（D-29）', async () => {
    const wrapper = mountSearch()
    await typeAndWait(wrapper, '不存在')

    // 操作项恒定：清空搜索词之外的任何情况下都保留「新建任务/新建文档」
    const buttons = wrapper.findAll('.gsearch__result')
    expect(buttons).toHaveLength(2)
    expect(wrapper.text()).toContain('新建任务')

    // 但空态判断只看"真实结果"（排除 action），所以引导文案必须出现
    const empty = wrapper.find('.gsearch__empty')
    expect(empty.exists()).toBe(true)
    expect(empty.text()).toContain('没有找到相关内容，可试试下面的操作')
  })

  it('加载中显示「搜索中…」，完成后隐藏', async () => {
    let resolveSearch: ((v: SearchResult) => void) | undefined
    search.mockImplementationOnce(
      () =>
        new Promise<SearchResult>((resolve) => {
          resolveSearch = resolve
        }),
    )
    const wrapper = mountSearch()
    await wrapper.find('input.gsearch__input').setValue('慢查询')
    await vi.advanceTimersByTimeAsync(200)
    await flushMicro()

    expect(wrapper.find('.gsearch__loading').text()).toContain('搜索中…')

    resolveSearch?.(makeSearch())
    await flushMicro()
    expect(wrapper.find('.gsearch__loading').exists()).toBe(false)
  })

  it('请求失败时降级：不抛错、loading 复位、只显示操作项', async () => {
    search.mockRejectedValueOnce(new Error('network down'))
    const wrapper = mountSearch()

    await typeAndWait(wrapper, 'boom')

    expect(wrapper.find('.gsearch__loading').exists()).toBe(false)
    expect(wrapper.findAll('.gsearch__result')).toHaveLength(2)
    expect(wrapper.text()).toContain('新建任务')
    // 失败同样等价于"没有真实结果"：显示引导文案，但不影响操作项
    expect(wrapper.find('.gsearch__empty').text()).toContain('没有找到相关内容，可试试下面的操作')
  })

  it('过期响应被丢弃：先发的请求后到，不能覆盖新结果', async () => {
    let resolveFirst: ((v: SearchResult) => void) | undefined
    search
      .mockImplementationOnce(
        () =>
          new Promise<SearchResult>((resolve) => {
            resolveFirst = resolve
          }),
      )
      .mockResolvedValueOnce(makeSearch({ documents: [{ id: 'd2', title: '新结果' }] as never }))
    const wrapper = mountSearch()

    await wrapper.find('input.gsearch__input').setValue('旧')
    await vi.advanceTimersByTimeAsync(200)
    await wrapper.find('input.gsearch__input').setValue('新')
    await vi.advanceTimersByTimeAsync(200)
    await flushMicro()
    expect(wrapper.text()).toContain('新结果')

    resolveFirst?.(makeSearch({ tasks: [{ id: 't9', title: '旧结果' }] as never }))
    await flushMicro()

    expect(wrapper.text()).toContain('新结果')
    expect(wrapper.text()).not.toContain('旧结果')
  })
})

describe('GlobalSearch：键盘与关闭', () => {
  async function mountWithTwoTasks() {
    search.mockResolvedValueOnce(
      makeSearch({
        tasks: [
          { id: 't1', title: '任务一', status: 'todo' },
          { id: 't2', title: '任务二', status: 'todo' },
        ] as never,
      }),
    )
    const wrapper = mountSearch()
    await typeAndWait(wrapper, '任务')
    return wrapper
  }

  it('↑↓ 移动高亮并在边界收敛', async () => {
    const wrapper = await mountWithTwoTasks()
    const root = wrapper.find('.gsearch')

    await root.trigger('keydown', { key: 'ArrowDown' })
    expect(wrapper.findAll('.gsearch__result.is-active')).toHaveLength(1)
    expect(wrapper.find('.gsearch__result.is-active').text()).toContain('任务二')

    await root.trigger('keydown', { key: 'ArrowDown' })
    // 已到末尾：不再越过（4 项：2 任务 + 2 操作）
    expect(wrapper.findAll('.gsearch__result.is-active')).toHaveLength(1)

    await root.trigger('keydown', { key: 'ArrowUp' })
    await root.trigger('keydown', { key: 'ArrowUp' })
    await root.trigger('keydown', { key: 'ArrowUp' })
    expect(wrapper.find('.gsearch__result.is-active').text()).toContain('任务一')
  })

  it('Enter 选中当前项：emit select + 关闭面板', async () => {
    const wrapper = await mountWithTwoTasks()

    await wrapper.find('.gsearch').trigger('keydown', { key: 'Enter' })

    const selected = wrapper.emitted('select')?.[0]?.[0] as { id: string; type: string }
    expect(selected).toMatchObject({ id: 't1', type: 'task' })
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
  })

  it('Esc 关闭面板（emit update:modelValue=false）', async () => {
    const wrapper = mountSearch()

    await wrapper.find('.gsearch').trigger('keydown', { key: 'Escape' })

    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
  })

  it('点击遮罩空白处关闭；点击面板内部不关闭', async () => {
    const wrapper = mountSearch()

    await wrapper.find('.gsearch__panel').trigger('click')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()

    await wrapper.find('.gsearch').trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
  })
})

describe('GlobalSearch：历史与生命周期', () => {
  it('空词时展示最近搜索，点击历史项立即检索（不再防抖）', async () => {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(['旧关键词']))
    const wrapper = mountSearch()

    expect(wrapper.text()).toContain('最近搜索')
    expect(wrapper.text()).toContain('旧关键词')

    await wrapper.find('.gsearch__result').trigger('click')
    await flushMicro()

    expect(search).toHaveBeenCalledWith('旧关键词')
  })

  it('选中结果后写入搜索历史（最多 5 条，去重）', async () => {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(['旧1', '旧2', '旧3', '旧4', '旧5']))
    search.mockResolvedValueOnce(
      makeSearch({ tasks: [{ id: 't1', title: '新命中', status: 'todo' }] as never }),
    )
    const wrapper = mountSearch()
    await typeAndWait(wrapper, '命中')

    await wrapper.find('.gsearch__result').trigger('click')

    const history = JSON.parse(localStorage.getItem(HISTORY_KEY) ?? '[]') as string[]
    expect(history[0]).toBe('新命中')
    expect(history).toHaveLength(5)
  })

  it('面板重新打开时清空输入与结果并聚焦输入框', async () => {
    const wrapper = mountSearch()
    await wrapper.find('input.gsearch__input').setValue('残留词')
    await vi.advanceTimersByTimeAsync(200)
    await flushMicro()

    await wrapper.setProps({ modelValue: false })
    await wrapper.setProps({ modelValue: true })
    await nextTick()
    await flushMicro()

    const input = wrapper.find('input.gsearch__input').element as HTMLInputElement
    expect(input.value).toBe('')
    expect(wrapper.findAll('.gsearch__result')).toHaveLength(0)
    expect(document.activeElement).toBe(input)
  })

  it('卸载时清理 200ms 防抖定时器：之后不再发请求', async () => {
    const wrapper = mountSearch()
    await wrapper.find('input.gsearch__input').setValue('要卸载了')

    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(500)

    expect(search).not.toHaveBeenCalled()
  })
})
