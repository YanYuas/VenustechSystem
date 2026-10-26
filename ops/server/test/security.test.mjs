// ============================================================
// 访问授权回归测试（node:test，零第三方依赖）
//
// 守的是 2026-10 审计的 P0：回环绕过。
// 关键用例：来源 127.0.0.1 但带 cloudflared/nginx 的代理头 → 必须要求令牌。
// ============================================================
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  isAuthorized,
  hasProxyHeaders,
  isLoopback,
  timingSafeEqualStr,
} from '../lib/security.mjs'

const TOKEN = 'a'.repeat(48)
const T = [TOKEN]

test('回环 + 无代理头 → 放行（本机浏览器零配置）', () => {
  const r = isAuthorized({ remoteAddress: '127.0.0.1', headers: {}, tokens: T })
  assert.equal(r.ok, true)
  assert.equal(r.reason, 'loopback-direct')
})

test('P0: 回环 + x-forwarded-for → 未带令牌必须拒绝（cloudflared 场景）', () => {
  const r = isAuthorized({
    remoteAddress: '127.0.0.1',
    headers: { 'x-forwarded-for': '203.0.113.7' },
    tokens: T,
  })
  assert.equal(r.ok, false)
  assert.equal(r.reason, 'proxied-without-token')
})

test('P0: 回环 + cf-connecting-ip → 未带令牌必须拒绝', () => {
  const r = isAuthorized({
    remoteAddress: '127.0.0.1',
    headers: { 'CF-Connecting-IP': '203.0.113.7' },
    tokens: T,
  })
  assert.equal(r.ok, false)
  assert.equal(r.reason, 'proxied-without-token')
})

test('回环 + 代理头 + 正确令牌 → 放行', () => {
  const r = isAuthorized({
    remoteAddress: '127.0.0.1',
    headers: { 'x-forwarded-for': '203.0.113.7', 'x-api-token': TOKEN },
    tokens: T,
  })
  assert.equal(r.ok, true)
  assert.equal(r.reason, 'token-ok')
})

test('非回环来源 → 必须令牌', () => {
  assert.equal(isAuthorized({ remoteAddress: '192.168.1.50', headers: {}, tokens: T }).ok, false)
  assert.equal(
    isAuthorized({ remoteAddress: '192.168.1.50', headers: { 'x-api-token': TOKEN }, tokens: T }).ok,
    true,
  )
})

test('错误令牌 / 空令牌 → 拒绝', () => {
  assert.equal(isAuthorized({ remoteAddress: '8.8.8.8', headers: { 'x-api-token': 'b'.repeat(48) }, tokens: T }).ok, false)
  assert.equal(isAuthorized({ remoteAddress: '8.8.8.8', headers: { 'x-api-token': '' }, tokens: T }).ok, false)
})

test('未配置任何令牌时 fail-closed（非回环一律拒绝）', () => {
  const r = isAuthorized({ remoteAddress: '8.8.8.8', headers: { 'x-api-token': 'anything' }, tokens: [] })
  assert.equal(r.ok, false)
  assert.equal(r.reason, 'no-token-configured')
})

test('轮换宽限期：旧令牌仍然有效', () => {
  const oldT = 'oldtoken'.repeat(6)
  const r = isAuthorized({
    remoteAddress: '8.8.8.8',
    headers: { 'x-api-token': oldT },
    tokens: [TOKEN, oldT],
  })
  assert.equal(r.ok, true)
})

test('伪造前缀/长度不同的令牌不会命中原令牌', () => {
  assert.equal(timingSafeEqualStr(TOKEN, TOKEN.slice(1)), false)
  assert.equal(timingSafeEqualStr(TOKEN, TOKEN), true)
  assert.equal(timingSafeEqualStr('', ''), false)
})

test('代理头识别与回环识别', () => {
  assert.equal(hasProxyHeaders({}), false)
  assert.equal(hasProxyHeaders({ 'X-Real-IP': '1.2.3.4' }), true)
  assert.equal(hasProxyHeaders({ forwarded: 'for=1.2.3.4' }), true)
  assert.equal(isLoopback('::1'), true)
  assert.equal(isLoopback('::ffff:127.0.0.1'), true)
  assert.equal(isLoopback('10.0.0.1'), false)
})
