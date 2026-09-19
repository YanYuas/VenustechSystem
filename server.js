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
import { basename, extname, isAbsolute, join, relative, resolve, sep } from 'node:path'
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

/** 必须每次校验的文件：一旦被缓存，应用更新后会加载到旧的入口/旧 SW */
const NO_CACHE_FILES = new Set(['index.html', 'sw.js', 'manifest.webmanifest'])

/**
 * 把请求 URL 解析为 dist 内的安全绝对路径。
 * 返回 null 表示越界（调用方回 403）。
 *
 * 两个关键点：
 *   - 先剥离 `?query` 与 `#hash`：req.url 是原始串，带参进 join 会变成
 *     非法文件名 → 静默 fallback 到 index.html（资源全变 HTML）
 *   - 越界判定用 relative()，不能用 startsWith()：后者会把
 *     `...\frontend\dist-secret` 误判为在 dist 之内
 */
function resolveStaticPath(rawUrl) {
  let pathOnly = (rawUrl ?? '/').split('?')[0].split('#')[0]
  try {
    pathOnly = decodeURIComponent(pathOnly)
  } catch {
    return null // 非法百分号编码
  }
  if (pathOnly.includes('\0')) return null
  const resolved = resolve(join(FRONTEND_DIST, pathOnly))
  const rel = relative(FRONTEND_DIST, resolved)
  if (rel.startsWith('..') || isAbsolute(rel)) return null
  return { full: resolved, rel }
}

/** 缓存策略：入口与 SW 不缓存；hash 资源长期缓存；其余短缓存 */
function cacheHeaderFor(fullPath) {
  if (NO_CACHE_FILES.has(basename(fullPath))) return 'no-cache, must-revalidate'
  if (fullPath.includes(`${sep}assets${sep}`)) return 'public, max-age=31536000, immutable'
  return 'public, max-age=3600'
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
const isApiRequest = (url) => url === '/api' || (url ?? '').startsWith('/api/')

const server = createServer((req, res) => {
  // 1. /api/* → 代理到后端（带令牌校验）
  if (isApiRequest(req.url)) {
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
  if (isApiRequest(req.url) && !isAuthorized(req)) {
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
  console.log(`      /api/* 需要 X-API-Token（本机回环来源豁免）。`)
  console.log(`      公共 WiFi 下建议改用 Tailscale，不要在开放网络暴露此端口。`)
})
