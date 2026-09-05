// ============================================================
// 第二分身（AI对话）API
// 对应 PRD §13.5
// ============================================================
import { http, sseRequest } from './http'
import type {
  Conversation, Message, SendMessageRequest, SseEvent,
  AiSummaryResult, AiTagsResult, AiInspirationResult,
} from '@/types'

export const conversationApi = {
  list() {
    return http.get<Conversation[]>('/conversations')
  },
  create(title?: string) {
    return http.post<Conversation>('/conversations', { title })
  },
  messages(id: string) {
    return http.get<Message[]>(`/conversations/${id}/messages`)
  },
  /** 发送消息（SSE流式） */
  sendStream(
    id: string,
    data: SendMessageRequest,
    onMessage: (event: SseEvent) => void,
    signal?: AbortSignal,
  ) {
    return sseRequest(`/conversations/${id}/messages`, data, onMessage, signal)
  },
  remove(id: string) {
    return http.delete<void>(`/conversations/${id}`)
  },
}

export const aiApi = {
  summarize(document_id: string) {
    return http.post<AiSummaryResult>('/ai/summarize', { document_id })
  },
  suggestTags(document_id: string) {
    return http.post<AiTagsResult>('/ai/suggest-tags', { document_id })
  },
  inspiration(document_id: string) {
    return http.post<AiInspirationResult>('/ai/inspiration', { document_id })
  },
  reflectionQuestions(review_type: string, date: string, data: unknown) {
    return http.post<Array<{ question: string }>>('/ai/reflection-questions', { review_type, date, data })
  },
}
