// ============================================================
// 静态文件解析与缓存策略（纯函数 + 可注入 dist 目录，便于单测）
//
// 从 server.js 抽出，原因：路径穿越是安全边界，必须有回归测试。
// 两个历史上的坑（保留注释，勿简化）：
//   1. 必须先剥离 ?query / #hash：req.url 是原始串，带参进 join 会变成
//      非法文件名 → 静默 fallback 到 index.html（资源全变 HTML）。
//   2. 越界判定用 relative() 而不是 startsWith()：后者会把
//      `<dist>-secret` 这类同级目录误判为在 dist 之内。
// ============================================================
import { basename, extname, isAbsolute, join, relative, resolve, sep } from 'node:path'

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript',
  '.mjs': 'application/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.txt': 'text/plain',
  '.webmanifest': 'application/manifest+json',
}

/** 必须每次校验的文件：一旦被缓存，应用更新后会加载到旧的入口/旧 SW */
export const NO_CACHE_FILES = new Set(['index.html', 'sw.js', 'manifest.webmanifest'])

export function getMimeType(filePath) {
  return MIME_TYPES[extname(filePath).toLowerCase()] ?? 'application/octet-stream'
}

/**
 * @param {string} distDir 前端构建产物目录（绝对路径）
 * @returns {{ resolveStaticPath: (rawUrl?: string) => ({full: string, rel: string}|null), cacheHeaderFor: (fullPath: string) => string }}
 */
export function createStaticResolver(distDir) {
  function resolveStaticPath(rawUrl) {
    let pathOnly = (rawUrl ?? '/').split('?')[0].split('#')[0]
    try {
      pathOnly = decodeURIComponent(pathOnly)
    } catch {
      return null // 非法百分号编码
    }
    if (pathOnly.includes('\0')) return null
    const resolved = resolve(join(distDir, pathOnly))
    const rel = relative(distDir, resolved)
    if (rel.startsWith('..') || isAbsolute(rel)) return null // 路径穿越
    return { full: resolved, rel }
  }

  function cacheHeaderFor(fullPath) {
    if (NO_CACHE_FILES.has(basename(fullPath))) return 'no-cache, must-revalidate'
    if (fullPath.includes(`${sep}assets${sep}`)) return 'public, max-age=31536000, immutable'
    return 'public, max-age=3600'
  }

  return { resolveStaticPath, cacheHeaderFor }
}
