// ============================================================
// 主题切换 —— 三套内置主题包 × 明暗模式
// 主题包: cream(奶油糖果) / guofeng(国风雅集) / abyss(深渊档案) / epic(史诗典藏)
// 模式: light / dark / system
// 映射:
//   cream+light   → :root（默认，不设 data-theme）
//   cream+dark    → data-theme="dark"
//   guofeng+light → data-theme="guofeng"
//   guofeng+dark  → data-theme="guofeng-dark"
//   abyss+light   → data-theme="abyss-light"
//   abyss+dark    → data-theme="abyss"
// ============================================================
import { computed, ref } from 'vue'
import type { ThemeConfig, ThemeMode, ThemePack } from '@/types/common'

const STORAGE_KEY = 'qm-star-theme'

const media = window.matchMedia('(prefers-color-scheme: dark)')

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
  if (mode === 'system') return media.matches ? 'dark' : 'light'
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
const onMediaChange = () => {
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
