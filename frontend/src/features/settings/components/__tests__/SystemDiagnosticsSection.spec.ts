// ============================================================
// SystemDiagnosticsSection —— 设置页「系统与诊断」交互组件测试
//
// 组件本身无状态：所有诊断数据经 props 传入、所有操作经 emit 上抛。
// 这里用 mount + setProps 覆盖三态（未加载/成功/失败）、折叠展开、
// 事件详情与清空、规则预览、插件开关等有分支的交互。
// ============================================================
import { afterEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import BaseSwitch from '@/shared/components/common/BaseSwitch.vue'
import type { EncryptionStatus, LogFile, PluginItem } from '@/features/system'
import SystemDiagnosticsSection from '../SystemDiagnosticsSection.vue'

type DiagProps = InstanceType<typeof SystemDiagnosticsSection>['$props']

function baseProps(patch: Partial<DiagProps> = {}): DiagProps {
  return {
    encryption: null,
    logFiles: [],
    logContent: '',
    activeLog: '',
    eventStats: [],
    activeEvent: '',
    eventTimeline: [],
    failedHandlerSummary: '',
    plugins: [],
    showSecurity: false,
    showLogs: false,
    showEvents: false,
    showRules: false,
    showPlugins: false,
    ruleText: '',
    ruleDomains: { builtin: 0, user: 0 },
    rulePreview: null,
    ...patch,
  } as DiagProps
}

const wrappers: Array<{ unmount: () => void }> = []
function mountSection(patch: Partial<DiagProps> = {}) {
  const wrapper = mount(SystemDiagnosticsSection, { props: baseProps(patch) })
  wrappers.push(wrapper)
  return wrapper
}

function linkButton(wrapper: ReturnType<typeof mountSection>, text: string) {
  const found = wrapper.findAll('button.settings__link-btn').find((b) => b.text().includes(text))
  if (!found) throw new Error(`未找到折叠按钮：${text}`)
  return found
}
function buttonByText(wrapper: ReturnType<typeof mountSection>, text: string) {
  const found = wrapper.findAll('button').find((b) => b.text().includes(text))
  if (!found) throw new Error(`未找到按钮：${text}`)
  return found
}

const encryption = (available: boolean): EncryptionStatus =>
  ({ available, algorithm: 'fernet' }) as unknown as EncryptionStatus
const logFile = (patch: Partial<LogFile> = {}): LogFile =>
  ({ name: 'app.log', size_kb: 12, ...patch }) as unknown as LogFile
const plugin = (patch: Partial<PluginItem> = {}): PluginItem =>
  ({ id: 'p1', name: '插件', version: '1.0.0', enabled: false, ...patch }) as unknown as PluginItem

afterEach(() => {
  wrappers.splice(0).forEach((w) => w.unmount())
})

describe('SystemDiagnosticsSection：加密存储三态', () => {
  it('未加载（encryption=null）时不渲染状态行，但仍可轮换密钥', async () => {
    const wrapper = mountSection({ showSecurity: true, encryption: null })

    expect(wrapper.text()).not.toContain('状态：')
    await buttonByText(wrapper, '轮换密钥').trigger('click')
    expect(wrapper.emitted('rotate-key')).toHaveLength(1)
  })

  it('成功/失败两态：available 决定「已启用 / 不可用」', async () => {
    const wrapper = mountSection({ showSecurity: true, encryption: encryption(true) })
    expect(wrapper.text()).toContain('已启用')

    await wrapper.setProps({ encryption: encryption(false) })
    expect(wrapper.text()).toContain('不可用')
  })

  it('折叠按钮 emit toggle-security，展开态显示内容', async () => {
    const wrapper = mountSection()
    expect(wrapper.find('.settings__diag').exists()).toBe(false)

    await linkButton(wrapper, '加密存储').trigger('click')
    expect(wrapper.emitted('toggle-security')).toHaveLength(1)
  })
})

describe('SystemDiagnosticsSection：系统日志', () => {
  it('折叠：收起不渲染操作区，展开且无文件时给出空态', async () => {
    const wrapper = mountSection()
    expect(wrapper.text()).not.toContain('刷新列表')

    await linkButton(wrapper, '系统日志').trigger('click')
    expect(wrapper.emitted('toggle-logs')).toHaveLength(1)

    await wrapper.setProps({ showLogs: true })
    expect(wrapper.text()).toContain('暂无日志文件')
  })

  it('有文件时渲染名称/大小、标记选中项、展示日志内容', () => {
    const wrapper = mountSection({
      showLogs: true,
      logFiles: [logFile(), logFile({ name: 'error.log', size_kb: 3 })],
      activeLog: 'error.log',
      logContent: 'ERROR boom',
    })

    expect(wrapper.text()).toContain('app.log')
    expect(wrapper.text()).toContain('error.log')
    const items = wrapper.findAll('button.settings__log-item')
    expect(items).toHaveLength(2)
    expect(items[1].classes()).toContain('is-active')
    expect(wrapper.find('pre.settings__log-content').text()).toContain('ERROR boom')
  })

  it('点击日志条目 emit view-log；刷新/清空按钮 emit 对应事件', async () => {
    const wrapper = mountSection({ showLogs: true, logFiles: [logFile()] })

    await wrapper.findAll('button.settings__log-item')[0].trigger('click')
    expect(wrapper.emitted('view-log')).toEqual([['app.log']])

    await buttonByText(wrapper, '刷新列表').trigger('click')
    await buttonByText(wrapper, '清空日志').trigger('click')
    expect(wrapper.emitted('refresh-logs')).toHaveLength(1)
    expect(wrapper.emitted('clear-logs')).toHaveLength(1)
  })
})

describe('SystemDiagnosticsSection：事件总线', () => {
  it('空态：显示"暂无事件记录（系统刚启动）"', () => {
    const wrapper = mountSection({ showEvents: true })

    expect(wrapper.text()).toContain('暂无事件记录（系统刚启动）')
    expect(wrapper.text()).not.toContain('清空历史')
  })

  it('列表：渲染次数/失败角标/告警样式，点击行 emit toggle-event-detail', async () => {
    const wrapper = mountSection({
      showEvents: true,
      eventStats: [
        { name: 'task.created', count: 8, failed: 0, failedHandlers: [], alert: false },
        { name: 'ai.error', count: 3, failed: 6, failedHandlers: ['h1'], alert: true },
      ],
      failedHandlerSummary: 'h1',
    })

    const rows = wrapper.findAll('.settings__event-row')
    expect(rows).toHaveLength(2)
    expect(rows[1].classes()).toContain('is-alert')
    expect(rows[1].text()).toContain('失败 6')
    expect(wrapper.text()).toContain('失败 handler：h1')

    await rows[1].trigger('click')
    expect(wrapper.emitted('toggle-event-detail')).toEqual([['ai.error']])
  })

  it('展开详情：时间线渲染成功/失败，清空历史 emit clear-events', async () => {
    const wrapper = mountSection({
      showEvents: true,
      eventStats: [{ name: 'ai.error', count: 3, failed: 6, failedHandlers: [], alert: true }],
      activeEvent: 'ai.error',
      eventTimeline: [
        { time: '10:00:00', success: true },
        { time: '10:01:00', success: false, failed_handlers: ['h1', 'h2'] },
      ],
    })

    const timeline = wrapper.findAll('.settings__event-timeline li')
    expect(timeline).toHaveLength(2)
    expect(timeline[0].text()).toContain('成功')
    expect(timeline[1].text()).toContain('失败（h1, h2）')

    await buttonByText(wrapper, '清空历史').trigger('click')
    expect(wrapper.emitted('clear-events')).toHaveLength(1)
  })
})

describe('SystemDiagnosticsSection：规则引擎', () => {
  it('展示领域库数量；输入与热重载分别 emit', async () => {
    const wrapper = mountSection({ showRules: true, ruleDomains: { builtin: 13, user: 2 } })

    expect(wrapper.text()).toContain('内置 13 个')
    expect(wrapper.text()).toContain('用户扩展 2 个')

    await wrapper.find('input[placeholder^="例如"]').setValue('我想学雅思')
    expect(wrapper.emitted('change-rule-text')).toEqual([['我想学雅思']])

    await buttonByText(wrapper, '热重载').trigger('click')
    expect(wrapper.emitted('reload-domains')).toHaveLength(1)
  })

  it('规则预览三态：无预览不渲染 → 命中 → 未命中回退', async () => {
    const wrapper = mountSection({ showRules: true })
    expect(wrapper.find('.settings__rule-preview').exists()).toBe(false)

    await wrapper.setProps({
      rulePreview: {
        matched: true,
        domain_name: '雅思',
        plans: [{ unit: '听力', task: '精听', duration: '30 分钟' }],
      },
    })
    expect(wrapper.text()).toContain('命中：雅思')
    expect(wrapper.text()).toContain('精听')

    await wrapper.setProps({
      rulePreview: { matched: false, domain_name: null, plans: [] },
    })
    expect(wrapper.text()).toContain('未命中领域库，使用通用拆解')
    expect(wrapper.text()).toContain('计划生成失败或为空')
  })
})

describe('SystemDiagnosticsSection：插件', () => {
  it('空态与扫描按钮', async () => {
    const wrapper = mountSection({ showPlugins: true })

    expect(wrapper.text()).toContain('暂无插件')

    await buttonByText(wrapper, '扫描插件').trigger('click')
    expect(wrapper.emitted('discover-plugins')).toHaveLength(1)
  })

  it('插件列表：渲染名称版本，开关 emit toggle-plugin（带插件对象）', async () => {
    const p = plugin({ enabled: true })
    const wrapper = mountSection({ showPlugins: true, plugins: [p] })

    expect(wrapper.text()).toContain('插件 v1.0.0')
    expect(wrapper.findAllComponents(BaseSwitch)[0].props('modelValue')).toBe(true)

    await wrapper.findAllComponents(BaseSwitch)[0].find('button').trigger('click')
    expect(wrapper.emitted('toggle-plugin')).toEqual([[p]])
  })
})

describe('SystemDiagnosticsSection：折叠开关', () => {
  it('5 个折叠按钮分别 emit toggle-*', async () => {
    const wrapper = mountSection()

    for (const label of ['加密存储', '系统日志', '事件总线', '规则引擎', '插件']) {
      await linkButton(wrapper, label).trigger('click')
    }

    expect(wrapper.emitted('toggle-security')).toHaveLength(1)
    expect(wrapper.emitted('toggle-logs')).toHaveLength(1)
    expect(wrapper.emitted('toggle-events')).toHaveLength(1)
    expect(wrapper.emitted('toggle-rules')).toHaveLength(1)
    expect(wrapper.emitted('toggle-plugins')).toHaveLength(1)
  })
})
