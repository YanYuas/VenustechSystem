// ============================================================
// 保险箱 API（三期 D）
// 明文出系统的唯一出口：revealSecret（要求解锁态）
// ============================================================
import { http } from './http'
import type { VaultStatus, VaultItem } from '@/types'

export const vaultApi = {
  status() {
    return http.get<VaultStatus>('/vault/status')
  },
  /** 初始化主密码（仅首次；≥8 位） */
  setup(masterPassword: string) {
    return http.put<VaultStatus>('/vault/setup', { master_password: masterPassword })
  },
  unlock(masterPassword: string) {
    return http.post<VaultStatus>('/vault/unlock', { master_password: masterPassword })
  },
  lock() {
    return http.post<VaultStatus>('/vault/lock')
  },
  changePassword(oldPassword: string, newPassword: string) {
    return http.post<VaultStatus>('/vault/change-password', {
      old_password: oldPassword, new_password: newPassword,
    })
  },
  /** 凭据列表（后端保证不含密文/明文） */
  items() {
    return http.get<VaultItem[]>('/vault/items')
  },
  createItem(data: {
    name: string; category: 'login' | 'note'; username?: string; url?: string
    secret?: string; notes?: string; identity_id?: string
    action_type?: 'none' | 'ssh'; action_host?: string; action_user?: string; action_port?: string
  }) {
    return http.post<VaultItem>('/vault/items', data)
  },
  updateItem(id: string, data: {
    name?: string; category?: 'login' | 'note'; username?: string; url?: string
    secret?: string; notes?: string; identity_id?: string
    action_type?: 'none' | 'ssh'; action_host?: string; action_user?: string; action_port?: string
  }) {
    return http.patch<VaultItem>(`/vault/items/${id}`, data)
  },
  removeItem(id: string) {
    return http.delete<{ deleted: boolean }>(`/vault/items/${id}`)
  },
  /** 查看明文（唯一出口，要求解锁态；后端会记录访问时间） */
  revealSecret(id: string) {
    return http.get<{ secret: string | null }>(`/vault/items/${id}/secret`)
  },
  /** 执行终端动作（白名单模板：ssh -i 密钥路径，后端校验注入面） */
  runAction(id: string) {
    return http.post<{ opened: boolean; command: string }>(`/vault/items/${id}/run-action`)
  },
}
