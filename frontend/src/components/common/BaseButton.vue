<script setup lang="ts">
// ============================================================
// I01 BaseButton —— 按钮（主/次/文字/危险/胶囊）
// 依据: docs/design/03-UI组件index.md §10 I01
// 状态: hover / active(scale .96 果冻) / disabled / loading
// 尺寸: sm(32) / md(40) / lg(48)
// ============================================================
import { computed } from 'vue'
import AppIcon from './AppIcon.vue'
import type { ButtonVariant, CompSize } from '@/types/common'

const props = withDefaults(defineProps<{
  variant?: ButtonVariant
  size?: CompSize
  disabled?: boolean
  loading?: boolean
  /** loading 时替换的文字，默认保留 children */
  loadingText?: string
  icon?: string
  block?: boolean
  type?: 'button' | 'submit' | 'reset'
}>(), {
  variant: 'primary',
  size: 'md',
  disabled: false,
  loading: false,
  loadingText: '',
  block: false,
  type: 'button',
})

const emit = defineEmits<{
  (e: 'click', ev: MouseEvent): void
}>()

const classes = computed(() => [
  `btn--${props.variant}`,
  `btn--${props.size}`,
  { 'btn--block': props.block, 'is-disabled': props.disabled, 'is-loading': props.loading },
])

function onClick(ev: MouseEvent) {
  if (props.disabled || props.loading) return
  emit('click', ev)
}
</script>

<template>
  <button
    class="btn"
    :class="classes"
    :type="type"
    :disabled="disabled || loading"
    @click="onClick"
  >
    <span v-if="loading" class="btn__icon is-spin">
      <AppIcon name="spin" :size="size === 'sm' ? 14 : size === 'lg' ? 20 : 16" />
    </span>
    <span v-else-if="icon" class="btn__icon">
      <AppIcon :name="icon" :size="size === 'sm' ? 14 : size === 'lg' ? 20 : 16" />
    </span>
    <span class="btn__label">
      <slot>{{ loading && loadingText ? loadingText : '' }}</slot>
    </span>
  </button>
</template>

<style scoped lang="scss">
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  border-radius: var(--radius-sm);
  font-family: var(--font-cute);
  font-weight: 500;
  white-space: nowrap;
  user-select: none;
  transition: transform 0.25s var(--ease-spring), box-shadow 0.25s var(--ease-soft),
    background-color 0.25s var(--ease-soft), color 0.25s var(--ease-soft),
    border-color 0.25s var(--ease-soft), opacity 0.25s var(--ease-soft);

  &--sm {
    height: var(--control-h-sm);
    padding: 0 var(--space-3);
    font-size: var(--text-sm);
  }
  &--md {
    height: var(--control-h);
    padding: 0 var(--space-5);
    font-size: var(--text-base);
  }
  &--lg {
    height: var(--control-h-lg);
    padding: 0 var(--space-6);
    font-size: var(--text-md);
  }
  &--block {
    display: flex;
    width: 100%;
  }

  &__icon {
    display: inline-flex;
    align-items: center;
    &.is-spin svg {
      animation: spin 0.8s linear infinite;
    }
  }
  &__label {
    display: inline-flex;
    align-items: center;
    line-height: 1;
  }

  // 主按钮
  &--primary {
    background: var(--primary);
    color: var(--on-primary);
    &:hover:not(.is-disabled) {
      box-shadow: var(--glow);
      filter: brightness(1.04);
    }
  }
  // 次按钮
  &--secondary {
    background: var(--bg-panel);
    border: 1px solid var(--line);
    color: var(--text-hi);
    &:hover:not(.is-disabled) {
      border-color: var(--primary);
      color: var(--primary);
    }
  }
  // 文字按钮
  &--text {
    background: transparent;
    color: var(--primary);
    &:hover:not(.is-disabled) {
      background: var(--bg-inset);
    }
  }
  // 危险按钮
  &--danger {
    background: var(--strawberry);
    color: var(--white);
    &:hover:not(.is-disabled) {
      box-shadow: var(--shadow-danger);
      filter: brightness(1.04);
    }
  }
  // 胶囊
  &--pill {
    background: var(--bg-inset);
    color: var(--text-mid);
    border-radius: var(--radius-pill);
    &:hover:not(.is-disabled) {
      background: var(--primary-soft);
      color: var(--primary);
    }
  }

  &:active:not(.is-disabled):not(.is-loading) {
    transform: scale(0.96);
  }

  &.is-disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}
</style>
