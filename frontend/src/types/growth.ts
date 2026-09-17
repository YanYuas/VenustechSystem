// ============================================================
// 成长体系类型（S6-2）
// 经验值 / 等级 / 技能树 / EXP 流水
// ============================================================

/** 成长状态（GET /growth/state） */
export interface GrowthState {
  exp: number
  level: number
  /** 当前等级内已获得的经验 */
  current: number
  /** 升到下一级还需的经验 */
  need: number
  percent: number
  /** 是否已满级（LV30） */
  is_max: boolean
  /** 下一级的门槛经验；满级时为 null */
  next_level_exp: number | null
  /** 到达满级所需累计经验（107069） */
  total_exp_to_max: number
}

/** EXP 流水条目 */
export interface GrowthEventItem {
  id: string
  event_type: string
  exp: number
  label: string | null
  skill_cat_ids: string[]
  created_at: string | null
}

/** 技能树节点（只包含有计数的分类） */
export interface SkillNode {
  id: string
  name: string
  count: number
  level: number
}

/** 静态元数据（GET /growth/levels） */
export interface GrowthMeta {
  max_level: number
  total_exp_to_max: number
  /** 等级门槛表，索引即等级 */
  table: number[]
  /** 行为 → EXP 映射（前端可用于展示"如何获得经验"） */
  exp_rules: Record<string, number>
  skill_categories: { id: string; name: string }[]
}

/** 桌宠四维数值 */
export interface PetStats {
  intimacy: number
  satiety: number
  mood: number
  energy: number
  updated_at: string | null
}
