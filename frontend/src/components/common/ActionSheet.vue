<script setup lang="ts">
// ============================================================
// ActionSheet —— 底部动作菜单（移动端专用交互底座）
//
// 用途：把桌面端的"双击/右键"等隐含交互，在移动端显式化为
// 点击后弹出的动作列表（PRD-模块-tools §5.2 工作区/保险箱要求）。
//
// 用法：
//   <ActionSheet v-model="sheetOpen" title="文件操作"
//     :actions="[{ key: 'terminal', label: '在父目录打开终端', icon: 'command' }]"
//     @select="onSheetSelect" />
// ============================================================
import AppIcon from '@/components/common/AppIcon.vue'

export interface SheetAction {
  key: string
  label: string
  icon?: string
  /** 危险动作（删除等）显示为草莓色 */
  danger?: boolean
  /** 次要说明（副标题） */
  hint?: string
}

withDefaults(
  defineProps<{
    modelValue: boolean
    title?: string
    actions: SheetAction[]
  }>(),
  { title: '' },
)

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'select', key: string): void
}>()

function close() {
  emit('update:modelValue', false)
}

function pick(key: string) {
  emit('select', key)
  close()
}
</script>

<template>
  <Teleport to="body">
    <Transition name="sheet">
      <div v-if="modelValue" class="action-sheet__mask" @click.self="close">
        <section class="action-sheet" role="dialog" aria-modal="true">
          <p v-if="title" class="action-sheet__title">{{ title }}</p>
          <ul class="action-sheet__list">
            <li v-for="a in actions" :key="a.key">
              <button
                class="action-sheet__item"
                :class="{ 'is-danger': a.danger }"
                type="button"
                @click="pick(a.key)"
              >
                <AppIcon :name="a.icon ?? 'dot'" :size="16" />
                <span class="action-sheet__label">
                  {{ a.label }}
                  <small v-if="a.hint" class="action-sheet__hint">{{ a.hint }}</small>
                </span>
              </button>
            </li>
          </ul>
          <button class="action-sheet__cancel" type="button" @click="close">取消</button>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped lang="scss">
.action-sheet__mask {
  position: fixed;
  inset: 0;
  z-index: 2100;
  display: flex;
  align-items: flex-end;
  background: var(--overlay);
}

.action-sheet {
  width: 100%;
  max-height: 70vh;
  overflow-y: auto;
  padding: var(--space-3) var(--space-4)
    calc(var(--space-4) + env(safe-area-inset-bottom, 0px));
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  background: var(--surface);
}

.action-sheet__title {
  margin: 0 0 var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-3);
  text-align: center;
  word-break: break-all;
}

.action-sheet__list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.action-sheet__item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
  min-height: 48px; // 移动端触摸目标（Apple HIG 44 起）
  padding: var(--space-2) var(--space-3);
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-1);
  font-size: var(--text-base);
  text-align: left;
  cursor: pointer;

  &:hover {
    background: var(--primary-soft);
  }

  &.is-danger {
    color: var(--straw-ink);
  }
}

.action-sheet__label {
  display: flex;
  flex-direction: column;
}

.action-sheet__hint {
  font-size: var(--text-xs);
  color: var(--text-3);
}

.action-sheet__cancel {
  width: 100%;
  min-height: 44px;
  margin-top: var(--space-2);
  border: none;
  border-radius: var(--radius-sm);
  background: var(--surface-2, var(--primary-soft));
  color: var(--text-2);
  font-size: var(--text-base);
  cursor: pointer;
}

.sheet-enter-active,
.sheet-leave-active {
  transition: opacity 180ms ease;
}
.sheet-enter-from,
.sheet-leave-to {
  opacity: 0;
}
</style>
