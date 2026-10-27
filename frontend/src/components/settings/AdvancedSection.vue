<script setup lang="ts">
// ============================================================
// 设置页分区 —— 高级设置（动画 / 字体缩放 / 性能 / 自动保存 / 保险箱 /
//                服务器地址 / 访问令牌 / 数据同步）
// 从 SettingsView.vue 拆出（D-09），模板、文案、class 逐字保留。
//
// 动画/字体/性能/自动保存是纯本地偏好（localStorage），留在组件内；
// 服务器地址/令牌/同步包状态由父级 useSettingsSync 持有，经 props/emit 传入。
// ============================================================
import { ref } from 'vue'
import BaseCard from '@/components/common/BaseCard.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import BaseInput from '@/components/common/BaseInput.vue'
import BaseSwitch from '@/components/common/BaseSwitch.vue'
import { formatSyncSizeKb } from '@/components/settings/settingsUtils'
import type { SyncPackage } from '@/api/sync'

defineProps<{
  apiBaseDraft: string
  tokenDraft: string
  syncExporting: boolean
  syncImporting: string
  syncPackagesOpen: boolean
  syncPackages: SyncPackage[]
}>()

defineEmits<{
  (e: 'change-api-base-draft', v: string): void
  (e: 'change-token-draft', v: string): void
  (e: 'save-api-base'): void
  (e: 'export-sync'): void
  (e: 'toggle-packages'): void
  (e: 'import-pkg', p: SyncPackage): void
}>()

// ---------- 高级设置（M08 P1） ----------
const animationEnabled = ref(true)
const fontScale = ref(100)
const performanceMode = ref(false)
const autoSave = ref(true)
const ADVANCED_KEY = 'venustech_advanced_settings'
function loadAdvanced() {
  try {
    const s = JSON.parse(localStorage.getItem(ADVANCED_KEY) || '{}')
    animationEnabled.value = s.animation ?? true
    fontScale.value = s.fontScale ?? 100
    performanceMode.value = s.performance ?? false
    autoSave.value = s.autoSave ?? true
  } catch { }
}
function saveAdvanced() {
  localStorage.setItem(ADVANCED_KEY, JSON.stringify({
    animation: animationEnabled.value,
    fontScale: fontScale.value,
    performance: performanceMode.value,
    autoSave: autoSave.value,
  }))
  // 应用字体缩放
  document.documentElement.style.fontSize = fontScale.value + '%'
  // 应用动画开关
  if (!animationEnabled.value) {
    document.documentElement.setAttribute('data-no-anim', 'true')
  } else {
    document.documentElement.removeAttribute('data-no-anim')
  }
}
loadAdvanced()
</script>

<template>
  <!-- 高级设置 -->
  <BaseCard title="高级设置" icon="settings">
    <div class="settings__group">
      <div class="settings__row">
        <label class="settings__label">动画效果</label>
        <BaseSwitch :model-value="animationEnabled" @update:model-value="(v) => { animationEnabled = v; saveAdvanced() }" />
      </div>
      <p class="settings__hint">关闭可提升低端设备性能</p>
    </div>
    <div class="settings__group">
      <div class="settings__row">
        <label class="settings__label">字体缩放</label>
        <span class="settings__value">{{ fontScale }}%</span>
      </div>
      <input type="range" min="80" max="130" step="5" :value="fontScale" @change="(e) => { fontScale = Number((e.target as HTMLInputElement).value); saveAdvanced() }" class="settings__slider" />
    </div>
    <div class="settings__group">
      <div class="settings__row">
        <label class="settings__label">性能模式</label>
        <BaseSwitch :model-value="performanceMode" @update:model-value="(v) => { performanceMode = v; saveAdvanced() }" />
      </div>
      <p class="settings__hint">降低视觉效果以提升响应速度</p>
    </div>
    <div class="settings__group">
      <div class="settings__row">
        <label class="settings__label">自动保存</label>
        <BaseSwitch :model-value="autoSave" @update:model-value="(v) => { autoSave = v; saveAdvanced() }" />
      </div>
    </div>
    <div class="settings__group">
      <div class="settings__row">
        <label class="settings__label">保险箱</label>
        <BaseButton size="sm" variant="secondary" icon="command" @click="$router.push('/vault')">
          打开保险箱
        </BaseButton>
      </div>
      <p class="settings__hint">用主密码加密保存账号密码、令牌与密钥（明文不落盘）</p>
    </div>
    <div class="settings__group">
      <div class="settings__row">
        <label class="settings__label">服务器地址</label>
        <BaseInput
          :model-value="apiBaseDraft"
          placeholder="http://100.x.y.z:3000/api/v1"
          @update:model-value="(v) => $emit('change-api-base-draft', v)"
        />
        <BaseButton size="sm" variant="secondary" @click="$emit('save-api-base')">保存</BaseButton>
      </div>
      <div class="settings__row">
        <label class="settings__label">访问令牌</label>
        <BaseInput
          :model-value="tokenDraft"
          placeholder="电脑首次启动服务时打印的令牌"
          @update:model-value="(v) => $emit('change-token-draft', v)"
        />
      </div>
      <p class="settings__hint">App 壳专用：填电脑首次启动服务时打印的访问令牌。Web/PWA 模式无需改动。</p>
    </div>
    <div class="settings__group">
      <div class="settings__row">
        <label class="settings__label">数据同步</label>
        <div style="display: flex; gap: 8px">
          <BaseButton size="sm" variant="secondary" icon="database" :loading="syncExporting" @click="$emit('export-sync')">
            导出同步包
          </BaseButton>
          <BaseButton size="sm" variant="secondary" icon="reload" @click="$emit('toggle-packages')">
            同步包列表
          </BaseButton>
        </div>
      </div>
      <p class="settings__hint">
        全库导出为单文件 JSON（身份/任务/日记/复盘…；工作区索引不同步、保险箱只同步密文、设备配置不跨机）。
      </p>
      <div v-if="syncPackagesOpen" class="settings__sync-packages">
        <p v-if="syncPackages.length === 0" class="settings__hint">还没有同步包 —— 先「导出同步包」。</p>
        <div v-for="p in syncPackages" :key="p.path" class="settings__sync-pkg">
          <span class="settings__sync-name">{{ p.name }}</span>
          <span class="settings__sync-size">{{ formatSyncSizeKb(p.size) }} KB</span>
          <BaseButton size="sm" variant="secondary" icon="reload" :loading="syncImporting === p.path" @click="$emit('import-pkg', p)">
            导入
          </BaseButton>
        </div>
      </div>
    </div>
  </BaseCard>
</template>
