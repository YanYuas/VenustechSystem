<script setup lang="ts">
// ============================================================
// I10 BaseSwitch —— 开关（Toggle）
// 依据: docs/design/03-UI组件index.md §10 I10
// 动效: 圆点滑动 200ms spring + 开启果冻微弹
// ============================================================

const props = withDefaults(defineProps<{
  modelValue?: boolean
  disabled?: boolean
  label?: string
}>(), {
  modelValue: false,
  disabled: false,
  label: '',
})

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
}>()

function toggle() {
  if (props.disabled) return
  emit('update:modelValue', !props.modelValue)
}
</script>

<template>
  <button
    class="switch"
    :class="{ 'is-on': modelValue, 'is-disabled': disabled }"
    type="button"
    role="switch"
    :aria-checked="modelValue"
    :aria-label="label || undefined"
    @click="toggle"
  >
    <span class="switch__dot" />
  </button>
</template>

<style scoped lang="scss">
.switch {
  position: relative;
  display: inline-flex;
  align-items: center;
  width: 40px;
  height: 22px;
  border-radius: var(--radius-pill);
  background: var(--line);
  padding: 2px;
  transition: background-color 0.2s var(--ease-soft), box-shadow 0.2s var(--ease-soft);
  cursor: pointer;

  &__dot {
    width: 18px;
    height: 18px;
    border-radius: var(--radius-pill);
    background: var(--white);
    box-shadow: var(--dot-shadow);
    transition: transform 0.2s var(--ease-spring);
  }

  &.is-on {
    background: var(--primary);
    box-shadow: var(--glow);
    .switch__dot {
      transform: translateX(18px);
      animation: jelly-pop 0.25s var(--ease-spring);
    }
  }

  &.is-disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}
</style>
