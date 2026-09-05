<script setup lang="ts">
// ============================================================
// TopNav —— 顶部水平导航栏（固定）
// 对齐参考UI：Logo + 水平导航标签 + 搜索 + 通知 + 头像
// 导航标签：首页 / 今天 / 项目 / 学习 / 工作台 / 复盘
// 通知：对接真实通知API，下拉面板展示列表
// ============================================================
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from '@/components/common/AppIcon.vue'
import { useNotification } from '@/composables/useNotification'
import type { NavItem } from '@/types/common'
import type { NotificationType } from '@/types'

const route = useRoute()
const router = useRouter()

const emit = defineEmits<{
  (e: 'open-search'): void
  (e: 'open-user-menu'): void
}>()

const { notifications, unreadCount, fetchList, markRead, markAllRead } = useNotification()
const notifOpen = ref(false)

// 顶部水平导航（对齐参考UI 6个标签）
const navItems: NavItem[] = [
  { id: 'dashboard', label: '首页', icon: 'home', route: '/dashboard' },
  { id: 'today', label: '今天', icon: 'calendar', route: '/tasks' },
  { id: 'projects', label: '项目', icon: 'folder', route: '/projects' },
  { id: 'learning', label: '学习', icon: 'book', route: '/documents' },
  { id: 'workbench', label: '工作台', icon: 'send', route: '/conversation' },
  { id: 'review', label: '复盘', icon: 'refresh', route: '/review' },
]

// 当前激活的导航项（根据路由路径匹配）
const activeId = computed(() => {
  const path = route.path
  if (path.startsWith('/dashboard')) return 'dashboard'
  if (path.startsWith('/projects')) return 'projects'
  if (path.startsWith('/tasks')) return 'today'
  if (path.startsWith('/documents')) return 'learning'
  if (path.startsWith('/conversation')) return 'workbench'
  if (path.startsWith('/review')) return 'review'
  return ''
})

function onNav(item: NavItem) {
  if (item.route) router.push(item.route)
}

const TYPE_ICON: Record<NotificationType, string> = {
  info: 'bell',
  success: 'check',
  warning: 'warning',
  error: 'error',
}

const TYPE_TONE: Record<NotificationType, string> = {
  info: 'var(--sky)',
  success: 'var(--mint)',
  warning: 'var(--gold)',
  error: 'var(--strawberry)',
}

function formatTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const min = Math.floor(diff / 60000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min}分钟前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}小时前`
  return `${Math.floor(hr / 24)}天前`
}

watch(notifOpen, (open) => {
  if (open) fetchList(false, 1, 20)
})

// 通知类型 → 路由映射
const NOTIF_ROUTE: Record<string, string> = {
  task: '/tasks',
  document: '/documents',
  conversation: '/conversation',
  review: '/review',
  system: '/settings',
  reminder: '/tasks',
}

function handleNotifClick(n: { id: string; is_read: boolean; type: string; related_id?: string }) {
  if (!n.is_read) markRead(n.id, true)
  notifOpen.value = false
  const route = NOTIF_ROUTE[n.type]
  if (route) router.push(route)
}
</script>

<template>
  <header class="topnav">
    <!-- Logo 区 -->
    <div class="topnav__brand">
      <div class="topnav__logo">
        <AppIcon name="spark" :size="20" />
      </div>
      <div class="topnav__brand-text">
        <span class="topnav__brand-name">Venustech System</span>
        <span class="topnav__brand-sub">启明星 · Personal OS</span>
      </div>
    </div>

    <!-- 水平导航标签 -->
    <nav class="topnav__nav">
      <button
        v-for="item in navItems"
        :key="item.id"
        class="topnav__item"
        :class="{ 'is-active': item.id === activeId }"
        type="button"
        @click="onNav(item)"
      >
        <AppIcon :name="item.icon ?? 'dot'" :size="16" />
        <span>{{ item.label }}</span>
      </button>
    </nav>

    <!-- 右侧操作区 -->
    <div class="topnav__actions">
      <!-- 搜索框 -->
      <button class="topnav__search" @click="emit('open-search')">
        <AppIcon name="search" :size="16" />
        <span class="topnav__search-placeholder">搜索任务、项目、笔记、资源...</span>
        <kbd class="topnav__search-kbd">⌘K</kbd>
      </button>

      <!-- 通知 -->
      <div class="topnav__notif">
        <button class="topnav__icon-btn" title="通知" @click="notifOpen = !notifOpen">
          <AppIcon name="bell" :size="18" />
          <span v-if="unreadCount > 0" class="topnav__badge" />
        </button>
        <Transition name="drop">
          <div v-if="notifOpen" class="topnav__notif-panel">
            <div class="topnav__notif-header">
              <p class="topnav__notif-title">通知</p>
              <button v-if="unreadCount > 0" class="topnav__notif-readall" @click="markAllRead">全部已读</button>
            </div>
            <ul v-if="notifications.length > 0" class="topnav__notif-list">
              <li
                v-for="n in notifications"
                :key="n.id"
                class="topnav__notif-item"
                :class="{ 'is-read': n.is_read }"
                @click="handleNotifClick(n)"
              >
                <span class="topnav__notif-icon" :style="{ color: TYPE_TONE[n.type] }">
                  <AppIcon :name="TYPE_ICON[n.type]" :size="16" />
                </span>
                <div class="topnav__notif-body">
                  <p class="topnav__notif-text">{{ n.title }}</p>
                  <p v-if="n.content" class="topnav__notif-content">{{ n.content }}</p>
                  <span class="topnav__notif-time">{{ formatTime(n.created_at) }}</span>
                </div>
              </li>
            </ul>
            <div v-else class="topnav__notif-empty">
              <AppIcon name="bell" :size="32" />
              <p>暂无通知</p>
            </div>
          </div>
        </Transition>
      </div>

      <!-- 用户头像 -->
      <button class="topnav__avatar" title="用户菜单" @click="emit('open-user-menu')">
        <AppIcon name="user" :size="20" />
      </button>
    </div>
  </header>
</template>

<style scoped lang="scss">
.topnav {
  display: flex;
  align-items: center;
  height: 56px;
  padding: 0 var(--space-4);
  background: var(--bg-panel);
  border-bottom: 1px solid var(--line);
  flex-shrink: 0;
  gap: var(--space-4);
}

/* Logo */
.topnav__brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}
.topnav__logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--primary), var(--lilac));
  color: var(--white);
  box-shadow: var(--glow);
}
.topnav__brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}
.topnav__brand-name {
  font-size: var(--text-sm);
  font-weight: 700;
  color: var(--text-hi);
  font-family: var(--font-cute);
}
.topnav__brand-sub {
  font-size: 10px;
  color: var(--text-low);
}

/* 水平导航 */
.topnav__nav {
  display: flex;
  align-items: center;
  gap: 2px;
  flex: 1;
  justify-content: center;
}
.topnav__item {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  height: 36px;
  padding: 0 var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-family: var(--font-cute);
  color: var(--text-mid);
  transition: all 0.2s var(--ease-soft);

  &:hover {
    background: var(--bg-inset);
    color: var(--text-hi);
  }

  &.is-active {
    color: var(--primary);
    background: var(--primary-soft);
    font-weight: 600;

    &::after {
      content: '';
      position: absolute;
      bottom: -10px;
      left: 50%;
      transform: translateX(-50%);
      width: 24px;
      height: 3px;
      border-radius: var(--radius-pill) var(--radius-pill) 0 0;
      background: var(--primary);
    }
  }
}

/* 右侧操作区 */
.topnav__actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

/* 搜索框 */
.topnav__search {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 280px;
  height: 34px;
  padding: 0 var(--space-3);
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--bg-body);
  color: var(--text-low);
  transition: all 0.2s var(--ease-soft);

  &:hover {
    border-color: var(--primary);
    background: var(--bg-panel);
  }
}
.topnav__search-placeholder {
  flex: 1;
  font-size: var(--text-xs);
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.topnav__search-kbd {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--bg-inset);
  color: var(--text-low);
  font-family: var(--font-mono, monospace);
}

/* 图标按钮 */
.topnav__icon-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: var(--radius-md);
  color: var(--text-mid);
  transition: all 0.2s var(--ease-soft);

  &:hover {
    background: var(--bg-inset);
    color: var(--text-hi);
  }
}
.topnav__badge {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--strawberry);
  border: 2px solid var(--bg-panel);
}

/* 通知下拉面板 */
.topnav__notif {
  position: relative;
}
.topnav__notif-panel {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 200;
  width: 340px;
  max-height: 420px;
  display: flex;
  flex-direction: column;
  padding: var(--space-3);
  background: var(--bg-raised);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-raise);
  animation: gudu 0.3s var(--ease-spring);
}
.topnav__notif-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-2) var(--space-2);
}
.topnav__notif-title {
  font-family: var(--font-cute);
  font-weight: 600;
  font-size: var(--text-base);
  color: var(--text-hi);
}
.topnav__notif-readall {
  font-size: var(--text-xs);
  color: var(--primary);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  &:hover { background: var(--bg-inset); }
}
.topnav__notif-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.topnav__notif-item {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-2);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.15s;
  &:hover { background: var(--bg-inset); }
  &.is-read { opacity: 0.55; }
}
.topnav__notif-icon {
  flex-shrink: 0;
  margin-top: 2px;
}
.topnav__notif-body {
  flex: 1;
  min-width: 0;
}
.topnav__notif-text {
  font-size: var(--text-sm);
  color: var(--text-hi);
  line-height: 1.4;
}
.topnav__notif-content {
  font-size: var(--text-xs);
  color: var(--text-mid);
  line-height: 1.3;
  margin-top: 2px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.topnav__notif-time {
  font-size: 10px;
  color: var(--text-low);
  margin-top: 4px;
  display: block;
}
.topnav__notif-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-8) var(--space-2);
  color: var(--text-low);
  font-size: var(--text-sm);
}

/* 用户头像 */
.topnav__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary-soft), var(--lilac-soft));
  color: var(--primary);
  border: 2px solid var(--line);
  transition: all 0.2s var(--ease-soft);

  &:hover {
    border-color: var(--primary);
    box-shadow: var(--glow);
  }
}
</style>

<style lang="scss">
.drop-enter-active,
.drop-leave-active {
  transition: opacity 0.2s var(--ease-soft), transform 0.2s var(--ease-soft);
  transform-origin: top right;
}
.drop-enter-from,
.drop-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.98);
}
</style>
