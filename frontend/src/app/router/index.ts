// ============================================================
// 路由 —— 依据技术架构 v2.0 §4.4
// 一期模块: 首页 / 项目 / 任务 / 知识 / 第二分身 / 复盘
// ============================================================
import { createRouter, createWebHashHistory } from 'vue-router'
import DefaultLayout from '@/components/layout/DefaultLayout.vue'
import { STORAGE_KEYS } from '@/constants'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      component: DefaultLayout,
      redirect: '/dashboard',
      children: [
        {
          path: 'dashboard',
          name: 'dashboard',
          component: () => import('@/views/Dashboard/DashboardView.vue'),
          meta: { icon: 'home', title: '首页', crumbs: ['首页'] },
        },
        {
          path: 'projects',
          name: 'projects',
          component: () => import('@/views/Project/ProjectListView.vue'),
          meta: { icon: 'folder', title: '项目', crumbs: ['项目'] },
        },
        {
          path: 'projects/:id',
          name: 'project-detail',
          component: () => import('@/views/Project/ProjectDetailView.vue'),
          meta: { icon: 'folder', title: '项目详情', crumbs: ['项目', '详情'], hidden: true },
        },
        {
          path: 'tasks',
          name: 'tasks',
          component: () => import('@/views/Task/TaskListView.vue'),
          meta: { icon: 'check', title: '任务', crumbs: ['任务'] },
        },
        {
          path: 'documents',
          name: 'documents',
          component: () => import('@/views/Document/DocumentExplorerView.vue'),
          meta: { icon: 'doc', title: '知识', crumbs: ['知识'] },
        },
        {
          path: 'conversation',
          name: 'conversation',
          component: () => import('@/views/Conversation/ConversationView.vue'),
          meta: { icon: 'send', title: '第二分身', crumbs: ['第二分身'] },
        },
        {
          path: 'review',
          name: 'review',
          component: () => import('@/views/Review/ReviewView.vue'),
          meta: { icon: 'refresh', title: '复盘', crumbs: ['复盘'] },
        },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('@/views/Settings/SettingsView.vue'),
          meta: { icon: 'setting', title: '设置', crumbs: ['设置'], hidden: true },
        },
      ],
    },
    // 404 兜底
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFound/NotFoundView.vue'),
      meta: { title: '页面未找到', hidden: true },
    },
  ],
})

// 启动时恢复最后访问的路由
let restored = false
router.beforeEach((to, _from, next) => {
  if (!restored && to.path === '/dashboard') {
    restored = true
    try {
      const last = localStorage.getItem(STORAGE_KEYS.lastRoute)
      if (last && last !== '/dashboard') {
        next(last)
        return
      }
    } catch { /* ignore */ }
  }
  restored = true
  next()
})

router.afterEach((to) => {
  const title = (to.meta.title as string) ?? '启明星'
  document.title = `${title} · 启明星`
  // 记录最后访问路由
  try {
    localStorage.setItem(STORAGE_KEYS.lastRoute, to.fullPath)
  } catch { /* ignore */ }
})

export default router
