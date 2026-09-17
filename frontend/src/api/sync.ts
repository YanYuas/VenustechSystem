// ============================================================
// 同步 API（S6-3b 前端出口）
// ============================================================
import { http } from './http'

export interface SyncPolicyOut {
  policy: Record<string, string>
  synced_tables: string[]
}

export interface SyncPackage {
  name: string
  path: string
  size: number
  modified_at: number
}

export interface SyncImportStats {
  ops: number
  insert: number
  update: number
  skipped: number
}

export const syncApi = {
  policy() {
    return http.get<SyncPolicyOut>('/sync/policy')
  },
  /** 可导入的同步包列表（数据目录 exports/，按时间倒序） */
  packages() {
    return http.get<{ dir: string; items: SyncPackage[] }>('/sync/packages')
  },
  /** 导出同步包（缺省目录 = 数据目录 exports/） */
  export(dir?: string) {
    return http.post<{ path: string }>('/sync/export', dir ? { dir } : {})
  },
  import(path: string) {
    return http.post<SyncImportStats>('/sync/import', { path })
  },
}
