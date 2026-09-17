<script setup lang="ts">
// ============================================================
// A02 AppSidebar —— 侧边栏导航（可折叠 220px ↔ 64px）
// 依据: docs/design/03-UI组件index.md §2 A02
// 视觉: 导航项高44 激活态 primary-soft 背景 + 3px竖条 + glow 微辉光
// 动效: 宽度切换 300ms ease-soft；激活项咕嘟弹入
// ============================================================
import AppIcon from '@/components/common/AppIcon.vue'
import BaseTooltip from '@/components/common/BaseTooltip.vue'
import type { NavItem } from '@/types/common'

const props = withDefaults(defineProps<{
  items?: NavItem[]
  activeId?: string
  collapsed?: boolean
  appName?: string
}>(), {
  items: () => [],
  activeId: '',
  collapsed: false,
  appName: '启明星',
})

const emit = defineEmits<{
  (e: 'update:collapsed', v: boolean): void
  (e: 'select', item: NavItem): void
}>()

function toggle() {
  emit('update:collapsed', !props.collapsed)
}
</script>

<template>
  <aside class="sidebar" :class="{ 'is-collapsed': collapsed }">
    <!-- Logo -->
    <div class="sidebar__logo">
      <div class="sidebar__logo-icon">
        <AppIcon name="spark" :size="22" />
      </div>
      <Transition name="fade-slide">
        <span v-if="!collapsed" class="sidebar__logo-name">{{ appName }}</span>
      </Transition>
    </div>

    <!-- 折叠按钮（220 宽时在底部，64 时在顶部；统一放此处便于演示） -->
    <div class="sidebar__fold-ctrl">
      <Transition name="fade-slide">
        <span v-if="!collapsed" class="sidebar__fold-label">收起导航</span>
      </Transition>
      <button
        class="sidebar__fold-btn"
        type="button"
        :aria-label="collapsed ? '展开导航' : '收起导航'"
        @click="toggle"
      >
        <AppIcon :name="collapsed ? 'chevron-right' : 'chevron-left'" :size="18" />
      </button>
    </div>

    <!-- 导航 -->
    <nav class="sidebar__nav">
      <BaseTooltip
        v-for="item in items"
        :key="item.id"
        :content="collapsed ? item.label : ''"
        placement="right"
        :disabled="!collapsed"
      >
        <button
          class="sidebar__item"
          :class="{ 'is-active': item.id === activeId }"
          type="button"
          @click="emit('select', item)"
        >
          <span class="sidebar__item-icon">
            <AppIcon :name="item.icon ?? 'dot'" :size="20" />
            <span v-if="item.badge" class="sidebar__item-badge">{{ item.badge }}</span>
          </span>
          <Transition name="fade-slide">
            <span v-if="!collapsed" class="sidebar__item-label">{{ item.label }}</span>
          </Transition>
        </button>
      </BaseTooltip>
    </nav>

    <div class="sidebar__foot">
      <slot name="footer" />
    </div>
  </aside>
</template>

<style scoped lang="scss">
.sidebar {
  position: relative;
  display: flex;
  flex-direction: column;
  width: 220px;
  background: var(--bg-panel);
  border-right: 1px solid var(--line);
  transition: width 0.3s var(--ease-soft);

  &.is-collapsed {
    width: 64px;
    .sidebar__logo-name,
    .sidebar__item-label,
    .sidebar__fold-label {
      display: none;
    }
    .sidebar__item {
      justify-content: center;
      padding: 0;
    }
    .sidebar__logo {
      justify-content: center;
      padding: 0;
    }
    .sidebar__fold-ctrl {
      justify-content: center;
      padding: 0 var(--space-2);
    }
  }

  &__logo {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    height: 56px;
    padding: 0 var(--space-4);
    border-bottom: 1px solid var(--line);
  }
  &__logo-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 34px;
    height: 34px;
    border-radius: var(--radius-md);
    background: linear-gradient(135deg, var(--primary), var(--lilac));
    color: var(--white);
    box-shadow: var(--glow);
    flex-shrink: 0;
  }
  &__logo-name {
    font-family: var(--font-cute);
    font-size: var(--text-lg);
    font-weight: 700;
    color: var(--text-hi);
    white-space: nowrap;
  }

  &__fold-ctrl {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: var(--space-2);
    height: 40px;
    padding: 0 var(--space-4);
    border-bottom: 1px solid var(--line);
  }
  &__fold-label {
    font-size: var(--text-xs);
    color: var(--text-low);
  }
  &__fold-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: var(--radius-sm);
    color: var(--text-mid);
    transition: background-color 0.2s var(--ease-soft), color 0.2s var(--ease-soft);
    &:hover {
      background: var(--bg-inset);
      color: var(--primary);
    }
  }

  &__nav {
    flex: 1;
    overflow-y: auto;
    padding: var(--space-3) var(--space-2);
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  &__item {
    position: relative;
    display: flex;
    align-items: center;
    gap: var(--space-3);
    height: 44px;
    padding: 0 var(--space-3);
    border-radius: var(--radius-sm);
    font-size: var(--text-md);
    font-family: var(--font-cute);
    color: var(--text-mid);
    transition: background-color 0.2s var(--ease-soft), color 0.2s var(--ease-soft),
      box-shadow 0.25s var(--ease-soft);
    &:hover {
      background: var(--bg-inset);
      color: var(--text-hi);
    }
    &.is-active {
      background: var(--primary-soft);
      color: var(--primary);
      box-shadow: var(--glow);
      animation: gudu 0.45s var(--ease-spring);
      &::before {
        content: '';
        position: absolute;
        left: 0;
        top: 50%;
        transform: translateY(-50%);
        width: 3px;
        height: 20px;
        border-radius: var(--radius-pill);
        background: var(--primary);
      }
    }
  }
  &__item-icon {
    position: relative;
    display: inline-flex;
    flex-shrink: 0;
  }
  &__item-badge {
    position: absolute;
    top: -6px;
    right: -8px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 16px;
    height: 16px;
    padding: 0 4px;
    border-radius: var(--radius-pill);
    background: var(--strawberry);
    color: var(--white);
    font-family: var(--font-cute);
    font-size: 10px;
  }
  &__item-label {
    white-space: nowrap;
  }

  &__foot {
    border-top: 1px solid var(--line);
  }
}
</style>

<style lang="scss">
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: opacity 0.2s var(--ease-soft), transform 0.2s var(--ease-soft);
}
.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateX(-6px);
}
</style>
