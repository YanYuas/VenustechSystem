// ============================================================
// 路由 —— 依据技术架构 v2.0 §4.4
// 一期模块: 首页 / 项目 / 任务 / 知识 / 第二分身 / 复盘
// ============================================================
import {
  createRouter,
  createWebHashHistory,
  type RouterHistory,
  type RouteRecordRaw,
} from 'vue-router'
import DefaultLayout from '../layout/DefaultLayout.vue'
import { STORAGE_KEYS } from '@/shared/constants'
import { aiHotView } from '@/features/aihot'
import { assetLibraryView } from '@/features/asset'
import { assistantView } from '@/features/assistant'
import { avatarSettingsView } from '@/features/avatar'
import { conversationView } from '@/features/conversation'
import { dashboardView } from '@/features/dashboard'
import { documentExplorerView } from '@/features/document'
import { experienceView } from '@/features/experience'
import { growthView } from '@/features/growth'
import { identityView } from '@/features/identity'
import { learningView } from '@/features/learning'
import { lifeView } from '@/features/life'
import { projectListView, projectDetailView } from '@/features/project'
import { reportView } from '@/features/report'
import { resourceCenterView } from '@/features/resource'
import { reviewView } from '@/features/review'
import { settingsView } from '@/features/settings'
import { taskView } from '@/features/task'
import { vaultView } from '@/features/vault'
import { workflowView } from '@/features/workflow'
import { workspaceView, workspaceSetupView } from '@/features/workspace'
import { petSettingsView } from '@/features/pet'
// 领域页面按 ADR-0007 从 feature 的唯一公开出口取（懒加载入口，保持路由级分包）

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: DefaultLayout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'dashboard',
        component: dashboardView,
        meta: { icon: 'home', title: '首页', crumbs: ['首页'] },
      },
      {
        path: 'projects',
        name: 'projects',
        component: projectListView,
        meta: { icon: 'folder', title: '项目', crumbs: ['项目'] },
      },
      {
        path: 'projects/:id',
        name: 'project-detail',
        component: projectDetailView,
        meta: { icon: 'folder', title: '项目详情', crumbs: ['项目', '详情'], hidden: true },
      },
      {
        path: 'tasks',
        name: 'tasks',
        component: taskView,
        meta: { icon: 'check', title: '任务', crumbs: ['任务'] },
      },
      {
        path: 'documents',
        name: 'documents',
        component: documentExplorerView,
        meta: { icon: 'doc', title: '知识', crumbs: ['知识'] },
      },
      {
        path: 'conversation',
        name: 'conversation',
        component: conversationView,
        meta: { icon: 'send', title: '第二分身', crumbs: ['第二分身'] },
      },
      {
        path: 'review',
        name: 'review',
        component: reviewView,
        meta: { icon: 'refresh', title: '复盘', crumbs: ['复盘'] },
      },
      {
        path: 'resource-center',
        name: 'resource-center',
        component: resourceCenterView,
        meta: { icon: 'folder', title: '资源中心', crumbs: ['资源中心'], hidden: true },
      },
      {
        path: 'learning',
        name: 'learning',
        component: learningView,
        meta: { icon: 'book', title: '学习成长', crumbs: ['学习成长'], hidden: true },
      },
      {
        path: 'life',
        name: 'life',
        component: lifeView,
        meta: { icon: 'heart', title: '生活记录', crumbs: ['生活记录'], hidden: true },
      },
      {
        path: 'assets',
        name: 'assets',
        component: assetLibraryView,
        meta: { icon: 'award', title: '长期资产库', crumbs: ['长期资产库'], hidden: true },
      },
      {
        path: 'workflows',
        name: 'workflows',
        component: workflowView,
        meta: { icon: 'workflow', title: '工作流中心', crumbs: ['工作流中心'], hidden: true },
      },
      {
        path: 'avatar',
        name: 'avatar',
        component: avatarSettingsView,
        meta: { icon: 'robot', title: '第二分身', crumbs: ['第二分身'], hidden: true },
      },
      {
        path: 'pet',
        name: 'pet',
        component: petSettingsView,
        meta: { icon: 'pet', title: '桌宠设置', crumbs: ['桌宠设置'], hidden: true },
      },
      {
        path: 'growth',
        name: 'growth',
        component: growthView,
        meta: { icon: 'spark', title: '成长体系', crumbs: ['成长体系'], hidden: true },
      },
      {
        path: 'identities',
        name: 'identities',
        component: identityView,
        meta: { icon: 'star', title: '身份管理', crumbs: ['身份管理'], hidden: true },
      },
      {
        path: 'experience',
        name: 'experience',
        component: experienceView,
        meta: { icon: 'book', title: '经历时间线', crumbs: ['经历时间线'], hidden: true },
      },
      {
        path: 'workspace',
        name: 'workspace',
        component: workspaceView,
        // 工作区是可选功能（三期规划 §5.0）：入口由 TopNav 按 enabled
        // 状态条件渲染，不进静态导航
        meta: { icon: 'folder', title: '工作区', crumbs: ['工作区'], hidden: true },
      },
      {
        path: 'workspace/setup',
        name: 'workspace-setup',
        component: workspaceSetupView,
        meta: {
          icon: 'spark',
          title: '工作区引导',
          crumbs: ['工作区', '引导设置'],
          hidden: true,
        },
      },
      {
        path: 'report',
        name: 'report',
        component: reportView,
        meta: { icon: 'doc', title: '人生报告', crumbs: ['人生报告'], hidden: true },
      },
      {
        path: 'vault',
        name: 'vault',
        component: vaultView,
        meta: { icon: 'command', title: '保险箱', crumbs: ['保险箱'], hidden: true },
      },
      {
        path: 'aihot',
        name: 'aihot',
        component: aiHotView,
        meta: { icon: 'spark', title: 'AI 资讯', crumbs: ['AI 资讯'], hidden: true },
      },
      {
        path: 'assistant',
        name: 'assistant',
        component: assistantView,
        meta: { icon: 'spark', title: 'AI 助理', crumbs: ['AI 助理'], hidden: true },
      },
      {
        path: 'settings',
        name: 'settings',
        component: settingsView,
        meta: { icon: 'setting', title: '设置', crumbs: ['设置'], hidden: true },
      },
    ],
  },
  // 404 兜底
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('../views/NotFoundView.vue'),
    meta: { title: '页面未找到', hidden: true },
  },
]

/**
 * 创建应用路由实例。
 *
 * 默认使用 hash history（生产入口）；测试可注入 `createMemoryHistory()`，
 * 既避免污染真实 location，也让「启动恢复 lastRoute」的状态（restored）
 * 成为每个实例私有的闭包变量，用例之间天然隔离。
 */
export function createAppRouter(history: RouterHistory = createWebHashHistory()) {
  const router = createRouter({
    history,
    // 路由切换滚动行为：保存滚动位置，新路由回到顶部
    scrollBehavior(to, _from, savedPosition) {
      if (savedPosition) return savedPosition
      if (to.hash) return { el: to.hash, behavior: 'smooth' }
      return { top: 0 }
    },
    routes,
  })

  // 启动时恢复最后访问的路由（每个 router 实例只恢复一次）
  let restored = false
  router.beforeEach((to, _from, next) => {
    if (!restored && to.path === '/dashboard') {
      restored = true
      try {
        const last = localStorage.getItem(STORAGE_KEYS.lastRoute)
        if (last && last !== '/dashboard') {
          // 只恢复**仍然有效**的路径：解析成 not-found / 无匹配记录的一律丢弃。
          // 否则访问过一次不存在的路由后，每次从根路径启动都会被重定向回 404。
          const resolved = router.resolve(last)
          const isKnownRoute =
            last.startsWith('/') &&
            resolved.name !== 'not-found' &&
            resolved.matched.length > 0 &&
            !resolved.matched.some((r) => r.name === 'not-found')
          if (isKnownRoute) {
            next(last)
            return
          }
          localStorage.removeItem(STORAGE_KEYS.lastRoute)
        }
      } catch {
        /* ignore */
      }
    }
    restored = true
    next()
  })

  router.afterEach((to) => {
    const title = (to.meta.title as string) ?? '启明星'
    document.title = `${title} · 启明星`
    // 记录最后访问路由：404 不落盘 —— 未知路径不是"上次访问的页面"，
    // 持久化后会在下次启动时把用户弹回 404。
    if (to.name === 'not-found') return
    try {
      localStorage.setItem(STORAGE_KEYS.lastRoute, to.fullPath)
    } catch {
      /* ignore */
    }
  })

  return router
}

const router = createAppRouter()

export default router
