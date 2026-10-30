// ============================================================
// AdvancedSection —— 设置页「高级设置」交互组件测试
//
// 该组件只做两件事：①4 组本地偏好（动画/字体缩放/性能/自动保存）
// 落 localStorage 并应用到 <html>；②其余能力经 props/emit 交给父级
// useSettingsSync。测试用 mount + 事件断言，不做 DOM 快照。
// ============================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import BaseSwitch from '@/shared/components/common/BaseSwitch.vue'
import type { SyncPackage } from '@/features/sync'
import AdvancedSection from '../AdvancedSection.vue'

type AdvancedProps = InstanceType<typeof AdvancedSection>['$props']

const ADVANCED_KEY = 'venustech_advanced_settings'
const routerPush = vi.fn()

function baseProps(patch: Partial<AdvancedProps> = {}): AdvancedProps {
  return {
    apiBaseDraft: '',
    tokenDraft: '',
    syncExporting: false,
    syncImporting: '',
    syncPackagesOpen: false,
    syncPackages: [],
    ...patch,
  } as AdvancedProps
}

const wrappers: Array<{ unmount: () => void }> = []
function mountSection(patch: Partial<AdvancedProps> = {}) {
  const wrapper = mount(AdvancedSection, {
    props: baseProps(patch),
    global: { mocks: { $router: { push: routerPush } } },
  })
  wrappers.push(wrapper)
  return wrapper
}

function readAdvanced(): Record<string, unknown> {
  return JSON.parse(localStorage.getItem(ADVANCED_KEY) ?? '{}') as Record<string, unknown>
}

function makeSyncPackage(patch: Partial<SyncPackage> = {}): SyncPackage {
  return { name: 'pkg-a', path: '/tmp/pkg-a.json', size: 2048, ...patch } as unknown as SyncPackage
}

function buttonByText(wrapper: ReturnType<typeof mountSection>, text: string) {
  const found = wrapper.findAll('button').find((b) => b.text().includes(text))
  if (!found) throw new Error(`未找到按钮：${text}`)
  return found
}

beforeEach(() => {
  localStorage.clear()
  routerPush.mockClear()
  document.documentElement.style.fontSize = ''
  document.documentElement.removeAttribute('data-no-anim')
})

afterEach(() => {
  wrappers.splice(0).forEach((w) => w.unmount())
  localStorage.clear()
  document.documentElement.style.fontSize = ''
  document.documentElement.removeAttribute('data-no-anim')
})

describe('AdvancedSection：本地偏好默认值与落盘', () => {
  it('默认：动画开 / 字体 100% / 性能关 / 自动保存开', () => {
    const wrapper = mountSection()

    const toggles = wrapper.findAllComponents(BaseSwitch)
    expect(toggles.map((t) => t.props('modelValue'))).toEqual([true, false, true])
    const slider = wrapper.find<HTMLInputElement>('input[type="range"]')
    expect(slider.element.value).toBe('100')
    expect(wrapper.text()).toContain('100%')
  })

  it('关闭动画：写入 localStorage 并给 <html> 加 data-no-anim，再次开启则移除', async () => {
    const wrapper = mountSection()
    const animation = wrapper.findAllComponents(BaseSwitch)[0]

    await animation.find('button').trigger('click')
    expect(readAdvanced().animation).toBe(false)
    expect(document.documentElement.getAttribute('data-no-anim')).toBe('true')

    await animation.find('button').trigger('click')
    expect(readAdvanced().animation).toBe(true)
    expect(document.documentElement.hasAttribute('data-no-anim')).toBe(false)
  })

  it('字体缩放：拖动滑块写 fontScale 并应用为根字号百分比', async () => {
    const wrapper = mountSection()
    const slider = wrapper.find('input[type="range"]')
    ;(slider.element as HTMLInputElement).value = '120'

    await slider.trigger('change')

    expect(readAdvanced().fontScale).toBe(120)
    expect(document.documentElement.style.fontSize).toBe('120%')
    expect(wrapper.text()).toContain('120%')
  })

  it('性能模式与自动保存：分别写 performance / autoSave 到 localStorage', async () => {
    const wrapper = mountSection()
    const toggles = wrapper.findAllComponents(BaseSwitch)

    await toggles[1].find('button').trigger('click')
    expect(readAdvanced().performance).toBe(true)

    await toggles[2].find('button').trigger('click')
    expect(readAdvanced().autoSave).toBe(false)
  })

  it('挂载时从 localStorage 恢复已有偏好', () => {
    localStorage.setItem(
      ADVANCED_KEY,
      JSON.stringify({ animation: false, fontScale: 110, performance: true, autoSave: false }),
    )
    const wrapper = mountSection()

    expect(wrapper.findAllComponents(BaseSwitch).map((t) => t.props('modelValue'))).toEqual([
      false,
      true,
      false,
    ])
    expect((wrapper.find('input[type="range"]').element as HTMLInputElement).value).toBe('110')
    expect(wrapper.text()).toContain('110%')
  })

  it('localStorage 内容损坏时回落到默认值（不让设置页挂掉）', () => {
    localStorage.setItem(ADVANCED_KEY, '{bad json')

    const wrapper = mountSection()

    expect(wrapper.findAllComponents(BaseSwitch).map((t) => t.props('modelValue'))).toEqual([
      true,
      false,
      true,
    ])
  })
})

describe('AdvancedSection：父级持有的同步/网络配置（emit）', () => {
  it('服务器地址输入与保存分别 emit change-api-base-draft / save-api-base', async () => {
    const wrapper = mountSection({ apiBaseDraft: 'http://old:3000' })
    const input = wrapper.find('input[placeholder^="http://100"]')

    await input.setValue('http://new:3000/api/v1')
    expect(wrapper.emitted('change-api-base-draft')).toEqual([['http://new:3000/api/v1']])

    await buttonByText(wrapper, '保存').trigger('click')
    expect(wrapper.emitted('save-api-base')).toHaveLength(1)
  })

  it('访问令牌输入 emit change-token-draft', async () => {
    const wrapper = mountSection()
    const input = wrapper.find('input[placeholder^="电脑首次"]')

    await input.setValue('tok-abc')

    expect(wrapper.emitted('change-token-draft')).toEqual([['tok-abc']])
  })

  it('导出同步包 / 同步包列表按钮 emit 对应事件', async () => {
    const wrapper = mountSection({ syncExporting: false })

    await buttonByText(wrapper, '导出同步包').trigger('click')
    await buttonByText(wrapper, '同步包列表').trigger('click')

    expect(wrapper.emitted('export-sync')).toHaveLength(1)
    expect(wrapper.emitted('toggle-packages')).toHaveLength(1)
  })

  it('同步包列表展开：渲染名称/大小，点击导入 emit import-pkg', async () => {
    const pkg = makeSyncPackage()
    const wrapper = mountSection({ syncPackagesOpen: true, syncPackages: [pkg] })

    expect(wrapper.text()).toContain('pkg-a')
    expect(wrapper.text()).toContain('2 KB')

    await buttonByText(wrapper, '导入').trigger('click')

    expect(wrapper.emitted('import-pkg')).toEqual([[pkg]])
  })

  it('同步包列表为空时给出引导文案', () => {
    const wrapper = mountSection({ syncPackagesOpen: true, syncPackages: [] })

    expect(wrapper.text()).toContain('还没有同步包')
  })

  it('打开保险箱按钮跳转 /vault', async () => {
    const wrapper = mountSection()

    await buttonByText(wrapper, '打开保险箱').trigger('click')

    expect(routerPush).toHaveBeenCalledWith('/vault')
  })
})
