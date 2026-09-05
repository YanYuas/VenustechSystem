<script setup lang="ts">
// ============================================================
// I08 BaseSkeleton —— 骨架屏（shimmer 扫过）
// 依据: docs/design/03-UI组件index.md §10 I08
// 变体: card(标题条+2行文本) / list(4行) / stats(大方块+小方块)
// ============================================================

const props = withDefaults(defineProps<{
  variant?: 'card' | 'list' | 'stats'
  rows?: number
}>(), {
  variant: 'card',
  rows: 4,
})

const listRows = Array.from({ length: Math.min(props.rows, 8) }, (_, i) => i)
</script>

<template>
  <div class="sk" :class="`sk--${variant}`">
    <!-- 卡片骨架 -->
    <template v-if="variant === 'card'">
      <div class="sk__bar sk__bar--title" />
      <div class="sk__bar sk__bar--line" />
      <div class="sk__bar sk__bar--line" />
    </template>

    <!-- 列表骨架 -->
    <template v-else-if="variant === 'list'">
      <div v-for="i in listRows" :key="i" class="sk__row">
        <div class="sk__dot" />
        <div class="sk__bar sk__bar--line" :style="{ width: `${80 - (i % 3) * 12}%` }" />
      </div>
    </template>

    <!-- 统计卡骨架 -->
    <template v-else>
      <div class="sk__big" />
      <div class="sk__small" />
    </template>
  </div>
</template>

<style scoped lang="scss">
.sk {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);

  &__bar,
  &__dot,
  &__big,
  &__small {
    position: relative;
    overflow: hidden;
    background: var(--bg-inset);
    border-radius: var(--radius-sm);
    &::after {
      content: '';
      position: absolute;
      inset: 0;
      background: linear-gradient(90deg, transparent, var(--bg-panel), transparent);
      animation: shimmer 1.5s infinite;
    }
  }

  &__bar {
    &--title { height: 18px; width: 55%; }
    &--line { height: 12px; width: 100%; }
  }

  &--list {
    gap: var(--space-4);
    .sk__row {
      display: flex;
      align-items: center;
      gap: var(--space-3);
    }
    .sk__dot {
      width: 16px;
      height: 16px;
      border-radius: var(--radius-pill);
      flex-shrink: 0;
    }
  }

  &--stats {
    .sk__big {
      width: 64px;
      height: 64px;
      border-radius: var(--radius-pill);
      align-self: center;
    }
    .sk__small {
      height: 12px;
      width: 60%;
      align-self: center;
    }
  }
}
</style>
