<script setup lang="ts">
// ============================================================
// I12 BasePagination —— 分页器
// 依据: docs/design/03-UI组件index.md §10 I12
// ============================================================
import { computed } from 'vue'
import AppIcon from './AppIcon.vue'

const props = withDefaults(defineProps<{
  total: number
  page?: number
  pageSize?: number
  /** 可见页码数（奇数） */
  around?: number
}>(), {
  total: 0,
  page: 1,
  pageSize: 20,
  around: 2,
})

const emit = defineEmits<{
  (e: 'update:page', v: number): void
  (e: 'change', v: number): void
}>()

const pages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

const visible = computed<number[]>(() => {
  const p = props.page
  const n = pages.value
  if (n <= props.around * 2 + 1) return Array.from({ length: n }, (_, i) => i + 1)
  const start = Math.max(1, Math.min(p - props.around, n - props.around * 2))
  const list: number[] = []
  for (let i = start; i <= start + props.around * 2; i++) list.push(i)
  return list
})

function go(p: number) {
  if (p < 1 || p > pages.value || p === props.page) return
  emit('update:page', p)
  emit('change', p)
}
</script>

<template>
  <nav v-if="pages > 1" class="pager" aria-label="分页">
    <button class="pager__btn" type="button" :disabled="page <= 1" @click="go(page - 1)">
      <AppIcon name="chevron-left" :size="16" />
    </button>

    <template v-if="visible[0] > 1">
      <button class="pager__btn" type="button" @click="go(1)">1</button>
      <span v-if="visible[0] > 2" class="pager__ellipsis">…</span>
    </template>

    <button
      v-for="p in visible"
      :key="p"
      class="pager__btn"
      :class="{ 'is-active': p === page }"
      type="button"
      @click="go(p)"
    >
      {{ p }}
    </button>

    <template v-if="visible[visible.length - 1] < pages">
      <span v-if="visible[visible.length - 1] < pages - 1" class="pager__ellipsis">…</span>
      <button class="pager__btn" type="button" @click="go(pages)">{{ pages }}</button>
    </template>

    <button class="pager__btn" type="button" :disabled="page >= pages" @click="go(page + 1)">
      <AppIcon name="chevron-right" :size="16" />
    </button>
  </nav>
</template>

<style scoped lang="scss">
.pager {
  display: flex;
  align-items: center;
  gap: var(--space-1);

  &__btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 32px;
    height: 32px;
    padding: 0 var(--space-2);
    border-radius: var(--radius-pill);
    font-size: var(--text-sm);
    font-family: var(--font-cute);
    color: var(--text-mid);
    transition: background-color 0.2s var(--ease-soft), color 0.2s var(--ease-soft),
      transform 0.2s var(--ease-spring), box-shadow 0.2s var(--ease-soft);
    &:hover:not(:disabled):not(.is-active) {
      background: var(--bg-inset);
      color: var(--text-hi);
    }
    &.is-active {
      background: var(--primary);
      color: var(--on-primary);
      box-shadow: var(--glow);
    }
    &:active:not(:disabled) {
      transform: scale(0.9);
    }
    &:disabled {
      opacity: 0.4;
      cursor: not-allowed;
    }
  }
  &__ellipsis {
    color: var(--text-low);
    padding: 0 var(--space-1);
  }
}
</style>
