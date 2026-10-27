<script setup lang="ts">
// ============================================================
// 设置页分区 —— 通知设置（M08 P0）
// 从 SettingsView.vue 拆出（D-09），模板、文案、class 逐字保留。
//
// 开关值由父级 useSettingsConfig 持有（读写后端 settings 表）：
//   翻转 → emit change-notify-*（父级同步 ref）；
//   change → emit save-notify（父级 300ms 合并落库）。
// 事件顺序与原来 BaseSwitch 的 "update:modelValue → change" 一致。
// ============================================================
import BaseCard from '@/shared/components/common/BaseCard.vue'
import BaseSwitch from '@/shared/components/common/BaseSwitch.vue'

defineProps<{
  notifyTask: boolean
  notifyReview: boolean
  notifySystem: boolean
  notifySound: boolean
  notifySaving: boolean
}>()

defineEmits<{
  (e: 'change-notify-task', v: boolean): void
  (e: 'change-notify-review', v: boolean): void
  (e: 'change-notify-system', v: boolean): void
  (e: 'change-notify-sound', v: boolean): void
  (e: 'save-notify'): void
}>()
</script>

<template>
  <!-- 通知设置 -->
  <BaseCard title="通知设置" icon="bell">
    <p v-if="notifySaving" class="settings__hint">保存中…</p>
    <div class="settings__group">
      <div class="settings__row">
        <label class="settings__label">任务提醒</label>
        <BaseSwitch
          :model-value="notifyTask"
          @update:model-value="(v) => $emit('change-notify-task', v)"
          @change="$emit('save-notify')"
        />
      </div>
    </div>
    <div class="settings__group">
      <div class="settings__row">
        <label class="settings__label">复盘提醒</label>
        <BaseSwitch
          :model-value="notifyReview"
          @update:model-value="(v) => $emit('change-notify-review', v)"
          @change="$emit('save-notify')"
        />
      </div>
    </div>
    <div class="settings__group">
      <div class="settings__row">
        <label class="settings__label">系统通知</label>
        <BaseSwitch
          :model-value="notifySystem"
          @update:model-value="(v) => $emit('change-notify-system', v)"
          @change="$emit('save-notify')"
        />
      </div>
    </div>
    <div class="settings__group">
      <div class="settings__row">
        <label class="settings__label">提示音</label>
        <BaseSwitch
          :model-value="notifySound"
          @update:model-value="(v) => $emit('change-notify-sound', v)"
          @change="$emit('save-notify')"
        />
      </div>
    </div>
  </BaseCard>
</template>
