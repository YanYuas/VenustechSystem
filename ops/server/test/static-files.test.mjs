// ============================================================
// 静态文件解析回归测试：路径穿越是安全边界，必须可验证
// ============================================================
import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { createStaticResolver, getMimeType, NO_CACHE_FILES } from '../lib/static-files.mjs'

const root = process.env.EDGE_TEST_DIST_ROOT || tmpdir()
const dist = mkdtempSync(join(root, 'qm-edge-dist-'))
mkdirSync(join(dist, 'assets'), { recursive: true })
writeFileSync(join(dist, 'index.html'), '<html>ok</html>')
writeFileSync(join(dist, 'assets', 'app-abc123.js'), 'console.log(1)')
writeFileSync(join(dist, 'sw.js'), '// sw')
process.on('exit', () => rmSync(dist, { recursive: true, force: true }))

const { resolveStaticPath, cacheHeaderFor } = createStaticResolver(dist)

test('正常路径解析', () => {
  const p = resolveStaticPath('/index.html')
  assert.equal(p.rel.replace(/\\/g, '/'), 'index.html')
  assert.ok(p.full.endsWith('index.html'))
})

test('剥离 query 与 hash（历史坑：带参会被当成文件名）', () => {
  const p = resolveStaticPath('/index.html?v=2#top')
  assert.equal(p.rel, 'index.html')
})

test('拒绝路径穿越（多种编码）', () => {
  assert.equal(resolveStaticPath('/../secret.txt'), null)
  assert.equal(resolveStaticPath('/%2e%2e/secret.txt'), null)
  assert.equal(resolveStaticPath('/..%2fsecret.txt'), null)
  assert.equal(resolveStaticPath('/a/../../secret.txt'), null)
  assert.equal(resolveStaticPath('/..\\secret.txt'), null)
  assert.equal(resolveStaticPath('/index.html%00.js'), null)
})

test('非法百分号编码 → null 而不是抛异常', () => {
  assert.equal(resolveStaticPath('/%E0%A4%A'), null)
})

test('缓存策略：入口/SW 不缓存，hash 资源长缓存', () => {
  assert.equal(cacheHeaderFor(join(dist, 'index.html')), 'no-cache, must-revalidate')
  assert.equal(cacheHeaderFor(join(dist, 'sw.js')), 'no-cache, must-revalidate')
  assert.match(cacheHeaderFor(join(dist, 'assets', 'app-abc123.js')), /immutable/)
  assert.equal(cacheHeaderFor(join(dist, 'other.txt')), 'public, max-age=3600')
})

test('MIME 与不缓存文件集', () => {
  assert.equal(getMimeType('a.js'), 'application/javascript')
  assert.equal(getMimeType('a.webmanifest'), 'application/manifest+json')
  assert.equal(getMimeType('a.unknown'), 'application/octet-stream')
  assert.ok(NO_CACHE_FILES.has('index.html'))
})
