<script setup lang="ts">
// ============================================================
// I02 BaseInput —— 输入框（文本/搜索/密码/多行）
// 依据: docs/design/03-UI组件index.md §10 I02
// 状态: focus(primary边框+白底) / error(strawberry) / disabled
// ============================================================
import { computed, ref, useAttrs } from 'vue'
import AppIcon from './AppIcon.vue'
import type { CompSize } from '@/types/common'

const props = withDefaults(defineProps<{
  modelValue?: string | number
  type?: 'text' | 'search' | 'password' | 'number'
  placeholder?: string
  disabled?: boolean
  readonly?: boolean
  error?: string
  size?: CompSize
  /** 多行输入（textarea），此时 rows 生效 */
  textarea?: boolean
  rows?: number
  maxLength?: number
  autofocus?: boolean
}>(), {
  modelValue: '',
  type: 'text',
  disabled: false,
  readonly: false,
  size: 'md',
  textarea: false,
  rows: 3,
})

const emit = defineEmits<{
  (e: 'update:modelValue', v: string): void
  (e: 'focus', ev: FocusEvent): void
  (e: 'blur', ev: FocusEvent): void
  (e: 'enter', ev: KeyboardEvent): void
}>()

const attrs = useAttrs()
const showPwd = ref(false)
const isPwd = computed(() => props.type === 'password' && !props.textarea)
const realType = computed(() => (isPwd.value ? (showPwd.value ? 'text' : 'password') : props.type === 'search' ? 'text' : props.type))

const inputClass = computed(() => [
  `input--${props.size}`,
  { 'is-error': props.error, 'is-disabled': props.disabled },
])

function onInput(e: Event) {
  emit('update:modelValue', (e.target as HTMLInputElement | HTMLTextAreaElement).value)
}
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') emit('enter', e)
}
</script>

<template>
  <div class="input-wrap">
    <div class="input-box" :class="inputClass">
      <span v-if="type === 'search'" class="input-box__icon">
        <AppIcon name="search" :size="16" />
      </span>
      <slot name="prefix" />

      <textarea
        v-if="textarea"
        class="input-box__field input-box__field--area"
        :rows="rows"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        :readonly="readonly"
        :maxlength="maxLength"
        :autofocus="autofocus"
        @input="onInput"
        @keydown="onKeydown"
        @focus="$emit('focus', $event)"
        @blur="$emit('blur', $event)"
        v-bind="attrs"
      />
      <input
        v-else
        class="input-box__field"
        :type="realType"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        :readonly="readonly"
        :maxlength="maxLength"
        :autofocus="autofocus"
        @input="onInput"
        @keydown="onKeydown"
        @focus="$emit('focus', $event)"
        @blur="$emit('blur', $event)"
        v-bind="attrs"
      />

      <slot name="suffix" />
      <button
        v-if="isPwd"
        class="input-box__pwd"
        type="button"
        tabindex="-1"
        @click="showPwd = !showPwd"
      >
        <AppIcon :name="showPwd ? 'eye-off' : 'eye'" :size="16" />
      </button>
    </div>

    <p v-if="error" class="input-wrap__error">{{ error }}</p>
  </div>
</template>

<style scoped lang="scss">
.input-wrap {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  width: 100%;

  &__error {
    font-size: var(--text-xs);
    color: var(--straw-ink);
    animation: slide-in-up 0.2s var(--ease-soft);
  }
}

.input-box {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  background: var(--bg-inset);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  padding: 0 var(--space-3);
  transition: border-color 0.25s var(--ease-soft), background-color 0.25s var(--ease-soft),
    box-shadow 0.25s var(--ease-soft);

  &--sm {
    height: var(--control-h-sm);
  }
  &--md {
    height: var(--control-h);
  }
  &--lg {
    height: var(--control-h-lg);
  }

  &:focus-within {
    border-color: var(--primary);
    background: var(--bg-panel);
    box-shadow: var(--shadow-card);
  }
  &.is-error {
    border-color: var(--strawberry);
    &:focus-within {
      box-shadow: var(--shadow-danger);
    }
  }
  &.is-disabled {
    opacity: 0.5;
    cursor: not-allowed;
    .input-box__field {
      cursor: not-allowed;
    }
  }

  &__icon {
    display: inline-flex;
    color: var(--text-low);
  }
  &__field {
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
    &--area {
      resize: none;
      padding: var(--space-2) 0;
      line-height: 1.6;
      max-height: 160px;
    }
  }
  &__pwd {
    display: inline-flex;
    align-items: center;
    padding: var(--space-1);
    border-radius: var(--radius-sm);
    color: var(--text-low);
    transition: color 0.2s var(--ease-soft);
    &:hover {
      color: var(--text-hi);
    }
  }
}
</style>
