<script setup lang="ts">
// ============================================================
// A03 AppHeader —— 顶栏（面包屑 + 全局搜索 + 通知 + 头像）
// 依据: docs/design/03-UI组件index.md §2 A03
// 搜索: 胶囊 bg-inset 360px，focus 边框 primary + 建议面板咕嘟弹入
// 通知: 未读 ping 扩散点；点击展开下拉，对接真实通知API
// ============================================================
import { ref, watch } from 'vue'
import AppIcon from '@/components/common/AppIcon.vue'
import BaseBreadcrumb from './BaseBreadcrumb.vue'
import WindowStatusIndicator from './WindowStatusIndicator.vue'
import { useNotification } from '@/composables/useNotification'
import type { CrumbItem } from './BaseBreadcrumb.vue'
import type { NotificationType } from '@/types'

withDefaults(defineProps<{
  crumbs?: CrumbItem[]
  user?: { name: string; avatarText?: string }
}>(), {
  crumbs: () => [],
  user: () => ({ name: '旅人', avatarText: '启' }),
})

const emit = defineEmits<{
  (e: 'open-search'): void
  (e: 'open-notifications'): void
  (e: 'open-user-menu'): void
}>()

const searchFocused = ref(false)
const notifOpen = ref(false)
const { notifications, unreadCount, fetchList, markRead, markAllRead } = useNotification()

const SUGGESTIONS = ['今日焦点', '任务', '最近文档', '第二分身']

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

// 打开通知面板时拉取最新列表
watch(notifOpen, (open) => {
  if (open) fetchList(false, 1, 20)
})

function handleItemClick(id: string, isRead: boolean) {
  if (!isRead) markRead(id, true)
  notifOpen.value = false
}
</script>

<template>
  <header class="header">
    <BaseBreadcrumb :items="crumbs" />

    <!-- 全局搜索框 -->
    <div class="header__search" :class="{ 'is-focus': searchFocused }">
      <AppIcon name="search" :size="16" class="header__search-icon" />
      <input
        class="header__search-input"
        placeholder="搜索文档/任务/对话…"
        @focus="searchFocused = true; emit('open-search')"
        @blur="searchFocused = false"
      />
      <kbd class="header__search-kbd">⌘K</kbd>

      <!-- 建议面板 -->
      <Transition name="drop">
        <div v-if="searchFocused" class="header__search-panel" @mousedown.prevent>
          <p class="header__search-panel-title">最近搜索</p>
          <button
            v-for="s in SUGGESTIONS"
            :key="s"
            class="header__search-suggest"
            type="button"
            @click="emit('open-search')"
          >
            <AppIcon name="search" :size="14" />
            {{ s }}
          </button>
        </div>
      </Transition>
    </div>

    <div class="header__right">
      <WindowStatusIndicator status="saved" class="header__status" />

      <!-- 通知铃 -->
      <div class="header__notif">
        <button
          class="header__icon-btn"
          type="button"
          aria-label="通知"
          @click="notifOpen = !notifOpen"
        >
          <AppIcon name="bell" :size="20" />
          <span v-if="unreadCount > 0" class="header__notif-dot">
            <span class="header__notif-ping" />
          </span>
        </button>

        <Transition name="drop">
          <div v-if="notifOpen" class="header__notif-panel">
            <div class="header__notif-header">
              <p class="header__notif-title">通知</p>
              <button
                v-if="unreadCount > 0"
                class="header__notif-readall"
                type="button"
                @click="markAllRead"
              >全部已读</button>
            </div>
            <ul v-if="notifications.length > 0" class="header__notif-list">
              <li
                v-for="n in notifications"
                :key="n.id"
                class="header__notif-item"
                :class="{ 'is-read': n.is_read }"
                @click="handleItemClick(n.id, n.is_read)"
              >
                <span class="header__notif-item-icon" :style="{ color: TYPE_TONE[n.type] }">
                  <AppIcon :name="TYPE_ICON[n.type]" :size="16" />
                </span>
                <div class="header__notif-item-body">
                  <p class="header__notif-item-text">{{ n.title }}</p>
                  <p v-if="n.content" class="header__notif-item-content">{{ n.content }}</p>
                  <span class="header__notif-item-time">{{ formatTime(n.created_at) }}</span>
                </div>
              </li>
            </ul>
            <div v-else class="header__notif-empty">
              <AppIcon name="bell" :size="32" />
              <p>暂无通知</p>
            </div>
          </div>
        </Transition>
      </div>

      <!-- 头像 -->
      <button class="header__avatar" type="button" aria-label="用户菜单" @click="emit('open-user-menu')">
        {{ user?.avatarText ?? '启' }}
      </button>
    </div>
  </header>
</template>

<style scoped lang="scss">
.header {
  display: flex;
  align-items: center;
  gap: var(--space-5);
  height: 52px;
  padding: 0 var(--space-6);
  background: transparent;

  &__search {
    position: relative;
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 360px;
    max-width: 40vw;
    height: 36px;
    margin-left: auto;
    padding: 0 var(--space-3);
    background: var(--bg-inset);
    border: 1px solid transparent;
    border-radius: var(--radius-pill);
    transition: border-color 0.25s var(--ease-soft), background-color 0.25s var(--ease-soft),
      box-shadow 0.25s var(--ease-soft);

    &.is-focus {
      border-color: var(--primary);
      background: var(--bg-panel);
      box-shadow: var(--shadow-card);
    }
  }
  &__search-icon {
    color: var(--text-low);
    flex-shrink: 0;
  }
  &__search-input {
    flex: 1;
    min-width: 0;
    border: none;
    outline: none;
    background: transparent;
    font-size: var(--text-base);
    color: var(--text-hi);
    &::placeholder {
      color: var(--text-low);
    }
  }
  &__search-kbd {
    padding: 2px 6px;
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    background: var(--bg-panel);
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--text-low);
    flex-shrink: 0;
  }
  &__search-panel {
    position: absolute;
    top: calc(100% + var(--space-2));
    left: 0;
    right: 0;
    z-index: 120;
    padding: var(--space-2);
    background: var(--bg-raised);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-raise);
    animation: gudu 0.3s var(--ease-spring);
  }
  &__search-panel-title {
    padding: var(--space-1) var(--space-2);
    font-size: var(--text-xs);
    color: var(--text-low);
  }
  &__search-suggest {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    height: 36px;
    padding: 0 var(--space-2);
    border-radius: var(--radius-sm);
    font-size: var(--text-base);
    color: var(--text-mid);
    text-align: left;
    &:hover {
      background: var(--bg-inset);
      color: var(--text-hi);
    }
  }

  &__right {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }
  &__status {
    margin-right: var(--space-1);
  }

  &__notif {
    position: relative;
  }
  &__icon-btn {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border-radius: var(--radius-pill);
    color: var(--text-mid);
    transition: background-color 0.2s var(--ease-soft), color 0.2s var(--ease-soft),
      transform 0.2s var(--ease-spring);
    &:hover {
      background: var(--bg-inset);
      color: var(--primary);
      transform: scale(1.05);
    }
  }
  &__notif-dot {
    position: absolute;
    top: 7px;
    right: 8px;
    width: 8px;
    height: 8px;
    border-radius: var(--radius-pill);
    background: var(--strawberry);
  }
  &__notif-ping {
    position: absolute;
    inset: 0;
    border-radius: var(--radius-pill);
    background: var(--strawberry);
    animation: ping 1.6s cubic-bezier(0, 0, 0.2, 1) infinite;
  }
  &__notif-panel {
    position: absolute;
    top: calc(100% + var(--space-2));
    right: 0;
    z-index: 120;
    width: 320px;
    padding: var(--space-3);
    background: var(--bg-raised);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-raise);
    animation: gudu 0.3s var(--ease-spring);
  }
  &__notif-title {
    padding: var(--space-1) var(--space-2) var(--space-2);
    font-family: var(--font-cute);
    font-weight: 600;
    color: var(--text-hi);
  }
  &__notif-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  &__notif-readall {
    padding: var(--space-1) var(--space-2);
    font-size: var(--text-xs);
    color: var(--primary);
    border-radius: var(--radius-sm);
    &:hover { background: var(--bg-inset); }
  }
  &__notif-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-6) var(--space-2);
    color: var(--text-low);
    font-size: var(--text-sm);
  }
  &__notif-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  &__notif-item {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
    padding: var(--space-2);
    border-radius: var(--radius-sm);
    &.is-read {
      opacity: 0.55;
    }
  }
  &__notif-item-icon {
    display: inline-flex;
    margin-top: 2px;
    flex-shrink: 0;
  }
  &__notif-item-body {
    flex: 1;
    min-width: 0;
  }
  &__notif-item-text {
    font-size: var(--text-sm);
    color: var(--text-hi);
    line-height: 1.5;
  }
  &__notif-item-content {
    font-size: var(--text-xs);
    color: var(--text-mid);
    line-height: 1.4;
    margin-top: 2px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  &__notif-item-time {
    font-size: var(--text-xs);
    color: var(--text-low);
  }

  &__avatar {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border-radius: var(--radius-pill);
    background: linear-gradient(135deg, var(--primary), var(--lilac));
    color: var(--white);
    font-family: var(--font-cute);
    font-size: var(--text-md);
    box-shadow: var(--shadow-card);
    transition: transform 0.25s var(--ease-spring), box-shadow 0.25s var(--ease-soft);
    &:hover {
      transform: scale(1.05);
      box-shadow: var(--glow);
    }
  }
}
</style>

<style lang="scss">
.drop-enter-active,
.drop-leave-active {
  transition: opacity 0.2s var(--ease-soft), transform 0.2s var(--ease-soft);
  transform-origin: top;
}
.drop-enter-from,
.drop-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
