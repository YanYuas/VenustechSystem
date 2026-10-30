// ============================================================
// BaseSelect —— 下拉选择组件交互测试（mount + 事件断言，无 DOM 快照）
//
// 覆盖：占位/选中态、打开关闭、options 渲染与选中态、点击选择、
// disabled（整体/单项）、clearable 清除、searchable 过滤与空态、
// 键盘 ↑↓/Enter/Esc、点击外部关闭、打开与值变化时的状态重置。
// ============================================================
import { afterEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import type { SelectOption } from '@/shared/types/common'
import BaseSelect from '../BaseSelect.vue'

const OPTIONS: SelectOption[] = [
  { value: 'a', label: 'Apple' },
  { value: 'b', label: 'Banana' },
  { value: 'c', label: 'Cherry', disabled: true },
]

type SelectProps = InstanceType<typeof BaseSelect>['$props']

function baseProps(patch: Partial<SelectProps> = {}): SelectProps {
  return {
    modelValue: '',
    options: OPTIONS,
    placeholder: '请选择',
    searchable: false,
    disabled: false,
    clearable: false,
    ...patch,
  } as SelectProps
}

const mounted: Array<{ unmount: () => void }> = []
function mountSelect(patch: Partial<SelectProps> = {}) {
  const wrapper = mount(BaseSelect, { props: baseProps(patch), attachTo: document.body })
  mounted.push(wrapper)
  return wrapper
}

function openPanel(wrapper: ReturnType<typeof mountSelect>) {
  return wrapper.find('.select__trigger').trigger('click')
}

afterEach(() => {
  mounted.splice(0).forEach((w) => w.unmount())
})

describe('BaseSelect：展示态', () => {
  it('未选中时显示 placeholder 并带 is-placeholder 样式', () => {
    const wrapper = mountSelect()

    const value = wrapper.find('.select__value')
    expect(value.text()).toBe('请选择')
    expect(value.classes()).toContain('is-placeholder')
  })

  it('已有值时显示对应 label（找到匹配项即不再有 placeholder 样式）', () => {
    const wrapper = mountSelect({ modelValue: 'b' })

    const value = wrapper.find('.select__value')
    expect(value.text()).toBe('Banana')
    expect(value.classes()).not.toContain('is-placeholder')
  })

  it('值在 options 中找不到时回落 placeholder（不显示空串）', () => {
    const wrapper = mountSelect({ modelValue: 'missing' })

    expect(wrapper.find('.select__value').text()).toBe('请选择')
    expect(wrapper.find('.select__value').classes()).toContain('is-placeholder')
  })

  it('disabled 时触发器带 is-disabled，且点击不展开面板', async () => {
    const wrapper = mountSelect({ disabled: true })

    expect(wrapper.find('.select__trigger').classes()).toContain('is-disabled')
    await openPanel(wrapper)
    expect(wrapper.find('.select__panel').exists()).toBe(false)
  })
})

describe('BaseSelect：打开/选择/关闭', () => {
  it('点击触发器打开面板（is-open），再次点击关闭', async () => {
    const wrapper = mountSelect()

    await openPanel(wrapper)
    expect(wrapper.find('.select__panel').exists()).toBe(true)
    expect(wrapper.find('.select__trigger').classes()).toContain('is-open')

    await openPanel(wrapper)
    expect(wrapper.find('.select__panel').exists()).toBe(false)
  })

  it('渲染全部 option，选中项带 is-active', async () => {
    const wrapper = mountSelect({ modelValue: 'a' })
    await openPanel(wrapper)

    const options = wrapper.findAll('.select__option')
    expect(options).toHaveLength(3)
    expect(options.map((o) => o.text())).toEqual(['Apple', 'Banana', 'Cherry'])
    expect(options[0].classes()).toContain('is-active')
    expect(options[1].classes()).not.toContain('is-active')
  })

  it('点击选项 emit update:modelValue + change 并关闭面板', async () => {
    const wrapper = mountSelect()
    await openPanel(wrapper)

    await wrapper.findAll('.select__option')[1].trigger('click')

    expect(wrapper.emitted('update:modelValue')).toEqual([['b']])
    expect(wrapper.emitted('change')).toEqual([['b']])
    expect(wrapper.find('.select__panel').exists()).toBe(false)
  })

  it('点击 disabled 选项不选中（不 emit、面板保持打开）', async () => {
    const wrapper = mountSelect()
    await openPanel(wrapper)

    await wrapper.findAll('.select__option')[2].trigger('click')

    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    expect(wrapper.find('.select__panel').exists()).toBe(true)
  })
})

describe('BaseSelect：清除与搜索', () => {
  it('clearable + 有值时显示清除按钮；点击 emit 空值并关闭', async () => {
    const wrapper = mountSelect({ modelValue: 'a', clearable: true })
    expect(wrapper.find('.select__clear').exists()).toBe(true)

    await wrapper.find('.select__clear').trigger('click')

    expect(wrapper.emitted('update:modelValue')).toEqual([['']])
    expect(wrapper.find('.select__panel').exists()).toBe(false)
  })

  it('无值时不显示清除按钮', () => {
    const wrapper = mountSelect({ modelValue: '', clearable: true })
    expect(wrapper.find('.select__clear').exists()).toBe(false)
  })

  it('searchable：打开后有搜索框，输入按 label 过滤（大小写不敏感）', async () => {
    const wrapper = mountSelect({ searchable: true })
    await openPanel(wrapper)
    expect(wrapper.find('.select__search').exists()).toBe(true)

    await wrapper.find('.select__search').setValue('AN')
    expect(wrapper.findAll('.select__option').map((o) => o.text())).toEqual(['Banana'])
  })

  it('搜索无匹配时显示空态文案', async () => {
    const wrapper = mountSelect({ searchable: true })
    await openPanel(wrapper)

    await wrapper.find('.select__search').setValue('zzz')

    expect(wrapper.find('.select__empty').text()).toBe('无匹配选项')
    expect(wrapper.findAll('.select__option')).toHaveLength(0)
  })
})

describe('BaseSelect：键盘与外部点击', () => {
  it('↑↓ 移动高亮并在边界收敛', async () => {
    const wrapper = mountSelect()
    await openPanel(wrapper)
    const trigger = wrapper.find('.select__trigger')

    await trigger.trigger('keydown', { key: 'ArrowDown' })
    expect(wrapper.findAll('.select__option')[1].classes()).toContain('is-highlight')

    await trigger.trigger('keydown', { key: 'ArrowDown' })
    await trigger.trigger('keydown', { key: 'ArrowDown' }) // 已到末尾
    expect(wrapper.findAll('.select__option')[2].classes()).toContain('is-highlight')

    await trigger.trigger('keydown', { key: 'ArrowUp' })
    expect(wrapper.findAll('.select__option')[1].classes()).toContain('is-highlight')
  })

  it('Enter 选中高亮项并 emit', async () => {
    const wrapper = mountSelect()
    await openPanel(wrapper)
    const trigger = wrapper.find('.select__trigger')

    await trigger.trigger('keydown', { key: 'ArrowDown' })
    await trigger.trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('update:modelValue')).toEqual([['b']])
    expect(wrapper.emitted('change')).toEqual([['b']])
  })

  it('Enter 落在 disabled 项上不选中', async () => {
    const wrapper = mountSelect()
    await openPanel(wrapper)
    const trigger = wrapper.find('.select__trigger')

    await trigger.trigger('keydown', { key: 'ArrowDown' })
    await trigger.trigger('keydown', { key: 'ArrowDown' })
    await trigger.trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })

  it('Esc 关闭面板', async () => {
    const wrapper = mountSelect()
    await openPanel(wrapper)

    await wrapper.find('.select__trigger').trigger('keydown', { key: 'Escape' })

    expect(wrapper.find('.select__panel').exists()).toBe(false)
  })

  it('点击组件外部（document mousedown）关闭面板', async () => {
    const wrapper = mountSelect()
    await openPanel(wrapper)
    expect(wrapper.find('.select__panel').exists()).toBe(true)

    document.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.select__panel').exists()).toBe(false)
  })

  it('关闭再打开时清空搜索词与高亮（不会残留上次状态）', async () => {
    const wrapper = mountSelect({ searchable: true })
    await openPanel(wrapper)
    await wrapper.find('.select__search').setValue('an')
    await wrapper.find('.select__trigger').trigger('keydown', { key: 'ArrowDown' })

    await wrapper.find('.select__trigger').trigger('keydown', { key: 'Escape' })
    await openPanel(wrapper)

    expect(wrapper.findAll('.select__option')).toHaveLength(3)
    expect(wrapper.findAll('.select__option')[0].classes()).toContain('is-highlight')
  })
})
