<script setup lang="ts">
// ============================================================
// I11 BaseSelect —— 下拉选择（可搜索）
// 依据: docs/design/03-UI组件index.md §10 I11
// 交互: 点击外部关闭 / ↑↓ 导航 / Enter 选中 / Esc 关闭
// ============================================================
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'
import type { SelectOption } from '@/types/common'

const props = withDefaults(defineProps<{
  modelValue?: string
  options?: SelectOption[]
  placeholder?: string
  searchable?: boolean
  disabled?: boolean
  clearable?: boolean
}>(), {
  modelValue: '',
  options: () => [],
  placeholder: '请选择',
  searchable: false,
  disabled: false,
  clearable: false,
})

const emit = defineEmits<{
  (e: 'update:modelValue', v: string): void
  (e: 'change', v: string): void
}>()

const open = ref(false)
const query = ref('')
const highlight = ref(0)
const rootEl = ref<HTMLElement | null>(null)

const filtered = computed(() => {
  if (!query.value) return props.options
  const q = query.value.toLowerCase()
  return props.options.filter((o) => o.label.toLowerCase().includes(q))
})

const selectedLabel = computed(
  () => props.options.find((o) => o.value === props.modelValue)?.label ?? '',
)

function toggle() {
  if (props.disabled) return
  open.value = !open.value
  query.value = ''
  highlight.value = 0
}
function select(opt: SelectOption) {
  emit('update:modelValue', opt.value)
  emit('change', opt.value)
  open.value = false
}
function clear() {
  emit('update:modelValue', '')
  open.value = false
}
function onKeydown(e: KeyboardEvent) {
  if (!open.value) return
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    highlight.value = Math.min(highlight.value + 1, filtered.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    highlight.value = Math.max(highlight.value - 1, 0)
  } else if (e.key === 'Enter') {
    e.preventDefault()
    const opt = filtered.value[highlight.value]
    if (opt && !opt.disabled) select(opt)
  } else if (e.key === 'Escape') {
    open.value = false
  }
}

function onClickOutside(e: MouseEvent) {
  if (rootEl.value && !rootEl.value.contains(e.target as Node)) open.value = false
}

onMounted(() => document.addEventListener('mousedown', onClickOutside))
onBeforeUnmount(() => document.removeEventListener('mousedown', onClickOutside))

watch(() => props.modelValue, () => { highlight.value = 0 })
</script>

<template>
  <div ref="rootEl" class="select">
    <!-- 触发器 -->
    <button
      class="select__trigger"
      type="button"
      :class="{ 'is-open': open, 'is-disabled': disabled }"
      @click="toggle"
      @keydown="onKeydown"
    >
      <span class="select__value" :class="{ 'is-placeholder': !selectedLabel }">
        {{ selectedLabel || placeholder }}
      </span>
      <span v-if="clearable && modelValue" class="select__clear" @click.stop="clear">
        <AppIcon name="close" :size="14" />
      </span>
      <AppIcon name="chevron-down" :size="16" class="select__arrow" />
    </button>

    <!-- 选项面板 -->
    <Transition name="drop">
      <div v-if="open" class="select__panel">
        <input
          v-if="searchable"
          v-model="query"
          class="select__search"
          placeholder="搜索…"
        />
        <ul class="select__list">
          <li
            v-for="(opt, i) in filtered"
            :key="opt.value"
            class="select__option"
            :class="{ 'is-active': opt.value === modelValue, 'is-highlight': i === highlight, 'is-disabled': opt.disabled }"
            @click="!opt.disabled && select(opt)"
            @mouseenter="highlight = i"
          >
            <span>{{ opt.label }}</span>
            <AppIcon v-if="opt.value === modelValue" name="check" :size="14" />
          </li>
          <li v-if="filtered.length === 0" class="select__empty">无匹配选项</li>
        </ul>
      </div>
    </Transition>
  </div>
</template>

<style scoped lang="scss">
.select {
  position: relative;
  width: 100%;

  &__trigger {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    height: var(--control-h);
    padding: 0 var(--space-3);
    background: var(--bg-inset);
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    font-size: var(--text-base);
    color: var(--text-hi);
    text-align: left;
    transition: border-color 0.25s var(--ease-soft), background-color 0.25s var(--ease-soft),
      box-shadow 0.25s var(--ease-soft);
    &:hover:not(.is-disabled) {
      border-color: var(--primary);
    }
    &.is-open {
      border-color: var(--primary);
      background: var(--bg-panel);
      box-shadow: var(--shadow-card);
    }
    &.is-disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  }
  &__value {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    &.is-placeholder {
      color: var(--text-low);
    }
  }
  &__clear {
    display: inline-flex;
    color: var(--text-low);
    &:hover {
      color: var(--text-hi);
    }
  }
  &__arrow {
    color: var(--text-low);
    transition: transform 0.25s var(--ease-soft);
  }
  .is-open &__arrow {
    transform: rotate(180deg);
  }

  &__panel {
    position: absolute;
    top: calc(100% + var(--space-2));
    left: 0;
    right: 0;
    z-index: 120;
    background: var(--bg-raised);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-raise);
    padding: var(--space-2);
    animation: gudu 0.25s var(--ease-spring);
  }
  &__search {
    width: 100%;
    height: 32px;
    margin-bottom: var(--space-1);
    padding: 0 var(--space-2);
    background: var(--bg-inset);
    border: none;
    border-radius: var(--radius-sm);
    font-size: var(--text-sm);
    outline: none;
  }
  &__list {
    max-height: 240px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  &__option {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 36px;
    padding: 0 var(--space-3);
    border-radius: var(--radius-sm);
    font-size: var(--text-base);
    color: var(--text-mid);
    cursor: pointer;
    transition: background-color 0.2s var(--ease-soft), color 0.2s var(--ease-soft);
    &:hover,
    &.is-highlight {
      background: var(--bg-inset);
      color: var(--text-hi);
    }
    &.is-active {
      color: var(--primary);
      font-weight: 600;
    }
    &.is-disabled {
      opacity: 0.4;
      cursor: not-allowed;
    }
  }
  &__empty {
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: var(--text-sm);
    color: var(--text-low);
  }
}
</style>

<style lang="scss">
.drop-enter-active,
.drop-leave-active {
  transition: opacity 0.2s var(--ease-soft), transform 0.2s var(--ease-soft);
  transform-origin: top;
}
.drop-enter-from,
.drop-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
