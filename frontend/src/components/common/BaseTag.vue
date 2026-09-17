<script setup lang="ts">
// ============================================================
// I09 BaseTag —— 标签/Chip（语义变体 + 可删除）
// 依据: docs/design/03-UI组件index.md §10 I09
// 语义: default / primary / mint / butter / sky / lilac / straw / gold
// ============================================================
import { computed } from 'vue'
import AppIcon from './AppIcon.vue'
import type { TagSemantic } from '@/types/common'

const props = withDefaults(defineProps<{
  semantic?: TagSemantic
  closable?: boolean
  size?: 'sm' | 'md'
}>(), {
  semantic: 'default',
  closable: false,
  size: 'md',
})

const emit = defineEmits<{ (e: 'close'): void }>()

const cls = computed(() => [`tag--${props.semantic}`, `tag--${props.size}`])
</script>

<template>
  <span class="tag" :class="cls">
    <slot />
    <button v-if="closable" class="tag__close" type="button" @click.stop="emit('close')">
      <AppIcon name="close" :size="12" />
    </button>
  </span>
</template>

<style scoped lang="scss">
.tag {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  border-radius: var(--radius-pill);
  font-size: var(--text-sm);
  line-height: 1;
  padding: 4px 10px;
  white-space: nowrap;
  animation: gudu 0.35s var(--ease-spring);

  &--sm {
    font-size: var(--text-xs);
    padding: 3px 8px;
  }

  // 变体
  &--default { background: var(--bg-inset); color: var(--text-mid); }
  &--primary { background: var(--primary-soft); color: var(--primary-ink); }
  &--mint { background: var(--mint-soft); color: var(--mint-ink); }
  &--butter { background: var(--butter-soft); color: var(--butter-ink); }
  &--sky { background: var(--sky-soft); color: var(--sky-ink); }
  &--lilac { background: var(--lilac-soft); color: var(--lilac-ink); }
  &--straw { background: var(--straw-soft); color: var(--straw-ink); }
  &--gold { background: var(--gold-soft); color: var(--gold-ink); }

  &__close {
    display: inline-flex;
    align-items: center;
    padding: 0;
    border-radius: var(--radius-pill);
    color: inherit;
    opacity: 0.65;
    transition: opacity 0.2s var(--ease-soft), transform 0.2s var(--ease-spring);
    &:hover {
      opacity: 1;
      transform: scale(1.2);
    }
  }
}
</style>
