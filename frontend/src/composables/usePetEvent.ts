// ============================================================
// usePetEvent —— 桌宠动作事件（轻量事件总线，window CustomEvent）
// 任意业务处可触发桌宠动作：任务完成→celebrate、设为焦点→happy…
// ============================================================
import type { PetAction } from '@/components/pet/DesktopPet.vue'

export const PET_ACTION_EVENT = 'pet:action'

export type PetActionName = Exclude<PetAction, 'idle'>

export function emitPetAction(action: PetActionName, duration = 2500): void {
  window.dispatchEvent(new CustomEvent(PET_ACTION_EVENT, { detail: { action, duration } }))
}
