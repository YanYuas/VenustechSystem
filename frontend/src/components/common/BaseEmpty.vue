<script setup lang="ts">
// ============================================================
// I07 BaseEmpty —— 空状态（云朵 + 瞌睡小猫头鹰插画）
// 依据: docs/design/03-UI组件index.md §10 I07 + §0.5 插画语言
// 治愈话术示例: 任务="还没有任务，去创建第一个吧"
// ============================================================
import AppIcon from './AppIcon.vue'

withDefaults(defineProps<{
  title?: string
  description?: string
  icon?: string
}>(), {
  title: '',
  description: '',
  icon: 'cloud',
})
</script>

<template>
  <div class="empty">
    <div class="empty__art">
      <AppIcon class="empty__cloud empty__cloud--back" name="cloud" :size="56" />
      <div class="empty__owl">
        <AppIcon name="owl" :size="40" />
        <span class="empty__zzz">
          <i>z</i><i>z</i><i>z</i>
        </span>
      </div>
      <AppIcon class="empty__cloud empty__cloud--front" name="cloud" :size="28" />
    </div>
    <p v-if="title" class="empty__title">{{ title }}</p>
    <p v-if="description" class="empty__desc">{{ description }}</p>
    <div v-if="$slots.default || $slots.action" class="empty__action">
      <slot name="action">
        <slot />
      </slot>
    </div>
  </div>
</template>

<style scoped lang="scss">
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-8) var(--space-5);
  text-align: center;

  &__art {
    position: relative;
    width: 120px;
    height: 80px;
    color: var(--lilac);
  }
  &__cloud {
    position: absolute;
    color: var(--lilac);
    opacity: 0.6;
    animation: floaty 6s ease-in-out infinite;
    &--back { top: 0; left: 4px; }
    &--front { bottom: 4px; right: 4px; color: var(--primary); opacity: 0.5; animation-delay: -3s; }
  }
  &__owl {
    position: absolute;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    color: var(--text-mid);
    animation: floaty 5s ease-in-out infinite;
  }
  &__zzz {
    position: absolute;
    top: -10px;
    right: -18px;
    display: flex;
    flex-direction: column;
    color: var(--lilac-ink);
    font-family: var(--font-cute);
    i {
      font-style: normal;
      opacity: 0.7;
      &:nth-child(1) { font-size: 10px; animation: floaty 3s ease-in-out infinite; }
      &:nth-child(2) { font-size: 13px; animation: floaty 3s ease-in-out infinite -1s; }
      &:nth-child(3) { font-size: 16px; animation: floaty 3s ease-in-out infinite -2s; }
    }
  }

  &__title {
    font-family: var(--font-cute);
    font-size: var(--text-md);
    font-weight: 600;
    color: var(--text-mid);
  }
  &__desc {
    font-size: var(--text-base);
    color: var(--text-low);
    max-width: 280px;
  }
  &__action {
    margin-top: var(--space-2);
  }
}
</style>
