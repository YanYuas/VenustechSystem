// ============================================================
// features/avatar/model.ts —— avatar 领域模型（迁移批次 P3，ADR-0007）
// ============================================================

// ---------- 从 api.ts 收编的内联类型 ----------
export interface AvatarMemory {
  id: string
  user_id: string
  memory_type: 'profile' | 'knowledge' | 'event' | 'relation'
  category: string | null
  title: string
  content: string | null
  tags: string[]
  source: string | null
  confidence: number
  is_verified: boolean
  importance: number
  created_at: string
  updated_at: string
}

export interface AvatarInspiration {
  id: string
  user_id: string
  title: string
  description: string | null
  domain: string | null
  estimated_value: string | null
  prompt: string | null
  result: string | null
  status: 'generated' | 'selected' | 'executing' | 'completed' | 'discarded'
  feedback: string | null
  batch_id: string | null
  source_type: string
  created_at: string
  updated_at: string
}

export interface AvatarConfig {
  id: string
  user_id: string
  automation_level: string
  local_model_enabled: boolean
  local_model_provider: string | null
  local_model_name: string | null
  local_model_url: string | null
  cloud_model_enabled: boolean
  cloud_model_provider: string | null
  cloud_model_name: string | null
  persona_name: string
  persona_setting: string | null
  inspiration_enabled: boolean
  inspiration_frequency: string
  inspiration_domains: string[]
  reply_length: string
  language_style: string
  creativity: number
  operation_overrides: Record<string, unknown>
  updated_at: string
}
