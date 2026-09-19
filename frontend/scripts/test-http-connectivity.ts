// ============================================================
// 连通性修复的行为测试（2026-09-19）
//
// 运行：esbuild --bundle → node（见 check_all 第 7 步）
//
// 覆盖三条修复，每条都是"改之前必然失败"的断言：
//   1. 网络级失败 → ApiUnreachableError（可识别）
//   2. 写操作在"服务不可达"时**入离线队列**（原来只认 navigator.onLine）
//   3. 幂等请求重试 1 次（原来的重试分支是死代码）
//   4. 请求成功后连通性自愈
//   5. 不可达期间次生 error 提示被抑制，统一提示放行
// ============================================================
import {
  ApiUnreachableError,
  OfflineQueuedError,
  http,
  setOfflineQueueHandler,
  type OfflineEnqueueHandler,
} from '../src/api/http'
import { backendUnreachable, isBackendUnreachable, markReachable } from '../src/api/connectivity'
import { toast } from '../src/composables/useToast'

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

// ---------- fetch 桩：可切换失败 / 成功，记录调用 ----------
const calls: Array<{ path: string; method: string }> = []
let mode: 'fail' | 'ok' = 'fail'

;(globalThis as unknown as { fetch: unknown }).fetch = async (url: unknown, init?: RequestInit) => {
  const u = String(url)
  calls.push({ path: u.replace(/^.*\/api\/v1/, ''), method: (init?.method ?? 'GET').toUpperCase() })
  if (mode === 'fail') throw new TypeError('Failed to fetch')
  return new Response(JSON.stringify({ code: 0, message: 'success', data: { ok: true } }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

function countCalls(path: string, method: string): number {
  return calls.filter((c) => c.path === path && c.method === method).length
}

async function main() {
  // ---------- 1 & 3：GET 网络失败 → 可识别的不可达错误，且重试 1 次 ----------
  let err1: unknown
  try {
    await http.get('/probe')
  } catch (e) {
    err1 = e
  }
  check('网络失败抛 ApiUnreachableError', err1 instanceof ApiUnreachableError, String(err1))
  check('不可达错误带 unreachable 标记',
    (err1 as ApiUnreachableError | undefined)?.unreachable === true, 'missing flag')
  check('幂等请求重试 1 次（共 2 次调用）', countCalls('/probe', 'GET') === 2,
    `called ${countCalls('/probe', 'GET')}`)

  // ---------- 2：不可达状态被标记（响应式，供顶栏使用） ----------
  check('不可达状态已标记（函数）', isBackendUnreachable() === true, 'false')
  check('不可达状态已标记（响应式 ref）', backendUnreachable.value === true, 'false')

  // 已判定不可达 → 不再重试（避免多等一个往返）
  try { await http.get('/probe2') } catch { /* expected */ }
  check('已知不可达时不再重试', countCalls('/probe2', 'GET') === 1,
    `called ${countCalls('/probe2', 'GET')}`)

  // ---------- 4：写操作在"服务不可达"时入离线队列（核心修复） ----------
  const enqueued: Array<{ path: string; method: string }> = []
  const handler: OfflineEnqueueHandler = async (path, method) => {
    enqueued.push({ path, method })
  }
  setOfflineQueueHandler(handler)

  let err2: unknown
  try {
    await http.post('/tasks', { title: '地铁上记的待办' })
  } catch (e) {
    err2 = e
  }
  check('服务不可达时写操作被离线队列接管', err2 instanceof OfflineQueuedError, String(err2))
  check('入队内容正确', enqueued.length === 1 && enqueued[0].path === '/tasks'
    && enqueued[0].method === 'POST', JSON.stringify(enqueued))
  check('写操作不重试（仅 1 次调用）', countCalls('/tasks', 'POST') === 1,
    `called ${countCalls('/tasks', 'POST')}`)

  // ---------- 5：提示收敛 ----------
  toast.clear()
  toast.error('加载失败', '左侧面板数据加载失败')
  const afterSecondary = toast.items.length
  check('不可达期间次生 error 提示被抑制', afterSecondary === 0, `items=${afterSecondary}`)
  toast.error('连不上后端服务', '无法连接服务器…')
  check('统一连通性提示放行', toast.items.length === 1, `items=${toast.items.length}`)
  toast.warning('请输入名称')
  check('本地校验类 warning 不受抑制', toast.items.length === 2, `items=${toast.items.length}`)

  // ---------- 6：自愈 ----------
  mode = 'ok'
  const ok = await http.get<{ ok: boolean }>('/recover')
  check('恢复后请求成功', ok?.ok === true, JSON.stringify(ok))
  check('恢复后连通性标记清除（函数）', isBackendUnreachable() === false, 'still true')
  check('恢复后连通性标记清除（响应式）', backendUnreachable.value === false, 'still true')
  toast.clear()
  toast.error('加载失败', '现在应正常显示')
  check('恢复后 error 提示恢复正常', toast.items.length === 1, `items=${toast.items.length}`)

  // 收尾：清掉全局状态，避免影响后续测试
  markReachable()
  setOfflineQueueHandler(null)

  console.log(`\n连通性测试: ${passed} 通过, ${failed} 失败`)
  if (failed > 0) process.exit(1)
}

void main()
