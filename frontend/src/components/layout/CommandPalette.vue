<script setup lang="ts">
// ============================================================
// A05 CommandPalette —— 命令面板（Cmd+Shift+P）
// 依据: docs/design/03-UI组件index.md §2 A05
// 用法: 命令操作列表，支持模糊匹配，Enter 执行
// ============================================================
import { computed, nextTick, ref, watch } from 'vue'
import AppIcon from '@/components/common/AppIcon.vue'

const props = withDefaults(defineProps<{ modelValue?: boolean }>(), {
  modelValue: false,
})

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'exec', command: Command): void
}>()

interface Command {
  id: string
  name: string
  icon: string
  shortcut?: string
  group: string
}

const COMMANDS: Command[] = [
  { id: 'task', name: '新建任务', icon: 'plus', shortcut: 'N', group: '常用' },
  { id: 'doc', name: '新建文档', icon: 'doc', shortcut: '⌘N', group: '常用' },
  { id: 'review', name: '开始今日复盘', icon: 'refresh', group: '常用' },
  { id: 'import', name: '导入数据', icon: 'cloud', group: '数据' },
  { id: 'export', name: '导出备份', icon: 'doc', group: '数据' },
  { id: 'theme-light', name: '切换到奶油日', icon: 'sun', group: '外观' },
  { id: 'theme-dark', name: '切换到可可夜', icon: 'moon', group: '外观' },
  { id: 'pet', name: '打开桌宠设置', icon: 'spark', group: '桌宠' },
  { id: 'settings', name: '打开设置', icon: 'setting', group: '其他' },
]

const query = ref('')
const highlight = ref(0)
const inputEl = ref<HTMLInputElement | null>(null)

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return COMMANDS
  return COMMANDS.filter((c) => c.name.toLowerCase().includes(q))
})

function close() {
  emit('update:modelValue', false)
}

function exec(c: Command) {
  emit('exec', c)
  close()
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    highlight.value = Math.min(highlight.value + 1, filtered.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    highlight.value = Math.max(highlight.value - 1, 0)
  } else if (e.key === 'Enter') {
    e.preventDefault()
    const c = filtered.value[highlight.value]
    if (c) exec(c)
  } else if (e.key === 'Escape') {
    close()
  }
}

watch(
  () => props.modelValue,
  async (v) => {
    if (v) {
      query.value = ''
      highlight.value = 0
      await nextTick()
      inputEl.value?.focus()
    }
  },
)
</script>

<template>
  <Teleport to="body">
    <Transition name="global">
      <div v-if="modelValue" class="cmd" @keydown="onKeydown" @click.self="close">
        <div class="cmd__panel" role="dialog" aria-modal="true">
          <div class="cmd__input-row">
            <AppIcon name="command" :size="18" class="cmd__icon" />
            <input
              ref="inputEl"
              v-model="query"
              class="cmd__input"
              placeholder="输入命令或搜索…"
            />
          </div>
          <ul class="cmd__list">
            <li
              v-for="(c, i) in filtered"
              :key="c.id"
              class="cmd__item"
              :class="{ 'is-active': i === highlight }"
              @click="exec(c)"
              @mouseenter="highlight = i"
            >
              <span class="cmd__item-icon">
                <AppIcon :name="c.icon" :size="16" />
              </span>
              <span class="cmd__item-name">{{ c.name }}</span>
              <kbd v-if="c.shortcut" class="cmd__item-kbd">{{ c.shortcut }}</kbd>
            </li>
            <li v-if="!filtered.length" class="cmd__empty">无匹配命令</li>
          </ul>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped lang="scss">
.cmd {
  position: fixed;
  inset: 0;
  z-index: 2100;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 16vh;
  background: var(--overlay);

  &__panel {
    width: 480px;
    max-width: calc(100vw - 48px);
    background: var(--bg-raised);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-raise);
    overflow: hidden;
    animation: gudu 0.45s var(--ease-spring);
  }
  &__input-row {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-4) var(--space-5);
    border-bottom: 1px solid var(--line);
  }
  &__icon {
    color: var(--primary);
  }
  &__input {
    flex: 1;
    min-width: 0;
    border: none;
    outline: none;
    background: transparent;
    font-size: var(--text-md);
    color: var(--text-hi);
    &::placeholder {
      color: var(--text-low);
    }
  }
  &__list {
    max-height: 300px;
    overflow-y: auto;
    padding: var(--space-2);
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  &__item {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    height: 40px;
    padding: 0 var(--space-3);
    border-radius: var(--radius-sm);
    cursor: pointer;
    &:hover,
    &.is-active {
      background: var(--bg-inset);
    }
  }
  &__item-icon {
    display: inline-flex;
    color: var(--text-mid);
  }
  &__item-name {
    flex: 1;
    font-size: var(--text-base);
    color: var(--text-hi);
  }
  &__item-kbd {
    padding: 1px 6px;
    border: 1px solid var(--line);
    border-radius: 4px;
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--text-low);
  }
  &__empty {
    padding: var(--space-5);
    text-align: center;
    font-size: var(--text-sm);
    color: var(--text-low);
  }
}
</style>

<style lang="scss">
.global-enter-active,
.global-leave-active {
  transition: opacity 0.2s var(--ease-soft);
}
.global-enter-from,
.global-leave-to {
  opacity: 0;
}
</style>
