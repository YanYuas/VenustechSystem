// ============================================================
// 人生报告单文件 HTML 生成器 —— 单元测试（前端首个 vitest 套件）
//
// 为什么优先测它：
//   1. 它是 S6-5 的**唯一交付物**（报告归用户所有、要能带走），
//      坏掉的后果是「用户下载了一份打不开/内容错的 HTML」，后端测试完全看不到
//   2. 纯函数 + 明确契约（内联样式 / 零外部依赖 / 零脚本），最适合先立样板
//   3. 大量字符串拼接 —— 一旦漏了转义就是 XSS，而 vue-tsc 查不出来
// ============================================================
import { describe, expect, it, vi } from 'vitest'

import { buildReportHtml, downloadReport } from '../reportHtml'
import type { ReportData } from '../model'

/** 造一份最小可用报告（在测试里按需覆盖字段） */
function makeReport(over: Partial<ReportData> = {}): ReportData {
  return {
    generated_at: '2026-10-11T17:10:09.123456',
    nickname: '衍煜',
    identity_axis: {
      identities: [],
      unassigned: { tasks_open: 0, documents: 0, diaries: 0, reviews: 0, memories: 0 },
    },
    growth_axis: {
      level: 3,
      exp: 250,
      percent: 42,
      skills: [],
      tasks_completed_total: 7,
      diaries_total: 5,
      reviews_total: 2,
    },
    archive_axis: {
      workspace_enabled: false,
      roots: [],
      documents_total: 12,
      sops_total: 1,
      prompts_total: 2,
      skills_total: 3,
      project_memories_total: 4,
      avatar_memories_total: 5,
    },
    recent_experience: [],
    ...over,
  }
}

function makeIdentity(over: Partial<ReportData['identity_axis']['identities'][number]> = {}) {
  return {
    id: 'i1',
    name: '研究生',
    slug: 'grad',
    color_token: 'lilac',
    icon: 'book',
    is_archived: false,
    tasks_open: 2,
    tasks_completed: 3,
    documents: 4,
    diaries: 5,
    reviews: 6,
    memories: 7,
    ...over,
  }
}

// ============================================================
// 第 1 组：交付物不变量（内联 / 零外部依赖 / 零脚本）
// ============================================================
describe('第1组：单文件交付物的硬契约', () => {
  it('产出完整的 HTML 文档骨架', () => {
    const html = buildReportHtml(makeReport())

    expect(html.startsWith('<!DOCTYPE html>')).toBe(true)
    expect(html).toContain('<html lang="zh-CN">')
    expect(html).toContain('</html>')
    expect(html).toContain('<meta charset="UTF-8">')
  })

  it('零外部依赖：不出现任何 http(s) 外链（断网也能打开）', () => {
    const html = buildReportHtml(
      makeReport({
        identity_axis: {
          identities: [makeIdentity()],
          unassigned: { tasks_open: 1, documents: 1, diaries: 1, reviews: 1, memories: 1 },
        },
        archive_axis: {
          ...makeReport().archive_axis,
          workspace_enabled: true,
          roots: [{ path: 'D:/YanYuas', label: '主工作区', file_count: 3, total_size: 2048 }],
        },
      }),
    )

    expect(html).not.toMatch(/https?:\/\//)
    expect(html).not.toContain('<link')
    expect(html).not.toContain('@import')
  })

  it('零脚本：整份报告里没有 <script>（数据主权 + 离线安全）', () => {
    const html = buildReportHtml(makeReport({ nickname: '衍煜' }))
    expect(html.toLowerCase()).not.toContain('<script')
  })

  it('样式全部内联在 <style> 里（不依赖应用主题，导出物脱离运行时）', () => {
    const html = buildReportHtml(makeReport())
    expect(html).toContain('<style>')
    expect(html).toContain('</style>')
  })
})

// ============================================================
// 第 2 组：转义（XSS 防线）
// ============================================================
describe('第2组：用户数据必须转义', () => {
  it('昵称里的 HTML 被转义，不产生可执行标签', () => {
    const html = buildReportHtml(makeReport({ nickname: '<script>alert(1)</script>' }))

    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')
    expect(html.toLowerCase()).not.toContain('<script')
  })

  it('身份名 / 技能名 / 经历标题 / 工作区路径都会转义', () => {
    const html = buildReportHtml(
      makeReport({
        identity_axis: {
          identities: [makeIdentity({ name: '<b>研究生</b>' })],
          unassigned: { tasks_open: 0, documents: 0, diaries: 0, reviews: 0, memories: 0 },
        },
        growth_axis: {
          ...makeReport().growth_axis,
          skills: [{ name: '<img src=x onerror=1>', count: 3 }],
        },
        archive_axis: {
          ...makeReport().archive_axis,
          workspace_enabled: true,
          roots: [{ path: '<svg/onload=1>', label: null, file_count: 1, total_size: 10 }],
        },
        recent_experience: [
          {
            source: 'diary',
            source_label: '<i>日记</i>',
            title: '<u>标题</u>',
            identity_name: '<em>身份</em>',
            occurred_at: '2026-10-01T09:00:00',
          },
        ],
      }),
    )

    expect(html).not.toContain('<b>研究生</b>')
    expect(html).toContain('&lt;b&gt;研究生&lt;/b&gt;')
    expect(html).not.toContain('<img src=x')
    expect(html).toContain('&lt;img src=x onerror=1&gt;')
    expect(html).not.toContain('<svg/onload=1>')
    expect(html).not.toContain('<i>日记</i>')
    expect(html).not.toContain('<u>标题</u>')
    expect(html).not.toContain('<em>身份</em>')
  })

  it('双引号被转义（属性值用双引号包裹，漏转义即可逃逸出属性）', () => {
    const html = buildReportHtml(makeReport({ nickname: '" onmouseover="alert(1)' }))
    expect(html).toContain('&quot;')
    expect(html).not.toContain('" onmouseover="')
  })

  it('空值不炸：name / skill name 为 null 时渲染空串', () => {
    const html = buildReportHtml(
      makeReport({
        identity_axis: {
          // 后端契约保证非 null，这里模拟脏数据，确认 esc 的兜底分支生效
          identities: [makeIdentity({ name: null as unknown as string })],
          unassigned: { tasks_open: 0, documents: 0, diaries: 0, reviews: 0, memories: 0 },
        },
      }),
    )
    expect(html).toContain('<b></b>')
  })
})

// ============================================================
// 第 3 组：各轴渲染
// ============================================================
describe('第3组：三轴与近期经历渲染', () => {
  it('渲染等级 / 经验 / 升级进度与三个总量', () => {
    const html = buildReportHtml(makeReport())
    expect(html).toContain('LV3')
    expect(html).toContain('250 EXP')
    expect(html).toContain('升级进度 42%')
    expect(html).toContain('完成 7 个任务 · 日记 5 篇 · 复盘 2 次')
  })

  it('身份卡片带六项计数与身份名', () => {
    const html = buildReportHtml(
      makeReport({
        identity_axis: {
          identities: [makeIdentity()],
          unassigned: { tasks_open: 0, documents: 0, diaries: 0, reviews: 0, memories: 0 },
        },
      }),
    )
    for (const s of ['待办 2', '完成 3', '文档 4', '日记 5', '复盘 6', '记忆 7']) {
      expect(html).toContain(s)
    }
    expect(html).toContain('<b>研究生</b>')
  })

  it('归档身份标「已归档」，未归档不标', () => {
    const archived = buildReportHtml(
      makeReport({
        identity_axis: {
          identities: [makeIdentity({ is_archived: true })],
          unassigned: { tasks_open: 0, documents: 0, diaries: 0, reviews: 0, memories: 0 },
        },
      }),
    )
    const active = buildReportHtml(
      makeReport({
        identity_axis: {
          identities: [makeIdentity({ is_archived: false })],
          unassigned: { tasks_open: 0, documents: 0, diaries: 0, reviews: 0, memories: 0 },
        },
      }),
    )

    expect(archived).toContain('<span class="archived">已归档</span>')
    expect(active).not.toContain('class="archived"')
  })

  it('没有任何身份时给出引导文案', () => {
    const html = buildReportHtml(makeReport())
    expect(html).toContain('还没有建立身份')
  })

  it('未归类数字逐项渲染（不是只显示第一项）', () => {
    const html = buildReportHtml(
      makeReport({
        identity_axis: {
          identities: [],
          unassigned: { tasks_open: 1, documents: 2, diaries: 3, reviews: 4, memories: 5 },
        },
      }),
    )
    expect(html).toContain('另有未归类：待办 1 · 文档 2 · 日记 3 · 复盘 4 · 记忆 5')
  })

  it('颜色 token 映射到报告固化色板；未知 token 回落主色', () => {
    const known = buildReportHtml(
      makeReport({
        identity_axis: {
          identities: [makeIdentity({ color_token: 'mint' })],
          unassigned: { tasks_open: 0, documents: 0, diaries: 0, reviews: 0, memories: 0 },
        },
      }),
    )
    const unknown = buildReportHtml(
      makeReport({
        identity_axis: {
          identities: [makeIdentity({ color_token: 'not-a-token' })],
          unassigned: { tasks_open: 0, documents: 0, diaries: 0, reviews: 0, memories: 0 },
        },
      }),
    )

    expect(known).toContain('background:#7BD3B2')
    expect(unknown).toContain('background:#FF8FA3')
  })
})

// ============================================================
// 第 4 组：成长轴（技能条与空态）
// ============================================================
describe('第4组：成长轴技能条', () => {
  it('无技能时给引导文案，而不是空面板', () => {
    const html = buildReportHtml(makeReport())
    expect(html).toContain('还没有点亮技能')
    expect(html).not.toContain('class="skill"')
  })

  it('技能条宽度按最高分归一：最高项 100%，其余按比例', () => {
    const html = buildReportHtml(
      makeReport({
        growth_axis: {
          ...makeReport().growth_axis,
          skills: [
            { name: 'A', count: 6 },
            { name: 'B', count: 3 },
          ],
        },
      }),
    )

    expect(html).toContain('style="width:100%"')
    expect(html).toContain('style="width:50%"')
    expect(html).toContain('<em>6</em>')
    expect(html).toContain('<em>3</em>')
  })

  it('只有一项技能时也能归一（不会除以 0 变 NaN）', () => {
    const html = buildReportHtml(
      makeReport({
        growth_axis: { ...makeReport().growth_axis, skills: [{ name: 'A', count: 1 }] },
      }),
    )
    expect(html).toContain('style="width:100%"')
    expect(html).not.toContain('NaN')
  })

  it('计数极大时宽度全部落在 0-100% 之间（不溢出面板）', () => {
    const html = buildReportHtml(
      makeReport({
        growth_axis: {
          ...makeReport().growth_axis,
          skills: [
            { name: 'A', count: 100 },
            { name: 'B', count: 1 },
          ],
        },
      }),
    )

    const widths = [...html.matchAll(/width:([\d.]+)%/g)].map((m) => Number(m[1]))
    expect(widths.length).toBe(2)
    expect(Math.max(...widths)).toBe(100)
    expect(Math.min(...widths)).toBe(1)
    expect(widths.every((w) => w >= 0 && w <= 100)).toBe(true)
  })
})

// ============================================================
// 第 5 组：档案轴（工作区开关 + 体积格式化）
// ============================================================
describe('第5组：档案轴与文件体积格式化', () => {
  it('资产总量渲染在档案轴卡片里', () => {
    const html = buildReportHtml(makeReport())
    expect(html).toContain('SOP 1 · 提示词 2 · 技能 3 · 项目记忆 4 · 分身记忆 5')
    expect(html).toContain('>12<')
  })

  it('工作区关闭时不渲染「工作区索引」区块（即使有根数据）', () => {
    const html = buildReportHtml(
      makeReport({
        archive_axis: {
          ...makeReport().archive_axis,
          workspace_enabled: false,
          roots: [{ path: 'D:/ShouldNotAppear', label: null, file_count: 1, total_size: 1 }],
        },
      }),
    )
    expect(html).not.toContain('工作区索引')
    expect(html).not.toContain('ShouldNotAppear')
  })

  it('工作区开启且有根时渲染路径与元数据', () => {
    const html = buildReportHtml(
      makeReport({
        archive_axis: {
          ...makeReport().archive_axis,
          workspace_enabled: true,
          roots: [{ path: 'D:/YanYuas', label: '主工作区', file_count: 7, total_size: 2048 }],
        },
      }),
    )
    expect(html).toContain('工作区索引')
    expect(html).toContain('D:/YanYuas')
    expect(html).toContain('7 项 · 2.0 KB')
  })

  it('工作区开启但没有根时不渲染空区块', () => {
    const html = buildReportHtml(
      makeReport({
        archive_axis: { ...makeReport().archive_axis, workspace_enabled: true, roots: [] },
      }),
    )
    expect(html).not.toContain('工作区索引')
  })

  it('体积格式化覆盖 B / KB / MB 三档边界', () => {
    const render = (total_size: number) =>
      buildReportHtml(
        makeReport({
          archive_axis: {
            ...makeReport().archive_axis,
            workspace_enabled: true,
            roots: [{ path: 'D:/x', label: null, file_count: 1, total_size }],
          },
        }),
      )

    expect(render(0)).toContain('0 B')
    expect(render(1023)).toContain('1023 B') // 刚好不到 1 KB
    expect(render(1024)).toContain('1.0 KB') // 边界：1024 → KB
    expect(render(1536)).toContain('1.5 KB')
    expect(render(1024 * 1024 - 1)).toContain('1024.0 KB') // 边界：差 1 字节仍是 KB
    expect(render(1024 * 1024)).toContain('1.0 MB') // 边界：1024² → MB
    expect(render(3.5 * 1024 * 1024)).toContain('3.5 MB')
  })
})

// ============================================================
// 第 6 组：近期经历与时间格式
// ============================================================
describe('第6组：近期经历', () => {
  it('无经历时给引导文案', () => {
    expect(buildReportHtml(makeReport())).toContain('近期还没有经历记录')
  })

  it('每条经历渲染来源标签 / 标题 / 身份名 / 日期', () => {
    const html = buildReportHtml(
      makeReport({
        recent_experience: [
          {
            source: 'project_memory',
            source_label: '项目记忆',
            title: '启明星三期',
            identity_name: '开发者',
            occurred_at: '2026-10-01T09:30:00',
          },
        ],
      }),
    )

    expect(html).toContain('项目记忆')
    expect(html).toContain('启明星三期')
    expect(html).toContain('· 开发者')
    expect(html).toContain('2026-10-01')
  })

  it('未归类经历不显示身份名（只留来源与日期）', () => {
    const html = buildReportHtml(
      makeReport({
        recent_experience: [
          {
            source: 'diary',
            source_label: '日记',
            title: '随手记',
            identity_name: null,
            occurred_at: '2026-10-02T08:00:00',
          },
        ],
      }),
    )

    expect(html).toContain('日记')
    expect(html).toContain('2026-10-02')
    // identity_name 为空 → 模板里 `· xxx` 整段消失，不留下孤立的「·」
    expect(html).toContain('<span class="muted"> · 2026-10-02</span>')
  })

  it('生成时间截到秒（毫秒不该出现在抬头）', () => {
    const html = buildReportHtml(makeReport({ generated_at: '2026-10-11T17:10:09.123456' }))
    expect(html).toContain('生成于 2026-10-11 17:10:09')
    expect(html).not.toContain('123456')
  })

  it('标题里的日期取生成日（不含时间）', () => {
    const html = buildReportHtml(makeReport({ generated_at: '2026-10-11T17:10:09.123456' }))
    expect(html).toContain('衍煜 的人生报告 · 2026-10-11')
  })
})

// ============================================================
// 第 7 组：下载行为
// ============================================================
describe('第7组：downloadReport', () => {
  it('构造 Blob 并以「人生报告-YYYY-MM-DD.html」触发下载', () => {
    const created: Blob[] = []
    const revoke = vi.fn()
    URL.createObjectURL = vi.fn((b: Blob) => {
      created.push(b)
      return 'blob:mock-url'
    })
    URL.revokeObjectURL = revoke

    let clicked: HTMLAnchorElement | null = null
    const realCreate = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation(((tag: string) => {
      const el = realCreate(tag)
      if (tag === 'a') {
        clicked = el as HTMLAnchorElement
        vi.spyOn(el as HTMLAnchorElement, 'click').mockImplementation(() => {})
      }
      return el
    }) as typeof document.createElement)

    downloadReport(makeReport({ generated_at: '2026-10-11T17:10:09' }))

    expect(created).toHaveLength(1)
    expect(created[0].type).toBe('text/html;charset=utf-8')
    expect(clicked).not.toBeNull()
    expect(clicked!.download).toBe('人生报告-2026-10-11.html')
    expect(clicked!.href).toContain('blob:mock-url')
    // 用完即释放，避免内存泄漏
    expect(revoke).toHaveBeenCalledWith('blob:mock-url')
  })
})
