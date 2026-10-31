// ============================================================
// DesktopPet —— 桌宠组件行为测试
//
// 覆盖：默认位置/层级、idle 状态与自动气泡、点击随机动作、拖拽（rAF 合帧）与
// 拖后吞 click、双击/右键菜单切换形态、喂食/玩耍/休息的状态守卫与增量提交、
// updateStats 失败降级、getStats 失败保留默认值、心情标签/属性条、
// 业务事件（celebrate）驱动、卸载清理。mock petApi；fake timers 在 afterEach 清理。
// ============================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import { petApi } from '../api'
import { PET_ACTION_EVENT } from '../composables/usePetEvent'
import type { PetStats, PetVitals } from '../model'
import DesktopPet from '../components/DesktopPet.vue'

vi.mock('../api', () => ({
  petApi: { getStats: vi.fn(), updateStats: vi.fn() },
}))

const api = petApi as unknown as {
  getStats: ReturnType<typeof vi.fn>
  updateStats: ReturnType<typeof vi.fn>
}

function vitals(patch: Partial<PetVitals> = {}): PetVitals {
  return { intimacy: 60, satiety: 60, mood: 60, energy: 60, ...patch }
}

function stats(patch: Partial<PetVitals> = {}): PetStats {
  return { ...vitals(patch), id: 'p1', user_id: 'u1' } as unknown as PetStats
}

const mounted: Array<{ unmount: () => void }> = []
function mountPet(props: Record<string, unknown> = {}) {
  const wrapper = mount(DesktopPet, {
    props: { position: { x: 10, y: 20 }, ...props },
    global: { stubs: { teleport: true } },
    attachTo: document.body,
  })
  mounted.push(wrapper)
  return wrapper
}

async function flush(wrapper: ReturnType<typeof mountPet>) {
  await Promise.resolve()
  await Promise.resolve()
  await Promise.resolve()
  await wrapper.vm.$nextTick()
}

function menuItem(wrapper: ReturnType<typeof mountPet>, label: string) {
  const found = wrapper.findAll('.pet__menu-item').find((b) => b.text().includes(label))
  if (!found) throw new Error(`未找到菜单项：${label}`)
  return found
}

function openMenu(wrapper: ReturnType<typeof mountPet>) {
  return wrapper.find('.pet').trigger('contextmenu', { clientX: 5, clientY: 5 })
}

beforeEach(() => {
  vi.useFakeTimers()
  localStorage.clear()
  api.getStats.mockResolvedValue(stats())
  api.updateStats.mockImplementation(async (delta: Partial<PetVitals>) =>
    stats({ ...vitals(), ...delta }),
  )
})

afterEach(() => {
  mounted.splice(0).forEach((w) => w.unmount())
  vi.useRealTimers()
  vi.unstubAllGlobals()
  localStorage.clear()
  document.body.style.overflow = ''
})

describe('DesktopPet：初始渲染与自动气泡', () => {
  it('按 position 定位、默认 z-index=100，topmost 时为 9999', async () => {
    const normal = mountPet()
    await flush(normal)
    expect(normal.find('.pet').attributes('style')).toContain('translate3d(10px, 20px, 0)')
    expect(normal.find('.pet').attributes('style')).toContain('z-index: 100')

    const top = mountPet({ topmost: true })
    await flush(top)
    expect(top.find('.pet').attributes('style')).toContain('z-index: 9999')
  })

  it('初始为 idle 状态且不显示气泡', async () => {
    const wrapper = mountPet()
    await flush(wrapper)

    expect(wrapper.find('.pet').classes()).toContain('pet--idle')
    expect(wrapper.find('.pet__bubble').exists()).toBe(false)
  })

  it('挂载 1s 后自动冒泡，3s 后自动消失', async () => {
    vi.spyOn(Math, 'random').mockReturnValue(0)
    const wrapper = mountPet()
    await flush(wrapper)

    await vi.advanceTimersByTimeAsync(1000)
    expect(wrapper.find('.pet__bubble').text()).toBe('今天也要加油哦~')

    await vi.advanceTimersByTimeAsync(3000)
    expect(wrapper.find('.pet__bubble').exists()).toBe(false)
  })

  it('点击：随机 happy/thinking/celebrate 动作 + 气泡 + emit click，2s 后回 idle', async () => {
    vi.spyOn(Math, 'random').mockReturnValue(0)
    const wrapper = mountPet()
    await flush(wrapper)

    await wrapper.find('.pet').trigger('click')

    expect(wrapper.find('.pet').classes()).toContain('pet--happy')
    expect(wrapper.find('.pet__bubble').text()).toBe('太棒了！')
    expect(wrapper.emitted('click')).toHaveLength(1)

    await vi.advanceTimersByTimeAsync(2000)
    expect(wrapper.find('.pet').classes()).toContain('pet--idle')
  })
})

describe('DesktopPet：拖拽与形态', () => {
  it('拖拽跟随 mousemove（rAF 合帧）并在 mouseup emit move', async () => {
    const wrapper = mountPet()
    await flush(wrapper)

    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      cb(0)
      return 1
    })
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    await wrapper.find('.pet').trigger('mousedown', { clientX: 60, clientY: 70 })
    document.dispatchEvent(new MouseEvent('mousemove', { clientX: 110, clientY: 170 }))
    await wrapper.vm.$nextTick()

    // offset = (50,50) → 新位置 = (110-50, 170-50)
    expect(wrapper.find('.pet').attributes('style')).toContain('translate3d(60px, 120px, 0)')

    document.dispatchEvent(new MouseEvent('mouseup'))
    expect(wrapper.emitted('move')).toEqual([[{ x: 60, y: 120 }]])
  })

  it('拖拽发生位移后紧跟的 click 被吞掉（不随机播动作、不 emit click）', async () => {
    vi.spyOn(Math, 'random').mockReturnValue(0)
    const wrapper = mountPet()
    await flush(wrapper)

    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      cb(0)
      return 1
    })
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    await wrapper.find('.pet').trigger('mousedown', { clientX: 60, clientY: 70 })
    document.dispatchEvent(new MouseEvent('mousemove', { clientX: 200, clientY: 200 }))
    await wrapper.vm.$nextTick()
    document.dispatchEvent(new MouseEvent('mouseup'))

    await wrapper.find('.pet').trigger('click')

    expect(wrapper.emitted('click')).toBeUndefined()
    expect(wrapper.find('.pet').classes()).toContain('pet--idle')
  })

  it('双击切换形态：300ms 后切到人形、写 localStorage 并 wave 打招呼', async () => {
    vi.spyOn(Math, 'random').mockReturnValue(0)
    const wrapper = mountPet()
    await flush(wrapper)
    expect(wrapper.find('.pet__svg--human').exists()).toBe(false)

    await wrapper.find('.pet').trigger('dblclick')
    await vi.advanceTimersByTimeAsync(300)

    expect(wrapper.find('.pet__svg--human').exists()).toBe(true)
    expect(localStorage.getItem('venustech_pet_form')).toBe('human')
    expect(wrapper.find('.pet__bubble').text()).toBe('你好呀~')
  })

  it('挂载时从 localStorage 恢复人形形态', async () => {
    localStorage.setItem('venustech_pet_form', 'human')
    const wrapper = mountPet()
    await flush(wrapper)

    expect(wrapper.find('.pet__svg--human').exists()).toBe(true)
  })
})

describe('DesktopPet：右键菜单与互动', () => {
  it('右键打开菜单：形态标题 + 8 个动作 + 喂食/玩耍/休息', async () => {
    const wrapper = mountPet()
    await flush(wrapper)

    await openMenu(wrapper)

    expect(wrapper.find('.pet__menu').exists()).toBe(true)
    expect(wrapper.find('.pet__menu-header').text()).toContain('桌宠模式')
    expect(wrapper.findAll('.pet__menu-item')).toHaveLength(8 + 3)
    expect(wrapper.find('.pet__menu').text()).toContain('喂食')
    expect(wrapper.find('.pet__menu').text()).toContain('60%')
  })

  it('点击菜单动作：播放对应动作并关闭菜单', async () => {
    vi.spyOn(Math, 'random').mockReturnValue(0)
    const wrapper = mountPet()
    await flush(wrapper)
    await openMenu(wrapper)

    await menuItem(wrapper, '跳舞').trigger('click')

    expect(wrapper.find('.pet__menu').exists()).toBe(false)
    expect(wrapper.find('.pet__bubble').text()).toBe('一起跳舞吧~')
  })

  it('菜单里「切换形态」按钮 300ms 后切换', async () => {
    const wrapper = mountPet()
    await flush(wrapper)
    await openMenu(wrapper)

    await wrapper.find('.pet__menu-switch').trigger('click')
    await vi.advanceTimersByTimeAsync(300)

    expect(wrapper.find('.pet__svg--human').exists()).toBe(true)
  })

  it('点击遮罩关闭菜单', async () => {
    const wrapper = mountPet()
    await flush(wrapper)
    await openMenu(wrapper)

    await wrapper.find('.pet__menu-overlay').trigger('click')

    expect(wrapper.find('.pet__menu').exists()).toBe(false)
  })

  it('喂食：正常时播放 happy + 提示语并提交 satiety/mood 增量', async () => {
    const wrapper = mountPet()
    await flush(wrapper)
    await openMenu(wrapper)

    await menuItem(wrapper, '喂食').trigger('click')
    await flush(wrapper)

    expect(wrapper.find('.pet__bubble').text()).toBe('好好吃~ 谢谢你！')
    expect(api.updateStats).toHaveBeenCalledWith({ satiety: 25, mood: 5 })
  })

  it('喂食：饱食度 >=95 时拒绝并保留本地提示，不调用接口', async () => {
    api.getStats.mockResolvedValue(stats({ satiety: 99 }))
    const wrapper = mountPet()
    await flush(wrapper)
    await openMenu(wrapper)

    await menuItem(wrapper, '喂食').trigger('click')
    await flush(wrapper)

    expect(wrapper.find('.pet__bubble').text()).toBe('人家吃饱啦~')
    expect(api.updateStats).not.toHaveBeenCalled()
  })

  it('玩耍：精力 <20 时转为睡觉并显示自定义关怀提示，不提交增量（D-53）', async () => {
    vi.spyOn(Math, 'random').mockReturnValue(0)
    api.getStats.mockResolvedValue(stats({ energy: 10 }))
    const wrapper = mountPet()
    await flush(wrapper)
    await openMenu(wrapper)

    await menuItem(wrapper, '玩耍').trigger('click')
    await flush(wrapper)

    // 先 setAction('sleep') 再写自定义提示 → 文案不再被随机气泡覆盖
    expect(wrapper.find('.pet__bubble').text()).toBe('好累哦...想休息一下...')
    expect(wrapper.find('.pet').classes()).toContain('pet--sleep')
    expect(api.updateStats).not.toHaveBeenCalled()

    // 2s 后气泡自动收起
    await vi.advanceTimersByTimeAsync(2000)
    expect(wrapper.find('.pet__bubble').exists()).toBe(false)
  })

  it('玩耍：精力充足时 dance 并提交 mood/energy/intimacy 增量', async () => {
    vi.spyOn(Math, 'random').mockReturnValue(0)
    const wrapper = mountPet()
    await flush(wrapper)
    await openMenu(wrapper)

    await menuItem(wrapper, '玩耍').trigger('click')
    await flush(wrapper)

    // petClass 未映射 dance（只覆盖 idle/happy/thinking/working/celebrate/sleep），
    // 因此这里断言"不是 sleep"这个真实分支语义 + 气泡/增量
    expect(wrapper.find('.pet').classes()).not.toContain('pet--sleep')
    expect(wrapper.find('.pet__bubble').text()).toBe('一起跳舞吧~')
    expect(api.updateStats).toHaveBeenCalledWith({ mood: 10, energy: -10, intimacy: 3 })
  })

  it('休息：sleep 动作 + 提示语 + energy/mood 增量', async () => {
    const wrapper = mountPet()
    await flush(wrapper)
    await openMenu(wrapper)

    await menuItem(wrapper, '休息').trigger('click')
    await flush(wrapper)

    expect(wrapper.find('.pet').classes()).toContain('pet--sleep')
    expect(wrapper.find('.pet__bubble').text()).toBe('Zzz... 休息一下~')
    expect(api.updateStats).toHaveBeenCalledWith({ energy: 30, mood: 5 })
  })

  it('喂食气泡按时出现，并在 2.5s 后自动收起（D-55 保持可见行为）', async () => {
    const wrapper = mountPet()
    await flush(wrapper)
    await vi.advanceTimersByTimeAsync(1000) // 先消化首条问候，避免其覆盖本用例气泡
    await openMenu(wrapper)

    await menuItem(wrapper, '喂食').trigger('click')
    await flush(wrapper)

    expect(wrapper.find('.pet__bubble').text()).toBe('好好吃~ 谢谢你！')
    await vi.advanceTimersByTimeAsync(2499)
    expect(wrapper.find('.pet__bubble').exists()).toBe(true)

    await vi.advanceTimersByTimeAsync(1)
    expect(wrapper.find('.pet__bubble').exists()).toBe(false)
  })

  it('玩耍气泡按时出现，并在 3s 后自动收起（D-55 保持可见行为）', async () => {
    vi.spyOn(Math, 'random').mockReturnValue(0)
    const wrapper = mountPet()
    await flush(wrapper)
    await vi.advanceTimersByTimeAsync(1000)
    await openMenu(wrapper)

    await menuItem(wrapper, '玩耍').trigger('click')
    await flush(wrapper)

    expect(wrapper.find('.pet__bubble').text()).toBe('一起跳舞吧~')
    await vi.advanceTimersByTimeAsync(2999)
    expect(wrapper.find('.pet__bubble').exists()).toBe(true)

    await vi.advanceTimersByTimeAsync(1)
    expect(wrapper.find('.pet__bubble').exists()).toBe(false)
  })

  it('双击抚摸（exposed pet）：happy + 亲密度/心情增量', async () => {
    const wrapper = mountPet()
    await flush(wrapper)

    ;(wrapper.vm as unknown as { pet: () => void }).pet()
    await flush(wrapper)

    expect(wrapper.find('.pet').classes()).toContain('pet--happy')
    expect(api.updateStats).toHaveBeenCalledWith({ intimacy: 2, mood: 3 })
  })
})

describe('DesktopPet：降级与状态展示', () => {
  it('updateStats 失败：互动仍有本地反馈，不抛出', async () => {
    api.updateStats.mockRejectedValue(new Error('stats down'))
    const wrapper = mountPet()
    await flush(wrapper)
    await openMenu(wrapper)

    await expect(menuItem(wrapper, '喂食').trigger('click')).resolves.toBeUndefined()
    await flush(wrapper)

    expect(wrapper.find('.pet__bubble').text()).toBe('好好吃~ 谢谢你！')
  })

  it('getStats 失败：保持默认数值继续可用（菜单显示 60%）', async () => {
    api.getStats.mockRejectedValue(new Error('stats down'))
    const wrapper = mountPet()
    await flush(wrapper)
    await openMenu(wrapper)

    expect(wrapper.find('.pet__menu').text()).toContain('60%')
  })

  it('心情标签按数值分档，亲密度属性条宽度跟随数值', async () => {
    api.getStats.mockResolvedValue(stats({ mood: 90, intimacy: 75 }))
    const wrapper = mountPet()
    await flush(wrapper)
    await openMenu(wrapper)

    expect(wrapper.find('.pet__menu').text()).toContain('超开心')
    const fills = wrapper.findAll('.pet__stat-fill')
    expect(fills[0].attributes('style')).toContain('75%')
  })

  it('业务事件 PET_ACTION_EVENT 驱动 celebrate（彩带 8 片），duration 后回 idle', async () => {
    const wrapper = mountPet()
    await flush(wrapper)

    window.dispatchEvent(
      new CustomEvent(PET_ACTION_EVENT, { detail: { action: 'celebrate', duration: 500 } }),
    )
    await flush(wrapper)

    expect(wrapper.find('.pet').classes()).toContain('pet--celebrate')
    expect(wrapper.findAll('.pet__confetti-piece')).toHaveLength(8)

    await vi.advanceTimersByTimeAsync(500)
    expect(wrapper.find('.pet').classes()).toContain('pet--idle')
  })

  it('事件缺 action 时忽略，不改变当前动作', async () => {
    const wrapper = mountPet()
    await flush(wrapper)

    window.dispatchEvent(new CustomEvent(PET_ACTION_EVENT, { detail: {} }))
    await flush(wrapper)

    expect(wrapper.find('.pet').classes()).toContain('pet--idle')
    expect(wrapper.find('.pet__bubble').exists()).toBe(false)
  })

  it('挂载后立即卸载：初始 1s 问候定时器被清理，推进 10s 无气泡且无残留定时器（D-52）', async () => {
    const wrapper = mountPet()
    await flush(wrapper)

    wrapper.unmount()
    mounted.splice(0)

    // 关键断言：卸载瞬间所有定时器都应被清掉（含 1s 首条问候）
    expect(vi.getTimerCount()).toBe(0)

    await vi.advanceTimersByTimeAsync(10_000)
    expect(vi.getTimerCount()).toBe(0)
    expect(wrapper.find('.pet__bubble').exists()).toBe(false)
  })

  it('喂食后气泡未到期即卸载：统一清理全部定时器（D-55）', async () => {
    const wrapper = mountPet()
    await flush(wrapper)
    await openMenu(wrapper)
    await menuItem(wrapper, '喂食').trigger('click')
    await flush(wrapper)
    const bubbleEl = wrapper.find('.pet__bubble').element
    expect(bubbleEl.isConnected).toBe(true)

    wrapper.unmount()
    mounted.splice(0)

    // VTU 的 wrapper.find() 卸载后仍会查询分离的旧 DOM 树，因此用 document 级断言判断气泡已随组件移除
    expect(document.body.contains(bubbleEl)).toBe(false)
    expect(vi.getTimerCount()).toBe(0)

    await vi.advanceTimersByTimeAsync(10_000)
    expect(vi.getTimerCount()).toBe(0)
    expect(document.querySelector('.pet__bubble')).toBeNull()
  })

  it('玩耍后气泡未到期即卸载：统一清理全部定时器（D-55）', async () => {
    const wrapper = mountPet()
    await flush(wrapper)
    await openMenu(wrapper)
    await menuItem(wrapper, '玩耍').trigger('click')
    await flush(wrapper)
    const bubbleEl = wrapper.find('.pet__bubble').element
    expect(bubbleEl.isConnected).toBe(true)

    wrapper.unmount()
    mounted.splice(0)

    // VTU 的 wrapper.find() 卸载后仍会查询分离的旧 DOM 树，因此用 document 级断言判断气泡已随组件移除
    expect(document.body.contains(bubbleEl)).toBe(false)
    expect(vi.getTimerCount()).toBe(0)

    await vi.advanceTimersByTimeAsync(10_000)
    expect(vi.getTimerCount()).toBe(0)
    expect(document.querySelector('.pet__bubble')).toBeNull()
  })

  it('休息后气泡未到期即卸载：统一清理全部定时器（D-55）', async () => {
    const wrapper = mountPet()
    await flush(wrapper)
    await openMenu(wrapper)
    await menuItem(wrapper, '休息').trigger('click')
    await flush(wrapper)
    const bubbleEl = wrapper.find('.pet__bubble').element
    expect(bubbleEl.isConnected).toBe(true)

    wrapper.unmount()
    mounted.splice(0)

    // VTU 的 wrapper.find() 卸载后仍会查询分离的旧 DOM 树，因此用 document 级断言判断气泡已随组件移除
    expect(document.body.contains(bubbleEl)).toBe(false)
    expect(vi.getTimerCount()).toBe(0)

    await vi.advanceTimersByTimeAsync(10_000)
    expect(vi.getTimerCount()).toBe(0)
    expect(document.querySelector('.pet__bubble')).toBeNull()
  })

  it('正常路径：未卸载时 1s 仍会自动冒泡（D-52 修复不误伤首条问候）', async () => {
    vi.spyOn(Math, 'random').mockReturnValue(0)
    const wrapper = mountPet()
    await flush(wrapper)

    await vi.advanceTimersByTimeAsync(1000)

    expect(wrapper.find('.pet__bubble').text()).toBe('今天也要加油哦~')
  })

  it('卸载后移除事件监听且清理定时器（不崩溃）', async () => {
    const wrapper = mountPet()
    await flush(wrapper)

    wrapper.unmount()
    mounted.splice(0)

    // 事件监听已移除：卸载后广播不应抛错
    expect(() => {
      window.dispatchEvent(
        new CustomEvent(PET_ACTION_EVENT, { detail: { action: 'celebrate', duration: 500 } }),
      )
    }).not.toThrow()

    // 定时器清理：推进足够时间后不应残留任何挂起定时器
    await vi.advanceTimersByTimeAsync(10_000)
    expect(vi.getTimerCount()).toBe(0)
  })
})
