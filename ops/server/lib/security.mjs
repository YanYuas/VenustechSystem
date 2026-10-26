// ============================================================
// 访问授权（纯函数，便于单测 —— 见 test/security.test.mjs）
//
// 为什么单独成文件：
//   2026-10 审计发现「回环绕过」漏洞：server.js 对 127.0.0.1 来源无条件放行，
//   而项目计划用 cloudflared 隧道该端口 —— 隧道把公网请求转成回环连接，
//   于是 X-API-Token 形同虚设。修好后必须能被测试证明，因此把判定逻辑
//   抽成不依赖 http server 的纯函数。
// ============================================================
import { timingSafeEqual } from 'node:crypto'

const LOOPBACK_HOSTS = new Set(['127.0.0.1', '::1', '::ffff:127.0.0.1'])

/**
 * 反向代理 / 隧道会追加的请求头。
 * 只要出现任意一个，就说明请求不是"本机浏览器直连"，回环来源不再可信：
 *   - cloudflared: cf-connecting-ip / cf-ray / x-forwarded-for
 *   - nginx/Caddy/Traefik: x-forwarded-for / x-real-ip / forwarded
 *   - Cloudflare 回源: x-forwarded-proto
 */
const PROXY_HEADERS = [
  'x-forwarded-for',
  'x-forwarded-host',
  'x-forwarded-proto',
  'x-real-ip',
  'cf-connecting-ip',
  'cf-ray',
  'true-client-ip',
  'forwarded',
  'client-ip',
  'x-client-ip',
]

/** 大小写无关地取 header 值（Node 会把 header 名小写，但纯函数可能收到任意对象） */
function headerValue(headers, name) {
  if (!headers) return ''
  const target = name.toLowerCase()
  if (typeof headers.get === 'function') return headers.get(target) ?? ''
  for (const [k, v] of Object.entries(headers)) {
    if (k.toLowerCase() === target) return Array.isArray(v) ? v.join(',') : (v ?? '')
  }
  return ''
}

export function isLoopback(address) {
  return LOOPBACK_HOSTS.has(address ?? '')
}

export function hasProxyHeaders(headers) {
  return PROXY_HEADERS.some((h) => String(headerValue(headers, h)).trim() !== '')
}

/** 常量时间字符串比较（避免按字节短路泄漏令牌内容） */
export function timingSafeEqualStr(a, b) {
  const ba = Buffer.from(String(a ?? ''), 'utf8')
  const bb = Buffer.from(String(b ?? ''), 'utf8')
  if (ba.length !== bb.length || ba.length === 0) return false
  return timingSafeEqual(ba, bb)
}

/**
 * 判定一个 /api 请求是否放行。
 *
 * 规则（顺序即优先级）：
 *   1. 来源是回环 **且没有任何代理头** → 放行（PC 浏览器零配置）。
 *      一旦有代理头，回环只代表"最后一跳是本机隧道"，不代表调用者是本机。
 *   2. 配了令牌且请求头 X-API-Token 命中任一有效令牌 → 放行。
 *   3. 其余拒绝。
 *
 * @param {{ remoteAddress?: string, headers?: object, tokens?: string[] }} input
 * @returns {{ ok: boolean, reason: string }}
 */
export function isAuthorized({ remoteAddress, headers = {}, tokens = [] } = {}) {
  const proxied = hasProxyHeaders(headers)
  if (isLoopback(remoteAddress) && !proxied) {
    return { ok: true, reason: 'loopback-direct' }
  }
  const valid = tokens.filter((t) => typeof t === 'string' && t.length > 0)
  if (valid.length === 0) {
    return { ok: false, reason: 'no-token-configured' }
  }
  const supplied = String(headerValue(headers, 'x-api-token')).trim()
  if (!supplied) {
    return { ok: false, reason: proxied ? 'proxied-without-token' : 'missing-token' }
  }
  for (const token of valid) {
    if (timingSafeEqualStr(supplied, token)) return { ok: true, reason: 'token-ok' }
  }
  return { ok: false, reason: 'bad-token' }
}

export const _internals = { PROXY_HEADERS, LOOPBACK_HOSTS, headerValue }
