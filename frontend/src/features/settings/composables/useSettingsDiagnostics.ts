// ============================================================
// 设置页 —— 系统与诊断（加密 / 日志 / 事件总线 / 插件 / 规则引擎）
//
// 拆分自 SettingsView.vue（D-09），逻辑逐字保留。
//
// 这四个模块后端一直都在，但此前前端没有任何入口 —— 相当于埋没了。
// 这里只做「接出来 + 展示」；危险操作（轮换密钥、清空日志）都保留确认。
// ============================================================
import { ref, computed, watch, onScopeDispose } from 'vue'
import { systemApi } from '@/features/system'
import { useToast } from '@/kernel/ui/toast'
import { useModal } from '@/kernel/ui/modal'
import type { EncryptionStatus, LogFile, PluginItem } from '@/features/system'

export function useSettingsDiagnostics() {
  const toast = useToast()
  const { confirm } = useModal()

  const encryption = ref<EncryptionStatus | null>(null)
  const logFiles = ref<LogFile[]>([])
  const logContent = ref('')
  const activeLog = ref('')
  const eventStats = ref<
    Array<{
      name: string
      count: number
      failed: number
      failedHandlers: string[]
      alert: boolean
    }>
  >([])
  let lastAlertedEvent = ''
  const activeEvent = ref('')
  const eventTimeline = ref<
    Array<{ time?: string; success?: boolean; failed_handlers?: string[] }>
  >([])
  const failedHandlerSummary = computed(() =>
    Array.from(new Set(eventStats.value.flatMap((e) => e.failedHandlers))).join('、'),
  )

  // ---------- 规则引擎调试（F4.3） ----------
  const showRules = ref(false)
  const ruleText = ref('')
  const ruleDomains = ref({ builtin: 0, user: 0 })
  const rulePreview = ref<{
    matched: boolean
    domain_name: string | null
    plans: Array<{ unit: string; task: string; duration: string }>
  } | null>(null)
  let ruleTimer: ReturnType<typeof setTimeout> | null = null

  async function loadRuleDomains() {
    try {
      const d = await systemApi.ruleDomains()
      ruleDomains.value = { builtin: d.builtin_count, user: d.user_count }
    } catch {
      /* 诊断面板失败不阻塞设置页 */
    }
  }

  function onRuleInput() {
    if (ruleTimer) clearTimeout(ruleTimer)
    // 输入停止 400ms 后再预览（PRD F4.3）
    ruleTimer = setTimeout(async () => {
      const text = ruleText.value.trim()
      if (!text) {
        rulePreview.value = null
        return
      }
      try {
        rulePreview.value = await systemApi.rulePreview(text)
      } catch {
        rulePreview.value = null
      }
    }, 400)
  }

  watch(ruleText, onRuleInput)

  // D-27：400ms 规则预览防抖定时器必须在作用域销毁时清掉。
  // 否则设置页已卸载后仍会触发一次 systemApi.rulePreview，并写已销毁的 ref。
  onScopeDispose(() => {
    if (ruleTimer) {
      clearTimeout(ruleTimer)
      ruleTimer = null
    }
  })

  async function onReloadDomains() {
    try {
      const r = await systemApi.ruleReload()
      ruleDomains.value = { builtin: r.builtin, user: r.user }
      toast.success('领域库已热重载', `用户扩展 ${r.user} 个`)
    } catch {
      toast.error('热重载失败')
    }
  }

  async function toggleEventDetail(name: string) {
    if (activeEvent.value === name) {
      activeEvent.value = ''
      return
    }
    activeEvent.value = name
    try {
      eventTimeline.value = await systemApi.eventHistory(10, name)
    } catch {
      eventTimeline.value = []
    }
  }

  async function onClearEvents() {
    const ok = await confirm({
      title: '清空事件历史',
      message: '仅清空内存中的历史记录，订阅关系与统计不受影响。',
    })
    if (!ok) return
    try {
      await systemApi.clearEventHistory()
      eventStats.value = []
      activeEvent.value = ''
      toast.success('事件历史已清空')
    } catch {
      toast.error('清空失败')
    }
  }
  const plugins = ref<PluginItem[]>([])

  const showSecurity = ref(false)
  const showLogs = ref(false)
  const showEvents = ref(false)
  const showPlugins = ref(false)

  async function loadDiagnostics() {
    // 每项独立 try：任一失败不该连累其他面板（例如插件目录不存在）
    try {
      encryption.value = await systemApi.encryptionStatus()
    } catch {
      /* ignore */
    }
    try {
      plugins.value = await systemApi.listPlugins()
    } catch {
      /* ignore */
    }
    try {
      const s = await systemApi.eventStats()
      eventStats.value = Object.entries(s ?? {})
        .map(([name, v]) => ({
          name,
          count: (v as { count?: number }).count ?? 0,
          failed: (v as { failed?: number }).failed ?? 0,
          failedHandlers: (v as { failed_handlers?: string[] }).failed_handlers ?? [],
          alert: Boolean((v as { alert?: boolean }).alert),
        }))
        .sort((a, b) => b.count - a.count)
      // 连续失败告警（PRD F1.2）：达阈值的事件提示一次
      const hot = eventStats.value.find((e) => e.alert && e.failed >= 5)
      if (hot && hot.name !== lastAlertedEvent) {
        lastAlertedEvent = hot.name
        toast.error(`事件 ${hot.name} 持续失败`, '请检查插件或服务')
      }
    } catch {
      /* ignore */
    }
  }

  async function refreshLogs() {
    try {
      const r = await systemApi.listLogs()
      logFiles.value = r.files ?? []
    } catch {
      /* ignore */
    }
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

  // ---------- 折叠面板开关（模板里只引用函数，保持原点击行为） ----------
  function toggleShowSecurity() {
    showSecurity.value = !showSecurity.value
  }
  function toggleShowLogs() {
    showLogs.value = !showLogs.value
  }
  function toggleShowEvents() {
    showEvents.value = !showEvents.value
  }
  function toggleShowRules() {
    showRules.value = !showRules.value
  }
  function toggleShowPlugins() {
    showPlugins.value = !showPlugins.value
  }
  function setRuleText(v: string) {
    ruleText.value = v
  }

  return {
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
  }
}
