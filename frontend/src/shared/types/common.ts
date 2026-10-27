// ============================================================
// 通用类型定义
// ============================================================

/** 语义状态 —— 对应 token 语义色 */
export type Semantic = 'info' | 'success' | 'warning' | 'error' | 'primary'

/** 组件尺寸 */
export type CompSize = 'sm' | 'md' | 'lg'

/** 按钮变体 */
export type ButtonVariant = 'primary' | 'secondary' | 'text' | 'danger' | 'pill'

/** 标签语义色 —— 对应 token 语义色 */
export type TagSemantic =
  'default' | 'primary' | 'mint' | 'butter' | 'sky' | 'lilac' | 'straw' | 'gold'

/** 主题模式 */
export type ThemeMode = 'light' | 'dark' | 'system'

/** 内置主题包 */
export type ThemePack = 'cream' | 'guofeng' | 'abyss' | 'epic'

/** 主题配置（主题包+明暗模式） */
export interface ThemeConfig {
  pack: ThemePack
  mode: ThemeMode
}

/** 导航项 */
export interface NavItem {
  id: string
  label: string
  icon?: string
  route?: string
  badge?: number
}

/** 下拉选项 */
export interface SelectOption<V = string> {
  label: string
  value: V
  disabled?: boolean
}

/** Toast 通知类型（迁移批次 P3：定义在 kernel/ui/types，这里 re-export 保持旧入口可用） */
export type { ToastItem, ToastType } from '@/kernel/ui/types'

/** 全局搜索结果项（UI层，与API层 SearchResult 区分） */
export interface SearchResultItem {
  type: 'task' | 'doc' | 'conv' | 'action'
  title: string
  path?: string
  id: string
  subtitle?: string
}

/** 窗口状态 */
export type WindowStatus = 'saved' | 'saving' | 'offline' | 'error'
