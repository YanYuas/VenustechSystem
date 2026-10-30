// ============================================================
// BaseModal —— 模态框交互测试（mount + 事件断言，无 DOM 快照）
//
// 覆盖：显隐渲染、标题/关闭按钮、宽度/danger、footer 显隐与自定义文案、
// confirm/cancel/dismiss 事件语义、遮罩点击（可配置）、Esc、
// body 滚动锁定与卸载兜底、关闭后 delayed closed、打开自动聚焦、
// footer 作用域插槽的 confirm/cancel。
// Teleport 用 stub 拉到 wrapper 内断言；焦点测试 attachTo body。
// ============================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { h, nextTick } from 'vue'
import { mount } from '@vue/test-utils'

import BaseModal from '../BaseModal.vue'

type ModalProps = InstanceType<typeof BaseModal>['$props']

function baseProps(patch: Partial<ModalProps> = {}): ModalProps {
  return {
    modelValue: false,
    title: '',
    width: 480,
    closable: true,
    maskClosable: true,
    confirmText: '确定',
    cancelText: '取消',
    danger: false,
    showFooter: true,
    ...patch,
  } as ModalProps
}

const mounted: Array<{ unmount: () => void }> = []
function mountModal(patch: Partial<ModalProps> = {}, slots: Record<string, unknown> = {}) {
  const wrapper = mount(BaseModal, {
    props: baseProps(patch),
    slots: slots as never,
    global: { stubs: { teleport: true } },
    attachTo: document.body,
  })
  mounted.push(wrapper)
  return wrapper
}

async function open(wrapper: ReturnType<typeof mountModal>) {
  await wrapper.setProps({ modelValue: true })
  await nextTick()
  await Promise.resolve()
}

function pressEsc() {
  window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
}

beforeEach(() => {
  document.body.style.overflow = ''
})

afterEach(() => {
  mounted.splice(0).forEach((w) => w.unmount())
  document.body.style.overflow = ''
  vi.useRealTimers()
})

describe('BaseModal：显隐与基础渲染', () => {
  it('modelValue=false 时不渲染任何内容', () => {
    const wrapper = mountModal({}, { default: '<p class="body">内容</p>' })

    expect(wrapper.find('.qm-modal').exists()).toBe(false)
    expect(wrapper.find('.body').exists()).toBe(false)
  })

  it('打开后渲染标题、body slot、dialog 语义与默认按钮', async () => {
    const wrapper = mountModal({ title: '确认操作' }, { default: '<p class="body">内容</p>' })
    await open(wrapper)

    expect(wrapper.find('.qm-modal__title').text()).toBe('确认操作')
    expect(wrapper.find('.body').text()).toBe('内容')
    expect(wrapper.find('[role="dialog"]').attributes('aria-modal')).toBe('true')
    expect(wrapper.find('.qm-modal__btn.is-confirm').text()).toBe('确定')
    expect(wrapper.find('.qm-modal__btn.is-cancel').text()).toBe('取消')
  })

  it('无标题但 closable 时仍渲染头部（只有关闭按钮）；closable=false 时无头部', async () => {
    const withClose = mountModal({ closable: true })
    await open(withClose)
    expect(withClose.find('.qm-modal__head').exists()).toBe(true)
    expect(withClose.find('.qm-modal__close').exists()).toBe(true)

    const noClose = mountModal({ closable: false })
    await open(noClose)
    expect(noClose.find('.qm-modal__head').exists()).toBe(false)
  })

  it('width 映射到面板内联样式；danger 作用于容器与确认按钮', async () => {
    const wrapper = mountModal({ width: 640, danger: true, title: '危险' })
    await open(wrapper)

    expect(wrapper.find('.qm-modal__panel').attributes('style')).toContain('width: 640px')
    expect(wrapper.find('.qm-modal').classes()).toContain('qm-modal--danger')
    expect(wrapper.find('.qm-modal__btn.is-confirm').classes()).toContain('is-danger')
  })

  it('showFooter=false 时不渲染底部按钮；自定义文案生效', async () => {
    const noFooter = mountModal({ showFooter: false })
    await open(noFooter)
    expect(noFooter.find('.qm-modal__foot').exists()).toBe(false)

    const custom = mountModal({ confirmText: '删除', cancelText: '再想想' })
    await open(custom)
    expect(custom.find('.qm-modal__btn.is-confirm').text()).toBe('删除')
    expect(custom.find('.qm-modal__btn.is-cancel').text()).toBe('再想想')
  })
})

describe('BaseModal：confirm / cancel / dismiss 语义', () => {
  it('确认按钮只 emit confirm，不自动关闭（由业务决定）', async () => {
    const wrapper = mountModal({ title: 't' })
    await open(wrapper)

    await wrapper.find('.qm-modal__btn.is-confirm').trigger('click')

    expect(wrapper.emitted('confirm')).toHaveLength(1)
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    expect(wrapper.find('.qm-modal').exists()).toBe(true)
  })

  it('取消按钮 emit cancel + dismiss + update:modelValue=false', async () => {
    const wrapper = mountModal({ title: 't' })
    await open(wrapper)

    await wrapper.find('.qm-modal__btn.is-cancel').trigger('click')

    expect(wrapper.emitted('cancel')).toHaveLength(1)
    expect(wrapper.emitted('dismiss')).toHaveLength(1)
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
  })

  it('右上角关闭按钮：emit dismiss + 关闭，但不 emit cancel', async () => {
    const wrapper = mountModal({ title: 't' })
    await open(wrapper)

    await wrapper.find('.qm-modal__close').trigger('click')

    expect(wrapper.emitted('dismiss')).toHaveLength(1)
    expect(wrapper.emitted('cancel')).toBeUndefined()
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
  })

  it('遮罩点击（maskClosable=true）关闭；面板内部点击不关闭', async () => {
    const wrapper = mountModal({ title: 't' })
    await open(wrapper)

    await wrapper.find('.qm-modal__panel').trigger('click')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()

    await wrapper.find('.qm-modal').trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
    expect(wrapper.emitted('dismiss')).toHaveLength(1)
  })

  it('maskClosable=false 时点击遮罩不关闭', async () => {
    const wrapper = mountModal({ title: 't', maskClosable: false })
    await open(wrapper)

    await wrapper.find('.qm-modal').trigger('click')

    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })
})

describe('BaseModal：Esc 与滚动锁定', () => {
  it('Esc 打开且 closable 时关闭；closable=false 时不关闭', async () => {
    const closable = mountModal({ title: 't', closable: true })
    await open(closable)
    pressEsc()
    await nextTick()
    expect(closable.emitted('update:modelValue')).toEqual([[false]])

    const locked = mountModal({ title: 't', closable: false })
    await open(locked)
    pressEsc()
    await nextTick()
    expect(locked.emitted('update:modelValue')).toBeUndefined()
  })

  it('关闭状态下按 Esc 不产生任何事件', async () => {
    const wrapper = mountModal({ title: 't', modelValue: false })

    pressEsc()
    await nextTick()

    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    expect(wrapper.emitted('dismiss')).toBeUndefined()
  })

  it('打开锁定 body 滚动，关闭后恢复；卸载时仍打开也兜底恢复', async () => {
    const wrapper = mountModal({ title: 't' })
    await open(wrapper)
    expect(document.body.style.overflow).toBe('hidden')

    await wrapper.setProps({ modelValue: false })
    expect(document.body.style.overflow).toBe('')

    const reopen = mountModal({ title: 't' })
    await open(reopen)
    expect(document.body.style.overflow).toBe('hidden')
    reopen.unmount()
    expect(document.body.style.overflow).toBe('')
  })

  it('关闭后延迟 150ms 才 emit closed', async () => {
    vi.useFakeTimers()
    const wrapper = mountModal({ title: 't' })
    await wrapper.setProps({ modelValue: true })
    await nextTick()

    await wrapper.setProps({ modelValue: false })
    expect(wrapper.emitted('closed')).toBeUndefined()

    await vi.advanceTimersByTimeAsync(150)
    expect(wrapper.emitted('closed')).toHaveLength(1)
  })

  it('打开时聚焦面板内第一个可聚焦元素', async () => {
    // 关闭头部（无标题且 closable=false），确保 body 里的 input 是面板内第一个可聚焦元素
    const wrapper = mountModal(
      { title: '', closable: false },
      { default: '<input class="first-field" />' },
    )
    await open(wrapper)
    await nextTick()
    await Promise.resolve()

    expect(document.activeElement).toBe(wrapper.find('input.first-field').element)
  })
})

describe('BaseModal：footer 作用域插槽', () => {
  it('自定义 footer 可拿到 confirm/cancel 并触发对应事件', async () => {
    const slots = {
      footer: (scope: { confirm: () => void; cancel: () => void }) =>
        h('div', [
          h('button', { class: 'slot-confirm', onClick: scope.confirm }, 'OK'),
          h('button', { class: 'slot-cancel', onClick: scope.cancel }, 'NO'),
        ]),
    }
    const wrapper = mountModal({ title: 't' }, slots)
    await open(wrapper)

    await wrapper.find('.slot-confirm').trigger('click')
    expect(wrapper.emitted('confirm')).toHaveLength(1)

    await wrapper.find('.slot-cancel').trigger('click')
    expect(wrapper.emitted('cancel')).toHaveLength(1)
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
  })
})
