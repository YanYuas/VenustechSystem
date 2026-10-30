// ============================================================
// BaseSwitch —— 开关组件测试（mount + 事件断言，无 DOM 快照）
//
// 该组件是纯受控组件（modelValue 由父级持有），无 loading/size 等 props
// （任务描述里提到的 loading 在实现中不存在，已在报告记录）。
// ============================================================
import { afterEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import BaseSwitch from '../BaseSwitch.vue'

type SwitchProps = InstanceType<typeof BaseSwitch>['$props']

function baseProps(patch: Partial<SwitchProps> = {}): SwitchProps {
  return { modelValue: false, disabled: false, label: '', ...patch } as SwitchProps
}

const mounted: Array<{ unmount: () => void }> = []
function mountSwitch(patch: Partial<SwitchProps> = {}) {
  const wrapper = mount(BaseSwitch, { props: baseProps(patch) })
  mounted.push(wrapper)
  return wrapper
}

afterEach(() => {
  mounted.splice(0).forEach((w) => w.unmount())
})

describe('BaseSwitch：受控展示', () => {
  it('默认关闭：aria-checked=false 且无 is-on', () => {
    const wrapper = mountSwitch()
    const btn = wrapper.find('.switch')

    expect(btn.attributes('aria-checked')).toBe('false')
    expect(btn.classes()).not.toContain('is-on')
  })

  it('modelValue=true：aria-checked=true 且带 is-on', () => {
    const wrapper = mountSwitch({ modelValue: true })
    const btn = wrapper.find('.switch')

    expect(btn.attributes('aria-checked')).toBe('true')
    expect(btn.classes()).toContain('is-on')
  })

  it('是 button + role=switch 的可访问控件', () => {
    const wrapper = mountSwitch()
    const btn = wrapper.find('.switch')

    expect(btn.element.tagName).toBe('BUTTON')
    expect(btn.attributes('type')).toBe('button')
    expect(btn.attributes('role')).toBe('switch')
  })

  it('label 映射为 aria-label；未提供时不渲染该属性', () => {
    expect(mountSwitch({ label: '自动保存' }).find('.switch').attributes('aria-label')).toBe(
      '自动保存',
    )
    expect(mountSwitch().find('.switch').attributes('aria-label')).toBeUndefined()
  })
})

describe('BaseSwitch：交互与事件', () => {
  it('关闭态点击：emit update:modelValue + change 且值取反为 true', async () => {
    const wrapper = mountSwitch({ modelValue: false })

    await wrapper.find('.switch').trigger('click')

    expect(wrapper.emitted('update:modelValue')).toEqual([[true]])
    expect(wrapper.emitted('change')).toEqual([[true]])
  })

  it('开启态点击：emit false（两个事件都带取反值）', async () => {
    const wrapper = mountSwitch({ modelValue: true })

    await wrapper.find('.switch').trigger('click')

    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
    expect(wrapper.emitted('change')).toEqual([[false]])
  })

  it('受控语义：props 不变时点击后自身 aria-checked 不自行翻转', async () => {
    const wrapper = mountSwitch({ modelValue: false })

    await wrapper.find('.switch').trigger('click')

    expect(wrapper.find('.switch').attributes('aria-checked')).toBe('false')
  })

  it('disabled：点击不 emit 任何事件，并带 is-disabled', async () => {
    const wrapper = mountSwitch({ disabled: true })
    const btn = wrapper.find('.switch')

    expect(btn.classes()).toContain('is-disabled')
    await btn.trigger('click')

    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    expect(wrapper.emitted('change')).toBeUndefined()
  })

  it('disabled 且开启：仍如实反映 aria-checked=true', () => {
    const wrapper = mountSwitch({ disabled: true, modelValue: true })

    expect(wrapper.find('.switch').attributes('aria-checked')).toBe('true')
    expect(wrapper.find('.switch').classes()).toContain('is-on')
  })

  it('连续两次点击产生两组事件（父级 v-model 更新后的正常交互）', async () => {
    const wrapper = mountSwitch({ modelValue: false })
    const btn = wrapper.find('.switch')

    await btn.trigger('click')
    await wrapper.setProps({ modelValue: true })
    await btn.trigger('click')

    expect(wrapper.emitted('update:modelValue')).toEqual([[true], [false]])
    expect(wrapper.emitted('change')).toEqual([[true], [false]])
  })
})
