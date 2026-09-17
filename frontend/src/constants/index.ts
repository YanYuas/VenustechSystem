// ============================================================
// 应用常量配置
// ============================================================

/** 应用信息 */
export const APP = {
  name: '启明星',
  nameEn: 'Venustech System',
  slogan: '方向启明，人生推演',
  version: __APP_VERSION__,
} as const

/** 本地存储 Key */
export const STORAGE_KEYS = {
  theme: 'qm-star-theme',
  userConfig: 'qm-star-user-config',
  sidebarCollapsed: 'qm-star-sidebar-collapsed',
  lastRoute: 'qm-star-last-route',
} as const

/** 路由路径 */
export const ROUTES = {
  dashboard: '/dashboard',
  tasks: '/tasks',
  documents: '/documents',
  conversation: '/conversation',
  review: '/review',
  settings: '/settings',
} as const

/** 任务状态映射 */
export const TASK_STATUS = {
  pending: { label: '待办', color: 'text-low' },
  in_progress: { label: '进行中', color: 'butter' },
  waiting: { label: '等待中', color: 'sky' },
  completed: { label: '已完成', color: 'mint' },
} as const

/** 任务优先级映射 */
export const TASK_PRIORITY = {
  low: { label: '低', color: 'text-low' },
  medium: { label: '中', color: 'sky' },
  high: { label: '高', color: 'butter' },
  urgent: { label: '紧急', color: 'straw' },
} as const

/** 快捷键映射 */
export const SHORTCUTS = {
  globalSearch: 'Ctrl+K',
  commandPalette: 'Ctrl+Shift+P',
  newTask: 'Ctrl+N',
  newDocument: 'Ctrl+Shift+N',
  save: 'Ctrl+S',
  escape: 'Esc',
} as const

/** 主题包列表 */
export const THEME_PACKS = [
  { id: 'cream', name: '奶油糖果', desc: '治愈软萌 · 薄荷绿' },
  { id: 'guofeng', name: '国风雅集', desc: '中国古典 · 朱砂红' },
  { id: 'abyss', name: '深渊档案', desc: '海洋神秘 · 磷火青' },
] as const

/** 自动化档位 */
export const AUTOMATION_LEVELS = {
  L1: { label: '完全手动', desc: '只在被问时回答' },
  L2: { label: '建议不执行', desc: '主动提建议，需用户确认' },
  L3: { label: '低风险自动', desc: '自动打标签/摘要，高风险需确认' },
  L4: { label: '大部分自动', desc: '大部分操作自动，仅删除/覆盖确认' },
  L5: { label: '完全自主', desc: '全自动，用户只看结果' },
} as const
