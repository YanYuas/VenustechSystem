<script setup lang="ts">
// ============================================================
// 设置页 —— 外观 / AI / 第二分身 / 数据管理 / 关于
// ============================================================
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { authApi, backupApi, systemApi, settingsApi, syncApi } from '@/api'
import type { SyncPackage } from '@/api/sync'
import type { EncryptionStatus, LogFile, PluginItem } from '@/api/system'
import { useTheme } from '@/composables/useTheme'
import { useToast } from '@/composables/useToast'
import BaseCard from '@/components/common/BaseCard.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import BaseInput from '@/components/common/BaseInput.vue'
import BaseSwitch from '@/components/common/BaseSwitch.vue'
import BaseSelect from '@/components/common/BaseSelect.vue'
import AppIcon from '@/components/common/AppIcon.vue'
import type { UserConfig, ThemePack, ThemeMode } from '@/types'

const toast = useToast()

// ---------- 数据同步（S6-3b 前端出口） ----------
const syncExporting = ref(false)
const syncImporting = ref('')
const syncPackagesOpen = ref(false)
const syncPackages = ref<SyncPackage[]>([])

async function onSyncExport() {
  syncExporting.value = true
  try {
    const res = await syncApi.export()
    toast.success('同步包已导出', res.path)
    await loadSyncPackages()
    syncPackagesOpen.value = true
  } catch { /* http 层已提示 */ } finally {
    syncExporting.value = false
  }
}

async function loadSyncPackages() {
  try {
    syncPackages.value = (await syncApi.packages()).items
  } catch { /* http 层已提示 */ }
}

async function onSyncImport(p: SyncPackage) {
  syncImporting.value = p.path
  try {
    const s = await syncApi.import(p.path)
    if (s.ops === 0) toast.info('没有需要应用的变化', '本地数据已是最新（LWW）')
    else toast.success(`已应用 ${s.ops} 处变化`, `新增 ${s.insert} · 更新 ${s.update}`)
  } catch { /* http 层已提示 */ } finally {
    syncImporting.value = ''
  }
}
const { pack, mode, setPack, setMode } = useTheme()

// 用户配置
const userConfig = ref<UserConfig | null>(null)
const loading = ref(false)
const saving = ref(false)

// AI 配置
const apiKey = ref('')
const verifying = ref(false)
const verifyResult = ref<{ valid: boolean; model: string } | null>(null)

// 自动化等级选项
const automationOptions = [
  { value: 'L1', label: 'L1 · 纯手动' },
  { value: 'L2', label: 'L2 · 提醒辅助' },
  { value: 'L3', label: 'L3 · 半自动' },
  { value: 'L4', label: 'L4 · 高度自动' },
  { value: 'L5', label: 'L5 · 全自主' },
]

// 主题包选项
const themePacks: { value: ThemePack; label: string; desc: string }[] = [
  { value: 'cream', label: '奶油糖果', desc: '温暖柔和，日常使用' },
  { value: 'guofeng', label: '国风雅集', desc: '古典雅致，文人气息' },
  { value: 'abyss', label: '深渊档案', desc: '深邃神秘，专注沉浸' },
  { value: 'epic', label: '史诗典藏', desc: '金琥珀传说，史诗质感' },
]

const modeOptions: { value: ThemeMode; label: string }[] = [
  { value: 'light', label: '浅色' },
  { value: 'dark', label: '深色' },
  { value: 'system', label: '跟随系统' },
]

// 数据统计
const dataStats = ref<{ documents: number; tasks: number; tags: number; conversations: number } | null>(null)

// 备份导入
const importFile = ref<File | null>(null)
const importing = ref(false)

async function loadConfig() {
  loading.value = true
  try {
    userConfig.value = await authApi.me()
    nicknameDraft.value = userConfig.value?.nickname ?? ''
  } catch (err) {
    console.error('[Settings] load config failed', err)
  } finally {
    loading.value = false
  }
}

// 昵称：本地草稿 + 防抖提交（避免每个击键发一次 PATCH）
const nicknameDraft = ref('')
let nicknameTimer: ReturnType<typeof setTimeout> | undefined
watch(nicknameDraft, (v) => {
  clearTimeout(nicknameTimer)
  nicknameTimer = setTimeout(() => {
    const name = v.trim()
    if (name && name !== userConfig.value?.nickname) saveConfig({ nickname: name })
  }, 800)
})
onBeforeUnmount(() => clearTimeout(nicknameTimer))

async function loadStats() {
  try {
    dataStats.value = await backupApi.stats()
  } catch { /* ignore */ }
}

// ============================================================
// 系统与诊断（加密 / 日志 / 事件总线 / 插件）
//
// 这四个模块后端一直都在，但此前前端没有任何入口 —— 相当于埋没了。
// 这里只做「接出来 + 展示」；危险操作（轮换密钥、清空日志）都保留确认。
// ============================================================
const encryption = ref<EncryptionStatus | null>(null)
const logFiles = ref<LogFile[]>([])
const logContent = ref('')
const activeLog = ref('')
const eventStats = ref<Array<{ name: string; count: number; failed: number }>>([])
const plugins = ref<PluginItem[]>([])

const showSecurity = ref(false)
const showLogs = ref(false)
const showEvents = ref(false)
const showPlugins = ref(false)

async function loadDiagnostics() {
  // 每项独立 try：任一失败不该连累其他面板（例如插件目录不存在）
  try {
    encryption.value = await systemApi.encryptionStatus()
  } catch { /* ignore */ }
  try {
    plugins.value = await systemApi.listPlugins()
  } catch { /* ignore */ }
  try {
    const s = await systemApi.eventStats()
    eventStats.value = Object.entries(s ?? {})
      .map(([name, v]) => ({ name, count: v.count ?? 0, failed: v.failed ?? 0 }))
      .sort((a, b) => b.count - a.count)
  } catch { /* ignore */ }
}

async function refreshLogs() {
  try {
    const r = await systemApi.listLogs()
    logFiles.value = r.files ?? []
  } catch { /* ignore */ }
}

async function viewLog(name: string) {
  activeLog.value = name
  try {
    const r = await systemApi.readLog(name)
    logContent.value = r.content ?? ''
  } catch {
    logContent.value = '(读取失败)'
  }
}

async function clearLogs() {
  try {
    const r = await systemApi.clearLogs()
    if (r.failed?.length) {
      toast.warning(`已清空 ${r.cleared} 个，${r.failed.length} 个失败`, r.failed.join('、'))
    } else {
      toast.success(`已清空 ${r.cleared} 个日志文件`)
    }
    logContent.value = ''
    activeLog.value = ''
    refreshLogs()
  } catch (e) {
    toast.error('清空失败', String(e))
  }
}

async function rotateKey() {
  try {
    await systemApi.rotateKey()
    toast.success('加密密钥已轮换')
    encryption.value = await systemApi.encryptionStatus()
  } catch (e) {
    toast.error('轮换失败', String(e))
  }
}

async function togglePlugin(p: PluginItem) {
  try {
    await systemApi.setPluginEnabled(p.id, !p.enabled)
    p.enabled = !p.enabled
    toast.success(p.enabled ? '插件已启用' : '插件已禁用')
  } catch (e) {
    toast.error('操作失败', String(e))
  }
}

async function discoverPlugins() {
  try {
    plugins.value = await systemApi.discoverPlugins()
    toast.success(`发现 ${plugins.value.length} 个插件`)
  } catch (e) {
    toast.error('扫描失败', String(e))
  }
}

watch(showLogs, (v) => {
  if (v && logFiles.value.length === 0) refreshLogs()
})

async function saveConfig(patch: Partial<UserConfig>) {
  saving.value = true
  try {
    userConfig.value = await authApi.update(patch)
    toast.success('已保存')
  } catch (err) {
    toast.error('保存失败', String(err))
  } finally {
    saving.value = false
  }
}

async function verifyApiKey() {
  if (!apiKey.value.trim()) {
    toast.warning('请输入 API Key')
    return
  }
  verifying.value = true
  verifyResult.value = null
  try {
    const result = await authApi.verifyApiKey(apiKey.value.trim())
    verifyResult.value = result
    if (result.valid) {
      toast.success('验证成功', `模型: ${result.model}`)
      // 验证成功后保存到用户配置
      await authApi.init({ nickname: userConfig.value?.nickname || '旅人', api_key: apiKey.value.trim() })
      await loadConfig()
    } else {
      toast.error('验证失败', 'API Key 无效')
    }
  } catch (err) {
    toast.error('验证失败', String(err))
  } finally {
    verifying.value = false
  }
}

async function exportBackup() {
  try {
    const result = await backupApi.export()
    toast.success('备份已导出', `路径: ${result.path}`)
  } catch (err) {
    toast.error('导出失败', String(err))
  }
}

function onFileSelect(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files && input.files[0]) {
    importFile.value = input.files[0]
  }
}

async function importBackup() {
  if (!importFile.value) {
    toast.warning('请选择备份文件')
    return
  }
  importing.value = true
  try {
    await backupApi.import(importFile.value)
    toast.success('导入成功', '请重启应用以生效')
  } catch (err) {
    toast.error('导入失败', String(err))
  } finally {
    importing.value = false
  }
}


// ---------- 桌宠设置（M08 P0） ----------
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

// ---------- 通知设置（M08 P0） ----------
//
// 修复（2026-09-16）：这四个开关此前只是本地 ref()，刷新即回到默认值，
// 后端 settings 表建好了却从没被读写过。现在改为读写后端配置表：
//   读 —— onMounted 拉取，未存过时由后端返回默认值；
//   写 —— 每次切换立即落库（连点 300ms 内的切换合并为一次 PUT）。
const notifyTask = ref(true)
const notifyReview = ref(true)
const notifySystem = ref(true)
const notifySound = ref(false)
const notifySaving = ref(false)

async function loadNotifySettings() {
  try {
    const res = await settingsApi.list()
    const n = settingsApi.readNotify(res.values)
    notifyTask.value = n.task
    notifyReview.value = n.review
    notifySystem.value = n.system
    notifySound.value = n.sound
  } catch (err) {
    console.error('[Settings] load notify settings failed', err)
  }
}

let notifyTimer: ReturnType<typeof setTimeout> | undefined
function saveNotifySettings() {
  clearTimeout(notifyTimer)
  // 连点合并：300ms 内的多次切换只发一次请求
  notifyTimer = setTimeout(async () => {
    notifySaving.value = true
    try {
      const res = await settingsApi.updateNotify({
        task: notifyTask.value,
        review: notifyReview.value,
        system: notifySystem.value,
        sound: notifySound.value,
      })
      const n = settingsApi.readNotify(res.values)
      notifyTask.value = n.task
      notifyReview.value = n.review
      notifySystem.value = n.system
      notifySound.value = n.sound
    } catch (err) {
      toast.error('通知设置保存失败', String(err))
    } finally {
      notifySaving.value = false
    }
  }, 300)
}
onBeforeUnmount(() => clearTimeout(notifyTimer))

// ---------- 数据目录（M08 P0） ----------
const dataDir = ref('')
async function loadDataDir() {
  try {
    const res = await fetch('http://127.0.0.1:8765/api/v1/health')
    const json = await res.json()
    dataDir.value = json.data?.data_dir || '默认目录'
  } catch {
    dataDir.value = '后端未连接'
  }
}
function openDataDir() {
  toast.info('数据目录', dataDir.value)
}
loadDataDir()

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

// ---------- 快捷键（M08 P1） ----------
const shortcuts = [
  { keys: 'Ctrl + N', desc: '新建任务/文档' },
  { keys: 'Ctrl + K', desc: '全局搜索' },
  { keys: 'Ctrl + S', desc: '保存当前内容' },
  { keys: 'Ctrl + Shift + P', desc: '命令面板' },
  { keys: 'Ctrl + ,', desc: '打开设置' },
  { keys: 'Ctrl + 1~6', desc: '切换模块' },
  { keys: 'Esc', desc: '关闭弹窗/取消' },
  { keys: 'Ctrl + /', desc: '切换桌宠显示' },
]

// ---------- 数据清理（M08 P1） ----------
const cleaning = ref(false)
const cleanCache = ref(true)
const cleanTemp = ref(true)
const cleanOldBackups = ref(false)
async function performClean() {
  cleaning.value = true
  try {
    // 清理localStorage中的临时数据
    if (cleanCache.value) {
      const keys = Object.keys(localStorage).filter(k => k.startsWith('venustech_cache_'))
      keys.forEach(k => localStorage.removeItem(k))
    }
    if (cleanTemp.value) {
      const keys = Object.keys(localStorage).filter(k => k.startsWith('venustech_temp_'))
      keys.forEach(k => localStorage.removeItem(k))
    }
    toast.success('清理完成', '已清理本地临时数据')
  } catch (err) {
    toast.error('清理失败', String(err))
  } finally {
    cleaning.value = false
  }
}

// ---------- 关于增强（M08 P1） ----------
const showChangelog = ref(false)
const changelog = [
  { version: 'v0.1.70', date: '2026-08-28', changes: ['一期工程基础版发布', '6大核心模块上线', '四套UI主题'] },
  { version: 'v0.1.71', date: '2026-09-04', changes: ['模块深度开发启动', '9个模块分支创建', 'UI组件V3.0对齐'] },
  { version: 'v0.2.0', date: '2026-09-06', changes: ['9模块深度开发完成', '四套UI主题V3.0对齐', '插件系统+加密存储', '首页跳转修复'] },
]

onMounted(() => {
  loadConfig()
  loadStats()
  loadDiagnostics()
  loadNotifySettings()
})
</script>

<template>
  <div class="settings">
    <h2 class="settings__title">设置</h2>

    <div v-if="loading" class="settings__loading">
      <AppIcon name="loading" :size="24" class="spin" />
      <span>加载中...</span>
    </div>

    <template v-else>
      <!-- 外观设置 -->
      <BaseCard title="外观" icon="palette">
        <div class="settings__group">
          <label class="settings__label">主题包</label>
          <div class="settings__theme-packs">
            <button
              v-for="t in themePacks"
              :key="t.value"
              class="settings__theme-card"
              :class="{ 'is-active': pack === t.value }"
              @click="setPack(t.value)"
            >
              <span class="settings__theme-preview" :class="`theme-${t.value}`" />
              <span class="settings__theme-name">{{ t.label }}</span>
              <span class="settings__theme-desc">{{ t.desc }}</span>
            </button>
          </div>
        </div>
        <div class="settings__group">
          <label class="settings__label">显示模式</label>
          <div class="settings__mode-btns">
            <button
              v-for="m in modeOptions"
              :key="m.value"
              class="settings__mode-btn"
              :class="{ 'is-active': mode === m.value }"
              @click="setMode(m.value)"
            >
              <AppIcon :name="m.value === 'dark' ? 'moon' : m.value === 'light' ? 'sun' : 'monitor'" :size="16" />
              {{ m.label }}
            </button>
          </div>
        </div>
      </BaseCard>

      <!-- AI 配置 -->
      <BaseCard title="AI 配置" icon="spark">
        <div class="settings__group">
          <div class="settings__row">
            <label class="settings__label">启用 AI 功能</label>
            <BaseSwitch
              :model-value="userConfig?.ai_enabled ?? false"
              @update:model-value="(v) => saveConfig({ ai_enabled: v })"
            />
          </div>
        </div>
        <div class="settings__group">
          <label class="settings__label">API Key</label>
          <div class="settings__row">
            <BaseInput
              v-model="apiKey"
              type="password"
              placeholder="输入 DeepSeek API Key"
              class="settings__input"
            />
            <BaseButton :loading="verifying" @click="verifyApiKey">验证并保存</BaseButton>
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
            @update:model-value="(v) => saveConfig({ automation_level: v as UserConfig['automation_level'] })"
          />
          <p class="settings__hint">控制第二分身的自主程度，L1 纯手动，L5 全自主</p>
        </div>
      </BaseCard>

      <!-- 第二分身 -->
      <BaseCard title="第二分身" icon="user">
        <div class="settings__group">
          <label class="settings__label">昵称</label>
          <BaseInput
            :model-value="userConfig?.nickname ?? ''"
            placeholder="你的昵称"
            class="settings__input"
            @update:model-value="(v) => saveConfig({ nickname: v })"
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
            @change="(e) => saveConfig({ inspiration_probability: Number((e.target as HTMLInputElement).value) })"
          />
        </div>
        <div class="settings__group">
          <div class="settings__row">
            <label class="settings__label">桌宠窗口置顶</label>
            <BaseSwitch
              :model-value="userConfig?.pet_topmost ?? false"
              @update:model-value="(v) => saveConfig({ pet_topmost: v })"
            />
          </div>
        </div>
      </BaseCard>


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

      <!-- 通知设置 -->
      <BaseCard title="通知设置" icon="bell">
        <p v-if="notifySaving" class="settings__hint">保存中…</p>
        <div class="settings__group">
          <div class="settings__row">
            <label class="settings__label">任务提醒</label>
            <BaseSwitch v-model="notifyTask" @change="saveNotifySettings" />
          </div>
        </div>
        <div class="settings__group">
          <div class="settings__row">
            <label class="settings__label">复盘提醒</label>
            <BaseSwitch v-model="notifyReview" @change="saveNotifySettings" />
          </div>
        </div>
        <div class="settings__group">
          <div class="settings__row">
            <label class="settings__label">系统通知</label>
            <BaseSwitch v-model="notifySystem" @change="saveNotifySettings" />
          </div>
        </div>
        <div class="settings__group">
          <div class="settings__row">
            <label class="settings__label">提示音</label>
            <BaseSwitch v-model="notifySound" @change="saveNotifySettings" />
          </div>
        </div>
      </BaseCard>

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
            <label class="settings__label">数据同步</label>
            <div style="display: flex; gap: 8px">
              <BaseButton size="sm" variant="secondary" icon="database" :loading="syncExporting" @click="onSyncExport">
                导出同步包
              </BaseButton>
              <BaseButton size="sm" variant="secondary" icon="reload" @click="syncPackagesOpen = !syncPackagesOpen">
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
              <span class="settings__sync-size">{{ Math.round(p.size / 1024) }} KB</span>
              <BaseButton size="sm" variant="secondary" icon="reload" :loading="syncImporting === p.path" @click="onSyncImport(p)">
                导入
              </BaseButton>
            </div>
          </div>
        </div>
      </BaseCard>

      <!-- 快捷键 -->
      <BaseCard title="快捷键" icon="keyboard">
        <div class="settings__shortcuts">
          <div v-for="s in shortcuts" :key="s.keys" class="settings__shortcut">
            <kbd class="settings__kbd">{{ s.keys }}</kbd>
            <span class="settings__shortcut-desc">{{ s.desc }}</span>
          </div>
        </div>
      </BaseCard>

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
            <BaseButton variant="secondary" size="sm" @click="openDataDir">打开</BaseButton>
          </div>
        </div>
        <div class="settings__group">
          <label class="settings__label">备份与恢复</label>
          <div class="settings__row">
            <BaseButton variant="secondary" @click="exportBackup">
              <AppIcon name="download" :size="16" /> 导出备份
            </BaseButton>
            <label class="settings__file-btn">
              <AppIcon name="upload" :size="16" /> 导入备份
              <input type="file" accept=".zip" hidden @change="onFileSelect" />
            </label>
            <BaseButton :loading="importing" :disabled="!importFile" @click="importBackup">
              确认导入
            </BaseButton>
          </div>
          <p v-if="importFile" class="settings__hint">已选择: {{ importFile.name }}</p>
          <p class="settings__hint">导入将覆盖当前数据，需重启应用生效</p>
        </div>
      </BaseCard>

      <!-- 系统与诊断：把后端早已存在、但此前没有入口的能力接出来 -->
      <BaseCard title="系统与诊断" icon="setting">
        <p class="settings__hint">这些能力后端一直都在，此前只是缺少界面入口。</p>

        <div class="settings__group">
          <button class="settings__link-btn" @click="showSecurity = !showSecurity">
            <AppIcon name="alert" :size="14" /> 加密存储
            <AppIcon :name="showSecurity ? 'chevron-up' : 'chevron-down'" :size="14" />
          </button>
          <div v-if="showSecurity" class="settings__diag">
            <p v-if="encryption" class="settings__hint">
              状态：{{ encryption.available ? '已启用' : '不可用' }}
            </p>
            <div class="settings__row">
              <BaseButton variant="secondary" size="sm" @click="rotateKey">轮换密钥</BaseButton>
            </div>
            <p class="settings__hint">轮换会用新密钥重新加密数据，旧密钥立即失效。</p>
          </div>
        </div>

        <div class="settings__group">
          <button class="settings__link-btn" @click="showLogs = !showLogs">
            <AppIcon name="doc" :size="14" /> 系统日志
            <AppIcon :name="showLogs ? 'chevron-up' : 'chevron-down'" :size="14" />
          </button>
          <div v-if="showLogs" class="settings__diag">
            <div class="settings__row">
              <BaseButton variant="secondary" size="sm" @click="refreshLogs">刷新列表</BaseButton>
              <BaseButton variant="secondary" size="sm" @click="clearLogs">清空日志</BaseButton>
            </div>
            <div v-if="logFiles.length" class="settings__log-list">
              <button
                v-for="f in logFiles"
                :key="f.name"
                class="settings__log-item"
                :class="{ 'is-active': activeLog === f.name }"
                @click="viewLog(f.name)"
              >
                {{ f.name }} · {{ f.size_kb }} KB
              </button>
            </div>
            <p v-else class="settings__hint">暂无日志文件</p>
            <pre v-if="logContent" class="settings__log-content">{{ logContent }}</pre>
          </div>
        </div>

        <div class="settings__group">
          <button class="settings__link-btn" @click="showEvents = !showEvents">
            <AppIcon name="chart" :size="14" /> 事件总线
            <AppIcon :name="showEvents ? 'chevron-up' : 'chevron-down'" :size="14" />
          </button>
          <div v-if="showEvents" class="settings__diag">
            <p v-if="eventStats.length === 0" class="settings__hint">暂无事件记录</p>
            <ul v-else class="settings__event-list">
              <li v-for="e in eventStats" :key="e.name">
                <span class="settings__event-name">{{ e.name }}</span>
                <span class="settings__event-count">
                  {{ e.count }} 次<template v-if="e.failed"> · 失败 {{ e.failed }}</template>
                </span>
              </li>
            </ul>
          </div>
        </div>

        <div class="settings__group">
          <button class="settings__link-btn" @click="showPlugins = !showPlugins">
            <AppIcon name="command" :size="14" /> 插件
            <AppIcon :name="showPlugins ? 'chevron-up' : 'chevron-down'" :size="14" />
          </button>
          <div v-if="showPlugins" class="settings__diag">
            <div class="settings__row">
              <BaseButton variant="secondary" size="sm" @click="discoverPlugins">扫描插件</BaseButton>
            </div>
            <div v-if="plugins.length" class="settings__plugin-list">
              <div v-for="p in plugins" :key="p.id" class="settings__plugin">
                <span class="settings__plugin-name">{{ p.name }} v{{ p.version }}</span>
                <BaseSwitch :model-value="p.enabled" @update:model-value="togglePlugin(p)" />
              </div>
            </div>
            <p v-else class="settings__hint">暂无插件 —— 插件目录还没有内容</p>
          </div>
        </div>
      </BaseCard>

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
          <button class="settings__link-btn" @click="showChangelog = !showChangelog">
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

  &__group {
    padding: var(--space-3) 0;
    border-bottom: 1px solid var(--line);
    &:last-child { border-bottom: none; }
  }

  &__label {
    display: block;
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--text-hi);
    margin-bottom: var(--space-2);
  }

  &__row {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  &__input {
    flex: 1;
  }

  &__select {
    width: 100%;
    max-width: 240px;
  }

  &__hint {
    font-size: var(--text-xs);
    color: var(--text-low);
    margin-top: var(--space-2);
    display: flex;
    align-items: center;
    gap: 4px;
    &--success { color: var(--mint); }
  }

  &__dir {
    flex: 1;
    font-size: var(--text-xs);
    color: var(--text-mid);
    background: var(--bg-inset);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    font-family: monospace;
    word-break: break-all;
  }

  &__value {
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--primary);
  }

  /* 主题包选择 */
  &__theme-packs {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: var(--space-3);
  }

  &__theme-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-3);
    border: 2px solid var(--line);
    border-radius: var(--radius-md);
    background: var(--bg-panel);
    transition: all 0.2s var(--ease-soft);
    &:hover { border-color: var(--primary-soft); }
    &.is-active {
      border-color: var(--primary);
      box-shadow: var(--glow);
    }
  }

  &__theme-preview {
    width: 100%;
    height: 48px;
    border-radius: var(--radius-sm);
    margin-bottom: var(--space-1);
    &.theme-cream { background: linear-gradient(135deg, #FFF5E6, #FFE4E1, #E8F5E9); }
    &.theme-guofeng { background: linear-gradient(135deg, #F5E6D3, #D4A574, #8B6914); }
    &.theme-abyss { background: linear-gradient(135deg, #1a1a2e, #16213e, #0f3460); }
    &.theme-epic { background: linear-gradient(135deg, #FAF6EE, #F5EFE0, #C89B3C); }
  }

  &__theme-name {
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--text-hi);
  }

  &__theme-desc {
    font-size: 10px;
    color: var(--text-low);
  }

  /* 模式切换 */
  &__mode-btns {
    display: flex;
    gap: var(--space-2);
  }

  &__mode-btn {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    font-size: var(--text-sm);
    color: var(--text-mid);
    background: var(--bg-panel);
    transition: all 0.2s;
    &.is-active {
      border-color: var(--primary);
      color: var(--primary);
      background: var(--primary-soft);
    }
  }

  /* 滑块 */
  &__slider {
    width: 100%;
    accent-color: var(--primary);
  }

  /* 数据统计 */
  &__stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: var(--space-3);
  }

  &__stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: var(--space-3);
    background: var(--bg-inset);
    border-radius: var(--radius-md);
  }

  &__stat-num {
    font-size: var(--text-xl);
    font-weight: 700;
    color: var(--primary);
    font-family: var(--font-cute);
  }

  &__stat-label {
    font-size: var(--text-xs);
    color: var(--text-low);
    margin-top: 2px;
  }

  /* 文件按钮 */
  &__file-btn {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    font-size: var(--text-sm);
    color: var(--text-mid);
    background: var(--bg-panel);
    cursor: pointer;
    transition: all 0.2s;
    &:hover { border-color: var(--primary); color: var(--primary); }
  }

  /* 关于 */
  &__about {
    display: flex;
    align-items: center;
    gap: var(--space-4);
  }

  &__about-logo {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 64px;
    height: 64px;
    border-radius: var(--radius-lg);
    background: linear-gradient(135deg, var(--primary), var(--lilac));
    color: var(--white);
    box-shadow: var(--glow);
  }

  &__about-info h3 {
    font-size: var(--text-lg);
    font-weight: 700;
    color: var(--text-hi);
    font-family: var(--font-cute);
  }

  &__about-info p {
    font-size: var(--text-sm);
    color: var(--text-mid);
    margin-top: 2px;
  }

  &__about-version {
    font-size: var(--text-xs) !important;
    color: var(--text-low) !important;
  }
}

.settings {
  /* 快捷键 */
  &__shortcuts { display: flex; flex-direction: column; gap: var(--space-2); }
  &__shortcut { display: flex; align-items: center; justify-content: space-between; padding: var(--space-1) 0; }
  &__kbd {
    display: inline-block; padding: 2px 8px; background: var(--bg-inset);
    border: 1px solid var(--line); border-radius: 4px; font-size: 11px;
    font-family: monospace; color: var(--text-mid); min-width: 100px; text-align: center;
  }
  &__shortcut-desc { font-size: var(--text-sm); color: var(--text-mid); }

  /* 链接按钮 */
  &__link-btn {
    display: flex; align-items: center; gap: 6px; width: 100%;
    padding: var(--space-2); background: none; border: none;
    font-size: var(--text-sm); color: var(--primary); cursor: pointer;
    &:hover { background: var(--primary-soft); border-radius: var(--radius-sm); }
  }

  /* 更新日志 */
  &__changelog { margin-top: var(--space-2); max-height: 300px; overflow-y: auto; }
  &__changelog-item { padding: var(--space-2) 0; border-bottom: 1px solid var(--line); &:last-child { border-bottom: none; } }
  &__changelog-header { display: flex; justify-content: space-between; margin-bottom: 4px; }
  &__changelog-version { font-weight: 700; color: var(--text-hi); font-size: var(--text-sm); }
  &__changelog-date { font-size: 11px; color: var(--text-low); }
  &__changelog-list { margin: 0; padding-left: 16px; font-size: var(--text-xs); color: var(--text-mid); }
  &__changelog-list li { margin: 2px 0; }

  /* 系统与诊断 */
  &__diag {
    margin-top: var(--space-2);
    padding: var(--space-3);
    background: var(--bg-inset);
    border-radius: var(--radius-md);
  }
  &__log-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin: var(--space-2) 0;
  }
  &__log-item {
    padding: 4px 10px;
    border: 1px solid var(--line);
    border-radius: var(--radius-pill);
    background: var(--bg-panel);
    color: var(--text-mid);
    font-size: var(--text-xs);
    cursor: pointer;
    &:hover {
      border-color: var(--primary);
      color: var(--primary);
    }
    &.is-active {
      background: var(--primary-soft);
      border-color: var(--primary);
      color: var(--primary-ink);
    }
  }
  &__log-content {
    margin: var(--space-2) 0 0;
    padding: var(--space-3);
    max-height: 280px;
    overflow: auto;
    background: var(--bg-panel);
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    font-family: var(--font-mono, monospace);
    font-size: 11px;
    line-height: 1.6;
    color: var(--text-mid);
    white-space: pre-wrap;
  }
  &__event-list {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  &__event-list li {
    display: flex;
    justify-content: space-between;
    padding: 4px 0;
    font-size: var(--text-sm);
  }
  &__event-name {
    color: var(--text-mid);
  }
  &__event-count {
    color: var(--text-low);
    font-size: var(--text-xs);
  }
  &__plugin-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: var(--space-2);
  }
  &__plugin {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
  }
  &__plugin-name {
    font-size: var(--text-sm);
    color: var(--text-hi);
  }
.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
}

.settings__sync-packages {
  margin-top: var(--space-2);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.settings__sync-pkg {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px var(--space-2);
  border-radius: var(--radius-sm);
  background: var(--bg-inset);
}
.settings__sync-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  color: var(--text-mid);
}
.settings__sync-size {
  font-size: var(--text-xs);
  color: var(--text-low);
}
</style>
