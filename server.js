#!/usr/bin/env node
// ============================================================
// 启明星系统 — 统一 Web 服务
// - 提供前端静态文件（dist/）
// - 代理 /api/* 到 FastAPI 后端（127.0.0.1:8765）
// - 单端口对外暴露，cloudflared 只需隧道一个端口
//
// 启动：node server.js
// 环境变量：PORT（默认 3000），BACKEND_URL（默认 http://127.0.0.1:8765）
// ============================================================
import { createServer } from 'node:http'
import pkg from 'http-proxy'
const { createProxyServer } = pkg
import { fileURLToPath } from 'node:url'
import { extname, join, resolve } from 'node:path'
import { readFileSync, writeFileSync, existsSync } from 'node:fs'

const __dirname = fileURLToPath(new URL('.', import.meta.url))

const PORT = parseInt(process.env.PORT ?? '3000', 10)
const BACKEND_URL = process.env.BACKEND_URL ?? 'http://127.0.0.1:8765'
const FRONTEND_DIST = resolve(__dirname, 'frontend', 'dist')

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

proxy.on('error', (err) => {
  console.error(`[proxy error] ${err.message}`)
})

// ---------- MIME 类型 ----------
const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript',
  '.mjs': 'application/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.txt': 'text/plain',
}

function getMimeType(path) {
  return MIME_TYPES[extname(path).toLowerCase()] ?? 'application/octet-stream'
}

// ---------- 访问令牌（安全审计修复：API 单点鉴权） ----------
// 后端只绑 127.0.0.1，server.js 是唯一外部入口 —— /api/* 必须携带
// X-API-Token（静态资源放行，App/PWA 首屏加载不受影响）。
// Token 来源：环境变量 QM_TOKEN > .qm-token 文件（首次启动自动生成）。
import { randomBytes } from 'node:crypto'
const TOKEN_FILE = resolve(__dirname, '.qm-token')
let API_TOKEN = process.env.QM_TOKEN ?? ''
if (!API_TOKEN) {
  try {
    API_TOKEN = readFileSync(TOKEN_FILE, 'utf8').trim()
  } catch { /* 首次启动 */ }
  if (!API_TOKEN) {
    API_TOKEN = randomBytes(24).toString('hex')
    try {
      writeFileSync(TOKEN_FILE, API_TOKEN)
      console.log(`🔑 已生成访问令牌（手机端"设置 → 服务器地址"页需填入）: ${API_TOKEN}`)
      console.log(`   令牌文件: ${TOKEN_FILE}`)
    } catch (e) {
      console.error('⚠️ 令牌写入失败，/api 将拒绝外部访问:', e.message)
    }
  }
}
// 本机回环来源不校验（PC 前端零改动可用）；外部来源必须持令牌
const LOOPBACK_HOSTS = new Set(['127.0.0.1', '::1', '::ffff:127.0.0.1'])

function isAuthorized(req) {
  if (LOOPBACK_HOSTS.has(req.socket.remoteAddress ?? '')) return true
  const token = req.headers['x-api-token'] ?? ''
  return API_TOKEN.length > 0 && token === API_TOKEN
}

// ---------- 静态文件服务器 ----------
const server = createServer((req, res) => {
  // 1. /api/* → 代理到后端（带令牌校验）
  if (req.url?.startsWith('/api')) {
    if (req.method === 'OPTIONS') {
      // CORS 预检放行（浏览器会先发预检，此时未必带令牌）
      res.writeHead(204, {
        'Access-Control-Allow-Origin': req.headers.origin ?? '*',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,PATCH,DELETE,OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-API-Token',
      })
      res.end()
      return
    }
    if (!isAuthorized(req)) {
      res.writeHead(401, { 'Content-Type': 'application/json; charset=utf-8' })
      res.end(JSON.stringify({ code: 4010, message: '需要访问令牌：请在设置页填入服务器访问令牌', data: null }))
      return
    }
    proxy.web(req, res, { target: BACKEND_URL })
    return
  }

  // 2. 其余 → 提供静态文件（SPA 支持：fallback 到 index.html）
  let filePath = join(FRONTEND_DIST, req.url === '/' ? 'index.html' : req.url ?? 'index.html')

  // 安全：防止路径穿越
  if (!filePath.startsWith(FRONTEND_DIST)) {
    res.writeHead(403)
    res.end('Forbidden')
    return
  }

  if (!existsSync(filePath)) {
    // SPA fallback：所有未知路径返回 index.html（Vue Router Hash 模式兼容）
    filePath = join(FRONTEND_DIST, 'index.html')
  }

  const contentType = getMimeType(filePath)
  const content = readFileSync(filePath)

  // 静态资源缓存策略（生产环境）
  res.setHeader('Cache-Control', 'public, max-age=86400')
  res.setHeader('Content-Type', contentType)
  res.writeHead(200)
  res.end(content)
})

// SSE 长连接代理（同样校验令牌 —— WS/升级通道不得绕过）
server.on('upgrade', (req, socket, head) => {
  if (req.url?.startsWith('/api') && !isAuthorized(req)) {
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
})
