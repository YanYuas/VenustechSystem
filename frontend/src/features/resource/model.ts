// ============================================================
// 资源中心类型定义（二期 M7）
// ============================================================

export interface InboxItem {
  id: string
  content_type: 'text' | 'link' | 'image' | 'file'
  content: string | null
  title: string | null
  preview_url: string | null
  file_path: string | null
  source: string | null
  tags: string[]
  status: 'pending' | 'processed' | 'archived'
  processed_at: string | null
  created_at: string
  updated_at: string
}

export interface Template {
  id: string
  name: string
  category: string
  description: string | null
  content: string
  variables: string[]
  tags: string[]
  is_builtin: boolean
  use_count: number
  created_at: string
  updated_at: string
}

export interface Domain {
  id: string
  name: string
  description: string | null
  icon: string | null
  color: string | null
  sort_order: number
  created_at: string
  updated_at: string
}
