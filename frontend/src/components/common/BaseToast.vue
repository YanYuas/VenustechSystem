<script setup lang="ts">
// ============================================================
// I06 BaseToast —— Toast 容器（右上角堆叠）
// 依据: docs/design/03-UI组件index.md §10 I06
// 用法: const toast = useToast(); toast.success('已保存')
// 挂载: main.ts 中 <BaseToast />
// ============================================================
import { onMounted } from 'vue'
import { toast } from '@/composables/useToast'
import ToastItem from './ToastItem.vue'

onMounted(() => toast.setReady())
</script>

<template>
  <Teleport to="body">
    <div class="toast-host">
      <TransitionGroup name="toast">
        <ToastItem v-for="item in toast.items" :key="item.id" :item="item" />
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped lang="scss">
.toast-host {
  position: fixed;
  top: var(--space-5);
  right: var(--space-5);
  z-index: 3000;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  pointer-events: none;
  > * {
    pointer-events: auto;
  }
}
</style>

<style lang="scss">
.toast-enter-active {
  transition: all 0.35s var(--ease-spring);
}
.toast-leave-active {
  transition: all 0.2s var(--ease-soft);
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(32px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(32px);
}
.toast-move {
  transition: transform 0.3s var(--ease-soft);
}
</style>
