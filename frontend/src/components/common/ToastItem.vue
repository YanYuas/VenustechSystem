<script setup lang="ts">
// ============================================================
// ToastItem —— 单条 Toast（hover 暂停计时）
// ============================================================
import { onBeforeUnmount, onMounted, ref } from 'vue'
import type { ToastItem as TItem } from '@/types/common'
import { toast } from '@/composables/useToast'
import AppIcon from './AppIcon.vue'

const props = defineProps<{ item: TItem }>()

const ICON: Record<string, string> = {
  info: 'info',
  success: 'check',
  warning: 'warning',
  error: 'warning',
}

let timer: number | null = null
/** 到期时间戳方案：单定时器直达，hover 只记录剩余毫秒（替代 100ms 定时器链） */
let deadline = 0
let remaining = 0
const paused = ref(false)

function arm() {
  if (timer) window.clearTimeout(timer)
  const ms = deadline - Date.now()
  if (ms <= 0) {
    toast.remove(props.item.id)
    return
  }
  timer = window.setTimeout(() => toast.remove(props.item.id), ms)
}
function start() {
  deadline = Date.now() + props.item.duration
  arm()
}
function pause() {
  paused.value = true
  remaining = Math.max(0, deadline - Date.now())
  if (timer) window.clearTimeout(timer)
}
function resume() {
  paused.value = false
  if (remaining > 0) {
    deadline = Date.now() + remaining
    arm()
  }
}

onMounted(start)
onBeforeUnmount(() => {
  if (timer) window.clearTimeout(timer)
})
</script>

<template>
  <div
    class="toast-item"
    :class="`toast-item--${item.type}`"
    @mouseenter="pause"
    @mouseleave="resume"
  >
    <span class="toast-item__icon">
      <AppIcon :name="ICON[item.type] ?? 'info'" :size="16" />
    </span>
    <div class="toast-item__body">
      <p class="toast-item__title">{{ item.title }}</p>
      <p v-if="item.message" class="toast-item__msg">{{ item.message }}</p>
    </div>
    <button class="toast-item__close" type="button" @click="toast.remove(item.id)">
      <AppIcon name="close" :size="14" />
    </button>
  </div>
</template>

<style scoped lang="scss">
.toast-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  width: 320px;
  padding: var(--space-3) var(--space-4);
  background: var(--bg-raised);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-raise);
  animation: slide-in-right 0.35s var(--ease-spring);
  transition: opacity 0.2s var(--ease-soft), transform 0.2s var(--ease-soft);

  &__icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border-radius: var(--radius-pill);
    flex-shrink: 0;
  }
  &--info &__icon { background: var(--sky-soft); color: var(--sky-ink); }
  &--success &__icon { background: var(--mint-soft); color: var(--mint-ink); }
  &--warning &__icon { background: var(--butter-soft); color: var(--butter-ink); }
  &--error &__icon { background: var(--straw-soft); color: var(--straw-ink); }

  &__body {
    flex: 1;
    min-width: 0;
  }
  &__title {
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--text-hi);
    line-height: 1.4;
  }
  &__msg {
    margin-top: 2px;
    font-size: var(--text-sm);
    color: var(--text-mid);
    line-height: 1.5;
  }
  &__close {
    display: inline-flex;
    align-items: center;
    padding: 2px;
    border-radius: var(--radius-sm);
    color: var(--text-low);
    opacity: 0;
    transition: opacity 0.2s var(--ease-soft);
    &:hover {
      color: var(--text-hi);
    }
  }
  &:hover &__close {
    opacity: 1;
  }
}
</style>
