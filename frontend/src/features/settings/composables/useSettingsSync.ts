// ============================================================
// 设置页 —— 数据同步 / 数据统计 / 备份恢复 / 数据目录
//
// 拆分自 SettingsView.vue（D-09），逻辑逐字保留：
//   - 服务器地址与访问令牌（App 壳用，运行时覆盖 baseURL）
//   - 全库同步包导出 / 列表 / 导入
//   - 数据统计（文档/任务/标签/对话）
//   - 备份导出 / 导入（zip）
//   - 数据目录（health 接口的 data_dir，失败显示「后端未连接」）
// ============================================================
import { ref } from 'vue'
import { syncApi } from '@/features/sync'
import { backupApi } from '@/features/dashboard'
import type { SyncPackage } from '@/features/sync'
import { getApiBase, setApiBase, getApiToken, setApiToken } from '@/kernel/http'
import { useToast } from '@/kernel/ui/toast'

export function useSettingsSync() {
  const toast = useToast()

  // ---------- 数据同步（S6-3b 前端出口） ----------
  const syncExporting = ref(false)
  const syncImporting = ref('')
  const apiBaseDraft = ref(getApiBase())
  const tokenDraft = ref(getApiToken())

  function onSaveApiBase() {
    setApiToken(tokenDraft.value)
    setApiBase(apiBaseDraft.value)
    toast.success('服务器地址已保存', '重新进入页面后生效')
  }
  const syncPackagesOpen = ref(false)
  const syncPackages = ref<SyncPackage[]>([])

  async function onSyncExport() {
    syncExporting.value = true
    try {
      const res = await syncApi.export()
      toast.success('同步包已导出', res.path)
      await loadSyncPackages()
      syncPackagesOpen.value = true
    } catch {
      /* http 层已提示 */
    } finally {
      syncExporting.value = false
    }
  }

  async function loadSyncPackages() {
    try {
      syncPackages.value = (await syncApi.packages()).items
    } catch {
      /* http 层已提示 */
    }
  }

  async function onSyncImport(p: SyncPackage) {
    syncImporting.value = p.path
    try {
      const s = await syncApi.import(p.path)
      if (s.ops === 0) toast.info('没有需要应用的变化', '本地数据已是最新（LWW）')
      else toast.success(`已应用 ${s.ops} 处变化`, `新增 ${s.insert} · 更新 ${s.update}`)
    } catch {
      /* http 层已提示 */
    } finally {
      syncImporting.value = ''
    }
  }

  function toggleSyncPackages() {
    syncPackagesOpen.value = !syncPackagesOpen.value
  }

  // ---------- 数据统计 ----------
  const dataStats = ref<{
    documents: number
    tasks: number
    tags: number
    conversations: number
  } | null>(null)

  async function loadStats() {
    try {
      dataStats.value = await backupApi.stats()
    } catch {
      /* ignore */
    }
  }

  // ---------- 备份导入 ----------
  const importFile = ref<File | null>(null)
  const importing = ref(false)

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

  return {
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
    loadSyncPackages,
    onSyncImport,
    toggleSyncPackages,
    loadStats,
    exportBackup,
    onFileSelect,
    importBackup,
    loadDataDir,
    openDataDir,
  }
}
