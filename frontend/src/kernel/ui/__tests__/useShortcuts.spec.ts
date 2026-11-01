// ============================================================
// kernel/ui/useShortcuts —— 全局快捷键注册测试
//
// 通过最小宿主组件挂载（依赖 onMounted/onUnmounted），把事件派发到 window 或
// 真实输入元素上；覆盖修饰键匹配、输入框忽略规则、preventDefault、卸载清理。
// ============================================================
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'

import { useShortcuts, type ShortcutHandlers } from '../useShortcuts'

const mounted: Array<{ unmount: () => void }> = []

function setup(handlers: ShortcutHandlers) {
  const wrapper = mount(
    defineComponent({
      setup() {
        useShortcuts(handlers)
        return () => h('div')
      },
    }),
  )
  mounted.push(wrapper)
  return wrapper
}

function press(init: KeyboardEventInit, target: EventTarget = window): KeyboardEvent {
  const event = new KeyboardEvent('keydown', { bubbles: true, cancelable: true, ...init })
  target.dispatchEvent(event)
  return event
}

function makeInput(): HTMLInputElement {
  const input = document.createElement('input')
  document.body.appendChild(input)
  return input
}

afterEach(() => {
  mounted.splice(0).forEach((w) => w.unmount())
  document.body.innerHTML = ''
})

describe('useShortcuts：全局组合键', () => {
  it('Ctrl+K / Meta+K 都触发 global-search 并 preventDefault', () => {
    const handlers = { 'global-search': vi.fn() }
    setup(handlers)

    const ctrlEvent = press({ key: 'k', ctrlKey: true })
    const metaEvent = press({ key: 'K', metaKey: true })

    expect(handlers['global-search']).toHaveBeenCalledTimes(2)
    expect(ctrlEvent.defaultPrevented).toBe(true)
    expect(metaEvent.defaultPrevented).toBe(true)
  })

  it('Ctrl+Shift+P 触发 command-palette（Ctrl+P 不触发）', () => {
    const handlers = { 'command-palette': vi.fn() }
    setup(handlers)

    press({ key: 'p', ctrlKey: true })
    press({ key: 'p', ctrlKey: true, shiftKey: true })

    expect(handlers['command-palette']).toHaveBeenCalledTimes(1)
  })

  it('Ctrl+Shift+N 触发 new-document；Ctrl+N 触发 new-task（互不干扰）', () => {
    const handlers = { 'new-task': vi.fn(), 'new-document': vi.fn() }
    setup(handlers)

    press({ key: 'n', ctrlKey: true })
    press({ key: 'n', ctrlKey: true, shiftKey: true })

    expect(handlers['new-task']).toHaveBeenCalledTimes(1)
    expect(handlers['new-document']).toHaveBeenCalledTimes(1)
  })

  it('Ctrl+1 / Ctrl+2 切换列表/看板视图', () => {
    const handlers = { 'view-list': vi.fn(), 'view-kanban': vi.fn() }
    setup(handlers)

    press({ key: '1', ctrlKey: true })
    press({ key: '2', metaKey: true })

    expect(handlers['view-list']).toHaveBeenCalledTimes(1)
    expect(handlers['view-kanban']).toHaveBeenCalledTimes(1)
  })

  it('Ctrl+] 触发 close-drawer', () => {
    const handlers = { 'close-drawer': vi.fn() }
    setup(handlers)

    press({ key: ']', ctrlKey: true })

    expect(handlers['close-drawer']).toHaveBeenCalledTimes(1)
  })

  it('无修饰键的普通按键不触发任何组合键', () => {
    const handlers = { 'global-search': vi.fn(), save: vi.fn() }
    setup(handlers)

    press({ key: 'k' })
    press({ key: 's' })

    expect(handlers['global-search']).not.toHaveBeenCalled()
    expect(handlers.save).not.toHaveBeenCalled()
  })
})

describe('useShortcuts：输入框忽略规则', () => {
  it('Ctrl+N / Ctrl+F 在 input 内不触发；Ctrl+S 在 input 内仍触发', () => {
    const handlers = { 'new-task': vi.fn(), 'module-search': vi.fn(), save: vi.fn() }
    setup(handlers)
    const input = makeInput()

    press({ key: 'n', ctrlKey: true }, input)
    press({ key: 'f', ctrlKey: true }, input)
    press({ key: 's', ctrlKey: true }, input)

    expect(handlers['new-task']).not.toHaveBeenCalled()
    expect(handlers['module-search']).not.toHaveBeenCalled()
    expect(handlers.save).toHaveBeenCalledTimes(1)
  })

  it('textarea 与 contentEditable 也被视为输入中', () => {
    const handlers = { 'new-task': vi.fn(), delete: vi.fn() }
    setup(handlers)
    const area = document.createElement('textarea')
    document.body.appendChild(area)
    const editable = document.createElement('div')
    editable.setAttribute('contenteditable', 'true')
    // jsdom 不实现 isContentEditable，这里显式模拟，仅用于覆盖判定分支
    Object.defineProperty(editable, 'isContentEditable', { configurable: true, value: true })
    document.body.appendChild(editable)

    press({ key: 'n', ctrlKey: true }, area)
    press({ key: 'Delete' }, editable)

    expect(handlers['new-task']).not.toHaveBeenCalled()
    expect(handlers.delete).not.toHaveBeenCalled()
  })

  it('Escape 全局生效（即使焦点在输入框）', () => {
    const handlers = { escape: vi.fn() }
    setup(handlers)
    const input = makeInput()

    press({ key: 'Escape' }, input)

    expect(handlers.escape).toHaveBeenCalledTimes(1)
  })

  it('Delete 在非输入区域触发，在 input 内不触发', () => {
    const handlers = { delete: vi.fn() }
    setup(handlers)
    const input = makeInput()

    press({ key: 'Delete' })
    press({ key: 'Delete' }, input)

    expect(handlers.delete).toHaveBeenCalledTimes(1)
  })
})

describe('useShortcuts：生命周期', () => {
  it('卸载后移除全局监听，按键不再触发', () => {
    const handlers = { 'global-search': vi.fn() }
    const wrapper = setup(handlers)

    wrapper.unmount()
    mounted.splice(0)
    press({ key: 'k', ctrlKey: true })

    expect(handlers['global-search']).not.toHaveBeenCalled()
  })

  it('未注册对应 handler 时按键不抛错', () => {
    setup({})

    expect(() => press({ key: 'k', ctrlKey: true })).not.toThrow()
    expect(() => press({ key: 'Escape' })).not.toThrow()
  })
})
