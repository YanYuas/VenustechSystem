// ============================================================
// 身份类型（三期 B · 横切标签）
// ============================================================

/** 身份。color_token 是设计令牌名（不含 #），映射见 useIdentity 的调色板 */
export interface Identity {
  id: string
  name: string
  slug: string
  color_token: string
  icon: string
  description: string | null
  sort_order: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CreateIdentityRequest {
  name: string
  slug: string
  color_token?: string
  icon?: string
  description?: string
  sort_order?: number
}

export interface UpdateIdentityRequest {
  name?: string
  color_token?: string
  icon?: string
  description?: string
  sort_order?: number
  is_active?: boolean
}
