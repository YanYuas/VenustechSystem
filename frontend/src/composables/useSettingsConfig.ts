// ============================================================
// 设置页 —— 用户配置 / AI 配置 / 通知设置
//
// 拆分自 SettingsView.vue（D-09），逻辑逐字保留：
//   - loadConfig / saveConfig（PATCH 后回填 userConfig 并 toast）
//   - 昵称防抖 800ms 自动提交
//   - verifyApiKey（验证成功后 authApi.init + 重新 loadConfig）
//   - 通知开关读写后端 settings 表（连点 300ms 合并为一次 PUT）
// ============================================================
import { ref, watch, onBeforeUnmount } from 'vue'
import { authApi, settingsApi } from '@/api'
import { useToast } from '@/composables/useToast'
import type { UserConfig } from '@/types'

export function useSettingsConfig() {
  const toast = useToast()

  // 用户配置
  const userConfig = ref<UserConfig | null>(null)
  const loading = ref(false)
  const saving = ref(false)

  // AI 配置
  const apiKey = ref('')
  const verifying = ref(false)
  const verifyResult = ref<{ valid: boolean; model: string } | null>(null)

  // 昵称：本地草稿 + 防抖提交（避免每个击键发一次 PATCH）
  const nicknameDraft = ref('')
  let nicknameTimer: ReturnType<typeof setTimeout> | undefined

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

  watch(nicknameDraft, (v) => {
    clearTimeout(nicknameTimer)
    nicknameTimer = setTimeout(() => {
      const name = v.trim()
      if (name && name !== userConfig.value?.nickname) saveConfig({ nickname: name })
    }, 800)
  })
  onBeforeUnmount(() => clearTimeout(nicknameTimer))

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

  return {
    userConfig,
    loading,
    saving,
    apiKey,
    verifying,
    verifyResult,
    nicknameDraft,
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
  }
}
