// ============================================================
// 前端单元测试全局前置（vitest setupFiles）
//
// jsdom 未实现 `window.matchMedia`，而 useTheme 在**模块级**就调用它
// （`window.matchMedia('(prefers-color-scheme: dark)')`）—— 缺这个桩，
// 任何 import useTheme 的用例都会在加载阶段直接炸。
//
// 这里**无条件**覆盖为自建实现（而不是「缺失才补」）：jsdom 自带的桩
// 不支持切换 matches，测不了「跟随系统」这条分支。自建版本可切换，
// 且 addEventListener 真会登记监听器，能验证模块级只注册一次的约定。
// ============================================================

type Listener = (e: { matches: boolean }) => void

export const mediaState = { dark: false, listeners: [] as Listener[] }

/** 切换系统明暗并通知已注册的监听器 */
export function setSystemDark(dark: boolean) {
  mediaState.dark = dark
  mediaState.listeners.forEach((fn) => fn({ matches: dark }))
}

window.matchMedia = ((query: string) => ({
  media: query,
  get matches() {
    return query.includes('dark') ? mediaState.dark : !mediaState.dark
  },
  onchange: null,
  addEventListener: (_: string, fn: Listener) => {
    mediaState.listeners.push(fn)
  },
  removeEventListener: (_: string, fn: Listener) => {
    mediaState.listeners = mediaState.listeners.filter((f) => f !== fn)
  },
  addListener: (fn: Listener) => {
    mediaState.listeners.push(fn)
  },
  removeListener: (fn: Listener) => {
    mediaState.listeners = mediaState.listeners.filter((f) => f !== fn)
  },
  dispatchEvent: () => false,
})) as unknown as typeof window.matchMedia
