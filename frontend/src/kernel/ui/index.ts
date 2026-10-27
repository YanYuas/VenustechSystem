// ============================================================
// kernel/ui —— UI 反馈底座（无业务语义）
//
// 只放"任何领域都会用到、且不知道业务存在"的 UI 基础设施：
//   - toast：命令式轻提示（含后端不可达时的提示收敛）
//   - modal：命令式弹窗栈（BaseModal/ModalHost 读取其 stack）
//
// 依赖规则：kernel 不得 import shared / features / api / views。
// 宿主组件（BaseToast/ModalHost/ModalItem）仍在 components/common，由 P3 迁入 shared。
// ============================================================
export * from './toast'
export * from './modal'
