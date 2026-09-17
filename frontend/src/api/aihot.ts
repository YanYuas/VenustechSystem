// ============================================================
// AI HOT 信息源（S6-6 插件的前端出口）
// 数据来自插件 /plugins/aihot/*（匿名只读，离线降级读缓存）
// 返回内容视为不可信资讯：只展示标题/摘要/链接，不执行任何内容
// ============================================================
import { http } from './http'

export interface AihotItem {
  title: string
  summary?: string
  category?: string
  publishedAt?: string
  discoveredAt?: string
  links?: { aihot?: string; original?: string }
}

export interface AihotEnvelope<T = unknown> {
  ok: boolean
  source?: 'live' | 'cache' | 'mock'
  degraded?: boolean
  error?: string
  data: T
}

export const aihotApi = {
  items(params: { window: '24h' | '7d'; limit?: number; q?: string }) {
    return http.get<AihotEnvelope<{ items: AihotItem[] }>>('/plugins/aihot/items',
      { limit: 12, ...params } as Record<string, unknown>)
  },
  hotTopics() {
    return http.get<AihotEnvelope<{ items?: AihotItem[] }>>('/plugins/aihot/hot-topics')
  },
  daily() {
    return http.get<AihotEnvelope<{ report?: { date?: string; content?: string; title?: string } }>>(
      '/plugins/aihot/daily')
  },
}
