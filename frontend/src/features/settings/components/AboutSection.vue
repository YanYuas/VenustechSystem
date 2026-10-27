<script setup lang="ts">
// ============================================================
// 设置页分区 —— 关于（版本信息 / 更新日志）
// 从 SettingsView.vue 拆出（D-09），模板、文案、class 逐字保留。
// ============================================================
import { ref } from 'vue'
import BaseCard from '@/shared/components/common/BaseCard.vue'
import AppIcon from '@/shared/components/common/AppIcon.vue'

// ---------- 关于增强（M08 P1） ----------
const showChangelog = ref(false)
const changelog = [
  {
    version: 'v0.1.70',
    date: '2026-08-28',
    changes: ['一期工程基础版发布', '6大核心模块上线', '四套UI主题'],
  },
  {
    version: 'v0.1.71',
    date: '2026-09-04',
    changes: ['模块深度开发启动', '9个模块分支创建', 'UI组件V3.0对齐'],
  },
  {
    version: 'v0.2.0',
    date: '2026-09-06',
    changes: ['9模块深度开发完成', '四套UI主题V3.0对齐', '插件系统+加密存储', '首页跳转修复'],
  },
]

function toggleShowChangelog() {
  showChangelog.value = !showChangelog.value
}
</script>

<template>
  <!-- 关于 -->
  <BaseCard title="关于" icon="info">
    <div class="settings__about">
      <div class="settings__about-logo">
        <AppIcon name="spark" :size="32" />
      </div>
      <div class="settings__about-info">
        <h3>Venustech System · 启明星</h3>
        <p>方向启明，人生推演</p>
        <p class="settings__about-version">版本 v0.2.0</p>
      </div>
    </div>
    <div class="settings__group">
      <button class="settings__link-btn" @click="toggleShowChangelog">
        <AppIcon name="clock" :size="14" /> 更新日志
        <AppIcon :name="showChangelog ? 'chevron-up' : 'chevron-down'" :size="14" />
      </button>
      <div v-if="showChangelog" class="settings__changelog">
        <div v-for="log in changelog" :key="log.version" class="settings__changelog-item">
          <div class="settings__changelog-header">
            <span class="settings__changelog-version">{{ log.version }}</span>
            <span class="settings__changelog-date">{{ log.date }}</span>
          </div>
          <ul class="settings__changelog-list">
            <li v-for="c in log.changes" :key="c">{{ c }}</li>
          </ul>
        </div>
      </div>
    </div>
    <div class="settings__group">
      <p class="settings__hint">基于 FastAPI + Vue3 + SQLite 构建 · 本地优先 · 数据加密</p>
    </div>
  </BaseCard>
</template>
