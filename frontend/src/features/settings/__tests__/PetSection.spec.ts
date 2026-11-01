// ============================================================
// PetSection —— 设置页「桌宠设置」交互测试
//
// 组件内自持 4 项偏好并落 localStorage；覆盖：默认值、两个开关、
// 默认形态切换、透明度滑杆（v-model.number + change 落盘）、
// 挂载恢复、坏 JSON 回落、storage 写入异常不抛出。
// ============================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import BaseSwitch from '@/shared/components/common/BaseSwitch.vue'
import PetSection from '../components/PetSection.vue'

const KEY = 'venustech_pet_settings'

const mounted: Array<{ unmount: () => void }> = []
function mountSection() {
  const wrapper = mount(PetSection)
  mounted.push(wrapper)
  return wrapper
}

function saved(): Record<string, unknown> {
  return JSON.parse(localStorage.getItem(KEY) ?? '{}') as Record<string, unknown>
}

function modeButtons(wrapper: ReturnType<typeof mountSection>) {
  return wrapper.findAll('.settings__mode-btn')
}

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  mounted.splice(0).forEach((w) => w.unmount())
  localStorage.clear()
})

describe('PetSection：默认值', () => {
  it('默认：启用桌宠开 / 桌宠形态高亮 / 互动开 / 透明度 90%', () => {
    const wrapper = mountSection()

    const switches = wrapper.findAllComponents(BaseSwitch)
    expect(switches.map((s) => s.props('modelValue'))).toEqual([true, true])
    expect(modeButtons(wrapper)[0].classes()).toContain('is-active')
    expect(modeButtons(wrapper)[1].classes()).not.toContain('is-active')
    expect(wrapper.text()).toContain('90%')
  })
})

describe('PetSection：开关与形态切换落盘', () => {
  it('关闭「启用桌宠」写入 localStorage enabled=false', async () => {
    const wrapper = mountSection()

    await wrapper.findAllComponents(BaseSwitch)[0].find('button').trigger('click')

    expect(saved()).toMatchObject({ enabled: false })
  })

  it('切换「人形」写入 defaultForm=human 并转移高亮', async () => {
    const wrapper = mountSection()

    await modeButtons(wrapper)[1].trigger('click')

    expect(saved()).toMatchObject({ defaultForm: 'human' })
    expect(modeButtons(wrapper)[1].classes()).toContain('is-active')
    expect(modeButtons(wrapper)[0].classes()).not.toContain('is-active')
  })

  it('关闭「互动反馈」写入 localStorage interaction=false', async () => {
    const wrapper = mountSection()

    await wrapper.findAllComponents(BaseSwitch)[1].find('button').trigger('click')

    expect(saved()).toMatchObject({ interaction: false })
  })
})

describe('PetSection：透明度滑杆', () => {
  it('拖动滑杆实时更新百分比显示，change 时写 opacity', async () => {
    const wrapper = mountSection()
    const slider = wrapper.find('input[type="range"]')
    ;(slider.element as HTMLInputElement).value = '60'

    await slider.trigger('input')
    expect(wrapper.text()).toContain('60%')

    await slider.trigger('change')
    expect(saved()).toMatchObject({ opacity: 60 })
  })
})

describe('PetSection：持久化恢复与异常', () => {
  it('挂载时从 localStorage 恢复已有配置', () => {
    localStorage.setItem(
      KEY,
      JSON.stringify({ enabled: false, defaultForm: 'human', interaction: false, opacity: 50 }),
    )

    const wrapper = mountSection()

    expect(wrapper.findAllComponents(BaseSwitch).map((s) => s.props('modelValue'))).toEqual([
      false,
      false,
    ])
    expect(modeButtons(wrapper)[1].classes()).toContain('is-active')
    expect(wrapper.text()).toContain('50%')
  })

  it('localStorage 内容损坏时回落默认值（不抛出）', () => {
    localStorage.setItem(KEY, '{bad json')

    const wrapper = mountSection()

    expect(wrapper.findAllComponents(BaseSwitch).map((s) => s.props('modelValue'))).toEqual([
      true,
      true,
    ])
    expect(wrapper.text()).toContain('90%')
  })

  it('localStorage 写入异常时静默降级（不抛出）', async () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota exceeded')
    })
    const wrapper = mountSection()

    await expect(
      wrapper.findAllComponents(BaseSwitch)[0].find('button').trigger('click'),
    ).resolves.toBeUndefined()
    expect(wrapper.findAllComponents(BaseSwitch)[0].props('modelValue')).toBe(false)
    spy.mockRestore()
  })
})
