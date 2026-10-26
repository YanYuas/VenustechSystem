// ============================================================
// 仪表盘 & 备份 API
// 对应 PRD §13.7 / §13.8
// ============================================================
import { http } from './http'
import type { DashboardData } from '@/types'

export const dashboardApi = {
  get() {
    return http.get<DashboardData>('/dashboard')
  },
}

export const backupApi = {
  export() {
    return http.post<{ path: string }>('/backup/export')
  },
  /**
   * 导入备份包（multipart 上传）。
   *
   * 必须走 `postForm`：`http.post` 会 JSON.stringify 请求体并把 Content-Type 设成
   * application/json，FormData 会变成 "{}"，后端 `UploadFile = File(...)` 必然 422。
   * /backup/verify 也要求 multipart，但前端当前未调用（导入前预检由 import 内部完成）。
   */
  import(file: File) {
    const form = new FormData()
    form.append('file', file)
    // 后端返回 backup_service.import_() 的完整结果；其余字段前端暂未使用，先按可选声明
    return http.postForm<{
      success: boolean
      restart_required?: boolean
      backup_of_original?: string
      manifest_version?: string | null
    }>('/backup/import', form)
  },
  stats() {
    return http.get<{ documents: number; tasks: number; tags: number; conversations: number }>('/data/stats')
  },
}
