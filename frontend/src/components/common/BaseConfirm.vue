<script setup lang="ts">
// ============================================================
// I14 BaseConfirm —— 确认对话框（危险操作，输入确认文字）
// 依据: docs/design/03-UI组件index.md §10 I14
// 用法(命令式): const ok = await useModal().confirm({ title, message, requireInput: '确认删除' })
// ============================================================
import { computed, ref } from 'vue'
import BaseModal from './BaseModal.vue'

const props = withDefaults(defineProps<{
  modelValue?: boolean
  title?: string
  message?: string
  confirmText?: string
  cancelText?: string
  /** 输入此文字后方可确认 */
  requireInput?: string
}>(), {
  modelValue: false,
  title: '确认操作',
  message: '',
  confirmText: '确认删除',
  cancelText: '取消',
  requireInput: '',
})

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'confirm'): void
  (e: 'cancel'): void
}>()

const typed = ref('')
const matched = computed(() => !props.requireInput || typed.value === props.requireInput)
</script>

<template>
  <BaseModal
    :model-value="modelValue"
    :title="title"
    :width="400"
    :danger="true"
    :confirm-text="confirmText"
    :cancel-text="cancelText"
    @update:model-value="emit('update:modelValue', $event)"
    @confirm="emit('confirm')"
    @cancel="emit('cancel')"
    @dismiss="emit('cancel')"
  >
    <p class="confirm-msg">{{ message }}</p>

    <template v-if="requireInput">
      <p class="confirm-hint">此操作不可恢复。输入「{{ requireInput }}」以继续</p>
      <input
        v-model="typed"
        class="confirm-input"
        :placeholder="requireInput"
      />
    </template>

    <template #footer>
      <button class="confirm-btn is-cancel" type="button" @click="emit('cancel')">
        {{ cancelText }}
      </button>
      <button
        class="confirm-btn is-danger"
        type="button"
        :disabled="!matched"
        @click="emit('confirm')"
      >
        {{ confirmText }}
      </button>
    </template>
  </BaseModal>
</template>

<style scoped lang="scss">
.confirm-msg {
  font-size: var(--text-base);
  color: var(--text-mid);
  line-height: 1.6;
}
.confirm-hint {
  margin-top: var(--space-3);
  font-size: var(--text-sm);
  color: var(--straw-ink);
}
.confirm-input {
  margin-top: var(--space-2);
  width: 100%;
  height: var(--control-h);
  padding: 0 var(--space-3);
  background: var(--bg-inset);
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  font-size: var(--text-base);
  &:focus {
    outline: none;
    border-color: var(--strawberry);
  }
}
.confirm-btn {
  height: var(--control-h);
  padding: 0 var(--space-5);
  border-radius: var(--radius-sm);
  font-family: var(--font-cute);
  font-size: var(--text-base);
  transition: transform 0.25s var(--ease-spring), box-shadow 0.25s var(--ease-soft);
  &.is-cancel {
    background: var(--bg-panel);
    border: 1px solid var(--line);
    color: var(--text-hi);
    &:hover {
      border-color: var(--primary);
    }
  }
  &.is-danger {
    background: var(--strawberry);
    color: var(--white);
    &:hover:not(:disabled) {
      box-shadow: var(--shadow-danger);
    }
    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  }
  &:active:not(:disabled) {
    transform: scale(0.96);
  }
}
</style>
