// ============================================================
// 用户配置 API（键值配置表 settings）
//
// 为什么需要它：设置页的 4 个通知开关此前只是前端 ref()，刷新即失效，
// 后端 settings 表建好了却从没被读写过。现在开关落库，前后端同源。
// ============================================================
import { http } from './http'

/** 配置字典：键为配置项名，值为字符串（布尔用 'true' / 'false'） */
export type SettingsValues = Record<string, string>

/** 已登记的通知配置键 */
export const NOTIFY_KEYS = {
  task: 'notify.task',
  review: 'notify.review',
  system: 'notify.system',
  sound: 'notify.sound',
} as const

function toBool(raw: string | undefined, fallback = false): boolean {
  if (raw === undefined || raw === '') return fallback
  return ['true', '1', 'yes', 'on'].includes(raw.trim().toLowerCase())
}

export const settingsApi = {
  /** 读取全部配置（已与后端默认值合并） */
  list() {
    return http.get<{ values: SettingsValues }>('/settings')
  },

  /** 批量写入配置，返回写入后的完整字典 */
  update(values: SettingsValues) {
    return http.put<{ values: SettingsValues }>('/settings', { values })
  },

  /** 便捷：只更新通知开关 */
  async updateNotify(patch: Partial<Record<keyof typeof NOTIFY_KEYS, boolean>>) {
    const values: SettingsValues = {}
    for (const [name, on] of Object.entries(patch)) {
      const key = NOTIFY_KEYS[name as keyof typeof NOTIFY_KEYS]
      if (key && on !== undefined) values[key] = String(on)
    }
    return this.update(values)
  },

  /** 便捷：把配置字典转成通知开关布尔值 */
  readNotify(values: SettingsValues) {
    return {
      task: toBool(values[NOTIFY_KEYS.task], true),
      review: toBool(values[NOTIFY_KEYS.review], true),
      system: toBool(values[NOTIFY_KEYS.system], true),
      sound: toBool(values[NOTIFY_KEYS.sound], false),
    }
  },
}
