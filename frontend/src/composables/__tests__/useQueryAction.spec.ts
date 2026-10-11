// ============================================================
// 路由动作参数消费器 —— 单元测试（修复 R-02 的那个 composable）
//
// 背景：首页「快速入口」过去只 push 到列表页，用户还得再点一次「新建」——
// 即「点了新建却没新建」。现在入口带 `?action=new`，本 composable 消费它
// 并**把参数清掉**（否则刷新/前进后退会重复触发弹窗）。
//
// 这两件事都必须被守住：
//   ① 参数确实触发了动作（否则回到老问题）
//   ② 参数确实被清掉了（否则弹窗会反复自己打开）
// ============================================================
import { describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { defineComponent, h } from 'vue'

import { useQueryAction } from '@/composables/useQueryAction'

const Blank = { render: () => h('div') }

async function setup(query: Record<string, string>, handlers?: Record<string, () => void>) {
  const calls: string[] = []
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/tasks', component: Blank }, { path: '/other', component: Blank }],
  })

  const Comp = defineComponent({
    setup() {
      useQueryAction(handlers ?? {
        new: () => calls.push('new'),
        edit: () => calls.push('edit'),
      })
      return () => h('div')
    },
  })

  router.push({ path: '/tasks', query })
  await router.isReady()

  const wrapper = mount(Comp, { global: { plugins: [router] } })
  await flushPromises()

  return { router, calls, wrapper }
}

// ============================================================
// 第 1 组：参数被消费掉
// ============================================================
describe('第1组：消费 action 参数', () => {
  it('?action=new 触发对应处理器', async () => {
    const { calls } = await setup({ action: 'new' })
    expect(calls).toEqual(['new'])
  })

  it('消费后 action 参数被清掉（防刷新/回退重复弹窗）', async () => {
    const { router } = await setup({ action: 'new' })
    expect(router.currentRoute.value.query.action).toBeUndefined()
  })

  it('清参数时保留其它 query（身份过滤等不能被一起抹掉）', async () => {
    const { router } = await setup({ action: 'new', identity_id: 'abc', page: '2' })

    const q = router.currentRoute.value.query
    expect(q.action).toBeUndefined()
    expect(q.identity_id).toBe('abc')
    expect(q.page).toBe('2')
  })

  it('没有 action 时不触发任何处理器，也不动 URL', async () => {
    const { calls, router } = await setup({ identity_id: 'abc' })

    expect(calls).toEqual([])
    expect(router.currentRoute.value.query.identity_id).toBe('abc')
  })

  it('未注册的 action 不触发，也不清参数（保持不动，便于排查）', async () => {
    const { calls, router } = await setup({ action: 'export' })

    expect(calls).toEqual([])
    expect(router.currentRoute.value.query.action).toBe('export')
  })

  it('action 为空串时不触发', async () => {
    const { calls } = await setup({ action: '' })
    expect(calls).toEqual([])
  })
})

// ============================================================
// 第 2 组：同一页面内再次触发
// ============================================================
describe('第2组：同页重复触发', () => {
  it('已在列表页时再次 push ?action=new 仍会打开弹窗', async () => {
    const { router, calls } = await setup({ action: 'new' })
    expect(calls).toEqual(['new'])

    await router.push({ path: '/tasks', query: { action: 'new' } })
    await flushPromises()

    expect(calls).toEqual(['new', 'new'])
    expect(router.currentRoute.value.query.action).toBeUndefined()
  })

  it('不同 action 依次触发各自处理器', async () => {
    const { router, calls } = await setup({ action: 'new' })

    await router.push({ path: '/tasks', query: { action: 'edit' } })
    await flushPromises()

    expect(calls).toEqual(['new', 'edit'])
  })

  it('离开再回来（组件重建）也能再次触发', async () => {
    const { router, calls, wrapper } = await setup({ action: 'new' })
    expect(calls).toEqual(['new'])

    await router.push({ path: '/other' })
    await flushPromises()
    wrapper.unmount()

    const second = await setup({ action: 'new' })
    expect(second.calls).toEqual(['new'])
  })
})

// ============================================================
// 第 3 组：边界与健壮性
// ============================================================
describe('第3组：边界与健壮性', () => {
  it('空 handlers 映射下调用不会抛异常', async () => {
    const { calls } = await setup({ action: 'new' }, {})
    expect(calls).toEqual([])
  })

  it('action 为重复参数（数组）时不触发 —— 只接受字符串', async () => {
    // ?action=new&action=edit 会被 vue-router 解析成 string[]；
    // 若判定写成 `if (v)`，数组也会 through，然后 handlers[数组] 未定义
    // 而静默什么都不做 —— 这里显式钉住「数组一律忽略」。
    const { calls } = await setup({ action: ['new', 'edit'] as unknown as string })

    expect(calls).toEqual([])
  })

  it('处理器抛错时不误清参数，把错误记到控制台而不是变成未捕获 rejection', async () => {
    // 修前的缺陷：handler() 直接调用，抛错会顺着 async consume 变成
    // **未捕获的 Promise rejection**（调用处是 `void consume(v)`，Vue 接不住），
    // vitest 会报 "Unhandled Rejection"。现在改为捕获 + 记日志，参数保留可重试。
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/tasks', component: Blank }],
    })
    const Comp = defineComponent({
      setup() {
        useQueryAction({ new: () => { throw new Error('boom') } })
        return () => h('div')
      },
    })

    await router.push({ path: '/tasks', query: { action: 'new' } })
    await router.isReady()

    expect(() => mount(Comp, { global: { plugins: [router] } })).not.toThrow()
    expect(errorSpy).toHaveBeenCalledOnce()
    expect(errorSpy.mock.calls[0][0]).toContain('[useQueryAction]')
    // 失败时保留参数：宁可用户能再点一次，也不要「既没打开弹窗又清掉了参数」
    expect(router.currentRoute.value.query.action).toBe('new')
  })
})
