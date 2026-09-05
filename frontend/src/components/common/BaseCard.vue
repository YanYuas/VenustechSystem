<script setup lang="ts">
// ============================================================
// I03 BaseCard —— 卡片容器
// 依据: docs/design/03-UI组件index.md §10 I03
// ============================================================

withDefaults(defineProps<{
  hoverable?: boolean
  /** padding 覆盖，默认 --space-4 */
  padding?: string
  /** 圆角覆盖，默认 --radius-md */
  radius?: string
  /** 卡片标题（可选，配合 #extra slot） */
  title?: string
  /** 内容区是否可滚动（用于一屏适配布局） */
  scroll?: boolean
}>(), {
  hoverable: false,
  padding: undefined,
  radius: undefined,
  title: '',
  scroll: false,
})
</script>

<template>
  <div class="card" :class="{ 'card--hoverable': hoverable, 'card--scroll': scroll }" :style="{ padding, borderRadius: radius }">
    <header v-if="title || $slots.title || $slots.extra" class="card__head">
      <slot name="title">
        <h3 class="card__title">{{ title }}</h3>
      </slot>
      <slot name="extra" />
    </header>
    <div v-if="scroll" class="card__body">
      <slot />
    </div>
    <slot v-else />
  </div>
</template>

<style scoped lang="scss">
.card {
  background: var(--bg-panel);
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  padding: var(--space-4);
  transition: transform 0.3s var(--ease-soft), box-shadow 0.3s var(--ease-soft);

  &--hoverable:hover {
    transform: translateY(-3px);
    box-shadow: var(--shadow-raise);
  }

  &__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-3);
    flex-shrink: 0;
  }
  &__title {
    font-size: var(--text-md);
    font-weight: 600;
    color: var(--text-hi);
  }
  &__body {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overflow-x: hidden;
  }

  /* scroll 模式：卡片撑满父容器，内容区滚动 */
  &--scroll {
    height: 100%;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
}
</style>
