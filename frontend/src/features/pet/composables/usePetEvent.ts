// ============================================================
// features/pet/composables/usePetEvent.ts —— 桌宠动作事件
// 原 `composables/usePetEvent.ts`（迁移批次 P2，ADR-0007）
//
// 轻量事件总线（window CustomEvent）：任意业务处可触发桌宠动作，
// 例如任务完成→celebrate、设为焦点→happy。
// 依赖规则：只依赖本领域 model，不再反向 import 组件。
// ============================================================
import type { PetAction } from '../model'

export const PET_ACTION_EVENT = 'pet:action'

export type PetActionName = Exclude<PetAction, 'idle'>

export function emitPetAction(action: PetActionName, duration = 2500): void {
  window.dispatchEvent(new CustomEvent(PET_ACTION_EVENT, { detail: { action, duration } }))
}
