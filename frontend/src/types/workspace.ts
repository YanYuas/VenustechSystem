// ============================================================
// 工作区类型（三期 C · 可选功能 + 引导部署）
// ============================================================

export interface WorkspaceRoot {
  id: string
  path: string
  label: string | null
  identity_id: string | null
  enabled: boolean
  scan_status: 'never' | 'ok' | 'error'
  scan_error: string | null
  last_scanned_at: string | null
  file_count: number
  total_size: number
  created_at: string
  updated_at: string
}

export interface WorkspaceFile {
  id: string
  root_id: string
  rel_path: string
  name: string
  ext: string | null
  is_dir: boolean
  size: number
  mtime: number
  identity_id: string | null
}

export interface WorkspaceStatus {
  enabled: boolean
  roots_count: number
  scanned_count: number
  terminal: string
}

export interface WorkspaceFilesOut {
  root: WorkspaceRoot
  items: WorkspaceFile[]
  total: number
  page: number
  page_size: number
}

export interface SkeletonResult {
  root_id: string
  created: string[]
  skipped: string[]
}
