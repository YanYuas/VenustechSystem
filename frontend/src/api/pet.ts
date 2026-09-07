// ============================================================
// 桌宠 API（二期 P1）
// 配置 + 形象管理 + 状态感知
// ============================================================
import { http } from './http'

export interface PetConfig {
  id: string
  user_id: string
  enabled: boolean
  size: 'small' | 'medium' | 'large'
  opacity: number
  always_on_top: boolean
  auto_start: boolean
  position_x: number
  position_y: number
  current_avatar_id: string | null
  state_awareness_enabled: boolean
  action_switch_interval: number
  show_bubble: boolean
  bubble_duration: number
  click_interaction: boolean
  draggable: boolean
  right_click_menu: boolean
  tts_enabled: boolean
  tts_voice: string | null
  tts_rate: number
  tts_pitch: number
  tts_volume: number
  speak_scene: 'never' | 'remind' | 'interact' | 'celebrate' | 'always'
  updated_at: string
}

export interface PetAvatar {
  id: string
  user_id: string
  name: string
  description: string | null
  avatar_type: 'builtin' | 'custom'
  image_url: string | null
  mode: 'simple' | 'advanced'
  eye_position: Record<string, unknown>
  mouth_position: Record<string, unknown>
  action_frames: Record<string, string[]>
  tags: string[]
  is_active: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

export interface PetState {
  time_state: string
  time_label: string
  action: string
  action_label: string
  mood: string
  mood_label: string
  bubble_text: string | null
  has_todo_tasks: boolean
  todo_count: number
  recent_mood: string | null
}

export const petApi = {
  // 配置
  getConfig() {
    return http.get<PetConfig>('/pet/config')
  },
  updateConfig(data: Partial<PetConfig>) {
    return http.patch<PetConfig>('/pet/config', data)
  },

  // 形象
  listAvatars() {
    return http.get<PetAvatar[]>('/pet/avatars')
  },
  createAvatar(data: Partial<PetAvatar>) {
    return http.post<PetAvatar>('/pet/avatars', data)
  },
  updateAvatar(id: string, data: Partial<PetAvatar>) {
    return http.patch<PetAvatar>(`/pet/avatars/${id}`, data)
  },
  deleteAvatar(id: string) {
    return http.delete<void>(`/pet/avatars/${id}`)
  },
  activateAvatar(id: string) {
    return http.post<PetConfig>(`/pet/avatars/${id}/activate`)
  },

  // 状态感知
  getState() {
    return http.get<PetState>('/pet/state')
  },
}
