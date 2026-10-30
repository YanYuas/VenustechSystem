// ============================================================
// BaseCard —— 卡片容器测试（mount + class/样式/slot 断言，无 DOM 快照）
//
// 实际 props 以组件实现为准：hoverable / padding / radius / title / scroll
// （任务描述里的 disabled/size 在该组件不存在，已在报告中记录）。
// ============================================================
import { afterEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import BaseCard from '../BaseCard.vue'

type CardProps = InstanceType<typeof BaseCard>['$props']

function baseProps(patch: Partial<CardProps> = {}): CardProps {
  return {
    hoverable: false,
    padding: undefined,
    radius: undefined,
    title: '',
    scroll: false,
    ...patch,
  } as CardProps
}

const mounted: Array<{ unmount: () => void }> = []
function mountCard(patch: Partial<CardProps> = {}, slots: Record<string, unknown> = {}) {
  const wrapper = mount(BaseCard, {
    props: baseProps(patch),
    slots: slots as never,
  })
  mounted.push(wrapper)
  return wrapper
}

afterEach(() => {
  mounted.splice(0).forEach((w) => w.unmount())
})

describe('BaseCard：结构与插槽', () => {
  it('默认渲染默认插槽内容，且无 header', () => {
    const wrapper = mountCard({}, { default: '<p class="body">内容</p>' })

    expect(wrapper.find('.card').exists()).toBe(true)
    expect(wrapper.find('.body').text()).toBe('内容')
    expect(wrapper.find('.card__head').exists()).toBe(false)
  })

  it('title 渲染为 h3 并带 header', () => {
    const wrapper = mountCard({ title: '我的卡片' })

    expect(wrapper.find('.card__head').exists()).toBe(true)
    expect(wrapper.find('.card__title').text()).toBe('我的卡片')
  })

  it('#title 插槽覆盖默认标题（不再渲染 h3）', () => {
    const wrapper = mountCard(
      { title: '默认标题' },
      { title: '<span class="custom-title">自定义</span>' },
    )

    expect(wrapper.find('.custom-title').text()).toBe('自定义')
    expect(wrapper.find('.card__title').exists()).toBe(false)
  })

  it('只有 #extra 插槽也会渲染 header（用于工具栏）', () => {
    const wrapper = mountCard({}, { extra: '<button class="tool">工具</button>' })

    expect(wrapper.find('.card__head').exists()).toBe(true)
    expect(wrapper.find('.tool').exists()).toBe(true)
  })
})

describe('BaseCard：样式开关', () => {
  it('hoverable / scroll 映射到对应 class', () => {
    const wrapper = mountCard({ hoverable: true, scroll: true })

    expect(wrapper.find('.card').classes()).toContain('card--hoverable')
    expect(wrapper.find('.card').classes()).toContain('card--scroll')
  })

  it('scroll 模式把默认插槽包进 card__body（内容区滚动）', () => {
    const wrapper = mountCard({ scroll: true }, { default: '<p class="body">内容</p>' })

    expect(wrapper.find('.card__body .body').exists()).toBe(true)
  })

  it('非 scroll 模式不包 card__body（避免多余滚动容器）', () => {
    const wrapper = mountCard({ scroll: false }, { default: '<p class="body">内容</p>' })

    expect(wrapper.find('.card__body').exists()).toBe(false)
    expect(wrapper.find('.body').exists()).toBe(true)
  })

  it('padding / radius 覆盖映射到内联样式', async () => {
    const wrapper = mountCard({ padding: '8px', radius: '2px' })
    const style = wrapper.find('.card').attributes('style') ?? ''

    expect(style).toContain('padding: 8px')
    expect(style).toContain('border-radius: 2px')

    await wrapper.setProps({ padding: undefined, radius: undefined })
    const cleared = wrapper.find('.card').attributes('style') ?? ''
    expect(cleared).not.toContain('padding: 8px')
  })
})
