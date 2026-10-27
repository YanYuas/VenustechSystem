<script setup lang="ts">
// ============================================================
// 设置页分区 —— 数据管理（统计 / 数据目录 / 备份恢复）
// 从 SettingsView.vue 拆出（D-09），模板、文案、class 逐字保留。
// 数据由父级 useSettingsSync 持有，经 props/emit 传入。
// ============================================================
import BaseCard from '@/shared/components/common/BaseCard.vue'
import BaseButton from '@/shared/components/common/BaseButton.vue'
import AppIcon from '@/shared/components/common/AppIcon.vue'

defineProps<{
  dataStats: { documents: number; tasks: number; tags: number; conversations: number } | null
  dataDir: string
  importFile: File | null
  importing: boolean
}>()

defineEmits<{
  (e: 'open-dir'): void
  (e: 'export-backup'): void
  (e: 'select-file', ev: Event): void
  (e: 'import-backup'): void
}>()
</script>

<template>
  <!-- 数据管理 -->
  <BaseCard title="数据管理" icon="database">
    <div class="settings__group">
      <div class="settings__stats">
        <div class="settings__stat">
          <span class="settings__stat-num">{{ dataStats?.documents ?? 0 }}</span>
          <span class="settings__stat-label">文档</span>
        </div>
        <div class="settings__stat">
          <span class="settings__stat-num">{{ dataStats?.tasks ?? 0 }}</span>
          <span class="settings__stat-label">任务</span>
        </div>
        <div class="settings__stat">
          <span class="settings__stat-num">{{ dataStats?.tags ?? 0 }}</span>
          <span class="settings__stat-label">标签</span>
        </div>
        <div class="settings__stat">
          <span class="settings__stat-num">{{ dataStats?.conversations ?? 0 }}</span>
          <span class="settings__stat-label">对话</span>
        </div>
      </div>
    </div>
    <div class="settings__group">
      <label class="settings__label">数据目录</label>
      <div class="settings__row">
        <span class="settings__dir">{{ dataDir }}</span>
        <BaseButton variant="secondary" size="sm" @click="$emit('open-dir')">打开</BaseButton>
      </div>
    </div>
    <div class="settings__group">
      <label class="settings__label">备份与恢复</label>
      <div class="settings__row">
        <BaseButton variant="secondary" @click="$emit('export-backup')">
          <AppIcon name="download" :size="16" /> 导出备份
        </BaseButton>
        <label class="settings__file-btn">
          <AppIcon name="upload" :size="16" /> 导入备份
          <input type="file" accept=".zip" hidden @change="(ev) => $emit('select-file', ev)" />
        </label>
        <BaseButton :loading="importing" :disabled="!importFile" @click="$emit('import-backup')">
          确认导入
        </BaseButton>
      </div>
      <p v-if="importFile" class="settings__hint">已选择: {{ importFile.name }}</p>
      <p class="settings__hint">导入将覆盖当前数据，需重启应用生效</p>
    </div>
  </BaseCard>
</template>
