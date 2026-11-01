// ============================================================
// AppIcon —— 图标映射/回退/尺寸/可访问性 测试
//
// 组件是「name → path 数组」的静态映射（setup 时一次性解析），
// 覆盖：常用图标路径数、未知 name 回退为空、size 映射、SVG 固定属性、
// 以及 aria-hidden 装饰语义。不做样式快照。
// ============================================================
import { afterEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import { DIMENSIONS } from '@/shared/constants/dimensions'
import AppIcon from '../AppIcon.vue'

const mounted: Array<{ unmount: () => void }> = []
function mountIcon(name: string, size?: number) {
  const wrapper = mount(AppIcon, { props: size === undefined ? { name } : { name, size } })
  mounted.push(wrapper)
  return wrapper
}

afterEach(() => {
  mounted.splice(0).forEach((w) => w.unmount())
})

describe('AppIcon：图标映射', () => {
  it('close 渲染两条交叉线路径', () => {
    const paths = mountIcon('close').findAll('path')

    expect(paths).toHaveLength(2)
    expect(paths.map((p) => p.attributes('d'))).toEqual(['M18 6 6 18', 'm6 6 12 12'])
  })

  it('home 渲染两条路径', () => {
    expect(mountIcon('home').findAll('path')).toHaveLength(2)
  })

  it('owl 渲染 8 条路径（多路径图标不被截断）', () => {
    expect(mountIcon('owl').findAll('path')).toHaveLength(8)
  })

  it('所有被渲染的 path 都有非空 d 属性', () => {
    for (const name of ['search', 'gear', 'star', 'heart', 'graph', 'cloud', 'list']) {
      for (const path of mountIcon(name).findAll('path')) {
        expect((path.attributes('d') ?? '').length).toBeGreaterThan(0)
      }
    }
  })

  it('未知 name 回退为 0 条 path，但 svg 仍渲染（占位不炸）', () => {
    // 注意：'loading' 已作为 spin 的别名（Phase21 补图标），这里必须用真正未定义的 name
    const wrapper = mountIcon('no-such-icon')

    expect(wrapper.find('svg').exists()).toBe(true)
    expect(wrapper.findAll('path')).toHaveLength(0)
  })

  it('空 name 同样回退为空图标', () => {
    expect(mountIcon('').findAll('path')).toHaveLength(0)
  })
})

describe('AppIcon：尺寸与 SVG 属性', () => {
  it('默认 size=20 映射到 width/height', () => {
    const svg = mountIcon('check').find('svg')

    expect(svg.attributes('width')).toBe('20')
    expect(svg.attributes('height')).toBe('20')
  })

  it('自定义 size 同时作用于 width/height', () => {
    const svg = mountIcon('check', 32).find('svg')

    expect(svg.attributes('width')).toBe('32')
    expect(svg.attributes('height')).toBe('32')
  })

  it('固定 24 视窗、currentColor 描边与圆头线帽（主题色继承）', () => {
    const svg = mountIcon('check').find('svg')

    // SVG 属性大小写敏感：viewBox 必须用 getAttribute 原生读取
    expect((svg.element as SVGElement).getAttribute('viewBox')).toBe('0 0 24 24')
    expect(svg.attributes('fill')).toBe('none')
    expect(svg.attributes('stroke')).toBe('currentColor')
    expect(svg.attributes('stroke-width')).toBe('2')
    expect(svg.attributes('stroke-linecap')).toBe('round')
    expect(svg.attributes('stroke-linejoin')).toBe('round')
  })

  it('装饰性图标 aria-hidden=true 且带 app-icon class', () => {
    const svg = mountIcon('bell').find('svg')

    expect(svg.attributes('aria-hidden')).toBe('true')
    expect(svg.classes()).toContain('app-icon')
  })
})

// ============================================================
// 图标完整性回归（Phase21 D-66）：全站曾因 AppIcon 缺名出现大量空白图标
// ============================================================
/** 后端契约图标清单（dashboard_service 的资源/生活/资产分类 + 路由 meta + 各页面动态图标） */
const CONTRACT_ICONS = [
  'inbox',
  'robot',
  'workflow',
  'pet',
  'mic',
  'graduation',
  'brain',
  'terminal',
  'layout',
  'activity',
  'zap',
  'trending-up',
  'award',
  'message',
  'database',
  'chat',
  'code',
  'idea',
  'monitor',
  'folder-plus',
  'settings',
]

describe('AppIcon：图标完整性（D-66 空白图标回归）', () => {
  it('DIMENSIONS 里每个 dimension.icon 与 tab.icon 都能渲染出路径', () => {
    for (const dim of DIMENSIONS) {
      expect(
        mountIcon(dim.icon).findAll('path').length,
        `dimension ${dim.id} icon=${dim.icon}`,
      ).toBeGreaterThan(0)
      for (const tab of dim.tabs) {
        expect(
          mountIcon(tab.icon).findAll('path').length,
          `dimension ${dim.id} tab ${tab.id} icon=${tab.icon}`,
        ).toBeGreaterThan(0)
      }
    }
  })

  it('后端契约图标清单逐个可渲染（缺一即红）', () => {
    for (const name of CONTRACT_ICONS) {
      const paths = mountIcon(name).findAll('path')
      expect(paths.length, `契约图标缺失：${name}`).toBeGreaterThan(0)
      for (const p of paths) {
        expect((p.attributes('d') ?? '').length, `${name} 存在空 path`).toBeGreaterThan(0)
      }
    }
  })

  it('契约图标与界面别名共用同一视觉（settings=gear / error=alert / loading=spin）', () => {
    const d = (name: string) =>
      mountIcon(name)
        .findAll('path')
        .map((p) => p.attributes('d'))

    expect(d('settings')).toEqual(d('gear'))
    expect(d('error')).toEqual(d('alert'))
    expect(d('loading')).toEqual(d('spin'))
  })
})
