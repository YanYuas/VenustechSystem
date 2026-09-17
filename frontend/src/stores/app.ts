// ============================================================
// 全局 UI 态 store —— 侧边栏折叠 / 全局加载
// 主题态由 composables/useTheme 独立管理，此处不重复
// 依据: 技术架构 v2.0 §4.3
// ============================================================
import { defineStore } from 'pinia'
import { STORAGE_KEYS } from '@/constants'

export const useAppStore = defineStore('app', {
  state: () => ({
    sidebarCollapsed: loadSidebar(),
    globalLoading: false,
  }),
  actions: {
    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed
      try {
        localStorage.setItem(STORAGE_KEYS.sidebarCollapsed, String(this.sidebarCollapsed))
      } catch { /* ignore */ }
    },
    setSidebar(collapsed: boolean) {
      this.sidebarCollapsed = collapsed
    },
    setGlobalLoading(v: boolean) {
      this.globalLoading = v
    },
  },
})

function loadSidebar(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEYS.sidebarCollapsed) === 'true'
  } catch {
    return false
  }
}
