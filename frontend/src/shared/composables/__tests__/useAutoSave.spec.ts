// ============================================================
// shared/composables/useAutoSave —— 自动保存单元测试
//
// 该 composable 依赖组件生命周期（onMounted 起定时器 / onUnmounted 兜底提交），
// 因此用 @vue/test-utils mount 一个最小宿主组件；定时器用假时钟，
// 断言的是"用户可感知的保存语义"：防抖合并、在途串行补存、失败不误清脏、卸载兜底。
// ============================================================
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'

import { useAutoSave } from '../useAutoSave'

type AutoSaveApi = ReturnType<typeof useAutoSave<string>>

/** 已挂载的宿主组件：afterEach 统一卸载，避免残留 interval 定时器影响后续文件 */
const mounted: Array<{ unmount: () => void }> = []

function mountAutoSave(onSave: (data: string) => Promise<void>, initial = 'v1') {
  const data = ref(initial)
  const state: { api?: AutoSaveApi } = {}
  const wrapper = mount(
    defineComponent({
      setup() {
        state.api = useAutoSave(() => data.value, { onSave, debounce: 1000 })
        return () => h('div')
      },
    }),
  )
  if (!state.api) throw new Error('useAutoSave 未在 setup 中初始化')
  mounted.push(wrapper)
  return { wrapper, data, api: state.api }
}

afterEach(() => {
  mounted.splice(0).forEach((w) => w.unmount())
  vi.useRealTimers()
})

describe('useAutoSave：防抖与合并', () => {
  it('连续多次 scheduleSave 只落一次保存，且保存的是最后一次数据', async () => {
    vi.useFakeTimers()
    const onSave = vi.fn(async () => undefined)
    const { data, api } = mountAutoSave(onSave)

    api.scheduleSave()
    data.value = 'v2'
    api.scheduleSave()
    data.value = 'v3'
    api.scheduleSave()

    expect(api.dirty.value).toBe(true)
    await vi.advanceTimersByTimeAsync(1000)
    await flushPromises()

    expect(onSave).toHaveBeenCalledTimes(1)
    expect(onSave).toHaveBeenCalledWith('v3')
    expect(api.dirty.value).toBe(false)
    expect(api.lastSaved.value).toBeInstanceOf(Date)
  })

  it('保存进行中再次 save 时排队，在途保存结束后用最新快照补存（不并发 PATCH）', async () => {
    const resolvers: Array<() => void> = []
    const onSave = vi.fn<(data: string) => Promise<void>>(
      () =>
        new Promise<void>((resolve) => {
          resolvers.push(resolve)
        }),
    )
    const { data, api } = mountAutoSave(onSave)

    const first = api.save()
    data.value = 'v2'
    void api.save() // saving 期间 → pendingSave
    expect(api.saving.value).toBe(true)

    resolvers[0]()
    await first
    await flushPromises()

    expect(resolvers).toHaveLength(2)
    resolvers[1]()
    await flushPromises()

    expect(onSave).toHaveBeenCalledTimes(2)
    expect(onSave.mock.calls[1][0]).toBe('v2')
    expect(api.dirty.value).toBe(false)
  })
})

describe('useAutoSave：失败与卸载', () => {
  it('保存失败时记录 error、不写 lastSaved，且不谎报成功', async () => {
    const onSave = vi.fn(async () => {
      throw new Error('network down')
    })
    const { api } = mountAutoSave(onSave)

    await api.save()

    expect(api.error.value?.message).toBe('network down')
    expect(api.lastSaved.value).toBeNull()
    expect(api.saving.value).toBe(false)
  })

  it('组件卸载时若有未保存数据，兜底提交一次且不重复', async () => {
    vi.useFakeTimers()
    const onSave = vi.fn(async () => undefined)
    const { wrapper, data, api } = mountAutoSave(onSave)

    api.scheduleSave()
    data.value = 'v2'
    wrapper.unmount()
    await flushPromises()

    expect(onSave).toHaveBeenCalledTimes(1)
    expect(onSave).toHaveBeenCalledWith('v2')

    // 卸载时已清理防抖定时器，推进时间不应再触发第二次保存
    await vi.advanceTimersByTimeAsync(2000)
    expect(onSave).toHaveBeenCalledTimes(1)
  })
})
