// ============================================================
// 同步 API（S6-3b 前端出口）
// ============================================================
import { http } from '@/kernel/http'
import type { SyncPolicyOut, SyncPackage, SyncImportStats } from './model'

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
