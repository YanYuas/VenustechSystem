<script setup lang="ts">
// ============================================================
// 设置页分区 —— 系统与诊断（加密存储 / 系统日志 / 事件总线 / 规则引擎 / 插件）
// 从 SettingsView.vue 拆出（D-09），模板、文案、class 逐字保留。
// 状态与 API 由父级 useSettingsDiagnostics 持有，经 props/emit 传入。
// ============================================================
import BaseCard from '@/components/common/BaseCard.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import BaseInput from '@/components/common/BaseInput.vue'
import BaseSwitch from '@/components/common/BaseSwitch.vue'
import AppIcon from '@/components/common/AppIcon.vue'
import type { EncryptionStatus, LogFile, PluginItem } from '@/api/system'

defineProps<{
  encryption: EncryptionStatus | null
  logFiles: LogFile[]
  logContent: string
  activeLog: string
  eventStats: Array<{
    name: string
    count: number
    failed: number
    failedHandlers: string[]
    alert: boolean
  }>
  activeEvent: string
  eventTimeline: Array<{ time?: string; success?: boolean; failed_handlers?: string[] }>
  failedHandlerSummary: string
  plugins: PluginItem[]
  showSecurity: boolean
  showLogs: boolean
  showEvents: boolean
  showRules: boolean
  showPlugins: boolean
  ruleText: string
  ruleDomains: { builtin: number; user: number }
  rulePreview: {
    matched: boolean
    domain_name: string | null
    plans: Array<{ unit: string; task: string; duration: string }>
  } | null
}>()

defineEmits<{
  (e: 'toggle-security'): void
  (e: 'toggle-logs'): void
  (e: 'toggle-events'): void
  (e: 'toggle-rules'): void
  (e: 'toggle-plugins'): void
  (e: 'change-rule-text', v: string): void
  (e: 'refresh-logs'): void
  (e: 'clear-logs'): void
  (e: 'view-log', name: string): void
  (e: 'rotate-key'): void
  (e: 'toggle-plugin', p: PluginItem): void
  (e: 'discover-plugins'): void
  (e: 'toggle-event-detail', name: string): void
  (e: 'clear-events'): void
  (e: 'reload-domains'): void
}>()
</script>

<template>
  <!-- 系统与诊断：把后端早已存在、但此前没有入口的能力接出来 -->
  <BaseCard title="系统与诊断" icon="setting">
    <p class="settings__hint">这些能力后端一直都在，此前只是缺少界面入口。</p>

    <div class="settings__group">
      <button class="settings__link-btn" @click="$emit('toggle-security')">
        <AppIcon name="alert" :size="14" /> 加密存储
        <AppIcon :name="showSecurity ? 'chevron-up' : 'chevron-down'" :size="14" />
      </button>
      <div v-if="showSecurity" class="settings__diag">
        <p v-if="encryption" class="settings__hint">
          状态：{{ encryption.available ? '已启用' : '不可用' }}
        </p>
        <div class="settings__row">
          <BaseButton variant="secondary" size="sm" @click="$emit('rotate-key')">轮换密钥</BaseButton>
        </div>
        <p class="settings__hint">轮换会用新密钥重新加密数据，旧密钥立即失效。</p>
      </div>
    </div>

    <div class="settings__group">
      <button class="settings__link-btn" @click="$emit('toggle-logs')">
        <AppIcon name="doc" :size="14" /> 系统日志
        <AppIcon :name="showLogs ? 'chevron-up' : 'chevron-down'" :size="14" />
      </button>
      <div v-if="showLogs" class="settings__diag">
        <div class="settings__row">
          <BaseButton variant="secondary" size="sm" @click="$emit('refresh-logs')">刷新列表</BaseButton>
          <BaseButton variant="secondary" size="sm" @click="$emit('clear-logs')">清空日志</BaseButton>
        </div>
        <div v-if="logFiles.length" class="settings__log-list">
          <button
            v-for="f in logFiles"
            :key="f.name"
            class="settings__log-item"
            :class="{ 'is-active': activeLog === f.name }"
            @click="$emit('view-log', f.name)"
          >
            {{ f.name }} · {{ f.size_kb }} KB
          </button>
        </div>
        <p v-else class="settings__hint">暂无日志文件</p>
        <pre v-if="logContent" class="settings__log-content">{{ logContent }}</pre>
      </div>
    </div>

    <div class="settings__group">
      <button class="settings__link-btn" @click="$emit('toggle-events')">
        <AppIcon name="chart" :size="14" /> 事件总线
        <AppIcon :name="showEvents ? 'chevron-up' : 'chevron-down'" :size="14" />
      </button>
      <div v-if="showEvents" class="settings__diag">
        <div v-if="eventStats.length === 0" class="settings__hint">暂无事件记录（系统刚启动）</div>
        <template v-else>
          <ul class="settings__event-list">
            <li
              v-for="e in eventStats.slice(0, 30)"
              :key="e.name"
              class="settings__event-row"
              :class="{ 'is-alert': e.alert }"
              @click="$emit('toggle-event-detail', e.name)"
            >
              <span class="settings__event-name">{{ e.name }}</span>
              <span class="settings__event-count">
                {{ e.count }} 次
                <template v-if="e.failed">
                  <em class="settings__event-badge">失败 {{ e.failed }}</em>
                </template>
              </span>
            </li>
          </ul>
          <p v-if="eventStats.some((e) => e.failedHandlers.length)"
             class="settings__hint">
            失败 handler：{{ failedHandlerSummary }}
          </p>
          <div v-if="activeEvent" class="settings__diag">
            <p class="settings__hint">最近 10 条：{{ activeEvent }}</p>
            <ul class="settings__event-timeline">
              <li v-for="(r, i) in eventTimeline" :key="i">
                <span>{{ r.time }}</span>
                <span :class="{ 'is-fail': !r.success }">
                  {{ r.success ? '成功' : `失败（${(r.failed_handlers ?? []).join(', ')}）` }}
                </span>
              </li>
            </ul>
          </div>
          <div class="settings__row">
            <BaseButton variant="text" size="sm" @click="$emit('clear-events')">清空历史</BaseButton>
          </div>
        </template>
      </div>
    </div>

    <div class="settings__group">
      <button class="settings__link-btn" @click="$emit('toggle-rules')">
        <AppIcon name="command" :size="14" /> 规则引擎
        <AppIcon :name="showRules ? 'chevron-up' : 'chevron-down'" :size="14" />
      </button>
      <div v-if="showRules" class="settings__diag">
        <p class="settings__hint">
          领域库：内置 {{ ruleDomains.builtin }} 个 · 用户扩展 {{ ruleDomains.user }} 个
        </p>
        <div class="settings__row">
          <BaseInput
            :model-value="ruleText"
            placeholder="例如：我想学雅思，30 天"
            @update:model-value="(v) => $emit('change-rule-text', v)"
          />
          <BaseButton variant="secondary" size="sm" @click="$emit('reload-domains')">热重载</BaseButton>
        </div>
        <div v-if="rulePreview" class="settings__rule-preview">
          <span v-if="rulePreview.matched" class="settings__rule-tag is-hit">
            命中：{{ rulePreview.domain_name }}
          </span>
          <span v-else class="settings__rule-tag is-fallback">
            未命中领域库，使用通用拆解
          </span>
          <ul v-if="rulePreview.plans.length" class="settings__event-list">
            <li v-for="(pl, i) in rulePreview.plans.slice(0, 5)" :key="i">
              <span class="settings__event-name">{{ pl.unit }}</span>
              <span class="settings__event-count">{{ pl.task }} · {{ pl.duration }}</span>
            </li>
          </ul>
          <p v-else class="settings__hint">计划生成失败或为空</p>
        </div>
      </div>
    </div>

    <div class="settings__group">
      <button class="settings__link-btn" @click="$emit('toggle-plugins')">
        <AppIcon name="command" :size="14" /> 插件
        <AppIcon :name="showPlugins ? 'chevron-up' : 'chevron-down'" :size="14" />
      </button>
      <div v-if="showPlugins" class="settings__diag">
        <div class="settings__row">
          <BaseButton variant="secondary" size="sm" @click="$emit('discover-plugins')">扫描插件</BaseButton>
        </div>
        <div v-if="plugins.length" class="settings__plugin-list">
          <div v-for="p in plugins" :key="p.id" class="settings__plugin">
            <span class="settings__plugin-name">{{ p.name }} v{{ p.version }}</span>
            <BaseSwitch :model-value="p.enabled" @update:model-value="$emit('toggle-plugin', p)" />
          </div>
        </div>
        <p v-else class="settings__hint">暂无插件 —— 插件目录还没有内容</p>
      </div>
    </div>
  </BaseCard>
</template>
