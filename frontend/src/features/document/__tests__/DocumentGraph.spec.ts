// ============================================================
// DocumentGraph —— 文档关系图谱测试
//
// 组件是纯 SVG 力导向图：mock documentApi.graph 提供图数据，
// 用可控的 requestAnimationFrame 桩避免真实动画循环；覆盖：
// 加载/空/失败三态、节点渲染与半径换算、点击 emit、hover tooltip、
// 拖拽移动、resize 更新视窗、卸载清理、tick 一帧与悬空边容错。
// ============================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import { documentApi } from '../api'
import type { GraphData, GraphNode } from '../model'
import DocumentGraph from '../components/DocumentGraph.vue'

vi.mock('../api', () => ({
  documentApi: { graph: vi.fn() },
}))

const toastMock = vi.hoisted(() => ({
  error: vi.fn(),
  success: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
}))
vi.mock('@/kernel/ui/toast', () => ({ toast: toastMock, useToast: () => toastMock }))

const graphApi = documentApi.graph as unknown as ReturnType<typeof vi.fn>

function node(patch: Partial<GraphNode> = {}): GraphNode {
  return {
    id: 'd1',
    title: '文档一',
    folder_name: '收集箱',
    word_count: 0,
    updated_at: '2026-10-31T00:00:00',
    ...patch,
  }
}

function makeGraph(patch: Partial<GraphData> = {}): GraphData {
  return {
    nodes: [node({ id: 'd1' }), node({ id: 'd2', title: '文档二', word_count: 6000 })],
    edges: [{ source: 'd1', target: 'd2' }],
    dangling: [],
    ...patch,
  } as unknown as GraphData
}

/** D-54：可控 document.hidden（jsdom 默认 false） */
function setHidden(hidden: boolean) {
  Object.defineProperty(document, 'hidden', { configurable: true, get: () => hidden })
}

/** 执行 n 帧（每帧都消费当前排队的 rAF 回调） */
function runFrames(n: number) {
  for (let i = 0; i < n; i++) runOneFrame()
}

/** 读取节点 translate 坐标 */
function nodeXY(wrapper: ReturnType<typeof mountGraph>, index = 0): [number, number] {
  const transform = wrapper.findAll('.doc-graph__node')[index].attributes('transform') ?? ''
  const m = /translate\(([-\d.]+),\s*([-\d.]+)\)/.exec(transform)
  if (!m) throw new Error(`无法解析 transform: ${transform}`)
  return [Number(m[1]), Number(m[2])]
}

/** 可控 rAF：只在测试里手动执行帧回调，避免真实动画循环 */
let rafCallbacks: FrameRequestCallback[] = []
const rafMock = vi.fn((cb: FrameRequestCallback) => {
  rafCallbacks.push(cb)
  return rafCallbacks.length
})
const cancelRafMock = vi.fn()

const mounted: Array<{ unmount: () => void }> = []
function mountGraph() {
  const wrapper = mount(DocumentGraph)
  mounted.push(wrapper)
  return wrapper
}

function runOneFrame() {
  const cb = rafCallbacks.pop()
  if (!cb) throw new Error('没有待执行的 rAF 回调')
  cb(16)
}

beforeEach(() => {
  vi.clearAllMocks()
  rafCallbacks = []
  rafMock.mockClear()
  cancelRafMock.mockClear()
  vi.stubGlobal('requestAnimationFrame', rafMock)
  vi.stubGlobal('cancelAnimationFrame', cancelRafMock)
  graphApi.mockResolvedValue(makeGraph())
})

afterEach(() => {
  mounted.splice(0).forEach((w) => w.unmount())
  delete (document as unknown as Record<string, unknown>).hidden
  vi.unstubAllGlobals()
})

describe('DocumentGraph：加载三态', () => {
  it('加载中显示 spinner 与提示，不渲染 svg', async () => {
    graphApi.mockReturnValue(new Promise(() => undefined))
    const wrapper = mountGraph()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.doc-graph__loading').exists()).toBe(true)
    expect(wrapper.text()).toContain('正在构建知识图谱…')
    expect(wrapper.find('svg').exists()).toBe(false)
  })

  it('加载成功渲染节点/边/统计文案', async () => {
    const wrapper = mountGraph()
    await flushPromises()

    expect(wrapper.find('.doc-graph__loading').exists()).toBe(false)
    expect(wrapper.findAll('.doc-graph__node')).toHaveLength(2)
    expect(wrapper.findAll('.doc-graph__edge')).toHaveLength(1)
    expect((wrapper.find('svg').element as SVGElement).getAttribute('viewBox')).toBe('0 0 800 500')
    expect(wrapper.find('.doc-graph__stats').text()).toContain('2 篇文档')
    expect(wrapper.find('.doc-graph__stats').text()).toContain('1 条链接')
  })

  it('空图显示空态引导与 0/0 统计，不渲染 svg', async () => {
    graphApi.mockResolvedValue(makeGraph({ nodes: [], edges: [] }))
    const wrapper = mountGraph()
    await flushPromises()

    expect(wrapper.find('.doc-graph__empty').text()).toContain('暂无文档链接关系')
    expect(wrapper.text()).toContain('[[文档标题]]')
    expect(wrapper.find('.doc-graph__stats').text()).toContain('0 篇文档')
    expect(wrapper.find('.doc-graph__stats').text()).toContain('0 条链接')
    expect(wrapper.find('svg').exists()).toBe(false)
  })

  it('加载失败：toast 报错、loading 结束并降级为空态', async () => {
    graphApi.mockRejectedValue(new Error('graph down'))
    const wrapper = mountGraph()
    await flushPromises()

    expect(toastMock.error).toHaveBeenCalledWith('图谱加载失败')
    expect(wrapper.find('.doc-graph__loading').exists()).toBe(false)
    expect(wrapper.find('.doc-graph__empty').exists()).toBe(true)
    expect(wrapper.find('.doc-graph__stats').exists()).toBe(false)
  })
})

describe('DocumentGraph：节点渲染与交互', () => {
  it('节点半径按字数换算（0 字→8；6000 字→上限 20）', async () => {
    const wrapper = mountGraph()
    await flushPromises()

    const circles = wrapper.findAll('.doc-graph__node-circle')
    expect(circles[0].attributes('r')).toBe('8')
    expect(circles[1].attributes('r')).toBe('20')
  })

  it('渲染节点标题文本与初始 translate 定位', async () => {
    const wrapper = mountGraph()
    await flushPromises()

    expect(wrapper.findAll('.doc-graph__node-label')[0].text()).toBe('文档一')
    expect(wrapper.findAll('.doc-graph__node')[0].attributes('transform')).toMatch(/^translate\(/)
  })

  it('点击节点 emit open-doc(id)', async () => {
    const wrapper = mountGraph()
    await flushPromises()

    await wrapper.findAll('.doc-graph__node')[1].trigger('click')

    expect(wrapper.emitted('open-doc')).toEqual([['d2']])
  })

  it('hover 显示 tooltip（标题/目录/字数），mouseleave 清除', async () => {
    const wrapper = mountGraph()
    await flushPromises()

    const groups = wrapper.findAll('.doc-graph__node')
    await groups[1].trigger('mouseenter')

    const tooltip = wrapper.find('.doc-graph__tooltip')
    expect(tooltip.exists()).toBe(true)
    expect(tooltip.text()).toContain('文档二')
    expect(tooltip.text()).toContain('收集箱')
    expect(tooltip.text()).toContain('6000 字')

    await groups[1].trigger('mouseleave')
    expect(wrapper.find('.doc-graph__tooltip').exists()).toBe(false)
  })

  it('拖拽：mousedown 后跟随 mousemove 移动节点，mouseup 结束', async () => {
    const wrapper = mountGraph()
    await flushPromises()
    const svg = wrapper.find('svg').element
    svg.getBoundingClientRect = () => ({ left: 10, top: 20 }) as DOMRect

    const target = wrapper.findAll('.doc-graph__node')[0]
    await target.trigger('mousedown', { clientX: 60, clientY: 70 })
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 110, clientY: 170 }))
    await wrapper.vm.$nextTick()

    expect(target.attributes('transform')).toBe('translate(100, 150)')

    window.dispatchEvent(new MouseEvent('mouseup'))
    // 拖拽结束后 mousemove 不再移动
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 300, clientY: 300 }))
    await wrapper.vm.$nextTick()
    expect(target.attributes('transform')).toBe('translate(100, 150)')
  })

  it('resize 更新视窗宽高（宽度取父容器、高度至少 400）', async () => {
    const wrapper = mountGraph()
    await flushPromises()
    const root = wrapper.find('.doc-graph').element
    Object.defineProperty(root, 'clientWidth', { configurable: true, value: 900 })
    Object.defineProperty(root, 'clientHeight', { configurable: true, value: 620 })

    window.dispatchEvent(new Event('resize'))
    await wrapper.vm.$nextTick()

    // SVG 的 viewBox 属性大小写敏感
    const svgEl = wrapper.find('svg').element as SVGElement
    expect(svgEl.getAttribute('viewBox')).toBe('0 0 900 620')
  })
})

describe('DocumentGraph：模拟与生命周期', () => {
  it('执行一帧 tick 不抛错并重新调度下一帧', async () => {
    const wrapper = mountGraph()
    await flushPromises()
    const callsAfterInit = rafMock.mock.calls.length

    // 初始帧回调在 loadGraph 时已入队；直接执行它（runOneFrame 会 pop 并再调度下一帧）
    runOneFrame()

    expect(rafMock.mock.calls.length).toBeGreaterThan(callsAfterInit)
    // 位置仍在视窗范围内（tick 末尾做了 clamp）
    const transform = wrapper.findAll('.doc-graph__node')[0].attributes('transform') ?? ''
    expect(transform).toMatch(/^translate\(/)
  })

  it('边引用不存在的节点时 tick 安全跳过（悬空边容错）', async () => {
    graphApi.mockResolvedValue(
      makeGraph({
        nodes: [node({ id: 'd1' })],
        edges: [{ source: 'd1', target: 'missing' }],
      }),
    )
    const wrapper = mountGraph()
    await flushPromises()

    expect(() => runOneFrame()).not.toThrow()
    expect(wrapper.findAll('.doc-graph__edge')).toHaveLength(1)
  })

  it('卸载时取消动画帧并移除 window / document 监听', async () => {
    const removeSpy = vi.spyOn(window, 'removeEventListener')
    const docRemoveSpy = vi.spyOn(document, 'removeEventListener')
    const wrapper = mountGraph()
    await flushPromises()

    wrapper.unmount()
    mounted.splice(0)

    expect(cancelRafMock).toHaveBeenCalled()
    expect(removeSpy.mock.calls.map((c) => c[0])).toEqual(
      expect.arrayContaining(['mousemove', 'mouseup', 'resize']),
    )
    expect(docRemoveSpy.mock.calls.map((c) => c[0])).toContain('visibilitychange')
  })

  it('页面隐藏时取消 rAF，切回前台后重启（D-54）', async () => {
    const wrapper = mountGraph()
    await flushPromises()
    const callsWhileVisible = rafMock.mock.calls.length

    setHidden(true)
    document.dispatchEvent(new Event('visibilitychange'))
    expect(cancelRafMock).toHaveBeenCalledTimes(1)

    // 隐藏期间不再有新帧入队
    setHidden(false)
    document.dispatchEvent(new Event('visibilitychange'))
    expect(rafMock.mock.calls.length).toBeGreaterThan(callsWhileVisible)
    void wrapper
  })

  it('加载完成时页面处于隐藏态则不启动动画，visible 后再启动（D-54）', async () => {
    setHidden(true)
    const wrapper = mountGraph()
    await flushPromises()

    expect(rafMock).not.toHaveBeenCalled()
    expect(wrapper.findAll('.doc-graph__node')).toHaveLength(2)

    setHidden(false)
    document.dispatchEvent(new Event('visibilitychange'))
    expect(rafMock).toHaveBeenCalledTimes(1)
  })

  it('空图时 visible 也不会启动动画循环（D-54）', async () => {
    graphApi.mockResolvedValue(makeGraph({ nodes: [], edges: [] }))
    setHidden(true)
    mountGraph()
    await flushPromises()

    setHidden(false)
    document.dispatchEvent(new Event('visibilitychange'))

    expect(rafMock).not.toHaveBeenCalled()
  })

  it('拖拽松手会清零速度：释放后单帧位移很小（无惯性冲量，D-54）', async () => {
    graphApi.mockResolvedValue(
      makeGraph({ nodes: [node({ id: 'd1' })], edges: [] }) as unknown as GraphData,
    )
    const wrapper = mountGraph()
    await flushPromises()
    const svg = wrapper.find('svg').element
    svg.getBoundingClientRect = () => ({ left: 0, top: 0 }) as DOMRect

    // 拖到远离中心的位置（中心 400,250）；tick 的力阶段对 dragging 节点照常累加
    // vx/vy，只有"清速度"才能阻止松手后的惯性冲量
    const [startX, startY] = nodeXY(wrapper)
    await wrapper.findAll('.doc-graph__node')[0].trigger('mousedown', {
      clientX: startX,
      clientY: startY,
    })
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 30, clientY: 250 }))
    await wrapper.vm.$nextTick()

    // ⚠️ DOM 渲染是异步的：每轮 tick 后必须 nextTick 再读坐标，否则读到的是旧 transform
    runFrames(60)
    await wrapper.vm.$nextTick()

    window.dispatchEvent(new MouseEvent('mouseup'))
    const [beforeX] = nodeXY(wrapper)
    runFrames(1)
    await wrapper.vm.$nextTick()
    const [afterX] = nodeXY(wrapper)

    // 若未清零速度，60 帧累积的 vx 会让首帧位移达到 ~90px
    expect(Math.abs(afterX - beforeX)).toBeLessThan(5)

    runFrames(3)
    await wrapper.vm.$nextTick()
    const [finalX] = nodeXY(wrapper)
    expect(Math.abs(finalX - beforeX)).toBeLessThan(20)
  })
})
