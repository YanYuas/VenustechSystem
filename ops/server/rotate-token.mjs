#!/usr/bin/env node
// ============================================================
// 访问令牌轮换
//
// 做两件事：
//   1. 把当前 .qm-token 备份为 .qm-token.prev（宽限期：旧令牌仍被接受）
//   2. 生成新令牌写入 .qm-token
//
// 为什么需要宽限期：手机上已配对的客户端存的是旧令牌。直接换掉会让所有
// 设备立刻 401。宽限期让用户有时间在每台设备上更新。
// 完成吊销：确认所有设备更新后删除 .qm-token.prev 并重启服务。
//
// 用法：cd ops/server && npm run token:rotate
// ============================================================
import { randomBytes } from 'node:crypto'
import { copyFileSync, existsSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const TOKEN_FILE = resolve(__dirname, '..', '..', '.qm-token')
const PREV_FILE = TOKEN_FILE + '.prev'

function main() {
  if (process.env.QM_TOKEN) {
    console.error('❌ 检测到环境变量 QM_TOKEN：它优先于令牌文件，轮换文件不会生效。')
    console.error('   请先移除 QM_TOKEN，或直接修改环境变量后重启服务。')
    process.exit(1)
  }

  if (existsSync(TOKEN_FILE)) {
    copyFileSync(TOKEN_FILE, PREV_FILE)
    console.log(`📦 旧令牌已备份（宽限期）：${PREV_FILE}`)
  } else {
    console.log('ℹ️ 尚无 .qm-token，将直接生成新令牌。')
  }

  const fresh = randomBytes(24).toString('hex')
  writeFileSync(TOKEN_FILE, fresh, { mode: 0o600 })
  console.log(`🔑 新访问令牌: ${fresh}`)
  console.log('')
  console.log('下一步：')
  console.log('  1) 重启统一服务（node ops/server/server.js）使新令牌生效')
  console.log('  2) 在每台设备「设置 → 服务器地址」更新令牌')
  console.log('  3) 全部更新后删除 .qm-token.prev 并重启 → 旧令牌彻底吊销')
}

main()
