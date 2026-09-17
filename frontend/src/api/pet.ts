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

/**
 * 桌宠四维陪伴数值（S6-2）。
 *
 * 命名说明：饱食度用 `satiety`（饱足感），不用旧代码里的 `hunger`（饥饿度）。
 * 旧代码写的是 `hunger >= 95 表示吃饱了` —— 说明它表达的其实也是饱食度，
 * 只是名字取反了，非常容易读错。
 */
export interface PetStats {
  intimacy: number  // 亲密度 0-100
  satiety: number   // 饱食度 0-100
  mood: number      // 心情 0-100
  energy: number    // 精力 0-100
  updated_at: string | null
  /** 本次读取是否发生了按时间的衰减（由后端惰性计算） */
  decayed: boolean
}

/** 互动时的**增量**（不是绝对值） */
export type PetStatsDelta = Partial<
  Record<'intimacy' | 'satiety' | 'mood' | 'energy', number>
>

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

  // 四维陪伴数值（S6-2：从 localStorage 迁入数据库）
  getStats() {
    return http.get<PetStats>('/pet/stats')
  },
  updateStats(delta: PetStatsDelta) {
    return http.put<PetStats>('/pet/stats', delta)
  },
}
