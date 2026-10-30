// ============================================================
// BaseInput —— 输入框组件测试（mount + 属性/事件断言，无 DOM 快照）
//
// 覆盖：v-model 输入、type（text/search/password/number）、size、
// disabled/readonly/maxlength/autofocus、error 文案、前后缀插槽、
// Enter/focus/blur 事件、textarea 分支、attrs 透传。
// ============================================================
import { afterEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import BaseInput from '../BaseInput.vue'

type InputProps = InstanceType<typeof BaseInput>['$props']

function baseProps(patch: Partial<InputProps> = {}): InputProps {
  return {
    modelValue: '',
    type: 'text',
    placeholder: '',
    disabled: false,
    readonly: false,
    size: 'md',
    textarea: false,
    rows: 3,
    ...patch,
  } as InputProps
}

const mounted: Array<{ unmount: () => void }> = []
function mountInput(patch: Partial<InputProps> = {}, slots: Record<string, unknown> = {}) {
  const wrapper = mount(BaseInput, { props: baseProps(patch), slots: slots as never })
  mounted.push(wrapper)
  return wrapper
}

afterEach(() => {
  mounted.splice(0).forEach((w) => w.unmount())
})

describe('BaseInput：基础渲染与 v-model', () => {
  it('默认渲染 text 输入框，带 placeholder、当前值、md 尺寸 class', () => {
    const wrapper = mountInput({ modelValue: 'hello', placeholder: '请输入' })
    const input = wrapper.find('input.input-box__field')

    expect(input.exists()).toBe(true)
    expect(input.attributes('type')).toBe('text')
    expect(input.attributes('placeholder')).toBe('请输入')
    expect((input.element as HTMLInputElement).value).toBe('hello')
    expect(wrapper.find('.input-box').classes()).toContain('input--md')
  })

  it('输入触发 update:modelValue', async () => {
    const wrapper = mountInput({ modelValue: '' })

    await wrapper.find('input.input-box__field').setValue('abc')

    expect(wrapper.emitted('update:modelValue')).toEqual([['abc']])
  })

  it('size=sm/lg 映射到对应 class', () => {
    expect(mountInput({ size: 'sm' }).find('.input-box').classes()).toContain('input--sm')
    expect(mountInput({ size: 'lg' }).find('.input-box').classes()).toContain('input--lg')
  })

  it('type=number 透传为 number 输入', () => {
    expect(mountInput({ type: 'number' }).find('input').attributes('type')).toBe('number')
  })

  it('attrs 透传到原生 input（如 data-testid）', () => {
    const wrapper = mount(BaseInput, {
      props: baseProps(),
      attrs: { 'data-testid': 'field' },
    })
    mounted.push(wrapper)

    expect(wrapper.find('input').attributes('data-testid')).toBe('field')
  })
})

describe('BaseInput：特殊类型与状态', () => {
  it('type=search 渲染搜索图标，input 实际 type 回落 text', () => {
    const wrapper = mountInput({ type: 'search' })

    expect(wrapper.find('.input-box__icon').exists()).toBe(true)
    expect(wrapper.find('input').attributes('type')).toBe('text')
  })

  it('type=password 渲染眼睛按钮，点击切换明文/密文', async () => {
    const wrapper = mountInput({ type: 'password' })
    const input = wrapper.find('input')

    expect(input.attributes('type')).toBe('password')
    expect(wrapper.find('.input-box__pwd').exists()).toBe(true)

    await wrapper.find('.input-box__pwd').trigger('click')
    expect(wrapper.find('input').attributes('type')).toBe('text')

    await wrapper.find('.input-box__pwd').trigger('click')
    expect(wrapper.find('input').attributes('type')).toBe('password')
  })

  it('disabled：input 带 disabled 且容器带 is-disabled', () => {
    const wrapper = mountInput({ disabled: true })

    expect(wrapper.find('input').attributes('disabled')).toBeDefined()
    expect(wrapper.find('.input-box').classes()).toContain('is-disabled')
  })

  it('readonly / maxlength / autofocus 透传', () => {
    const wrapper = mountInput({ readonly: true, maxLength: 10, autofocus: true })
    const input = wrapper.find('input')

    expect(input.attributes('readonly')).toBeDefined()
    expect(input.attributes('maxlength')).toBe('10')
    expect((input.element as HTMLInputElement).hasAttribute('autofocus')).toBe(true)
  })

  it('error：容器 is-error 并显示错误文案；无 error 时不渲染', async () => {
    const wrapper = mountInput({ error: '必填' })

    expect(wrapper.find('.input-box').classes()).toContain('is-error')
    expect(wrapper.find('.input-wrap__error').text()).toBe('必填')

    await wrapper.setProps({ error: undefined })
    expect(wrapper.find('.input-wrap__error').exists()).toBe(false)
  })

  it('prefix / suffix 插槽渲染', () => {
    const wrapper = mountInput(
      {},
      {
        prefix: '<span class="pre">￥</span>',
        suffix: '<span class="suf">元</span>',
      },
    )

    expect(wrapper.find('.pre').text()).toBe('￥')
    expect(wrapper.find('.suf').text()).toBe('元')
  })
})

describe('BaseInput：textarea 分支与事件', () => {
  it('textarea：渲染 textarea、rows 生效且不渲染 input', () => {
    const wrapper = mountInput({ textarea: true, rows: 4, modelValue: '多行' })
    const area = wrapper.find('textarea.input-box__field--area')

    expect(area.exists()).toBe(true)
    expect(area.attributes('rows')).toBe('4')
    expect((area.element as HTMLTextAreaElement).value).toBe('多行')
    expect(wrapper.find('input').exists()).toBe(false)
  })

  it('textarea 同样触发 update:modelValue', async () => {
    const wrapper = mountInput({ textarea: true })

    await wrapper.find('textarea').setValue('内容')

    expect(wrapper.emitted('update:modelValue')).toEqual([['内容']])
  })

  it('Enter 触发 enter 事件', async () => {
    const wrapper = mountInput()

    await wrapper.find('input').trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('enter')).toHaveLength(1)
  })

  it('非 Enter 键不触发 enter', async () => {
    const wrapper = mountInput()

    await wrapper.find('input').trigger('keydown', { key: 'a' })

    expect(wrapper.emitted('enter')).toBeUndefined()
  })

  it('focus / blur 事件透出', async () => {
    const wrapper = mountInput()
    const input = wrapper.find('input')

    await input.trigger('focus')
    await input.trigger('blur')

    expect(wrapper.emitted('focus')).toHaveLength(1)
    expect(wrapper.emitted('blur')).toHaveLength(1)
  })
})
