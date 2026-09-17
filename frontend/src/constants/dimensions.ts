// ============================================================
// 维度导航配置 —— 前端UI重构 v1.0
// 六大维度：首页 / 执行 / 知识 / 人生 / 资产 / 伙伴
// ============================================================
import type { NavItem } from '@/types/common'

export type DimensionId = 'dashboard' | 'execution' | 'knowledge' | 'life' | 'asset' | 'companion'

export interface DimensionTab {
  id: string
  label: string
  icon: string
  route: string
  optional?: boolean
}

export interface Dimension {
  id: DimensionId
  label: string
  icon: string
  defaultRoute: string
  tabs: DimensionTab[]
}

export const DIMENSIONS: Dimension[] = [
  {
    id: 'dashboard',
    label: '首页',
    icon: 'home',
    defaultRoute: '/dashboard',
    tabs: [],
  },
  {
    id: 'execution',
    label: '执行',
    icon: 'check',
    defaultRoute: '/tasks',
    tabs: [
      { id: 'tasks', label: '任务', icon: 'check', route: '/tasks' },
      { id: 'projects', label: '项目', icon: 'folder', route: '/projects' },
    ],
  },
  {
    id: 'knowledge',
    label: '知识',
    icon: 'doc',
    defaultRoute: '/documents',
    tabs: [
      { id: 'documents', label: '文档', icon: 'doc', route: '/documents' },
      { id: 'resources', label: '资源中心', icon: 'folder', route: '/resource-center' },
    ],
  },
  {
    id: 'life',
    label: '人生',
    icon: 'star',
    defaultRoute: '/identities',
    tabs: [
      { id: 'identities', label: '身份', icon: 'star', route: '/identities' },
      { id: 'experience', label: '经历', icon: 'clock', route: '/experience' },
      { id: 'growth', label: '成长', icon: 'award', route: '/growth' },
      { id: 'review', label: '复盘', icon: 'refresh', route: '/review' },
      { id: 'report', label: '报告', icon: 'doc', route: '/report' },
    ],
  },
  {
    id: 'asset',
    label: '资产',
    icon: 'book',
    defaultRoute: '/learning',
    tabs: [
      { id: 'learning', label: '学习', icon: 'book', route: '/learning' },
      { id: 'life-record', label: '生活', icon: 'heart', route: '/life' },
      { id: 'assets', label: '长期资产', icon: 'award', route: '/assets' },
      { id: 'workflows', label: '工作流', icon: 'workflow', route: '/workflows' },
    ],
  },
  {
    id: 'companion',
    label: '伙伴',
    icon: 'send',
    defaultRoute: '/conversation',
    tabs: [
      { id: 'assistant', label: 'AI 助理', icon: 'spark', route: '/assistant' },
      { id: 'conversation', label: '第二分身', icon: 'send', route: '/conversation' },
      { id: 'pet', label: '桌宠', icon: 'pet', route: '/pet' },
      { id: 'workspace', label: '工作区', icon: 'folder', route: '/workspace', optional: true },
      { id: 'vault', label: '保险箱', icon: 'command', route: '/vault' },
      { id: 'aihot', label: 'AI资讯', icon: 'spark', route: '/aihot' },
      { id: 'settings', label: '设置', icon: 'settings', route: '/settings' },
    ],
  },
]

export const ROUTE_TO_DIMENSION: Record<string, DimensionId> = {
  '/dashboard': 'dashboard',
  '/tasks': 'execution',
  '/projects': 'execution',
  '/documents': 'knowledge',
  '/resource-center': 'knowledge',
  '/identities': 'life',
  '/experience': 'life',
  '/growth': 'life',
  '/review': 'life',
  '/report': 'life',
  '/learning': 'asset',
  '/life': 'asset',
  '/assets': 'asset',
  '/workflows': 'asset',
  '/conversation': 'companion',
  '/assistant': 'companion',
  '/avatar': 'companion',
  '/pet': 'companion',
  '/workspace': 'companion',
  '/vault': 'companion',
  '/aihot': 'companion',
  '/settings': 'companion',
}

export function getDimensionByRoute(path: string): Dimension | undefined {
  if (ROUTE_TO_DIMENSION[path]) {
    return DIMENSIONS.find(d => d.id === ROUTE_TO_DIMENSION[path])
  }
  for (const [routePrefix, dimId] of Object.entries(ROUTE_TO_DIMENSION)) {
    if (path.startsWith(routePrefix + '/')) {
      return DIMENSIONS.find(d => d.id === dimId)
    }
  }
  return undefined
}

export const MAIN_NAV_ITEMS: NavItem[] = DIMENSIONS.map(d => ({
  id: d.id,
  label: d.label,
  icon: d.icon,
  route: d.defaultRoute,
}))