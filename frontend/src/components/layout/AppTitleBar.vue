<script setup lang="ts">
// ============================================================
// A01 AppTitleBar —— 窗口标题栏（自定义 Traffic Light + 窗口控制）
// 依据: docs/design/03-UI组件index.md §2 A01
// 视觉: 高36px bg-panel + 底部1px line；左侧 Traffic Light，中拖拽区，右窗口控制
// 交互: hover 图标淡入 150ms；窗口控制 hover 背景 bg-inset
// ============================================================
import { ref, computed } from 'vue'
import { electron } from '@/utils/electron'
import AppIcon from '@/components/common/AppIcon.vue'

const props = withDefaults(defineProps<{
  /** 窗口控制风格：mac(Traffic Light) / win(右侧按钮) / auto(自动检测) */
  platform?: 'mac' | 'win' | 'auto'
}>(), {
  platform: 'auto',
})

const isMac = computed(() => {
  if (props.platform === 'auto') {
    return /Mac|iPhone|iPad/.test(navigator.platform)
  }
  return props.platform === 'mac'
})

const tlHover = ref<'close' | 'min' | 'max' | null>(null)

const TL = [
  { key: 'close', color: 'var(--strawberry)', icon: 'close', action: () => electron.close() },
  { key: 'min', color: 'var(--butter)', icon: 'minus', action: () => electron.minimize() },
  { key: 'max', color: 'var(--mint)', icon: 'check', action: () => electron.maximize() },
] as const

const winBtns = [
  { key: 'min', icon: 'minus', action: () => electron.minimize() },
  { key: 'max', icon: 'menu', action: () => electron.maximize() },
  { key: 'close', icon: 'close', action: () => electron.close() },
] as const
</script>

<template>
  <header class="titlebar">
    <!-- macOS Traffic Light（左侧） -->
    <div v-if="isMac" class="titlebar__traffic">
      <button
        v-for="tl in TL"
        :key="tl.key"
        class="titlebar__tl"
        :style="{ backgroundColor: tl.color }"
        type="button"
        :aria-label="tl.key"
        @mouseenter="tlHover = tl.key"
        @mouseleave="tlHover = null"
        @click="tl.action()"
      >
        <AppIcon
          v-if="tlHover === tl.key"
          :name="tl.icon"
          :size="8"
          class="titlebar__tl-icon"
        />
      </button>
    </div>

    <!-- 拖拽区 -->
    <div class="titlebar__drag" />

    <!-- Windows 窗口控制（右侧） -->
    <div v-if="!isMac" class="titlebar__win">
      <button
        v-for="btn in winBtns"
        :key="btn.key"
        class="titlebar__win-btn"
        type="button"
        :aria-label="btn.key"
        @click="btn.action()"
      >
        <AppIcon :name="btn.icon" :size="14" />
      </button>
    </div>
  </header>
</template>

<style scoped lang="scss">
.titlebar {
  display: flex;
  align-items: center;
  height: 36px;
  padding: 0 var(--space-3);
  background: var(--bg-panel);
  border-bottom: 1px solid var(--line);
  user-select: none;

  &__traffic {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  &__tl {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 12px;
    height: 12px;
    border-radius: var(--radius-pill);
    color: var(--white);
    transition: transform 0.2s var(--ease-spring);
    &:hover {
      transform: scale(1.15);
    }
  }
  &__tl-icon {
    opacity: 0.9;
  }
  &__drag {
    flex: 1;
    height: 100%;
    -webkit-app-region: drag;
  }
  &__win {
    display: flex;
    align-items: center;
    gap: 2px;
  }
  &__win-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 26px;
    border-radius: var(--radius-sm);
    color: var(--text-mid);
    transition: background-color 0.15s var(--ease-soft), color 0.15s var(--ease-soft);
    &:hover {
      background: var(--bg-inset);
      color: var(--primary);
    }
  }
}
</style>
