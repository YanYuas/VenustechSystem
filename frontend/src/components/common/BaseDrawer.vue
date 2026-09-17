<script setup lang="ts">
// ============================================================
// I05 BaseDrawer —— 抽屉（左/右滑出）
// 依据: docs/design/03-UI组件index.md §10 I05
// 动效: slideIn 300ms ease-soft + 遮罩 fade
// ============================================================
import { onBeforeUnmount, onMounted, watch } from 'vue'
import AppIcon from './AppIcon.vue'

const props = withDefaults(defineProps<{
  modelValue?: boolean
  title?: string
  placement?: 'left' | 'right'
  width?: number
  closable?: boolean
}>(), {
  modelValue: false,
  title: '',
  placement: 'right',
  width: 420,
  closable: true,
})

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'closed'): void
}>()

function close() {
  emit('update:modelValue', false)
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
    if (v) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
      setTimeout(() => emit('closed'), 300)
    }
  },
)
</script>

<template>
  <Teleport to="body">
    <Transition name="drawer">
      <div v-if="modelValue" class="qm-drawer-mask" @click.self="close">
        <aside
          class="qm-drawer"
          :class="`qm-drawer--${placement}`"
          :style="{ width: `${width}px` }"
          role="dialog"
          aria-modal="true"
        >
          <header class="qm-drawer__head">
            <h3 class="qm-drawer__title">{{ title }}</h3>
            <button v-if="closable" class="qm-drawer__close" type="button" @click="close">
              <AppIcon name="close" :size="18" />
            </button>
          </header>
          <div class="qm-drawer__body">
            <slot />
          </div>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped lang="scss">
.qm-drawer-mask {
  position: fixed;
  inset: 0;
  z-index: 1900;
  background: var(--overlay);
}

.qm-drawer {
  position: absolute;
  top: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-panel);
  box-shadow: var(--shadow-raise);

  &--left {
    left: 0;
    border-right: 1px solid var(--line);
  }
  &--right {
    right: 0;
    border-left: 1px solid var(--line);
  }

  &__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-5) var(--space-5) var(--space-3);
    border-bottom: 1px solid var(--line);
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
    &:hover {
      background: var(--bg-inset);
      color: var(--text-hi);
    }
  }
  &__body {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: var(--space-5);
  }
}
</style>

<style lang="scss">
.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.25s var(--ease-soft);
  .qm-drawer--right {
    transition: transform 0.3s var(--ease-soft);
  }
  .qm-drawer--left {
    transition: transform 0.3s var(--ease-soft);
  }
}
.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
  .qm-drawer--right {
    transform: translateX(100%);
  }
  .qm-drawer--left {
    transform: translateX(-100%);
  }
}
</style>
