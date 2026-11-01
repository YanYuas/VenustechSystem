// ============================================================
// PetSettingsView —— 控件设计系统化回归（Phase21 D-68）
//
// 覆盖：不再出现原生 <select>/<input type=checkbox>；显示设置用 BaseSwitch/BaseSelect；
// 主题化 range（form-range）保留；切到语音页同样无原生控件；保存仍调用 petApi.updateConfig。
// ============================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import type { PetConfig } from '../model'

vi.mock('../api', () => ({
  petApi: {
    getConfig: vi.fn(),
    getState: vi.fn(),
    updateConfig: vi.fn(),
    listAvatars: vi.fn(),
    createAvatar: vi.fn(),
    activateAvatar: vi.fn(),
    deleteAvatar: vi.fn(),
  },
}))

import { petApi } from '../api'
import BaseSelect from '@/shared/components/common/BaseSelect.vue'
import BaseSwitch from '@/shared/components/common/BaseSwitch.vue'
import PetSettingsView from '../views/PetSettingsView.vue'

const api = petApi as unknown as Record<string, ReturnType<typeof vi.fn>>

function config(patch: Partial<PetConfig> = {}): PetConfig {
  return {
    id: 'c1',
    user_id: 'u1',
    enabled: true,
    size: 'medium',
    opacity: 0.9,
    always_on_top: false,
    auto_start: false,
    position_x: 0,
    position_y: 0,
    current_avatar_id: null,
    state_awareness_enabled: true,
    action_switch_interval: 30,
    show_bubble: true,
    bubble_duration: 6,
    click_interaction: true,
    draggable: true,
    right_click_menu: true,
    tts_enabled: false,
    tts_voice: null,
    tts_rate: 1,
    tts_pitch: 1,
    tts_volume: 1,
    speak_scene: 'never',
    updated_at: '2026-11-01T00:00:00',
    ...patch,
  }
}

const mounted: Array<{ unmount: () => void }> = []
async function mountView(patch: Partial<PetConfig> = {}) {
  api.getConfig.mockResolvedValue(config(patch))
  api.getState.mockResolvedValue({
    time_label: '上午',
    action_label: '工作',
    mood_label: '开心',
    todo_count: 0,
    bubble_text: '',
    action: 'idle',
    mood: 'happy',
  })
  api.listAvatars.mockResolvedValue([])
  api.updateConfig.mockImplementation(async (c: PetConfig) => c)
  const wrapper = mount(PetSettingsView)
  mounted.push(wrapper)
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  mounted.splice(0).forEach((w) => w.unmount())
})

describe('PetSettingsView：控件设计系统化', () => {
  it('显示设置不再渲染原生 select / checkbox，改用 BaseSelect / BaseSwitch', async () => {
    const wrapper = await mountView()

    expect(wrapper.findAll('select')).toHaveLength(0)
    expect(wrapper.findAll('input[type="checkbox"]')).toHaveLength(0)
    expect(wrapper.findAllComponents(BaseSelect).length).toBeGreaterThan(0)
    expect(wrapper.findAllComponents(BaseSwitch).length).toBeGreaterThan(0)
  })

  it('透明度/气泡时长仍用 range，但套用主题化 form-range 类', async () => {
    const wrapper = await mountView()

    const ranges = wrapper.findAll('input[type="range"]')
    expect(ranges.length).toBeGreaterThan(0)
    expect(ranges.every((r) => r.classes().includes('form-range'))).toBe(true)
  })

  it('关闭「启用桌宠」开关后保存，仍提交更新后的配置（字段与保存逻辑不变）', async () => {
    const wrapper = await mountView()
    const enabledSwitch = wrapper.findAllComponents(BaseSwitch)[0]

    await enabledSwitch.find('button').trigger('click')
    await wrapper.find('.save-btn').trigger('click')
    await flushPromises()

    expect(api.updateConfig).toHaveBeenCalledTimes(1)
    expect(api.updateConfig.mock.calls[0][0]).toMatchObject({ enabled: false })
  })

  it('旧数据 size=120 / speak_scene=notification 归一化后下拉显示当前值（不显示 placeholder）', async () => {
    // 模拟后端/历史数据的真实脏值（类型上强转，运行时确为字符串/数字）
    const wrapper = await mountView({
      size: '120' as never,
      speak_scene: 'notification' as never,
      tts_enabled: true,
    })

    // 显示设置页：size 归一化为 medium → 显示「中 (120px)」
    const selectValues = wrapper.findAll('.select__value')
    expect(selectValues.map((v) => v.text())).toContain('中 (120px)')
    expect(wrapper.findAll('.select__value.is-placeholder')).toHaveLength(0)

    // 语音页：speak_scene 归一化为 remind → 显示「仅提醒时」
    const voiceTab = wrapper.findAll('.tab-btn').find((b) => b.text().includes('语音TTS'))
    await voiceTab!.trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.select__value').map((v) => v.text())).toContain('仅提醒时')

    // 保存写回的是归一化后的合法值
    await wrapper.find('.save-btn').trigger('click')
    await flushPromises()
    expect(api.updateConfig.mock.calls[0][0]).toMatchObject({
      size: 'medium',
      speak_scene: 'remind',
    })
  })

  it('无法识别的 size 回退 medium，合法值原样保留', async () => {
    const bad = await mountView({ size: 'huge' as never })
    expect(bad.findAll('.select__value').map((v) => v.text())).toContain('中 (120px)')

    const ok = await mountView({ size: 'large' })
    expect(ok.findAll('.select__value').map((v) => v.text())).toContain('大 (160px)')
  })

  it('切到语音页也不再出现原生 select（说话场景为 BaseSelect）', async () => {
    // tts_enabled=true 才会渲染「说话场景」下拉
    const wrapper = await mountView({ tts_enabled: true })
    const voiceTab = wrapper.findAll('.tab-btn').find((b) => b.text().includes('语音TTS'))
    await voiceTab!.trigger('click')
    await flushPromises()

    expect(wrapper.findAll('select')).toHaveLength(0)
    expect(wrapper.findAllComponents(BaseSelect).length).toBeGreaterThan(0)
  })
})
