<script setup lang="ts">
// ============================================================
// A08 SidebarFooter —— 侧边栏底部（用户卡 + 设置入口）
// 依据: docs/design/03-UI组件index.md §2 A08
// 动效: 头像 hover scale(1.05) spring
// ============================================================
import AppIcon from '@/components/common/AppIcon.vue'

withDefaults(defineProps<{
  name?: string
  avatarText?: string
  collapsed?: boolean
}>(), {
  name: '旅人',
  avatarText: '启',
  collapsed: false,
})

const emit = defineEmits<{
  (e: 'open-user-menu'): void
  (e: 'open-settings'): void
}>()
</script>

<template>
  <div class="sfoot" :class="{ 'is-collapsed': collapsed }">
    <button class="sfoot__user" type="button" @click="emit('open-user-menu')">
      <span class="sfoot__avatar">{{ avatarText }}</span>
      <span v-if="!collapsed" class="sfoot__meta">
        <span class="sfoot__name">{{ name }}</span>
        <span class="sfoot__space">个人空间</span>
      </span>
    </button>
    <button
      class="sfoot__gear"
      type="button"
      aria-label="设置"
      @click="emit('open-settings')"
    >
      <AppIcon name="setting" :size="20" />
    </button>
  </div>
</template>

<style scoped lang="scss">
.sfoot {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  height: 64px;
  padding: 0 var(--space-3);
  border-top: 1px solid var(--line);

  &.is-collapsed {
    justify-content: center;
    flex-direction: column;
    gap: var(--space-1);
    padding: var(--space-2);
    .sfoot__gear {
      width: 100%;
      justify-content: center;
    }
  }

  &__user {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    flex: 1;
    min-width: 0;
    padding: var(--space-1);
    border-radius: var(--radius-sm);
    transition: background-color 0.2s var(--ease-soft);
    &:hover {
      background: var(--bg-inset);
    }
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
    flex-shrink: 0;
    transition: transform 0.25s var(--ease-spring);
  }
  &__user:hover &__avatar {
    transform: scale(1.05);
  }
  &__meta {
    display: flex;
    flex-direction: column;
    min-width: 0;
    text-align: left;
  }
  &__name {
    font-family: var(--font-cute);
    font-size: var(--text-base);
    color: var(--text-hi);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  &__space {
    font-size: var(--text-xs);
    color: var(--text-low);
  }
  &__gear {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border-radius: var(--radius-sm);
    color: var(--text-mid);
    flex-shrink: 0;
    transition: background-color 0.2s var(--ease-soft), color 0.2s var(--ease-soft),
      transform 0.2s var(--ease-spring);
    &:hover {
      background: var(--bg-inset);
      color: var(--primary);
      transform: rotate(20deg);
    }
  }
}
</style>
