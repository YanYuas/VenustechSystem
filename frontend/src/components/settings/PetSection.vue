<script setup lang="ts">
// ============================================================
// 设置页分区 —— 桌宠设置（M08 P0）
// 从 SettingsView.vue 拆出（D-09），模板、文案、class 逐字保留。
// 状态原本就是本分区专属（localStorage 持久化），因此留在组件内。
// ============================================================
import { ref } from 'vue'
import BaseCard from '@/components/common/BaseCard.vue'
import BaseSwitch from '@/components/common/BaseSwitch.vue'

const petEnabled = ref(true)
const petDefaultForm = ref<'pet' | 'human'>('pet')
const petInteraction = ref(true)
const petOpacity = ref(90)
const PET_SETTINGS_KEY = 'venustech_pet_settings'
function loadPetSettings() {
  try {
    const saved = localStorage.getItem(PET_SETTINGS_KEY)
    if (saved) {
      const s = JSON.parse(saved)
      petEnabled.value = s.enabled ?? true
      petDefaultForm.value = s.defaultForm ?? 'pet'
      petInteraction.value = s.interaction ?? true
      petOpacity.value = s.opacity ?? 90
    }
  } catch { }
}
function savePetSettings() {
  try {
    localStorage.setItem(PET_SETTINGS_KEY, JSON.stringify({
      enabled: petEnabled.value,
      defaultForm: petDefaultForm.value,
      interaction: petInteraction.value,
      opacity: petOpacity.value,
    }))
  } catch { }
}
loadPetSettings()
</script>

<template>
  <!-- 桌宠设置 -->
  <BaseCard title="桌宠设置" icon="spark">
    <div class="settings__group">
      <div class="settings__row">
        <label class="settings__label">启用桌宠</label>
        <BaseSwitch :model-value="petEnabled" @update:model-value="(v) => { petEnabled = v; savePetSettings() }" />
      </div>
    </div>
    <div class="settings__group">
      <label class="settings__label">默认形态</label>
      <div class="settings__mode-btns">
        <button class="settings__mode-btn" :class="{ 'is-active': petDefaultForm === 'pet' }" @click="petDefaultForm = 'pet'; savePetSettings()">桌宠</button>
        <button class="settings__mode-btn" :class="{ 'is-active': petDefaultForm === 'human' }" @click="petDefaultForm = 'human'; savePetSettings()">人形</button>
      </div>
    </div>
    <div class="settings__group">
      <div class="settings__row">
        <label class="settings__label">互动反馈</label>
        <BaseSwitch :model-value="petInteraction" @update:model-value="(v) => { petInteraction = v; savePetSettings() }" />
      </div>
    </div>
    <div class="settings__group">
      <div class="settings__row">
        <label class="settings__label">透明度</label>
        <span class="settings__value">{{ petOpacity }}%</span>
      </div>
      <input type="range" min="30" max="100" v-model.number="petOpacity" @change="savePetSettings" class="settings__slider" />
    </div>
  </BaseCard>
</template>
