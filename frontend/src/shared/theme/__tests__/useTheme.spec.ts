// ============================================================
// 主题切换 —— 单元测试
//
// useTheme 是**模块级单例**（config 在模块作用域、加载即 apply 到
// document.documentElement），所以每个用例都要 vi.resetModules() 后动态
// import，才能测到「冷启动时读 localStorage」这条真实路径。
//
// 覆盖的核心契约是那张映射表（包 × 明暗 → data-theme 属性值）：
//    cream   + light → 不设属性（:root 默认）
//    cream   + dark  → "dark"
//    guofeng + light → "guofeng"      guofeng + dark → "guofeng-dark"
//    abyss   + light → "abyss-light"  abyss   + dark → "abyss"
//    epic    + light → "epic"         epic    + dark → "epic-dark"
// 这张表错了不会报错，只会「切到某个主题后页面颜色不对」。
// ============================================================
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { mediaState, setSystemDark } from '@/shared/test/setup'

type ThemeApi = ReturnType<(typeof import('../useTheme'))['useTheme']>

const STORAGE_KEY = 'qm-star-theme'

/**
 * 冷启动：清空存储与 DOM 属性，重新加载模块再取 useTheme()。
 *
 * 注意 `config` / `setPack` 等是模块私有、**不在模块的导出里** ——
 * 想拿到它们只能调用 useTheme()（这也正是它在实际组件里的用法）。
 * 动态 import 保证每次都是全新的模块实例（模块级 apply 会立即执行）。
 */
async function coldStart(saved?: unknown): Promise<ThemeApi> {
  vi.resetModules()
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
  mediaState.dark = false
  mediaState.listeners.length = 0
  if (saved !== undefined) {
    localStorage.setItem(STORAGE_KEY, typeof saved === 'string' ? saved : JSON.stringify(saved))
  }
  const mod = await import('../useTheme')
  return mod.useTheme()
}

const attr = () => document.documentElement.getAttribute('data-theme')

beforeEach(() => {
  mediaState.dark = false
})

// ============================================================
// 第 1 组：冷启动与持久化
// ============================================================
describe('第1组：冷启动与持久化', () => {
  it('无存储时默认 cream + light，且不设 data-theme（走 :root 默认）', async () => {
    const { config } = await coldStart()

    expect(config.value).toEqual({ pack: 'cream', mode: 'light' })
    expect(attr()).toBeNull()
  })

  it('从 localStorage 恢复已保存的主题，并在模块加载时立即应用', async () => {
    await coldStart({ pack: 'abyss', mode: 'dark' })

    expect(attr()).toBe('abyss')
  })

  it('存储内容损坏（非 JSON）时回落默认值，不抛异常', async () => {
    const mod = await coldStart('{ 这不是 JSON')

    expect(mod.config.value).toEqual({ pack: 'cream', mode: 'light' })
    expect(attr()).toBeNull()
  })

  it('存储里是非法主题包/模式时回落默认值', async () => {
    const bad1 = await coldStart({ pack: 'not-a-theme', mode: 'dark' })
    expect(bad1.config.value.pack).toBe('cream')

    const bad2 = await coldStart({ pack: 'abyss', mode: 'not-a-mode' })
    expect(bad2.config.value.mode).toBe('light')
  })

  it('setPack / setMode 会写回 localStorage（刷新后主题不丢）', async () => {
    const { setPack, setMode } = await coldStart()

    setPack('epic')
    setMode('dark')

    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!)).toEqual({ pack: 'epic', mode: 'dark' })
  })
})

// ============================================================
// 第 2 组：映射表（包 × 明暗 → data-theme）
// ============================================================
describe('第2组：data-theme 映射表', () => {
  const cases: Array<
    [pack: 'cream' | 'guofeng' | 'abyss' | 'epic', dark: boolean, expected: string | null]
  > = [
    ['cream', false, null],
    ['cream', true, 'dark'],
    ['guofeng', false, 'guofeng'],
    ['guofeng', true, 'guofeng-dark'],
    ['abyss', false, 'abyss-light'],
    ['abyss', true, 'abyss'],
    ['epic', false, 'epic'],
    ['epic', true, 'epic-dark'],
  ]

  for (const [pack, dark, expected] of cases) {
    it(`${pack} + ${dark ? 'dark' : 'light'} → ${expected ?? '（移除属性）'}`, async () => {
      const { setPack, setMode } = await coldStart()

      // 顺序要紧：coldStart 会把系统偏好复位为 light，
      // 且系统明暗必须通过 setSystemDark 走**事件**（resolveMode 读的是事件驱动的 ref，
      // 直接改 mediaState.dark 不会生效 —— 这正是修掉的那个响应式缺陷）。
      setSystemDark(dark)
      setPack(pack)
      setMode('system')

      expect(attr()).toBe(expected)
    })
  }

  it('从有属性切回 cream + light 时属性被移除（不是留成 "cream"）', async () => {
    const { setPack, setMode } = await coldStart()

    setPack('guofeng')
    expect(attr()).toBe('guofeng')

    setPack('cream')
    setMode('light')

    expect(attr()).toBeNull()
  })
})

// ============================================================
// 第 3 组：跟随系统
// ============================================================
describe('第3组：跟随系统明暗', () => {
  it('mode=system 时 isDark 跟随系统偏好变化（响应式，不是只在加载时读一次）', async () => {
    // 防的缺陷（本套件测出并已修）：isDark 是
    // computed(() => resolveMode(config.value.mode) === 'dark')，依赖里只有 config；
    // 原实现 resolveMode 直接读 media.matches，于是系统切换时 computed 不重算，
    // data-theme 已变而 isDark 仍是旧值（图标/文案不跟着变）。
    const { setMode, isDark } = await coldStart()

    setMode('system')
    expect(isDark.value).toBe(false)

    setSystemDark(true)
    expect(isDark.value).toBe(true)

    setSystemDark(false)
    expect(isDark.value).toBe(false)
  })

  it('跟随系统时 data-theme 属性与 isDark 保持一致', async () => {
    const { setPack, setMode, isDark } = await coldStart()
    setPack('guofeng')
    setMode('system')

    setSystemDark(true)
    expect(isDark.value).toBe(true)
    expect(attr()).toBe('guofeng-dark')

    setSystemDark(false)
    expect(isDark.value).toBe(false)
    expect(attr()).toBe('guofeng')
  })

  it('系统偏好变化只在 mode=system 时落到 DOM（固定 light 不该被系统拖走）', async () => {
    const { setMode, isDark } = await coldStart()

    setMode('light')
    setSystemDark(true)
    expect(isDark.value).toBe(false)
    expect(attr()).toBeNull()

    setMode('system')
    expect(isDark.value).toBe(true)
  })

  it('模块级只注册一个系统明暗监听器（多组件挂载不会互相覆盖）', async () => {
    await coldStart()

    // 连续 import 两次同一个 composable 模块，模块级代码只执行一次
    const again = await import('../useTheme')
    again.useTheme()

    expect(mediaState.listeners.length).toBe(1)
  })
})

// ============================================================
// 第 4 组：toggleMode / cyclePack
// ============================================================
describe('第4组：切换行为', () => {
  it('toggleMode 在 light/dark 之间来回切', async () => {
    const { toggleMode, mode, isDark } = await coldStart()

    expect(mode.value).toBe('light')
    toggleMode()
    expect(mode.value).toBe('dark')
    expect(isDark.value).toBe(true)
    toggleMode()
    expect(mode.value).toBe('light')
  })

  it('system + 系统为 dark 时 toggle 到 light（以「解析后的实际模式」为基准）', async () => {
    const { toggleMode, mode, setMode } = await coldStart()

    setSystemDark(true)
    setMode('system')

    toggleMode()

    expect(mode.value).toBe('light')
  })

  it('cyclePack 按 cream→guofeng→abyss→epic 循环', async () => {
    const { cyclePack, pack } = await coldStart()

    const seen = [pack.value]
    for (let i = 0; i < 4; i++) {
      cyclePack()
      seen.push(pack.value)
    }

    expect(seen).toEqual(['cream', 'guofeng', 'abyss', 'epic', 'cream'])
  })

  it('cyclePack 每次都落盘（循环一圈后存储里是最终主题）', async () => {
    const { cyclePack } = await coldStart()

    cyclePack()
    cyclePack()

    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!).pack).toBe('abyss')
  })
})
