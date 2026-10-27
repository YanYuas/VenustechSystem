// ============================================================
// kernel/http/client.ts —— 传输层「环境与策略」：baseURL / token / 超时 / 重试参数
//
// 从原 416 行的 kernel/http/index.ts 拆出（P4，ADR-0007）。
// 行为零变化：常量值与读写 localStorage 的逻辑逐字保留。
// 依赖边界：本文件不 import 任何上层模块（shared/features/api/views）。
// ============================================================

const ENV_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8765/api/v1'
// 运行时可覆盖（Capacitor App 壳里指向 PC 的 Tailscale 地址；localStorage 持久）
const API_BASE_KEY = 'qm-star-api-base'

export function getApiBase(): string {
  try {
    return localStorage.getItem(API_BASE_KEY) || ENV_BASE
  } catch {
    return ENV_BASE
  }
}

export function getApiToken(): string {
  try {
    return localStorage.getItem('qm-star-token') || ''
  } catch {
    return ''
  }
}

export function setApiToken(token: string): void {
  try {
    localStorage.setItem('qm-star-token', token.trim())
  } catch {
    /* ignore */
  }
}

export function setApiBase(url: string): void {
  let clean = url.trim().replace(/\/+$/, '')
  // 防呆：服务器地址漏带 /api/v1 时自动补全（头号连接故障源）
  if (clean && !clean.endsWith('/api/v1')) clean = `${clean}/api/v1`
  if (clean) localStorage.setItem(API_BASE_KEY, clean)
  else localStorage.removeItem(API_BASE_KEY)
}

/** 常规请求超时 */
export const TIMEOUT = 15000
/**
 * 已判定后端不可达时的探活超时。
 * 15s 的常规超时用在"服务根本没开"的场景上，会让每个页面都干等 15 秒；
 * 降到 4s 既能让 UI 快速给出结论，也不影响服务恢复后的正常请求。
 */
export const FAST_FAIL_TIMEOUT = 4000
/** SSE 首包超时：LLM 冷启动/长 prompt 时首包可能远超 15s */
export const SSE_TIMEOUT = 60000
/** 网络错误自动重试次数（PRD §21：重试1次，间隔2秒） */
export const RETRY_COUNT = 1
export const RETRY_DELAY = 2000
/** 仅幂等方法允许自动重试：POST 重试可能造成重复创建 */
export const IDEMPOTENT_METHODS = new Set(['GET', 'HEAD', 'PUT', 'DELETE'])

export const WRITE_METHODS = new Set(['POST', 'PATCH', 'PUT', 'DELETE'])

/**
 * 按运行环境给出可操作的排查指引。
 * App 壳（Capacitor）里后端在电脑上，用户需要的是检查地址；
 * 浏览器/开发环境里通常就是"服务没启动"。
 */
export function HINT_SUFFIX(): string {
  try {
    const native = Boolean(
      (
        window as unknown as { Capacitor?: { isNativePlatform?: () => boolean } }
      ).Capacitor?.isNativePlatform?.(),
    )
    if (native) return '，请确认电脑端服务已启动、设置里的服务器地址与访问令牌正确'
  } catch {
    /* 非 Capacitor 环境 */
  }
  return '，请先启动后端服务（双击「启动移动服务.bat」，或运行 node server.js）'
}
