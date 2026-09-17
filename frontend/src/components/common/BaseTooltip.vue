<script setup lang="ts">
// ============================================================
// I13 BaseTooltip —— 工具提示（hover 延迟 300ms）
// 依据: docs/design/03-UI组件index.md §10 I13
// 用法: <BaseTooltip content="说明"><button>H</button></BaseTooltip>
// ============================================================
import { onBeforeUnmount, ref } from 'vue'

withDefaults(defineProps<{
  content: string
  placement?: 'top' | 'bottom' | 'left' | 'right'
  /** 禁用（如 disabled 按钮不触发） */
  disabled?: boolean
}>(), {
  content: '',
  placement: 'top',
  disabled: false,
})

const visible = ref(false)
let timer: number | null = null

function show() {
  if (timer) window.clearTimeout(timer)
  timer = window.setTimeout(() => (visible.value = true), 300)
}
function hide() {
  if (timer) window.clearTimeout(timer)
  visible.value = false
}
onBeforeUnmount(() => {
  if (timer) window.clearTimeout(timer)
})
</script>

<template>
  <span class="tip" @mouseenter="show" @mouseleave="hide" @focus="show" @blur="hide">
    <slot />
    <Transition name="tip">
      <span v-if="visible && content && !disabled" class="tip__bubble" :class="`tip__bubble--${placement}`">
        {{ content }}
      </span>
    </Transition>
  </span>
</template>

<style scoped lang="scss">
.tip {
  position: relative;
  display: inline-flex;
  cursor: default;

  &__bubble {
    position: absolute;
    z-index: 150;
    max-width: 240px;
    padding: 6px 10px;
    background: var(--text-hi);
    color: var(--bg-cream);
    font-size: var(--text-sm);
    line-height: 1.4;
    border-radius: var(--radius-sm);
    white-space: nowrap;
    pointer-events: none;

    &::after {
      content: '';
      position: absolute;
      border: 5px solid transparent;
    }

    &--top { bottom: calc(100% + 6px); left: 50%; transform: translateX(-50%);
      &::after { top: 100%; left: 50%; margin-left: -5px; border-top-color: var(--text-hi); }
    }
    &--bottom { top: calc(100% + 6px); left: 50%; transform: translateX(-50%);
      &::after { bottom: 100%; left: 50%; margin-left: -5px; border-bottom-color: var(--text-hi); }
    }
    &--left { right: calc(100% + 6px); top: 50%; transform: translateY(-50%);
      &::after { left: 100%; top: 50%; margin-top: -5px; border-left-color: var(--text-hi); }
    }
    &--right { left: calc(100% + 6px); top: 50%; transform: translateY(-50%);
      &::after { right: 100%; top: 50%; margin-top: -5px; border-right-color: var(--text-hi); }
    }
  }
}
</style>

<style lang="scss">
.tip-enter-active,
.tip-leave-active {
  transition: opacity 0.15s var(--ease-soft);
}
.tip-enter-from,
.tip-leave-to {
  opacity: 0;
}
</style>
