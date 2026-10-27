<script setup lang="ts">
// ============================================================
// 设置页分区 —— 外观（主题包 / 显示模式）
// 从 SettingsView.vue 拆出（D-09），模板、文案、class 逐字保留。
// ============================================================
import { useTheme } from '@/shared/theme/useTheme'
import BaseCard from '@/shared/components/common/BaseCard.vue'
import AppIcon from '@/shared/components/common/AppIcon.vue'
import type { ThemePack, ThemeMode } from '@/shared/types/common'

const { pack, mode, setPack, setMode } = useTheme()

// 主题包选项
const themePacks: { value: ThemePack; label: string; desc: string }[] = [
  { value: 'cream', label: '奶油糖果', desc: '温暖柔和，日常使用' },
  { value: 'guofeng', label: '国风雅集', desc: '古典雅致，文人气息' },
  { value: 'abyss', label: '深渊档案', desc: '深邃神秘，专注沉浸' },
  { value: 'epic', label: '史诗典藏', desc: '金琥珀传说，史诗质感' },
]

const modeOptions: { value: ThemeMode; label: string }[] = [
  { value: 'light', label: '浅色' },
  { value: 'dark', label: '深色' },
  { value: 'system', label: '跟随系统' },
]
</script>

<template>
  <!-- 外观设置 -->
  <BaseCard title="外观" icon="palette">
    <div class="settings__group">
      <label class="settings__label">主题包</label>
      <div class="settings__theme-packs">
        <button
          v-for="t in themePacks"
          :key="t.value"
          class="settings__theme-card"
          :class="{ 'is-active': pack === t.value }"
          @click="setPack(t.value)"
        >
          <span class="settings__theme-preview" :class="`theme-${t.value}`" />
          <span class="settings__theme-name">{{ t.label }}</span>
          <span class="settings__theme-desc">{{ t.desc }}</span>
        </button>
      </div>
    </div>
    <div class="settings__group">
      <label class="settings__label">显示模式</label>
      <div class="settings__mode-btns">
        <button
          v-for="m in modeOptions"
          :key="m.value"
          class="settings__mode-btn"
          :class="{ 'is-active': mode === m.value }"
          @click="setMode(m.value)"
        >
          <AppIcon
            :name="m.value === 'dark' ? 'moon' : m.value === 'light' ? 'sun' : 'monitor'"
            :size="16"
          />
          {{ m.label }}
        </button>
      </div>
    </div>
  </BaseCard>
</template>
