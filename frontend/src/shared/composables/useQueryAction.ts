// ============================================================
// 路由动作参数消费器（2026-09-15 新增，修复 R-02）
//
// 场景：首页「快速入口」的"新建任务 / 新建笔记 / 新建项目"原本只 push 到列表页
// （如 /tasks），用户还得再点一次"新建"按钮 —— 也就是"点了新建却没新建"。
//
// 现在入口带上 `?action=new`，本页用本 composable 消费该参数、直接打开新建弹窗，
// 随后把参数清掉（否则刷新或前进/后退会重复触发）。
//
// 用法：
//   useQueryAction({ new: () => { createOpen.value = true } })
//
// 设计为通用映射而非写死 'new'，后续可扩展 ?action=import / ?action=filter 等。
// ============================================================
import { watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { LocationQueryRaw } from 'vue-router'

export function useQueryAction(handlers: Record<string, () => void>) {
  const route = useRoute()
  const router = useRouter()

  async function consume(action: string) {
    const handler = handlers[action]
    if (!handler) return

    try {
      handler()
    } catch (err) {
      // 动作失败：**不清参数**（刷新/重进可重试），但必须把错误抛到明面上。
      // 为什么不能让它自然冒泡：consume 是 async，而调用处是 `void consume(v)`，
      // 异常会变成**未捕获的 Promise rejection** —— Vue 的 errorHandler 接不住它
      // （watch 回调返回 undefined），控制台只会多一条无上下文的报错。
      // 2026-10-11 由前端 vitest 套件（useQueryAction.spec.ts 第 3 组）测出。
      console.error('[useQueryAction] 路由动作执行失败:', action, err)
      return
    }

    // 清掉 action 参数，避免刷新/回退时重复触发
    const rest: LocationQueryRaw = {}
    for (const [k, v] of Object.entries(route.query)) {
      if (k === 'action') continue
      rest[k] = v
    }
    try {
      await router.replace({ query: rest })
    } catch {
      // 路由替换失败不影响已触发的动作，静默即可
    }
  }

  // immediate：首次进入页面时也要生效；
  // 同时监听变化：已经在 /tasks 上时再次点击首页入口也应重新打开弹窗。
  watch(
    () => route.query.action,
    (v) => {
      if (typeof v === 'string' && v) void consume(v)
    },
    { immediate: true },
  )
}
