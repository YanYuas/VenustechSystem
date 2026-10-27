<script setup lang="ts">
// ============================================================
// ModalItem —— 单个命令式弹窗实例
// 管理 requireInput 确认文字匹配状态
// ============================================================
import { computed, ref } from 'vue'
import type { ModalRequest } from '@/kernel/ui/modal'
import BaseModal from './BaseModal.vue'

const props = defineProps<{ request: ModalRequest }>()

const emit = defineEmits<{ (e: 'confirm'): void; (e: 'cancel'): void }>()

const typed = ref('')
const matched = computed(
  () => !props.request.requireInput || typed.value === props.request.requireInput,
)
const confirmed = ref(false)

// 处理器抽成命名函数：Prettier(semi:false) 会把模板里的多语句内联处理器
// 打印成换行分隔，Vue 表达式解析失败（task-19）。一次函数调用则格式化稳定。
// 子组件 confirm 与底部按钮点击行为完全一致，共用同一个函数。
function onConfirm() {
  confirmed.value = true
  emit('confirm')
}
</script>

<template>
  <BaseModal
    :model-value="true"
    :title="request.title"
    :width="request.width ?? 400"
    :danger="request.danger"
    :confirm-text="request.confirmText ?? '确定'"
    :cancel-text="request.cancelText ?? '取消'"
    :closable="request.closable"
    @confirm="onConfirm"
    @cancel="emit('cancel')"
    @dismiss="emit('cancel')"
  >
    <template v-if="typeof request.content === 'string'">{{ request.content }}</template>
    <component :is="request.content" v-else-if="request.content" />

    <div v-if="request.requireInput" class="modal-item__input">
      <p class="modal-item__hint">输入「{{ request.requireInput }}」以继续</p>
      <input v-model="typed" class="modal-item__field" placeholder="确认文字" />
    </div>

    <template #footer>
      <button class="modal-item__btn is-cancel" type="button" @click="emit('cancel')">
        {{ request.cancelText ?? '取消' }}
      </button>
      <button
        class="modal-item__btn is-danger"
        type="button"
        :disabled="!matched"
        @click="onConfirm"
      >
        {{ request.confirmText ?? '确认删除' }}
      </button>
    </template>
  </BaseModal>
</template>

<style scoped lang="scss">
.modal-item {
  &__input {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  &__hint {
    font-size: var(--text-sm);
    color: var(--text-mid);
  }
  &__field {
    height: var(--control-h);
    padding: 0 var(--space-3);
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    background: var(--bg-inset);
    font-size: var(--text-base);
    color: var(--text-hi);
    &:focus {
      outline: none;
      border-color: var(--strawberry);
    }
  }
  &__btn {
    height: var(--control-h);
    padding: 0 var(--space-5);
    border-radius: var(--radius-sm);
    font-family: var(--font-cute);
    font-size: var(--text-base);
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
}
</style>
