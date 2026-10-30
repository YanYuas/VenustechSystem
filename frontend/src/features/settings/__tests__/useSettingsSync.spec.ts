// ============================================================
// useSettingsSync —— 设置页「数据同步 / 统计 / 备份 / 数据目录」单元测试
//
// 纯编排 composable（无生命周期钩子），直接调用即可；领域 api、http 配置
// 读写、toast 全部 mock，health 请求用 stub fetch，不真连后端。
// ============================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { syncApi } from '@/features/sync'
import { backupApi } from '@/features/dashboard'
import { getApiBase, getApiToken, setApiBase, setApiToken } from '@/kernel/http'
import type { SyncPackage } from '@/features/sync'
import { useSettingsSync } from '../composables/useSettingsSync'

vi.mock('@/features/sync', () => ({
  syncApi: { export: vi.fn(), packages: vi.fn(), import: vi.fn() },
}))
vi.mock('@/features/dashboard', () => ({
  backupApi: { stats: vi.fn(), export: vi.fn(), import: vi.fn() },
}))
vi.mock('@/kernel/http', () => ({
  getApiBase: vi.fn(),
  getApiToken: vi.fn(),
  setApiBase: vi.fn(),
  setApiToken: vi.fn(),
}))

const toastMock = vi.hoisted(() => ({
  error: vi.fn(),
  success: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
}))
vi.mock('@/kernel/ui/toast', () => ({ toast: toastMock, useToast: () => toastMock }))

type AnyMock = ReturnType<typeof vi.fn>
const sync = syncApi as unknown as { export: AnyMock; packages: AnyMock; import: AnyMock }
const backup = backupApi as unknown as { stats: AnyMock; export: AnyMock; import: AnyMock }
const http = { getApiBase, getApiToken, setApiBase, setApiToken } as unknown as Record<
  string,
  AnyMock
>
const toastSuccess = toastMock.success
const toastError = toastMock.error
const toastInfo = toastMock.info
const toastWarning = toastMock.warning

function makePackage(patch: Partial<SyncPackage> = {}): SyncPackage {
  return {
    name: 'pkg-a',
    path: '/tmp/pkg-a.json',
    size: 2048,
    created_at: '2026-10-30T10:00:00',
    ...patch,
  } as unknown as SyncPackage
}

function stubFetch(impl: (input: RequestInfo | URL) => Promise<Response>) {
  const mock = vi.fn(impl)
  vi.stubGlobal('fetch', mock)
  return mock
}

beforeEach(() => {
  vi.clearAllMocks()
  http.getApiBase.mockReturnValue('http://127.0.0.1:8765/api/v1')
  http.getApiToken.mockReturnValue('tok-1')
  sync.export.mockResolvedValue({ path: '/tmp/export.json' })
  sync.packages.mockResolvedValue({ dir: '/tmp', items: [makePackage()] })
  sync.import.mockResolvedValue({ ops: 3, insert: 1, update: 2 })
  backup.stats.mockResolvedValue({ documents: 1, tasks: 2, tags: 3, conversations: 4 })
  backup.export.mockResolvedValue({ path: '/tmp/backup.zip' })
  backup.import.mockResolvedValue(undefined)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useSettingsSync：服务器地址与令牌', () => {
  it('初始草稿来自当前运行时配置', () => {
    const s = useSettingsSync()

    expect(s.apiBaseDraft.value).toBe('http://127.0.0.1:8765/api/v1')
    expect(s.tokenDraft.value).toBe('tok-1')
  })

  it('保存：先写 token 再写 base（避免新地址配旧令牌），并 toast', () => {
    const s = useSettingsSync()
    s.apiBaseDraft.value = 'http://10.0.0.5:3000/api/v1'
    s.tokenDraft.value = 'tok-new'

    s.onSaveApiBase()

    expect(http.setApiToken).toHaveBeenCalledWith('tok-new')
    expect(http.setApiBase).toHaveBeenCalledWith('http://10.0.0.5:3000/api/v1')
    expect(toastSuccess).toHaveBeenCalledWith('服务器地址已保存', '重新进入页面后生效')
  })
})

describe('useSettingsSync：同步包导出 / 列表 / 导入', () => {
  it('导出成功：toast 路径、刷新列表并自动展开列表', async () => {
    const s = useSettingsSync()

    const pending = s.onSyncExport()
    expect(s.syncExporting.value).toBe(true)
    await pending

    expect(sync.export).toHaveBeenCalledTimes(1)
    expect(toastSuccess).toHaveBeenCalledWith('同步包已导出', '/tmp/export.json')
    expect(sync.packages).toHaveBeenCalledTimes(1)
    expect(s.syncPackages.value).toHaveLength(1)
    expect(s.syncPackagesOpen.value).toBe(true)
    expect(s.syncExporting.value).toBe(false)
  })

  it('导出失败：不抛错、loading 复位、不展开列表', async () => {
    sync.export.mockRejectedValueOnce(new Error('export down'))
    const s = useSettingsSync()

    await s.onSyncExport()

    expect(s.syncExporting.value).toBe(false)
    expect(s.syncPackagesOpen.value).toBe(false)
    expect(s.syncPackages.value).toHaveLength(0)
  })

  it('loadSyncPackages 成功写入 items；失败时保留旧列表', async () => {
    const s = useSettingsSync()
    await s.loadSyncPackages()
    expect(s.syncPackages.value.map((p) => p.name)).toEqual(['pkg-a'])

    sync.packages.mockRejectedValueOnce(new Error('list down'))
    await s.loadSyncPackages()
    expect(s.syncPackages.value.map((p) => p.name)).toEqual(['pkg-a'])
  })

  it('导入：ops=0 时提示"没有需要应用的变化"', async () => {
    sync.import.mockResolvedValueOnce({ ops: 0, insert: 0, update: 0 })
    const s = useSettingsSync()

    await s.onSyncImport(makePackage())

    expect(sync.import).toHaveBeenCalledWith('/tmp/pkg-a.json')
    expect(toastInfo).toHaveBeenCalledWith('没有需要应用的变化', '本地数据已是最新（LWW）')
    expect(s.syncImporting.value).toBe('')
  })

  it('导入：ops>0 时提示应用数量与新增/更新明细，并在期间标记 importing', async () => {
    let release: ((v: unknown) => void) | undefined
    sync.import.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          release = resolve
        }),
    )
    const s = useSettingsSync()

    const pending = s.onSyncImport(makePackage({ path: '/tmp/pkg-b.json' }))
    expect(s.syncImporting.value).toBe('/tmp/pkg-b.json')

    release?.({ ops: 3, insert: 1, update: 2 })
    await pending

    expect(toastSuccess).toHaveBeenCalledWith('已应用 3 处变化', '新增 1 · 更新 2')
    expect(s.syncImporting.value).toBe('')
  })

  it('导入失败：静默（http 层已提示），但 importing 复位', async () => {
    sync.import.mockRejectedValueOnce(new Error('import down'))
    const s = useSettingsSync()

    await s.onSyncImport(makePackage())

    expect(s.syncImporting.value).toBe('')
    expect(toastError).not.toHaveBeenCalled()
  })

  it('toggleSyncPackages 翻转展开状态', () => {
    const s = useSettingsSync()
    expect(s.syncPackagesOpen.value).toBe(false)

    s.toggleSyncPackages()
    expect(s.syncPackagesOpen.value).toBe(true)

    s.toggleSyncPackages()
    expect(s.syncPackagesOpen.value).toBe(false)
  })
})

describe('useSettingsSync：数据统计与备份', () => {
  it('loadStats 成功写入；失败保持 null 且不抛错', async () => {
    const s = useSettingsSync()
    await s.loadStats()
    expect(s.dataStats.value).toEqual({ documents: 1, tasks: 2, tags: 3, conversations: 4 })

    backup.stats.mockRejectedValueOnce(new Error('stats down'))
    await expect(s.loadStats()).resolves.toBeUndefined()
    expect(s.dataStats.value).toEqual({ documents: 1, tasks: 2, tags: 3, conversations: 4 })
  })

  it('导出备份：成功 toast 路径；失败 toast 错误', async () => {
    const s = useSettingsSync()
    await s.exportBackup()
    expect(toastSuccess).toHaveBeenCalledWith('备份已导出', '路径: /tmp/backup.zip')

    backup.export.mockRejectedValueOnce(new Error('zip down'))
    await s.exportBackup()
    expect(toastError).toHaveBeenCalledWith('导出失败', 'Error: zip down')
  })

  it('onFileSelect：有文件时记录；无文件时忽略', () => {
    const s = useSettingsSync()
    const file = new File(['{}'], 'backup.zip')

    s.onFileSelect({ target: { files: [file] } } as unknown as Event)
    expect(s.importFile.value).toBe(file)

    s.onFileSelect({ target: { files: [] } } as unknown as Event)
    expect(s.importFile.value).toBe(file)
  })

  it('导入备份：未选文件先 warning，不调用 api', async () => {
    const s = useSettingsSync()

    await s.importBackup()

    expect(toastWarning).toHaveBeenCalledWith('请选择备份文件')
    expect(backup.import).not.toHaveBeenCalled()
  })

  it('导入备份：成功 toast 并复位 importing；失败 toast 错误', async () => {
    const s = useSettingsSync()
    const file = new File(['{}'], 'backup.zip')
    s.importFile.value = file

    const pending = s.importBackup()
    expect(s.importing.value).toBe(true)
    await pending
    expect(backup.import).toHaveBeenCalledWith(file)
    expect(toastSuccess).toHaveBeenCalledWith('导入成功', '请重启应用以生效')
    expect(s.importing.value).toBe(false)

    backup.import.mockRejectedValueOnce(new Error('bad zip'))
    await s.importBackup()
    expect(toastError).toHaveBeenCalledWith('导入失败', 'Error: bad zip')
    expect(s.importing.value).toBe(false)
  })
})

describe('useSettingsSync：数据目录', () => {
  it('loadDataDir：健康检查返回 data_dir 时展示；缺失时回落默认目录', async () => {
    const fetchMock = stubFetch(
      async () =>
        ({
          json: async () => ({ data: { data_dir: '/data/qmx' } }),
        }) as unknown as Response,
    )
    const s = useSettingsSync()

    await s.loadDataDir()
    expect(fetchMock.mock.calls[0][0]).toBe('http://127.0.0.1:8765/api/v1/health')
    expect(s.dataDir.value).toBe('/data/qmx')

    stubFetch(async () => ({ json: async () => ({ data: {} }) }) as unknown as Response)
    await s.loadDataDir()
    expect(s.dataDir.value).toBe('默认目录')
  })

  it('loadDataDir：请求失败时显示"后端未连接"', async () => {
    stubFetch(async () => {
      throw new TypeError('Failed to fetch')
    })
    const s = useSettingsSync()

    await s.loadDataDir()

    expect(s.dataDir.value).toBe('后端未连接')
  })

  it('openDataDir：toast 当前数据目录', () => {
    const s = useSettingsSync()
    s.dataDir.value = '/data/qmx'

    s.openDataDir()

    expect(toastInfo).toHaveBeenCalledWith('数据目录', '/data/qmx')
  })
})
