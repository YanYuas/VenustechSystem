<script setup lang="ts">
// ============================================================
// 设置页分区 —— 第二分身（昵称 / 灵感触发概率 / 桌宠置顶）
// 从 SettingsView.vue 拆出（D-09），模板、文案、class 逐字保留。
// ============================================================
import BaseCard from '@/components/common/BaseCard.vue'
import BaseInput from '@/components/common/BaseInput.vue'
import BaseSwitch from '@/components/common/BaseSwitch.vue'
import type { UserConfig } from '@/types'

defineProps<{
  userConfig: UserConfig | null
}>()

defineEmits<{
  (e: 'save-config', patch: Partial<UserConfig>): void
}>()
</script>

<template>
  <!-- 第二分身 -->
  <BaseCard title="第二分身" icon="user">
    <div class="settings__group">
      <label class="settings__label">昵称</label>
      <BaseInput
        :model-value="userConfig?.nickname ?? ''"
        placeholder="你的昵称"
        class="settings__input"
        @update:model-value="(v) => $emit('save-config', { nickname: v })"
      />
    </div>
    <div class="settings__group">
      <div class="settings__row">
        <label class="settings__label">灵感触发概率</label>
        <span class="settings__value">{{ userConfig?.inspiration_probability ?? 60 }}%</span>
      </div>
      <input
        type="range"
        min="0"
        max="100"
        :value="userConfig?.inspiration_probability ?? 60"
        class="settings__slider"
        @change="(e) => $emit('save-config', { inspiration_probability: Number((e.target as HTMLInputElement).value) })"
      />
    </div>
    <div class="settings__group">
      <div class="settings__row">
        <label class="settings__label">桌宠窗口置顶</label>
        <BaseSwitch
          :model-value="userConfig?.pet_topmost ?? false"
          @update:model-value="(v) => $emit('save-config', { pet_topmost: v })"
        />
      </div>
    </div>
  </BaseCard>
</template>
