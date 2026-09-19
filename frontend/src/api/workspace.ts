// ============================================================
// 工作区 API（三期 C · 可选功能 + 引导部署）
// ============================================================
import { http } from './http'
import type {
  WorkspaceRoot, WorkspaceStatus, WorkspaceFilesOut, SkeletonResult,
} from '@/types'

export const workspaceApi = {
  /** 功能状态（开关 + 根概况）—— 引导向导首屏 */
  status() {
    return http.get<WorkspaceStatus>('/workspace/status')
  },
  /** 启用/停用整个工作区功能 */
  setEnabled(enabled: boolean) {
    return http.put<Record<string, string>>('/workspace/enabled', { enabled })
  },
  roots() {
    return http.get<WorkspaceRoot[]>('/workspace/roots')
  },
  /** 引导路径 a：登记用户现有文件夹 */
  registerRoot(path: string, label?: string, identity_id?: string) {
    return http.post<WorkspaceRoot>('/workspace/roots', { path, label, identity_id })
  },
  updateRoot(id: string, data: { label?: string; enabled?: boolean; identity_id?: string }) {
    return http.patch<WorkspaceRoot>(`/workspace/roots/${id}`, data)
  },
  /** 删根 + 清索引（后端保证不碰磁盘文件） */
  removeRoot(id: string) {
    return http.delete<{ deleted: boolean }>(`/workspace/roots/${id}`)
  },
  /** 启动异步扫描（P1-4）：立即返回 scanning 态，随后用 scanProgress 轮询 */
  scan(id: string) {
    return http.post<WorkspaceRoot>(`/workspace/roots/${id}/scan`)
  },
  /** 引导路径 b：按用户自己的活跃身份生成目录骨架 */
  buildSkeleton(id: string) {
    return http.post<SkeletonResult>(`/workspace/roots/${id}/skeleton`)
  },
  files(rootId: string, params?: { search?: string; page?: number; page_size?: number }) {
    return http.get<WorkspaceFilesOut>('/workspace/files', {
      root_id: rootId, ...params,
    } as Record<string, unknown>)
  },
  /** 扫描进度（P1-4） */
  scanProgress(rootId: string) {
    return http.get<{
      root_id: string
      status: 'never' | 'scanning' | 'ok' | 'error'
      phase: 'queued' | 'walking' | 'writing' | 'done' | 'error' | null
      found: number
      total: number
      file_count: number
      error: string | null
      interrupted: boolean
    }>(`/workspace/roots/${rootId}/scan-progress`)
  },
  /** 一键开终端（后端唯一白名单动作，路径必须在已启用根内） */
  openTerminal(path: string) {
    return http.post<{ opened: boolean }>('/workspace/open-terminal', { path })
  },
}
