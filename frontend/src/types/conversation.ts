// ============================================================
// 第二分身（AI对话）模块类型
// 对应 PRD §13.5 第二分身模块 + §15.8-15.9 表结构
// ============================================================

export type MessageRole = 'user' | 'assistant' | 'system'

export interface Conversation {
  id: string
  title: string | null
  scene: string
  created_at: string
  updated_at: string
}

export interface Message {
  id: string
  conversation_id: string
  role: MessageRole
  content: string
  tokens: number | null
  referenced_doc_ids: string[]
  created_at: string
}

export interface SendMessageRequest {
  content: string
  referenced_doc_ids?: string[]
  /** 思维模式：normal | deep | creative | critical | brainstorm */
  mode?: string
}

/** SSE 流式响应事件 */
export type SseEventType = 'content' | 'done' | 'error'

export interface SseEvent {
  type: SseEventType
  content?: string
  tokens?: number
  error?: string
}

export interface AiSummaryResult {
  summary: string
}

export interface AiTagsResult {
  tags: string[]
}

export interface AiInspirationResult {
  inspiration: string
  direction: string[]
  prompt: string
}

export interface ReflectionQuestion {
  question: string
  answer?: string
}
