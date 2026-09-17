// ============================================================
// 认证 & 用户配置 API
// 对应 PRD §13.2
// ============================================================
import { http } from './http'
import type { UserConfig, InitRequest, UpdateConfigRequest, ApiVerifyResult } from '@/types'

export const authApi = {
  init(data: InitRequest) {
    return http.post<UserConfig>('/auth/init', data)
  },
  me() {
    return http.get<UserConfig>('/auth/me')
  },
  update(data: UpdateConfigRequest) {
    return http.patch<UserConfig>('/auth/me', data)
  },
  verifyApiKey(api_key: string) {
    return http.post<ApiVerifyResult>('/auth/verify-api', { api_key })
  },
}
