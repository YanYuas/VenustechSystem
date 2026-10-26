#!/usr/bin/env node
// ============================================================
// 启明星系统 — 统一 Web 服务
// - 提供前端静态文件（dist/）
// - 代理 /api/* 到 FastAPI 后端（127.0.0.1:8765）
// - 单端口对外暴露，cloudflared 只需隧道一个端口
//
// 启动（仓库根）：node ops/server/server.js
// 本目录内也可：node server.js
// 环境变量：PORT（默认 3000），BACKEND_URL（默认 http://127.0.0.1:8765）
// ============================================================
import { createServer } from 'node:http'
import pkg from 'http-proxy'
const { createProxyServer } = pkg
import { fileURLToPath } from 'node:url'
import { join, resolve } from 'node:path'
import { readFileSync, existsSync } from 'node:fs'
import { createStaticResolver, getMimeType } from './lib/static-files.mjs'
import { isAuthorized } from './lib/security.mjs'
import { loadAccessTokens } from './lib/access-token.mjs'

const __dirname = fileURLToPath(new URL('.', import.meta.url))

const PORT = parseInt(process.env.PORT ?? '3000', 10)
const BACKEND_URL = process.env.BACKEND_URL ?? 'http://127.0.0.1:8765'
// 本文件位于 <repo>/ops/server/，前端产物在 <repo>/frontend/dist
const FRONTEND_DIST = resolve(__dirname, '..', '..', 'frontend', 'dist')

if (!existsSync(FRONTEND_DIST)) {
  console.error(`❌ 找不到前端构建目录: ${FRONTEND_DIST}`)
  console.error('   请先运行: cd frontend && npm run build')
  process.exit(1)
}

// ---------- HTTP 代理到后端 ----------
const proxy = createProxyServer({
  target: BACKEND_URL,
  changeOrigin: true,
  ws: true,
  timeout: 60000,
})

proxy.on('error', (err, _req, res) => {
  console.error(`[proxy error] ${err.message}`)
  // 必须给出响应：否则客户端一直挂到自身超时。
  // 502 让前端识别为"后端不可达"（而非业务错误）并提示用户去启动服务。
  // WS 升级场景下 res 是 socket，没有 writeHead —— 只销毁连接。
  if (res && typeof res.writeHead === 'function' && !res.headersSent) {
    try {
      res.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' })
      res.end(JSON.stringify({
        code: 5020,
        message: `后端服务不可达（${BACKEND_URL}）——请确认后端已启动`,
        data: null,
      }))
    } catch {
      /* 连接已断开 */
    }
  } else if (res && typeof res.destroy === 'function') {
    res.destroy()
  }
})

// ---------- 静态路径解析（实现在 lib/static-files.mjs，含路径穿越测试） ----------
const { resolveStaticPath, cacheHeaderFor } = createStaticResolver(FRONTEND_DIST)

// ---------- 安全响应头 ----------
// 静态资源与 API 响应都带。CSP 暂不启用：index.html 有内联主题脚本（FOUC 防护），
// 上 CSP 需要先改造成 nonce/hash，属 Phase 3。
function setSecurityHeaders(res) {
  res.setHeader('X-Content-Type-Options', 'nosniff')
  res.setHeader('Referrer-Policy', 'no-referrer')
  res.setHeader('X-Frame-Options', 'SAMEORIGIN')
}


// ---------- 访问令牌（安全审计修复：API 单点鉴权） ----------
// 后端只绑 127.0.0.1，server.js 是唯一外部入口 —— /api/* 必须携带
// X-API-Token（静态资源放行，App/PWA 首屏加载不受影响）。
// Token 来源：环境变量 QM_TOKEN > .qm-token 文件（首次启动自动生成）；
//             .qm-token.prev 是轮换宽限期内的旧令牌。
const TOKEN_FILE = resolve(__dirname, '..', '..', '.qm-token')
const { tokens: API_TOKENS, generated: TOKEN_GENERATED } = loadAccessTokens({
  tokenFile: TOKEN_FILE,
  envToken: process.env.QM_TOKEN,
})
if (TOKEN_GENERATED) {
  console.log(`🔑 已生成访问令牌（手机端"设置 → 服务器地址"页需填入）: ${API_TOKENS[0]}`)
  console.log(`   令牌文件: ${TOKEN_FILE}`)
}
if (API_TOKENS.length === 0) {
  console.error('⚠️ 无可用访问令牌：/api 将拒绝所有非本机直连请求（fail-closed）')
}

/**
 * 回环绕过只对"本机浏览器直连"生效：
 * 一旦请求带代理头（cloudflared / nginx / Caddy 等隧道），回环地址仅代表
 * 最后一跳在本机，不等于调用者可信 —— 必须校验令牌。判定逻辑在
 * lib/security.mjs（纯函数，有单测），此处只做请求对象适配。
 */
function authorize(req) {
  return isAuthorized({
    remoteAddress: req.socket?.remoteAddress,
    headers: req.headers,
    tokens: API_TOKENS,
  })
}

// ---------- 静态文件服务器 ----------
const isApiRequest = (url) => url === '/api' || (url ?? '').startsWith('/api/')

const server = createServer((req, res) => {
  setSecurityHeaders(res)

  // 1. /api/* → 代理到后端（带令牌校验）
  if (isApiRequest(req.url)) {
    if (req.method === 'OPTIONS') {
      // CORS 预检放行（浏览器会先发预检，此时未必带令牌）
      res.setHeader('Vary', 'Origin')
      res.writeHead(204, {
        'Access-Control-Allow-Origin': req.headers.origin ?? '*',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-API-Token',
      })
      res.end()
      return
    }
    const auth = authorize(req)
    if (!auth.ok) {
      // 服务端留证据，客户端不泄露具体原因（避免探测）
      console.warn(
        `[auth] 拒绝 /api 请求: reason=${auth.reason} remote=${req.socket?.remoteAddress} ` +
          `proxied=${req.headers['x-forwarded-for'] ?? req.headers['cf-connecting-ip'] ?? '-'}`,
      )
      res.writeHead(401, { 'Content-Type': 'application/json; charset=utf-8' })
      res.end(JSON.stringify({ code: 4010, message: '需要访问令牌：请在设置页填入服务器访问令牌', data: null }))
      return
    }
    proxy.web(req, res, { target: BACKEND_URL })
    return
  }

  // 2. 其余 → 提供静态文件（SPA 支持：fallback 到 index.html）
  const parsed = resolveStaticPath(req.url === '/' ? '/index.html' : req.url)
  if (parsed === null) {
    res.writeHead(403)
    res.end('Forbidden')
    return
  }

  let filePath = parsed.full
  if (!existsSync(filePath)) {
    // SPA fallback：未知路径交给前端路由
    filePath = join(FRONTEND_DIST, 'index.html')
  }
  if (!existsSync(filePath)) {
    // dist 存在但没有 index.html（构建被中断）—— 明确报错而不是抛异常
    res.writeHead(503, { 'Content-Type': 'text/plain; charset=utf-8' })
    res.end('frontend/dist/index.html missing - run: cd frontend && npm run build')
    return
  }

  let content
  try {
    content = readFileSync(filePath)
  } catch (e) {
    // 读失败不能把整个进程带崩（未捕获异常会终止 node）
    console.error(`[static error] ${filePath}: ${e.message}`)
    res.writeHead(500)
    res.end('Internal Server Error')
    return
  }

  res.setHeader('Cache-Control', cacheHeaderFor(filePath))
  res.setHeader('Content-Type', getMimeType(filePath))
  res.writeHead(200)
  res.end(content)
})

// SSE 长连接代理（同样校验令牌 —— WS/升级通道不得绕过）
server.on('upgrade', (req, socket, head) => {
  if (isApiRequest(req.url) && !authorize(req).ok) {
    socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n')
    socket.destroy()
    return
  }
  proxy.ws(req, socket, head, { target: BACKEND_URL })
})

server.listen(PORT, '0.0.0.0', () => {
  console.log(`✅ 启明星统一服务已启动`)
  console.log(`   本地访问：http://localhost:${PORT}`)
  console.log(`   后端代理：${BACKEND_URL}`)
  console.log(`   前端资源：${FRONTEND_DIST}`)
  console.log(``)
  console.log(`   ⚠️  已监听 0.0.0.0:${PORT} —— 同网络的其他设备都能访问本端口。`)
  console.log(`      /api/* 需要 X-API-Token；仅「本机浏览器直连」豁免。`)
  console.log(`      经隧道/反代（cloudflared 等）访问时一律校验令牌，回环不放行。`)
  console.log(`      令牌轮换：cd ops/server && npm run token:rotate（旧令牌宽限 1 轮，删 .qm-token.prev 即吊销）`)
  console.log(`      公共 WiFi 下建议改用 Tailscale，不要在开放网络暴露此端口。`)
})
