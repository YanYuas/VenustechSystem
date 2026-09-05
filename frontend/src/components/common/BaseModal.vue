<script setup lang="ts">
// ============================================================
// I04 BaseModal —— 模态框
// 依据: docs/design/03-UI组件index.md §10 I04
// 交互: Esc 关闭 / 遮罩点击关闭(可配置) / 打开聚焦首元素
// 动效: 遮罩 fade 200ms + 面板咕嘟弹入 450ms，关闭 scale(.95) 淡出
// 命令式用法见 composables/useModal + components/common/ModalHost.vue
// ============================================================
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'

const props = withDefaults(defineProps<{
  modelValue?: boolean
  title?: string
  width?: number
  closable?: boolean
  maskClosable?: boolean
  confirmText?: string
  cancelText?: string
  danger?: boolean
  showFooter?: boolean
}>(), {
  modelValue: false,
  title: '',
  width: 480,
  closable: true,
  maskClosable: true,
  confirmText: '确定',
  cancelText: '取消',
  danger: false,
  showFooter: true,
})

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'confirm'): void
  (e: 'cancel'): void
  /** 被关闭（Esc/遮罩/关闭按钮）—— 未走业务确认，命令式层据此视为放弃 */
  (e: 'dismiss'): void
  (e: 'closed'): void
}>()

const panelRef = ref<HTMLElement | null>(null)
let isClosing = false

/** 仅关闭，不触发 cancel（用于遮罩点击/Esc/关闭按钮） */
function close() {
  if (isClosing) return
  isClosing = true
  emit('dismiss')
  emit('update:modelValue', false)
}

/** 取消操作（触发 cancel 事件 + 关闭） */
function cancel() {
  emit('cancel')
  close()
}

function onMaskClick() {
  if (props.maskClosable) close()
}

async function focusFirst() {
  await nextTick()
  // 使用组件实例的 panelRef，避免多 modal 叠加时选择器冲突
  const el = panelRef.value?.querySelector(
    '[tabindex]:not([tabindex="-1"]), input, button, select, textarea',
  )
  ;(el as HTMLElement | null)?.focus?.()
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.modelValue && props.closable) close()
}

onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  // 组件带 open 状态被直接卸载（如路由跳转）时，watch(false) 不会触发，需兜底恢复滚动
  if (props.modelValue) document.body.style.overflow = ''
})

watch(
  () => props.modelValue,
  (v) => {
    isClosing = false
    if (v) {
      document.body.style.overflow = 'hidden'
      focusFirst()
    } else {
      document.body.style.overflow = ''
      setTimeout(() => emit('closed'), 150)
    }
  },
)
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="modelValue"
        class="qm-modal qm-modal--open"
        :class="{ 'qm-modal--danger': danger }"
        @click.self="onMaskClick"
      >
        <div ref="panelRef" class="qm-modal__panel" :style="{ width: `${width}px` }" role="dialog" aria-modal="true" :aria-label="title">
          <header v-if="title || closable" class="qm-modal__head">
            <h3 class="qm-modal__title">{{ title }}</h3>
            <button v-if="closable" class="qm-modal__close" type="button" @click="close">
              <AppIcon name="close" :size="18" />
            </button>
          </header>

          <div class="qm-modal__body">
            <slot />
          </div>

          <footer v-if="showFooter" class="qm-modal__foot">
            <slot name="footer" :confirm="() => emit('confirm')" :cancel="cancel">
              <button class="qm-modal__btn is-cancel" type="button" @click="cancel">{{ cancelText }}</button>
              <button
                class="qm-modal__btn is-confirm"
                :class="{ 'is-danger': danger }"
                type="button"
                @click="emit('confirm')"
              >
                {{ confirmText }}
              </button>
            </slot>
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped lang="scss">
.qm-modal {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--overlay);

  &__panel {
    max-width: calc(100vw - 48px);
    max-height: calc(100vh - 96px);
    display: flex;
    flex-direction: column;
    background: var(--bg-raised);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-raise);
    animation: gudu 0.45s var(--ease-spring);
  }

  &__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-5) var(--space-6) 0;
  }
  &__title {
    font-size: var(--text-lg);
    font-weight: 700;
  }
  &__close {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: var(--radius-sm);
    color: var(--text-mid);
    transition: background-color 0.2s var(--ease-soft), color 0.2s var(--ease-soft), transform 0.2s var(--ease-spring);
    &:hover {
      background: var(--bg-inset);
      color: var(--text-hi);
      transform: rotate(6deg);
    }
  }

  &__body {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: var(--space-5) var(--space-6);
  }

  &__foot {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-3);
    padding: 0 var(--space-6) var(--space-5);
  }

  &__btn {
    height: var(--control-h);
    padding: 0 var(--space-5);
    border-radius: var(--radius-sm);
    font-family: var(--font-cute);
    font-size: var(--text-base);
    transition: transform 0.25s var(--ease-spring), box-shadow 0.25s var(--ease-soft),
      background-color 0.25s var(--ease-soft), color 0.25s var(--ease-soft);

    &.is-cancel {
      background: var(--bg-panel);
      border: 1px solid var(--line);
      color: var(--text-hi);
      &:hover {
        border-color: var(--primary);
        color: var(--primary);
      }
    }
    &.is-confirm {
      background: var(--primary);
      color: var(--on-primary);
      &:hover {
        box-shadow: var(--glow);
      }
    }
    &.is-danger {
      background: var(--strawberry);
      color: var(--white);
      &:hover {
        box-shadow: var(--shadow-danger);
      }
    }
    &:active {
      transform: scale(0.96);
    }
  }
}
</style>

<style lang="scss">
// 非 scoped：Teleport 到 body 的过渡类
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s var(--ease-soft);
  .qm-modal__panel {
    transition: transform 0.3s var(--ease-spring), opacity 0.2s var(--ease-soft);
  }
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
  .qm-modal__panel {
    transform: scale(0.95);
    opacity: 0;
  }
}
</style>
