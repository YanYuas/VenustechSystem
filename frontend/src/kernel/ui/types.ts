// ============================================================
// kernel/ui/types.ts —— UI 反馈底座的类型（迁移批次 P3，ADR-0007）
//
// 从 `types/common.ts` 收编：toast 的类型属于 kernel/ui（shared/types/common
// 反向 re-export 它们，避免 shared → kernel 的消费方断裂）。
// ============================================================

/** Toast 通知级别 */
export type ToastType = 'info' | 'success' | 'warning' | 'error'

/** Toast 队列条目 */
export interface ToastItem {
  id: number
  type: ToastType
  title: string
  message?: string
  duration: number
}
