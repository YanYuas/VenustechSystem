<script setup lang="ts">
// ============================================================
// 设置页分区 —— AI 配置
// 从 SettingsView.vue 拆出（D-09），模板、文案、class 逐字保留。
// 状态由父级 useSettingsConfig 持有，这里只读 props + emit 回写。
// ============================================================
import BaseCard from '@/shared/components/common/BaseCard.vue'
import BaseButton from '@/shared/components/common/BaseButton.vue'
import BaseInput from '@/shared/components/common/BaseInput.vue'
import BaseSwitch from '@/shared/components/common/BaseSwitch.vue'
import BaseSelect from '@/shared/components/common/BaseSelect.vue'
import AppIcon from '@/shared/components/common/AppIcon.vue'
import type { UserConfig } from '@/shared/types/user'

defineProps<{
  userConfig: UserConfig | null
  apiKey: string
  verifying: boolean
}>()

const emit = defineEmits<{
  (e: 'change-api-key', v: string): void
  (e: 'save-config', patch: Partial<UserConfig>): void
  (e: 'verify'): void
}>()

// 自动化等级变更抽成命名函数：多行内联箭头会被 Prettier(semi:false) 换行拆散，
// Vue 表达式解析失败（task-19）。一次函数调用则格式化稳定。
function onAutomationLevelChange(v: string) {
  emit('save-config', { automation_level: v as UserConfig['automation_level'] })
}

// 自动化等级选项
const automationOptions = [
  { value: 'L1', label: 'L1 · 纯手动' },
  { value: 'L2', label: 'L2 · 提醒辅助' },
  { value: 'L3', label: 'L3 · 半自动' },
  { value: 'L4', label: 'L4 · 高度自动' },
  { value: 'L5', label: 'L5 · 全自主' },
]
</script>

<template>
  <!-- AI 配置 -->
  <BaseCard title="AI 配置" icon="spark">
    <div class="settings__group">
      <div class="settings__row">
        <label class="settings__label">启用 AI 功能</label>
        <BaseSwitch
          :model-value="userConfig?.ai_enabled ?? false"
          @update:model-value="(v) => $emit('save-config', { ai_enabled: v })"
        />
      </div>
    </div>
    <div class="settings__group">
      <label class="settings__label">API Key</label>
      <div class="settings__row">
        <BaseInput
          :model-value="apiKey"
          type="password"
          placeholder="输入 DeepSeek API Key"
          class="settings__input"
          @update:model-value="(v) => $emit('change-api-key', v)"
        />
        <BaseButton :loading="verifying" @click="$emit('verify')">验证并保存</BaseButton>
      </div>
      <p v-if="userConfig?.api_key_configured" class="settings__hint settings__hint--success">
        <AppIcon name="check" :size="14" /> 已配置 API Key
      </p>
      <p v-else class="settings__hint">未配置 API Key，AI 功能将不可用</p>
    </div>
    <div class="settings__group">
      <label class="settings__label">自动化等级</label>
      <BaseSelect
        :model-value="userConfig?.automation_level ?? 'L2'"
        :options="automationOptions"
        class="settings__select"
        @update:model-value="onAutomationLevelChange"
      />
      <p class="settings__hint">控制第二分身的自主程度，L1 纯手动，L5 全自主</p>
    </div>
  </BaseCard>
</template>
