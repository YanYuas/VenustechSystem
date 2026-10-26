// ============================================================
// 访问令牌加载与轮换
//
// 令牌来源优先级：环境变量 QM_TOKEN > .qm-token 文件 > 自动生成。
// 轮换宽限：rotate-token.mjs 会把旧令牌留在 .qm-token.prev，
// 本模块同时接受两者 —— 已配对的手机不必立刻重填；确认所有设备更新后，
// 删除 .qm-token.prev 即完成吊销。
//
// 注意：令牌文件固定在仓库根（历史位置），迁移到 var/secrets/ 需要同时改
// start-mobile.bat 的读取逻辑与已配对设备，属 Phase 3（见 ARCHITECTURE §10 D-12）。
// ============================================================
import { randomBytes } from 'node:crypto'
import { readFileSync, writeFileSync } from 'node:fs'

function readTrimmed(p) {
  try {
    const v = readFileSync(p, 'utf8').trim()
    return v || null
  } catch {
    return null
  }
}

export const PREV_SUFFIX = '.prev'

/**
 * @param {{ tokenFile: string, envToken?: string }} opts
 * @returns {{ tokens: string[], generated: boolean, tokenFile: string }}
 */
export function loadAccessTokens({ tokenFile, envToken }) {
  const tokens = []
  const env = typeof envToken === 'string' ? envToken.trim() : ''
  if (env) tokens.push(env)

  const current = readTrimmed(tokenFile)
  const previous = readTrimmed(tokenFile + PREV_SUFFIX)
  if (current) tokens.push(current)
  if (previous && previous !== current) tokens.push(previous)

  let generated = false
  if (tokens.length === 0) {
    const fresh = randomBytes(24).toString('hex')
    try {
      writeFileSync(tokenFile, fresh, { mode: 0o600 })
      tokens.push(fresh)
      generated = true
    } catch {
      // 写不进去就保持空：调用方会拒绝所有非回环请求（fail-closed）
    }
  }
  // 去重（env 与文件可能相同）
  return { tokens: [...new Set(tokens)], generated, tokenFile }
}
