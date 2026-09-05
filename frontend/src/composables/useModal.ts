// ============================================================
// 命令式弹窗服务 —— 配合 BaseModal 使用
// 用法:
//   const modal = useModal()
//   modal.open({ title, content, onConfirm, confirmText })
//   modal.confirm({ title, message }) -> Promise<boolean>  // 危险确认
// 依赖: I04 BaseModal / I14 BaseConfirm
// ============================================================
import { reactive } from 'vue'
import type { Component, VNode } from 'vue'

export interface ModalRequest {
  id: number
  title: string
  content?: string | Component | VNode
  width?: number
  confirmText?: string
  cancelText?: string
  danger?: boolean
  /** 需要输入确认文字才可确认（危险操作） */
  requireInput?: string
  onConfirm?: () => void | Promise<void>
  onCancel?: () => void
  closable?: boolean
}

const stack = reactive<ModalRequest[]>([])
let seed = 0
let ready = false

function open(req: Omit<ModalRequest, 'id'>): number {
  const id = ++seed
  stack.push({ closable: true, ...req, id })
  return id
}

function close(id: number) {
  const idx = stack.findIndex((m) => m.id === id)
  if (idx >= 0) stack.splice(idx, 1)
}

function closeTop() {
  if (stack.length) close(stack[stack.length - 1].id)
}

/** 危险确认：resolve(true) 当用户确认 */
function confirm(opts: {
  title: string
  message?: string
  confirmText?: string
  requireInput?: string
}): Promise<boolean> {
  return new Promise((resolve) => {
    open({
      ...opts,
      danger: true,
      cancelText: '取消',
      onConfirm: () => resolve(true),
      onCancel: () => resolve(false),
    })
  })
}

export const modal = {
  setReady() {
    ready = true
  },
  get isReady() {
    return ready
  },
  open,
  confirm,
  close,
  closeTop,
  get stack() {
    return stack
  },
}

export type ModalService = typeof modal

export function useModal(): ModalService {
  return modal
}
