<script setup lang="ts">
// ============================================================
// 设置页分区 —— 数据清理（M08 P1）
// 从 SettingsView.vue 拆出（D-09），模板、文案、class、清理逻辑逐字保留。
// ============================================================
import { ref } from 'vue'
import BaseCard from '@/shared/components/common/BaseCard.vue'
import BaseButton from '@/shared/components/common/BaseButton.vue'
import BaseSwitch from '@/shared/components/common/BaseSwitch.vue'
import AppIcon from '@/shared/components/common/AppIcon.vue'
import { useToast } from '@/kernel/ui/toast'

const toast = useToast()

const cleaning = ref(false)
const cleanCache = ref(true)
const cleanTemp = ref(true)
const cleanOldBackups = ref(false)
async function performClean() {
  cleaning.value = true
  try {
    // 清理localStorage中的临时数据
    if (cleanCache.value) {
      const keys = Object.keys(localStorage).filter((k) => k.startsWith('venustech_cache_'))
      keys.forEach((k) => localStorage.removeItem(k))
    }
    if (cleanTemp.value) {
      const keys = Object.keys(localStorage).filter((k) => k.startsWith('venustech_temp_'))
      keys.forEach((k) => localStorage.removeItem(k))
    }
    toast.success('清理完成', '已清理本地临时数据')
  } catch (err) {
    toast.error('清理失败', String(err))
  } finally {
    cleaning.value = false
  }
}
</script>

<template>
  <!-- 数据清理 -->
  <BaseCard title="数据清理" icon="trash">
    <div class="settings__group">
      <div class="settings__row">
        <label class="settings__label">清理缓存</label>
        <BaseSwitch v-model="cleanCache" />
      </div>
    </div>
    <div class="settings__group">
      <div class="settings__row">
        <label class="settings__label">清理临时文件</label>
        <BaseSwitch v-model="cleanTemp" />
      </div>
    </div>
    <div class="settings__group">
      <div class="settings__row">
        <label class="settings__label">清理旧备份（保留最近5个）</label>
        <BaseSwitch v-model="cleanOldBackups" />
      </div>
    </div>
    <div class="settings__group">
      <BaseButton variant="danger" :loading="cleaning" @click="performClean">
        <AppIcon name="trash" :size="16" /> 立即清理
      </BaseButton>
    </div>
  </BaseCard>
</template>
