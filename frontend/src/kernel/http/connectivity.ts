// ============================================================
// 后端连通性状态（只依赖 vue 的响应式，无业务依赖）
//
// 为什么单独成文件：http 层要写这个状态，toast 层要读它来做提示收敛，
// 而 http 层已 import useToast —— 若 toast 反过来 import http 就成环。
// 本模块不 import 任何东西，两边都可以安全引用。
// ============================================================

import { ref } from 'vue'

/** 统一连通性提示的标题（toast 层据此放行，不做抑制） */
export const CONNECTIVITY_TOAST_TITLE = '连不上后端服务'

/** 同一原因的提示节流窗口：不可达期间最多每 8s 提示一次 */
const NOTIFY_DEDUPE_MS = 8000

/**
 * 响应式连通性状态：顶栏「未连接」标记据此显示。
 * 必须是 ref —— 普通函数的值变化 Vue 模板追踪不到。
 */
export const backendUnreachable = ref(false)

let unreachableAt = 0
let lastNotifiedAt = 0

/** 标记为不可达（网络级失败：连不上 / 超时） */
export function markUnreachable(): void {
  unreachableAt = Date.now()
  backendUnreachable.value = true
}

/** 标记为可达（任一请求成功）—— 自愈：提示与顶栏标记同时恢复正常 */
export function markReachable(): void {
  unreachableAt = 0
  backendUnreachable.value = false
}

export function isBackendUnreachable(): boolean {
  return backendUnreachable.value
}

/**
 * 是否应该发出这次统一提示。
 * 不可达期间每个页面/组件都会各自失败，若都提示会刷屏，故做节流。
 */
export function shouldNotifyUnreachable(): boolean {
  const now = Date.now()
  if (now - lastNotifiedAt < NOTIFY_DEDUPE_MS) return false
  lastNotifiedAt = now
  return true
}

/** 不可达持续了多久（毫秒）——供 UI 展示"已断开 N 秒" */
export function unreachableForMs(): number {
  return unreachableAt > 0 ? Date.now() - unreachableAt : 0
}
