<script setup lang="ts">
// ============================================================
// A07 WindowStatusIndicator —— 窗口状态指示器（保存中/已保存/离线）
// 依据: docs/design/03-UI组件index.md §2 A07
// 状态: saved(薄荷绿) / saving(奶黄呼吸) / offline(灰) / error(草莓红)
// ============================================================
import { computed } from 'vue'
import type { WindowStatus } from '@/types/common'

const props = withDefaults(defineProps<{ status?: WindowStatus }>(), {
  status: 'saved',
})

const MAP: Record<WindowStatus, { label: string; color: string; breathe?: boolean }> = {
  saved: { label: '已同步', color: 'var(--mint)' },
  saving: { label: '保存中…', color: 'var(--butter)', breathe: true },
  offline: { label: '离线模式', color: 'var(--text-low)' },
  error: { label: '保存失败', color: 'var(--strawberry)', breathe: true },
}

const cur = computed(() => MAP[props.status])
</script>

<template>
  <span class="wstatus">
    <span
      class="wstatus__dot"
      :class="{ 'is-breathe': cur.breathe }"
      :style="{ backgroundColor: cur.color }"
    />
    <span class="wstatus__label">{{ cur.label }}</span>
  </span>
</template>

<style scoped lang="scss">
.wstatus {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-xs);
  color: var(--text-low);
  animation: fade-in 0.2s var(--ease-soft);

  &__dot {
    width: 8px;
    height: 8px;
    border-radius: var(--radius-pill);
    &.is-breathe {
      animation: breathe 1.2s ease-in-out infinite;
    }
  }
}
</style>
