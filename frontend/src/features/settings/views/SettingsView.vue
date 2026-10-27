<script setup lang="ts">
// ============================================================
// 设置页 —— 外观 / AI / 第二分身 / 数据管理 / 关于
//
// 2026-10-27 结构拆分（D-09）：本文件只保留
//   ① 布局骨架（标题 / 搜索 / 加载态）② 分区组件编排 ③ 设置项搜索（DOM 级过滤）
// 14 个分区模板搬进 components/settings/*.vue，
// 跨分区状态与 API 调用收进 composables/useSettings{Config,Diagnostics,Sync}.ts。
// 文案 / DOM 层级 / class / 交互流程均未改动；分区样式见
// components/settings/settings-sections.scss（由 scoped 迁出，选择器逐字保留）。
// ============================================================
import { ref, onMounted, watch, nextTick } from 'vue'
import { useSettingsConfig } from '../composables/useSettingsConfig'
import { useSettingsDiagnostics } from '../composables/useSettingsDiagnostics'
import { useSettingsSync } from '../composables/useSettingsSync'
import {
  isSettingsHotkey,
  matchesSettingsSearch,
  normalizeSearchQuery,
} from '../components/settingsUtils'
import AppIcon from '@/shared/components/common/AppIcon.vue'
import SettingsSearchBar from '../components/SettingsSearchBar.vue'
import AppearanceSection from '../components/AppearanceSection.vue'
import AiSection from '../components/AiSection.vue'
import ProfileSection from '../components/ProfileSection.vue'
import PetSection from '../components/PetSection.vue'
import NotificationSection from '../components/NotificationSection.vue'
import AdvancedSection from '../components/AdvancedSection.vue'
import ShortcutsSection from '../components/ShortcutsSection.vue'
import CleanupSection from '../components/CleanupSection.vue'
import DataManagementSection from '../components/DataManagementSection.vue'
import SystemDiagnosticsSection from '../components/SystemDiagnosticsSection.vue'
import AboutSection from '../components/AboutSection.vue'

// ---------- 跨分区状态（原 42 个 ref / 4 处 api 调用） ----------
const config = useSettingsConfig()
const diag = useSettingsDiagnostics()
const sync = useSettingsSync()

const {
  userConfig,
  loading,
  apiKey,
  verifying,
  loadConfig,
  saveConfig,
  verifyApiKey,
  notifyTask,
  notifyReview,
  notifySystem,
  notifySound,
  notifySaving,
  loadNotifySettings,
  saveNotifySettings,
} = config

const {
  encryption,
  logFiles,
  logContent,
  activeLog,
  eventStats,
  activeEvent,
  eventTimeline,
  failedHandlerSummary,
  plugins,
  showSecurity,
  showLogs,
  showEvents,
  showRules,
  showPlugins,
  ruleText,
  ruleDomains,
  rulePreview,
  loadDiagnostics,
  loadRuleDomains,
  refreshLogs,
  viewLog,
  clearLogs,
  rotateKey,
  togglePlugin,
  discoverPlugins,
  toggleEventDetail,
  onClearEvents,
  onReloadDomains,
  toggleShowSecurity,
  toggleShowLogs,
  toggleShowEvents,
  toggleShowRules,
  toggleShowPlugins,
  setRuleText,
} = diag

const {
  syncExporting,
  syncImporting,
  apiBaseDraft,
  tokenDraft,
  syncPackagesOpen,
  syncPackages,
  dataStats,
  importFile,
  importing,
  dataDir,
  onSaveApiBase,
  onSyncExport,
  onSyncImport,
  toggleSyncPackages,
  loadStats,
  exportBackup,
  onFileSelect,
  importBackup,
  loadDataDir,
  openDataDir,
} = sync

// 模板侧不做直接赋值（保持 setup 绑定只读），统一走这些回写函数
function setApiKey(v: string) {
  apiKey.value = v
}
function setNotifyTask(v: boolean) {
  notifyTask.value = v
}
function setNotifyReview(v: boolean) {
  notifyReview.value = v
}
function setNotifySystem(v: boolean) {
  notifySystem.value = v
}
function setNotifySound(v: boolean) {
  notifySound.value = v
}
function setApiBaseDraft(v: string) {
  apiBaseDraft.value = v
}
function setTokenDraft(v: string) {
  tokenDraft.value = v
}

// ---------- 设置项搜索（F6.1） ----------
// 卡片数量多（10+ 张、36 个字段组），这里对 .settings__group 与其所属
// BaseCard 做文本匹配过滤：包含即命中、大小写不敏感、空搜索显示全部。
const searchQuery = ref('')
const settingsRoot = ref<HTMLElement | null>(null)
const searchBarRef = ref<InstanceType<typeof SettingsSearchBar> | null>(null)
const searchHitCount = ref(0)

function applySearch() {
  const root = settingsRoot.value
  if (!root) return
  const groups = Array.from(root.querySelectorAll<HTMLElement>('.settings__group'))
  if (!normalizeSearchQuery(searchQuery.value)) {
    groups.forEach((el) => el.classList.remove('is-search-hidden'))
    searchHitCount.value = 0
    return
  }
  // 先按字段组匹配，再按所属卡片标题匹配（卡片标题在 BaseCard 头部）
  let hits = 0
  const cardHit = new Map<Element, boolean>()
  groups.forEach((el) => {
    const card = el.closest('.base-card')
    const cardText = card?.querySelector('.base-card__title')?.textContent ?? ''
    const text = `${el.textContent ?? ''}`
    const hit = matchesSettingsSearch(text, cardText, searchQuery.value)
    el.classList.toggle('is-search-hidden', !hit)
    if (hit) hits += 1
    if (card) cardHit.set(card, (cardHit.get(card) ?? false) || hit)
  })
  // 整卡无命中时隐藏卡片，避免只剩标题的空壳
  cardHit.forEach((hit, card) => {
    ;(card as HTMLElement).classList.toggle('is-search-hidden', !hit)
  })
  searchHitCount.value = hits
}

watch(searchQuery, () => nextTick(applySearch))

function onSearchHotkey(e: KeyboardEvent) {
  if (isSettingsHotkey(e)) {
    e.preventDefault()
    searchBarRef.value?.focus()
  }
}

onMounted(() => {
  loadConfig()
  loadStats()
  loadDiagnostics()
  loadNotifySettings()
  loadRuleDomains()
  // 设置页内 Ctrl+, 聚焦搜索框（F6.1）
  window.addEventListener('keydown', onSearchHotkey)
})

// 数据目录：拆分前在 setup 阶段立即读取，这里保持同样的时机
loadDataDir()
</script>

<template>
  <div class="settings" ref="settingsRoot">
    <h2 class="settings__title">设置</h2>

    <!-- 设置项搜索（F6.1）：过滤卡片与其内字段；Ctrl+, 聚焦 -->
    <SettingsSearchBar ref="searchBarRef" v-model="searchQuery" :hit-count="searchHitCount" />

    <div v-if="loading" class="settings__loading">
      <AppIcon name="spin" :size="24" class="spin" />
      <span>加载中...</span>
    </div>

    <template v-else>
      <!-- 外观设置 -->
      <AppearanceSection />

      <!-- AI 配置 -->
      <AiSection
        :user-config="userConfig"
        :api-key="apiKey"
        :verifying="verifying"
        @change-api-key="setApiKey"
        @save-config="saveConfig"
        @verify="verifyApiKey"
      />

      <!-- 第二分身 -->
      <ProfileSection :user-config="userConfig" @save-config="saveConfig" />

      <!-- 桌宠设置 -->
      <PetSection />

      <!-- 通知设置 -->
      <NotificationSection
        :notify-task="notifyTask"
        :notify-review="notifyReview"
        :notify-system="notifySystem"
        :notify-sound="notifySound"
        :notify-saving="notifySaving"
        @change-notify-task="setNotifyTask"
        @change-notify-review="setNotifyReview"
        @change-notify-system="setNotifySystem"
        @change-notify-sound="setNotifySound"
        @save-notify="saveNotifySettings"
      />

      <!-- 高级设置 -->
      <AdvancedSection
        :api-base-draft="apiBaseDraft"
        :token-draft="tokenDraft"
        :sync-exporting="syncExporting"
        :sync-importing="syncImporting"
        :sync-packages-open="syncPackagesOpen"
        :sync-packages="syncPackages"
        @change-api-base-draft="setApiBaseDraft"
        @change-token-draft="setTokenDraft"
        @save-api-base="onSaveApiBase"
        @export-sync="onSyncExport"
        @toggle-packages="toggleSyncPackages"
        @import-pkg="onSyncImport"
      />

      <!-- 快捷键 -->
      <ShortcutsSection />

      <!-- 数据清理 -->
      <CleanupSection />

      <!-- 数据管理 -->
      <DataManagementSection
        :data-stats="dataStats"
        :data-dir="dataDir"
        :import-file="importFile"
        :importing="importing"
        @open-dir="openDataDir"
        @export-backup="exportBackup"
        @select-file="onFileSelect"
        @import-backup="importBackup"
      />

      <!-- 系统与诊断 -->
      <SystemDiagnosticsSection
        :encryption="encryption"
        :log-files="logFiles"
        :log-content="logContent"
        :active-log="activeLog"
        :event-stats="eventStats"
        :active-event="activeEvent"
        :event-timeline="eventTimeline"
        :failed-handler-summary="failedHandlerSummary"
        :plugins="plugins"
        :show-security="showSecurity"
        :show-logs="showLogs"
        :show-events="showEvents"
        :show-rules="showRules"
        :show-plugins="showPlugins"
        :rule-text="ruleText"
        :rule-domains="ruleDomains"
        :rule-preview="rulePreview"
        @toggle-security="toggleShowSecurity"
        @toggle-logs="toggleShowLogs"
        @toggle-events="toggleShowEvents"
        @toggle-rules="toggleShowRules"
        @toggle-plugins="toggleShowPlugins"
        @change-rule-text="setRuleText"
        @refresh-logs="refreshLogs"
        @clear-logs="clearLogs"
        @view-log="viewLog"
        @rotate-key="rotateKey"
        @toggle-plugin="togglePlugin"
        @discover-plugins="discoverPlugins"
        @toggle-event-detail="toggleEventDetail"
        @clear-events="onClearEvents"
        @reload-domains="onReloadDomains"
      />

      <!-- 关于 -->
      <AboutSection />
    </template>
  </div>
</template>

<style scoped lang="scss">
.settings {
  max-width: 720px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  padding-top: var(--space-3);

  &__title {
    font-size: var(--text-xl);
    font-weight: 700;
    font-family: var(--font-cute);
    color: var(--text-hi);
  }

  &__loading {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    padding: var(--space-8);
    color: var(--text-low);
  }

  .spin {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }
}
</style>

<!-- 分区共享样式：拆分前在上一段 scoped 样式里，因作用域限制迁出（选择器逐字保留） -->
<style lang="scss" src="../components/settings-sections.scss"></style>
