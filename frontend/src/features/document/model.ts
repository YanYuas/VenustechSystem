// ============================================================
// 知识资源模块类型
// 对应 PRD §13.4 知识资源模块 + §15.4-15.7 表结构
// ============================================================

export interface Folder {
  id: string
  name: string
  parent_id: string | null
  sort_order: number
  is_inbox: boolean
  created_at: string
  updated_at: string
  children?: Folder[]
}

export interface Document {
  id: string
  title: string
  /** Markdown 纯文本内容（Tiptap 编辑器序列化后存储） */
  content: string | null
  folder_id: string | null
  folder_name: string
  project_id: string | null
  /** 身份轴（三期 B）：可空 = 未归类 */
  identity_id: string | null
  tags: string[]
  summary: string | null
  ai_suggested_tags: string[]
  version: number
  word_count: number
  created_at: string
  updated_at: string
}

export interface DocumentVersion {
  id: string
  document_id: string
  /** Markdown 纯文本内容 */
  content: string
  version: number
  word_count: number
  created_at: string
}

export interface Backlink {
  id: string
  source_doc_id: string
  target_doc_id: string
  target_title: string
  created_at: string
}

export interface DocumentListQuery {
  folder_id?: string
  tag?: string
  search?: string
  page?: number
  page_size?: number
  sort?: string
}

export interface CreateDocumentRequest {
  // ADR-0008：null = 清空该字段，省略 = 不改
  title: string
  folder_id?: string | null
  project_id?: string | null
  /** 身份轴（三期 B）：可空 = 未归类 */
  identity_id?: string | null
  /** Markdown 纯文本内容 */
  content?: string | null
  /** 标签（backend schemas/document.py:36 `tags: list[str] | None`） */
  tags?: string[] | null
}

export interface UpdateDocumentRequest {
  // ADR-0008：null = 清空该字段，省略 = 不改
  title?: string | null
  /** Markdown 纯文本内容 */
  content?: string | null
  tags?: string[]
  folder_id?: string | null
  /** 所属项目（backend schemas/document.py:44） */
  project_id?: string | null
  identity_id?: string | null
}

export interface SearchResult {
  tasks: Array<{ id: string; title: string; type: 'task'; status: string }>
  documents: Array<{
    id: string
    title: string
    snippet: string
    updated_at: string
    type: 'document'
  }>
  conversations: Array<{
    id: string
    title: string
    updated_at: string
    type: 'conversation'
  }>
  actions: Array<{
    id: string
    name: string
    type: 'action'
  }>
}

// ---------- 从 api.ts 收编的内联类型 ----------
export interface GraphNode {
  id: string
  title: string
  folder_name: string
  word_count: number
  updated_at: string
}

export interface GraphEdge {
  source: string
  target: string
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  dangling: Array<{ source: string; target_title: string }>
}
