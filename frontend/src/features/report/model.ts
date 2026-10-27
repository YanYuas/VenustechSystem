// ============================================================
// 人生报告类型（S6-5 · 三轴聚合）
// ============================================================

export interface ReportIdentityStat {
  id: string
  name: string
  slug: string
  color_token: string
  icon: string
  is_archived: boolean
  tasks_open: number
  tasks_completed: number
  documents: number
  diaries: number
  reviews: number
  memories: number
}

export interface ReportUnassignedStat {
  tasks_open: number
  documents: number
  diaries: number
  reviews: number
  memories: number
}

export interface ReportSkillStat {
  name: string
  count: number
}

export interface ReportRootStat {
  path: string
  label: string | null
  file_count: number
  total_size: number
}

export interface ReportExperienceItem {
  source: string
  source_label: string
  title: string
  identity_name: string | null
  occurred_at: string
}

export interface ReportData {
  generated_at: string
  nickname: string
  identity_axis: {
    identities: ReportIdentityStat[]
    unassigned: ReportUnassignedStat
  }
  growth_axis: {
    level: number
    exp: number
    percent: number
    skills: ReportSkillStat[]
    tasks_completed_total: number
    diaries_total: number
    reviews_total: number
  }
  archive_axis: {
    workspace_enabled: boolean
    roots: ReportRootStat[]
    documents_total: number
    sops_total: number
    prompts_total: number
    skills_total: number
    project_memories_total: number
    avatar_memories_total: number
  }
  recent_experience: ReportExperienceItem[]
}
