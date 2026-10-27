// ============================================================
// 用户 & 配置类型
// 对应 PRD §13.2 认证模块
// ============================================================

export interface UserConfig {
  nickname: string
  avatar: string
  theme: string
  api_key_configured: boolean
  automation_level: 'L1' | 'L2' | 'L3' | 'L4' | 'L5'
  pet_position: { x: number; y: number }
  pet_topmost: boolean
  inspiration_probability: number
  ai_enabled: boolean
}

export interface InitRequest {
  nickname: string
  api_key: string
}

export interface UpdateConfigRequest {
  nickname?: string
  avatar?: string
  theme?: string
  automation_level?: string
  pet_position?: { x: number; y: number }
  pet_topmost?: boolean
  inspiration_probability?: number
  ai_enabled?: boolean
}

export interface ApiVerifyResult {
  valid: boolean
  model: string
}
