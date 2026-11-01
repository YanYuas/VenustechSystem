// ============================================================
// ModalItem —— 命令式弹窗实例测试
//
// 覆盖：request 透传（title/width/danger/按钮文案）、字符串/组件 content、
// requireInput 文字匹配门槛、confirm/cancel 事件转发（含 BaseModal 的
// cancel/dismiss 两条关闭路径）。
// ============================================================
import { afterEach, describe, expect, it } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'

import type { ModalRequest } from '@/kernel/ui/modal'
import BaseModal from '../BaseModal.vue'
import ModalItem from '../ModalItem.vue'

function makeRequest(patch: Partial<ModalRequest> = {}): ModalRequest {
  return {
    id: 1,
    title: '删除文档',
    content: '此操作不可撤销',
    ...patch,
  } as ModalRequest
}

const mounted: Array<{ unmount: () => void }> = []
function mountItem(patch: Partial<ModalRequest> = {}) {
  const wrapper = mount(ModalItem, {
    props: { request: makeRequest(patch) },
    global: { stubs: { teleport: true } },
    attachTo: document.body,
  })
  mounted.push(wrapper)
  return wrapper
}

afterEach(() => {
  mounted.splice(0).forEach((w) => w.unmount())
})

describe('ModalItem：request 透传', () => {
  it('渲染标题、字符串 content 与默认按钮文案', () => {
    const wrapper = mountItem()

    expect(wrapper.find('.qm-modal__title').text()).toBe('删除文档')
    expect(wrapper.text()).toContain('此操作不可撤销')
    expect(wrapper.find('.modal-item__btn.is-cancel').text()).toBe('取消')
    expect(wrapper.find('.modal-item__btn.is-danger').text()).toBe('确认删除')
  })

  it('自定义按钮文案 / width / danger 透传到 BaseModal', () => {
    const wrapper = mountItem({
      confirmText: '删除',
      cancelText: '再想想',
      width: 520,
      danger: true,
    })

    expect(wrapper.find('.modal-item__btn.is-danger').text()).toBe('删除')
    expect(wrapper.find('.modal-item__btn.is-cancel').text()).toBe('再想想')
    expect(wrapper.find('.qm-modal__panel').attributes('style')).toContain('width: 520px')
    expect(wrapper.find('.qm-modal').classes()).toContain('qm-modal--danger')
  })

  it('content 为组件时渲染该组件', () => {
    const Content = defineComponent({
      render: () => h('span', { class: 'custom-content' }, '组件内容'),
    })
    const wrapper = mountItem({ content: Content })

    expect(wrapper.find('.custom-content').text()).toBe('组件内容')
  })
})

describe('ModalItem：requireInput 门槛', () => {
  it('未匹配时确认按钮 disabled；输入完全匹配后才可点击', async () => {
    const wrapper = mountItem({ requireInput: '删除文档' })
    const confirmBtn = wrapper.find('.modal-item__btn.is-danger')

    expect(confirmBtn.attributes('disabled')).toBeDefined()
    expect(wrapper.find('.modal-item__hint').text()).toContain('删除文档')

    await wrapper.find('.modal-item__field').setValue('删除')
    expect(wrapper.find('.modal-item__btn.is-danger').attributes('disabled')).toBeDefined()

    await wrapper.find('.modal-item__field').setValue('删除文档')
    expect(wrapper.find('.modal-item__btn.is-danger').attributes('disabled')).toBeUndefined()
  })
})

describe('ModalItem：事件转发', () => {
  it('点击确认按钮 emit confirm', async () => {
    const wrapper = mountItem()

    await wrapper.find('.modal-item__btn.is-danger').trigger('click')

    expect(wrapper.emitted('confirm')).toHaveLength(1)
  })

  it('底部取消按钮 emit cancel', async () => {
    const wrapper = mountItem()

    await wrapper.find('.modal-item__btn.is-cancel').trigger('click')

    expect(wrapper.emitted('cancel')).toHaveLength(1)
  })

  it('BaseModal 的 dismiss（右上角关闭）转发为 cancel', async () => {
    const wrapper = mountItem()

    await wrapper.find('.qm-modal__close').trigger('click')

    expect(wrapper.emitted('cancel')).toHaveLength(1)
  })

  it('BaseModal 的 cancel（Esc）转发为 cancel', async () => {
    const wrapper = mountItem()

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('cancel')).toHaveLength(1)
  })

  it('同一实例可重复关闭：dismiss 后 Esc 仍能 emit cancel（D-63）', async () => {
    const wrapper = mountItem()

    await wrapper.find('.qm-modal__close').trigger('click')
    expect(wrapper.emitted('cancel')).toHaveLength(1)

    // 等 BaseModal 在 nextTick 重置内部 isClosing
    await wrapper.vm.$nextTick()

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('cancel')).toHaveLength(2)
  })

  it('BaseModal 的 confirm 事件（footer 默认按钮）也走 onConfirm 并 emit confirm', async () => {
    const wrapper = mountItem()

    // BaseModal 默认 footer 已被 ModalItem 的 #footer 覆盖，此处验证直接触发子组件事件
    wrapper.findComponent(BaseModal).vm.$emit('confirm')
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('confirm')).toHaveLength(1)
  })
})
