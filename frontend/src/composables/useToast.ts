// ============================================================
// Toast 通知服务 —— 命令式调用，配合 BaseToast 容器渲染
// 用法: const toast = useToast(); toast.success('已保存')
// 依赖: I06 BaseToast（容器挂载点 #toast-container）
// ============================================================
import { reactive } from 'vue'
import type { ToastItem, ToastType } from '@/types/common'
import { CONNECTIVITY_TOAST_TITLE, isBackendUnreachable } from '@/api/connectivity'

const DEFAULT_DURATION: Record<ToastType, number> = {
  info: 3000,
  success: 3000,
  warning: 5000,
  error: 5000,
}

const toasts = reactive<ToastItem[]>([])
let seed = 0
let containerReady = false

function push(item: Omit<ToastItem, 'id' | 'duration'> & { duration?: number }) {
  const id = ++seed
  const duration = item.duration ?? DEFAULT_DURATION[item.type]
  // 计时由 BaseToast/ToastItem 组件层管理（支持 hover 暂停），此处只入队
  toasts.push({ ...item, id, duration })
  return id
}

function remove(id: number) {
  const idx = toasts.findIndex((t) => t.id === id)
  if (idx >= 0) toasts.splice(idx, 1)
}

function clear() {
  toasts.splice(0, toasts.length)
}

export const toast = {
  /** 供 BaseToast 容器在挂载时调用，声明渲染就绪 */
  setReady() {
    containerReady = true
  },
  get isReady() {
    return containerReady
  },
  show(title: string, message?: string, type: ToastType = 'info', duration?: number) {
    return push({ type, title, message, duration })
  },
  info(title: string, message?: string, duration?: number) {
    return push({ type: 'info', title, message, duration })
  },
  success(title: string, message?: string, duration?: number) {
    return push({ type: 'success', title, message, duration })
  },
  warning(title: string, message?: string, duration?: number) {
    return push({ type: 'warning', title, message, duration })
  },
  error(title: string, message?: string, duration?: number) {
    // 后端不可达期间，各组件各自的「加载失败」都是同一原因的次生提示
    // （真正的原因已由 http 层统一提示过一次）。全项目 92 处 catch 里的
    // error 提示散布 20+ 文件，与其逐个改，不如在提示层收敛。
    // 只抑制 error 级别：本地校验类提示走 warning/info，不受影响。
    if (isBackendUnreachable() && title !== CONNECTIVITY_TOAST_TITLE) {
      console.warn('[toast 已抑制 · 后端不可达]', title, message ?? '')
      return 0
    }
    return push({ type: 'error', title, message, duration })
  },
  remove,
  clear,
  /** 渲染列表（仅 BaseToast 使用） */
  get items() {
    return toasts
  },
}

export type ToastService = typeof toast

export function useToast(): ToastService {
  return toast
}
