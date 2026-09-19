// ============================================================
// 离线队列核心测试（mod-tools F4.3）
//
// 运行：node_modules/.bin/esbuild --bundle → node（见 check_all 第 5 步）
// 覆盖 PRD 验收：入队字段 / FIFO 重放 / 失败计数 / 最多 3 次 /
//              重试全部 / 清空失败 / 重启不丢（存储层持久）
// ============================================================
import {
  createQueueManager,
  type QueueEntry,
  type QueueStorage,
} from '../src/utils/offlineQueueCore'

let passed = 0
let failed = 0

function check(name: string, cond: boolean, extra = '') {
  if (cond) {
    passed += 1
    console.log(`  ✅ ${name}`)
  } else {
    failed += 1
    console.log(`  ❌ ${name} ${extra}`)
  }
}

/** 内存存储：模拟 IndexedDB（含自增主键与持久性） */
function memoryStorage(): QueueStorage & { dump(): QueueEntry[] } {
  let seq = 0
  const rows: QueueEntry[] = []
  return {
    async add(entry) {
      const id = ++seq
      rows.push({ ...entry, id })
      return id
    },
    async all() {
      return rows.map((r) => ({ ...r }))
    },
    async update(entry) {
      const i = rows.findIndex((r) => r.id === entry.id)
      if (i >= 0) rows[i] = { ...entry }
    },
    async remove(id) {
      const i = rows.findIndex((r) => r.id === id)
      if (i >= 0) rows.splice(i, 1)
    },
    async removeFailed(maxRetries) {
      let n = 0
      for (let i = rows.length - 1; i >= 0; i--) {
        if (rows[i].retries >= maxRetries) {
          rows.splice(i, 1)
          n += 1
        }
      }
      return n
    },
    dump: () => rows.map((r) => ({ ...r })),
  }
}

async function main() {
  console.log('离线队列核心测试（mod-tools F4.3）')

  // ---------- 1. 入队字段完整 ----------
  {
    const storage = memoryStorage()
    const sent: string[] = []
    const mgr = createQueueManager({
      storage,
      send: async (e) => {
        sent.push(e.path)
        return {}
      },
      intervalMs: 1,
    })
    await mgr.enqueue({ path: '/assistant/apply', method: 'POST', body: { a: 1 }, label: 'AI 助理 · 加入待办' })
    const items = await mgr.list()
    const it = items[0]
    check(
      '入队条目含 路径/方法/请求体/时间戳/重试次数',
      items.length === 1 &&
        it.path === '/assistant/apply' &&
        it.method === 'POST' &&
        JSON.stringify(it.body) === '{"a":1}' &&
        typeof it.createdAt === 'number' &&
        it.retries === 0,
      JSON.stringify(it),
    )
    check('pending 计数正确', (await mgr.pending()) === 1, String(await mgr.pending()))
  }

  // ---------- 2. FIFO 重放 + 出队 ----------
  {
    const storage = memoryStorage()
    const sent: string[] = []
    const mgr = createQueueManager({
      storage,
      send: async (e) => {
        sent.push(e.path)
        return {}
      },
      intervalMs: 1,
    })
    await mgr.enqueue({ path: '/p1', method: 'POST', body: {} })
    await new Promise((r) => setTimeout(r, 2))
    await mgr.enqueue({ path: '/p2', method: 'PATCH', body: {} })
    await new Promise((r) => setTimeout(r, 2))
    await mgr.enqueue({ path: '/p3', method: 'DELETE' })
    const res = await mgr.flush()
    check('FIFO 顺序重放', sent.join(',') === '/p1,/p2,/p3', sent.join(','))
    check('重放成功全部出队', res.sent === 3 && (await mgr.pending()) === 0, JSON.stringify(res))
  }

  // ---------- 3. 失败计数 + 最多 3 次 ----------
  {
    const storage = memoryStorage()
    let calls = 0
    const mgr = createQueueManager({
      storage,
      send: async () => {
        calls += 1
        throw new Error('网络错误')
      },
      intervalMs: 1,
      maxRetries: 3,
    })
    await mgr.enqueue({ path: '/will-fail', method: 'POST', body: {} })
    const first = await mgr.flush()
    const after1 = (await mgr.list())[0]
    check('失败后条目保留且重试次数 +1（未达上限不计入终态 failed）',
      first.failed === 0 && after1.retries === 1 && after1.lastError === '网络错误',
      JSON.stringify({ first, after1 }))
    const second = await mgr.flush()
    check('第二次重放失败 → 重试次数 2',
      second.failed === 0 && (await mgr.list())[0].retries === 2,
      JSON.stringify(await mgr.list()))
    const third = await mgr.flush()
    const item = (await mgr.list())[0]
    check('达到 3 次上限 → 标记失败并停止本轮',
      third.stopped === true && item.retries === 3 && item.lastError?.includes('网络错误'),
      JSON.stringify(item))
    const callsBefore = calls
    await mgr.flush()
    check('已达上限的条目不被自动重放', calls === callsBefore, `${calls} vs ${callsBefore}`)

    // 手动重试全部：清零后重放（此处 send 仍失败 → 重试计数从 1 重新累计）
    const retried = await mgr.retryAll()
    check('重试全部会再次尝试失败条目',
      calls > callsBefore && retried.sent === 0 && (await mgr.list())[0].retries === 1,
      JSON.stringify({ calls, retried, item: (await mgr.list())[0] }))

    // 再失败两次 → 达到上限，此时才进入终态 failed，可被「清空失败」移除
    await mgr.flush()
    await mgr.flush()
    const stuck = (await mgr.list())[0]
    check('累计 3 次失败后进入终态 failed', stuck.retries === 3, JSON.stringify(stuck))
    const cleared = await mgr.clearFailed()
    check('清空失败移除终态失败条目', cleared === 1 && (await mgr.pending()) === 0, String(cleared))
  }

  // ---------- 4. 部分成功：成功的出队、失败的保留 ----------
  {
    const storage = memoryStorage()
    const mgr = createQueueManager({
      storage,
      send: async (e) => {
        if (e.path === '/bad') throw new Error('500')
        return {}
      },
      intervalMs: 1,
    })
    await mgr.enqueue({ path: '/good1', method: 'POST', body: {} })
    await mgr.enqueue({ path: '/bad', method: 'POST', body: {} })
    await mgr.enqueue({ path: '/good2', method: 'POST', body: {} })
    const res = await mgr.flush()
    const left = await mgr.list()
    check('部分成功：2 成功 1 保留', res.sent === 2 && left.length === 1 && left[0].path === '/bad',
      JSON.stringify({ res, left: left.map((l) => l.path) }))
  }

  // ---------- 5. 重启不丢（存储层持久性） ----------
  {
    const storage = memoryStorage()
    const mgr1 = createQueueManager({ storage, send: async () => ({}), intervalMs: 1 })
    await mgr1.enqueue({ path: '/persist-me', method: 'POST', body: { x: 1 } })
    // 模拟 App 重启：用同一个持久存储新建管理器
    const mgr2 = createQueueManager({ storage, send: async () => ({}), intervalMs: 1 })
    const items = await mgr2.list()
    check('重启后队列仍在（同一持久存储）',
      items.length === 1 && items[0].path === '/persist-me', JSON.stringify(items))
  }

  // ---------- 6. 重放间隔 ----------
  {
    const storage = memoryStorage()
    const stamps: number[] = []
    const mgr = createQueueManager({
      storage,
      send: async () => {
        stamps.push(Date.now())
        return {}
      },
      intervalMs: 40,
    })
    await mgr.enqueue({ path: '/s1', method: 'POST', body: {} })
    await mgr.enqueue({ path: '/s2', method: 'POST', body: {} })
    await mgr.flush()
    const gap = stamps.length === 2 ? stamps[1] - stamps[0] : -1
    check('重放条目之间有间隔（默认 500ms 可配）', gap >= 35, `gap=${gap}ms`)
  }

  // ---------- 7. 并发保护 ----------
  {
    const storage = memoryStorage()
    let concurrent = 0
    let maxConcurrent = 0
    const mgr = createQueueManager({
      storage,
      send: async () => {
        concurrent += 1
        maxConcurrent = Math.max(maxConcurrent, concurrent)
        await new Promise((r) => setTimeout(r, 10))
        concurrent -= 1
        return {}
      },
      intervalMs: 1,
    })
    await mgr.enqueue({ path: '/c1', method: 'POST', body: {} })
    await Promise.all([mgr.flush(), mgr.flush()])
    check('并发 flush 不会重复发送', maxConcurrent === 1, `maxConcurrent=${maxConcurrent}`)
  }

  console.log(`\n离线队列测试结果: ${passed} 通过, ${failed} 失败`)
  process.exit(failed === 0 ? 0 : 1)
}

void main()
