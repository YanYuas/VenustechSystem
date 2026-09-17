// ============================================================
// 保险箱类型（三期 D）
// ============================================================

export interface VaultStatus {
  configured: boolean
  unlocked: boolean
  items_count: number
  hint: string | null
}

export interface VaultItem {
  id: string
  name: string
  category: 'login' | 'note'
  username: string | null
  url: string | null
  notes: string | null
  identity_id: string | null
  has_secret: boolean
  last_accessed_at: string | null
  created_at: string
  updated_at: string
  /** 终端动作（D 收尾）：白名单模板，当前仅 ssh */
  action_type: 'none' | 'ssh'
  action_host: string | null
  action_user: string | null
  action_port: string | null
}
