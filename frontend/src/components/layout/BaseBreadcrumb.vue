<script setup lang="ts">
// ============================================================
// A06 BaseBreadcrumb —— 面包屑
// 依据: docs/design/03-UI组件index.md §2 A06
// 视觉: 13px text-mid，分隔符"/" text-low，末级 text-hi 快乐体，可点 hover primary
// ============================================================

export interface CrumbItem {
  label: string
  /** 为空则视为末级不可点 */
  to?: string
}

withDefaults(defineProps<{ items?: CrumbItem[] }>(), {
  items: () => [],
})

const emit = defineEmits<{ (e: 'select', item: CrumbItem): void }>()
</script>

<template>
  <nav class="crumb" aria-label="面包屑">
    <template v-for="(item, i) in items" :key="i">
      <span v-if="i > 0" class="crumb__sep">/</span>
      <button
        class="crumb__item"
        :class="{ 'is-last': i === items.length - 1 }"
        type="button"
        :disabled="i === items.length - 1 || !item.to"
        @click="emit('select', item)"
      >
        {{ item.label }}
      </button>
    </template>
  </nav>
</template>

<style scoped lang="scss">
.crumb {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-base);
  color: var(--text-mid);

  &__sep {
    color: var(--text-low);
  }
  &__item {
    padding: 2px 6px;
    border-radius: var(--radius-sm);
    color: var(--text-mid);
    transition: color 0.2s var(--ease-soft), background-color 0.2s var(--ease-soft);
    &:hover:not(:disabled) {
      color: var(--primary);
    }
    &.is-last {
      color: var(--text-hi);
      font-family: var(--font-cute);
      font-weight: 600;
      cursor: default;
    }
  }
}
</style>
