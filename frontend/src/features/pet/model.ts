// ============================================================
// features/pet/model.ts —— 桌宠领域模型（迁移批次 P2，ADR-0007）
//
// 领域类型的**唯一落点**：从原 `api/pet.ts` 的内联类型抽出，
// 并收编原先散落在组件里的 `PetAction`（此前 composable 反向 import 组件的类型）。
//
// 约定：model.ts 只含类型/纯语义定义，不 import 任何运行时模块。
// 跨域使用请从 `@/features/pet` 导入，不要深链本文件。
// ============================================================

/** 桌宠配置（后端 /pet/config） */
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

/** 桌宠形象（后端 /pet/avatars） */
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

/** 状态感知结果（后端 /pet/state） */
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
  intimacy: number // 亲密度 0-100
  satiety: number // 饱食度 0-100
  mood: number // 心情 0-100
  energy: number // 精力 0-100
  updated_at: string | null
  /** 本次读取是否发生了按时间的衰减（由后端惰性计算） */
  decayed: boolean
}

/** 桌宠当前四维数值（不含 updated_at/decayed 的纯数值视图，组件内部持有） */
export type PetVitals = Pick<PetStats, 'intimacy' | 'satiety' | 'mood' | 'energy'>

/** 互动时的**增量**（不是绝对值） */
export type PetStatsDelta = Partial<Record<'intimacy' | 'satiety' | 'mood' | 'energy', number>>

/**
 * 桌宠动作名。
 *
 * 迁移说明：原先定义在 `components/pet/DesktopPet.vue` 的 `<script setup>` 里，
 * 导致 `usePetEvent` 反过来 import 组件（composable → component 反向依赖）。
 * P2 起收编到领域 model，组件与 composable 都从这里取。
 */
export type PetAction =
  | 'idle'
  | 'happy'
  | 'thinking'
  | 'working'
  | 'celebrate'
  | 'sleep'
  | 'wave'
  | 'dance'
  | 'read'
  | 'run'
  | 'shy'
  | 'surprised'
