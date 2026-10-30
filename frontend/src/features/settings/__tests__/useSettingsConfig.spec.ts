// ============================================================
// useSettingsConfig —— 设置页用户配置 / AI 配置 / 通知设置 单元测试
//
// 该 composable 依赖组件生命周期（onBeforeUnmount 清理两个防抖定时器），
// 因此 mount 一个最小宿主组件承载；领域 api 与 toast 全部 mock。
// 覆盖：加载/保存的成功与失败、昵称防抖（800ms）、API Key 验证的
// 空值/无效/成功/异常、通知设置读取与 300ms 连点合并、卸载清理。
// ============================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { mount } from '@vue/test-utils'

import { authApi } from '@/features/auth'
import { settingsApi } from '../api'
import { useSettingsConfig } from '../composables/useSettingsConfig'
import type { UserConfig } from '@/shared/types/user'

vi.mock('@/features/auth', () => ({
  authApi: { me: vi.fn(), update: vi.fn(), verifyApiKey: vi.fn(), init: vi.fn() },
}))
vi.mock('../api', () => ({
  settingsApi: { list: vi.fn(), update: vi.fn(), updateNotify: vi.fn(), readNotify: vi.fn() },
}))

const toastMock = vi.hoisted(() => ({
  error: vi.fn(),
  success: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
}))
vi.mock('@/kernel/ui/toast', () => ({ toast: toastMock, useToast: () => toastMock }))

type AnyMock = ReturnType<typeof vi.fn>
const auth = authApi as unknown as {
  me: AnyMock
  update: AnyMock
  verifyApiKey: AnyMock
  init: AnyMock
}
const settings = settingsApi as unknown as {
  list: AnyMock
  updateNotify: AnyMock
  readNotify: AnyMock
}
const toastError = toastMock.error
const toastSuccess = toastMock.success
const toastWarning = toastMock.warning

type Api = ReturnType<typeof useSettingsConfig>

function makeConfig(patch: Partial<UserConfig> = {}): UserConfig {
  return {
    nickname: '旅人',
    api_key_configured: false,
    ...patch,
  } as UserConfig
}

let wrapper: ReturnType<typeof mount> | undefined
function setup(): Api {
  const state: { api?: Api } = {}
  wrapper = mount(
    defineComponent({
      setup() {
        state.api = useSettingsConfig()
        return () => h('div')
      },
    }),
  )
  if (!state.api) throw new Error('useSettingsConfig 未在 setup 中初始化')
  return state.api
}

async function flushAll() {
  await Promise.resolve()
  await Promise.resolve()
  await Promise.resolve()
  await nextTick()
}

beforeEach(() => {
  vi.clearAllMocks()
  auth.me.mockResolvedValue(makeConfig())
  auth.update.mockImplementation((patch: Partial<UserConfig>) =>
    Promise.resolve(makeConfig({ ...patch })),
  )
  auth.verifyApiKey.mockResolvedValue({ valid: true, model: 'deepseek-chat' })
  auth.init.mockResolvedValue(makeConfig())
  settings.list.mockResolvedValue({ values: {} })
  settings.updateNotify.mockResolvedValue({ values: {} })
  settings.readNotify.mockImplementation(
    (values: Record<string, string | undefined>): Record<string, boolean> => ({
      task: values.task !== 'false',
      review: values.review !== 'false',
      system: values.system !== 'false',
      sound: values.sound === 'true',
    }),
  )
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  vi.useRealTimers()
})

describe('useSettingsConfig：加载配置', () => {
  it('loadConfig 成功：写入 userConfig、同步昵称草稿、loading 复位', async () => {
    auth.me.mockResolvedValueOnce(makeConfig({ nickname: '小明' }))
    const api = setup()

    const pending = api.loadConfig()
    expect(api.loading.value).toBe(true)
    await pending

    expect(api.userConfig.value).toEqual(makeConfig({ nickname: '小明' }))
    expect(api.nicknameDraft.value).toBe('小明')
    expect(api.loading.value).toBe(false)
  })

  it('loadConfig 失败：只记日志，不抛错、loading 复位、保留原配置', async () => {
    const api = setup()
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    auth.me.mockRejectedValueOnce(new Error('me down'))

    await api.loadConfig()

    expect(errorSpy).toHaveBeenCalled()
    expect(api.userConfig.value).toBeNull()
    expect(api.loading.value).toBe(false)
  })
})

describe('useSettingsConfig：保存配置', () => {
  it('saveConfig 成功：回填返回值并 toast 已保存', async () => {
    const api = setup()
    const pending = api.saveConfig({ nickname: '新名字' })
    expect(api.saving.value).toBe(true)
    await pending

    expect(auth.update).toHaveBeenCalledWith({ nickname: '新名字' })
    expect(api.userConfig.value?.nickname).toBe('新名字')
    expect(toastSuccess).toHaveBeenCalledWith('已保存')
    expect(api.saving.value).toBe(false)
  })

  it('saveConfig 失败：toast 报错且不覆盖已有配置', async () => {
    const api = setup()
    api.userConfig.value = makeConfig({ nickname: '旧名字' })
    auth.update.mockRejectedValueOnce(new Error('patch down'))

    await api.saveConfig({ nickname: '新名字' })

    expect(toastError).toHaveBeenCalledWith('保存失败', 'Error: patch down')
    expect(api.userConfig.value?.nickname).toBe('旧名字')
    expect(api.saving.value).toBe(false)
  })

  it('昵称防抖：停止输入 800ms 后才提交，提交的是 trim 后的值', async () => {
    vi.useFakeTimers()
    const api = setup()
    await api.loadConfig()

    api.nicknameDraft.value = '  新昵称  '
    await nextTick()
    await vi.advanceTimersByTimeAsync(799)
    expect(auth.update).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1)
    await flushAll()

    expect(auth.update).toHaveBeenCalledTimes(1)
    expect(auth.update).toHaveBeenCalledWith({ nickname: '新昵称' })
  })

  it('昵称防抖：空白/与原昵称相同的值不提交', async () => {
    vi.useFakeTimers()
    const api = setup()
    await api.loadConfig()

    api.nicknameDraft.value = '   '
    await nextTick()
    await vi.advanceTimersByTimeAsync(800)
    await flushAll()
    expect(auth.update).not.toHaveBeenCalled()

    api.nicknameDraft.value = '旅人' // 与当前配置相同
    await nextTick()
    await vi.advanceTimersByTimeAsync(800)
    await flushAll()
    expect(auth.update).not.toHaveBeenCalled()
  })

  it('昵称连续输入只提交最后一次（清掉前一个定时器）', async () => {
    vi.useFakeTimers()
    const api = setup()
    await api.loadConfig()

    api.nicknameDraft.value = '甲'
    await nextTick()
    await vi.advanceTimersByTimeAsync(500)
    api.nicknameDraft.value = '甲乙'
    await nextTick()
    await vi.advanceTimersByTimeAsync(800)
    await flushAll()

    expect(auth.update).toHaveBeenCalledTimes(1)
    expect(auth.update).toHaveBeenCalledWith({ nickname: '甲乙' })
  })

  it('卸载时清理昵称防抖定时器：不再提交', async () => {
    vi.useFakeTimers()
    const api = setup()
    await api.loadConfig()

    api.nicknameDraft.value = '卸载前输入'
    await nextTick()
    wrapper?.unmount()
    wrapper = undefined

    await vi.advanceTimersByTimeAsync(1000)
    expect(auth.update).not.toHaveBeenCalled()
  })
})

describe('useSettingsConfig：API Key 验证', () => {
  it('空 Key 直接 warning，不发请求', async () => {
    const api = setup()
    api.apiKey.value = '   '

    await api.verifyApiKey()

    expect(toastWarning).toHaveBeenCalledWith('请输入 API Key')
    expect(auth.verifyApiKey).not.toHaveBeenCalled()
  })

  it('验证成功：记录模型、init 保存并重新加载配置', async () => {
    const api = setup()
    api.apiKey.value = '  sk-1  '

    await api.verifyApiKey()

    expect(auth.verifyApiKey).toHaveBeenCalledWith('sk-1')
    expect(api.verifyResult.value).toEqual({ valid: true, model: 'deepseek-chat' })
    expect(toastSuccess).toHaveBeenCalledWith('验证成功', '模型: deepseek-chat')
    expect(auth.init).toHaveBeenCalledWith({ nickname: '旅人', api_key: 'sk-1' })
    expect(auth.me).toHaveBeenCalledTimes(1) // 验证后重新 loadConfig
    expect(api.verifying.value).toBe(false)
  })

  it('验证失败（valid=false）：toast 报错且不 init', async () => {
    const api = setup()
    auth.verifyApiKey.mockResolvedValueOnce({ valid: false, model: '' })
    api.apiKey.value = 'sk-bad'

    await api.verifyApiKey()

    expect(toastError).toHaveBeenCalledWith('验证失败', 'API Key 无效')
    expect(auth.init).not.toHaveBeenCalled()
    expect(api.verifying.value).toBe(false)
  })

  it('验证请求异常：toast 报错并复位 verifying', async () => {
    const api = setup()
    auth.verifyApiKey.mockRejectedValueOnce(new Error('timeout'))
    api.apiKey.value = 'sk-x'

    await api.verifyApiKey()

    expect(toastError).toHaveBeenCalledWith('验证失败', 'Error: timeout')
    expect(api.verifying.value).toBe(false)
  })
})

describe('useSettingsConfig：通知设置（连点合并）', () => {
  it('loadNotifySettings 成功：四个开关按后端值回填', async () => {
    settings.list.mockResolvedValueOnce({
      values: { task: 'false', review: 'true', system: 'false', sound: 'true' },
    } as never)
    const api = setup()

    await api.loadNotifySettings()

    expect(api.notifyTask.value).toBe(false)
    expect(api.notifyReview.value).toBe(true)
    expect(api.notifySystem.value).toBe(false)
    expect(api.notifySound.value).toBe(true)
  })

  it('loadNotifySettings 失败：记日志并保持默认值', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    settings.list.mockRejectedValueOnce(new Error('settings down'))
    const api = setup()

    await api.loadNotifySettings()

    expect(errorSpy).toHaveBeenCalled()
    expect(api.notifyTask.value).toBe(true)
    expect(api.notifyReview.value).toBe(true)
    expect(api.notifySystem.value).toBe(true)
    expect(api.notifySound.value).toBe(false)
  })

  it('300ms 内连续切换只发一次 PUT，并用最新四个值', async () => {
    vi.useFakeTimers()
    const api = setup()

    api.notifyTask.value = false
    api.saveNotifySettings()
    await vi.advanceTimersByTimeAsync(100)
    api.notifySound.value = true
    api.saveNotifySettings()

    await vi.advanceTimersByTimeAsync(300)
    await flushAll()

    expect(settings.updateNotify).toHaveBeenCalledTimes(1)
    expect(settings.updateNotify).toHaveBeenCalledWith({
      task: false,
      review: true,
      system: true,
      sound: true,
    })
    expect(api.notifySaving.value).toBe(false)
  })

  it('保存通知设置失败：toast 报错并复位 notifySaving', async () => {
    vi.useFakeTimers()
    settings.updateNotify.mockRejectedValueOnce(new Error('put down'))
    const api = setup()

    api.saveNotifySettings()
    await vi.advanceTimersByTimeAsync(300)
    await flushAll()

    expect(toastError).toHaveBeenCalledWith('通知设置保存失败', 'Error: put down')
    expect(api.notifySaving.value).toBe(false)
  })

  it('卸载时清理通知防抖定时器：不再发请求', async () => {
    vi.useFakeTimers()
    const api = setup()

    api.saveNotifySettings()
    wrapper?.unmount()
    wrapper = undefined

    await vi.advanceTimersByTimeAsync(600)
    expect(settings.updateNotify).not.toHaveBeenCalled()
  })
})
