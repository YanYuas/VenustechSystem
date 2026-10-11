// ============================================================
// 主题切换 —— 内置主题包 × 明暗模式
// 主题包: cream(奶油糖果) / guofeng(国风雅集) / abyss(深渊档案) / epic(史诗典藏)
// 模式: light / dark / system
// 映射（完整表见 src/composables/__tests__/useTheme.spec.ts，用例逐行钉死）:
//   cream+light   → :root（默认，不设 data-theme）
//   cream+dark    → data-theme="dark"
//   guofeng+light → data-theme="guofeng"      guofeng+dark → "guofeng-dark"
//   abyss+light   → data-theme="abyss-light"  abyss+dark   → "abyss"
//   epic+light    → data-theme="epic"         epic+dark    → "epic-dark"
// ============================================================
import { computed, ref } from 'vue'
import type { ThemeConfig, ThemeMode, ThemePack } from '@/types/common'

const STORAGE_KEY = 'qm-star-theme'

const media = window.matchMedia('(prefers-color-scheme: dark)')

// 系统明暗必须进 ref：此前 resolveMode 直接读 `media.matches`，
// 而 isDark 是 `computed(() => resolveMode(config.value.mode) === 'dark')`
// —— 依赖里只有 config，系统切换时 computed **不会重算**。
// 症状：mode=system 下用户切换 OS 主题，data-theme 变了（监听器里 apply 了），
// 但组件读到的 isDark 仍是旧值 → 月亮/太阳图标、依赖明暗的文案不跟着变。
// （2026-10-11 由前端首个 vitest 套件测出）
const systemDark = ref(media.matches)

const config = ref<ThemeConfig>(load())

function load(): ThemeConfig {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      const parsed = JSON.parse(saved)
      if (['cream', 'guofeng', 'abyss', 'epic'].includes(parsed.pack)
        && ['light', 'dark', 'system'].includes(parsed.mode)) {
        return parsed
      }
    }
  } catch { /* ignore */ }
  return { pack: 'cream', mode: 'light' }
}

function resolveMode(mode: ThemeMode): 'light' | 'dark' {
  if (mode === 'system') return systemDark.value ? 'dark' : 'light'
  return mode
}

/** 主题包+明暗模式 → data-theme 属性值 */
function resolveDataTheme(pack: ThemePack, mode: ThemeMode): string | null {
  const m = resolveMode(mode)
  if (pack === 'cream') return m === 'dark' ? 'dark' : null
  if (pack === 'guofeng') return m === 'dark' ? 'guofeng-dark' : 'guofeng'
  // abyss
  if (pack === 'abyss') return m === 'dark' ? 'abyss' : 'abyss-light'
  // epic
  return m === 'dark' ? 'epic-dark' : 'epic'
}

function apply(cfg: ThemeConfig) {
  const attr = resolveDataTheme(cfg.pack, cfg.mode)
  if (attr === null) {
    document.documentElement.removeAttribute('data-theme')
  } else {
    document.documentElement.dataset.theme = attr
  }
}

function persist(cfg: ThemeConfig) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(cfg))
}

function setPack(pack: ThemePack) {
  config.value = { ...config.value, pack }
  persist(config.value)
  apply(config.value)
}

function setMode(mode: ThemeMode) {
  config.value = { ...config.value, mode }
  persist(config.value)
  apply(config.value)
}

function toggleMode() {
  const m = resolveMode(config.value.mode)
  setMode(m === 'dark' ? 'light' : 'dark')
}

function cyclePack() {
  const order: ThemePack[] = ['cream', 'guofeng', 'abyss', 'epic']
  const idx = order.indexOf(config.value.pack)
  setPack(order[(idx + 1) % order.length])
}

// 模块级立即应用（不等组件 mounted）：配合 index.html 内联脚本消除主题闪烁
apply(config.value)

// 系统明暗变化监听：模块级只注册一次，避免多组件挂载/卸载互相覆盖导致泄漏
const onMediaChange = (e: MediaQueryListEvent) => {
  // 先更新 ref（让 isDark 等派生状态失效重算），再按需落到 DOM
  systemDark.value = e.matches
  if (config.value.mode === 'system') apply(config.value)
}
media.addEventListener('change', onMediaChange)

export function useTheme() {
  const isDark = computed(() => resolveMode(config.value.mode) === 'dark')
  const pack = computed(() => config.value.pack)
  const mode = computed(() => config.value.mode)

  return {
    config,
    pack,
    mode,
    isDark,
    setPack,
    setMode,
    toggleMode,
    cyclePack,
  }
}
