<script setup lang="ts">
// ============================================================
// 设置页 —— 设置项搜索框（F6.1）
//
// 从 SettingsView.vue 拆出（D-09），模板与文案逐字保留：
//   - 图标 + 输入框 + 清除按钮
//   - 搜索无结果时的提示行（含「清除搜索」按钮）
// 过滤作用在父级 DOM（.settings__group / .base-card），因此这里只负责
// 输入与清除，命中数由父级计算后传入。
// ============================================================
import { ref } from 'vue'
import BaseButton from '@/components/common/BaseButton.vue'
import AppIcon from '@/components/common/AppIcon.vue'

defineProps<{
  /** 当前搜索词（父级 v-model） */
  modelValue: string
  /** 当前命中分组数（0 = 无结果，用于显示空态提示） */
  hitCount: number
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: string): void
}>()

const inputRef = ref<HTMLInputElement | null>(null)

/** 与 v-model 在 input 上的行为一致：输入即同步 */
function onInput(e: Event) {
  emit('update:modelValue', (e.target as HTMLInputElement).value)
}

/** 供父级 Ctrl+, 热键聚焦输入框 */
function focus() {
  inputRef.value?.focus()
}

defineExpose({ focus })
</script>

<template>
  <div class="settings__search">
    <AppIcon name="search" :size="16" />
    <input
      ref="inputRef"
      :value="modelValue"
      class="settings__search-input"
      type="text"
      placeholder="搜索设置项（如 主题 / 备份 / 令牌）"
      aria-label="搜索设置项"
      @input="onInput"
    />
    <button
      v-if="modelValue"
      class="settings__search-clear"
      type="button"
      aria-label="清除搜索"
      @click="$emit('update:modelValue', '')"
    >
      <AppIcon name="close" :size="14" />
    </button>
  </div>
  <p v-if="modelValue && !hitCount" class="settings__search-empty">
    没有找到相关设置
    <BaseButton size="sm" variant="text" @click="$emit('update:modelValue', '')">清除搜索</BaseButton>
  </p>
</template>

<style scoped lang="scss">
.settings__search {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  height: var(--control-h);
  padding: 0 var(--space-3);
  margin-bottom: var(--space-3);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-pill);
  background: var(--surface);

  &:focus-within {
    border-color: var(--primary);
  }
}

.settings__search-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-1);
  font-size: var(--text-sm);
}

.settings__search-clear {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--text-3);
  cursor: pointer;
}

.settings__search-empty {
  margin: 0 0 var(--space-3);
  color: var(--text-3);
  font-size: var(--text-sm);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
</style>
