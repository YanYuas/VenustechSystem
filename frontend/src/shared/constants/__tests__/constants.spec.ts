// ============================================================
// 应用常量 —— 单元测试
//
// 为什么值得测：这些常量是**跨模块的唯一真源**，但它们没有类型层面的
// 联动保护 —— `ThemePack` 类型加了新成员、`constants/index.ts` 忘了加，
// vue-tsc 完全不会报（因为没人用那个常量）。
// 本文件把那类「真源之间必须一致」的约束落成断言。
// ============================================================
import { describe, expect, it } from 'vitest'

import {
  APP, AUTOMATION_LEVELS, ROUTES, SHORTCUTS, STORAGE_KEYS,
  TASK_PRIORITY, TASK_STATUS, THEME_PACKS,
} from '@/shared/constants'

// ============================================================
// 第 1 组：主题包清单（与 ThemePack 类型 / useTheme / 设置页三方对齐）
// ============================================================
describe('第1组：THEME_PACKS', () => {
  it('必须覆盖 ThemePack 联合类型的全部 4 个成员', () => {
    // types/common.ts: export type ThemePack = 'cream' | 'guofeng' | 'abyss' | 'epic'
    // 同时 useTheme.ts 的 cyclePack 顺序与 SettingsView.vue 的主题选择器都是这 4 个。
    // 任何一处漏掉 → 主题选择器少一个选项，且不会有任何报错。
    const expected = ['cream', 'guofeng', 'abyss', 'epic']

    expect(THEME_PACKS.map((t) => t.id)).toEqual(expected)
  })

  it('每个主题包都有非空的中文名与描述', () => {
    for (const t of THEME_PACKS) {
      expect(t.id.length).toBeGreaterThan(0)
      expect(t.name.length).toBeGreaterThan(0)
      expect(t.desc.length).toBeGreaterThan(0)
    }
  })

  it('主题包 id 不重复', () => {
    const ids = THEME_PACKS.map((t) => t.id)
    expect(new Set(ids).size).toBe(ids.length)
  })
})

// ============================================================
// 第 2 组：任务状态 / 优先级映射
// ============================================================
describe('第2组：任务状态与优先级映射', () => {
  it('TASK_STATUS 覆盖后端状态机的 4 个合法状态', () => {
    // 后端 workflow_service 的状态集合：pending / in_progress / waiting / completed
    // （"todo" 是非法状态，曾导致任务永久卡死 —— 见 tests/ROADMAP 第一轮修复）
    expect(Object.keys(TASK_STATUS).sort()).toEqual(
      ['completed', 'in_progress', 'pending', 'waiting'],
    )
  })

  it('TASK_PRIORITY 覆盖 4 档优先级', () => {
    expect(Object.keys(TASK_PRIORITY).sort()).toEqual(
      ['high', 'low', 'medium', 'urgent'],
    )
  })

  it('每个状态/优先级都有中文标签与颜色 token', () => {
    for (const m of [TASK_STATUS, TASK_PRIORITY]) {
      for (const [key, v] of Object.entries(m)) {
        expect(v.label.length, `${key} 缺 label`).toBeGreaterThan(0)
        expect(v.color.length, `${key} 缺 color`).toBeGreaterThan(0)
      }
    }
  })

  it('颜色引用的是语义 token 名，而不是写死的色值', () => {
    // 设计令牌铁律：颜色只能引用 token。这里防的是有人往映射表里塞 #RRGGBB
    // （组件文件内的 `#` 由 frontend/scripts/audit-tokens.py 守着，但常量文件不在其扫描范围）
    for (const m of [TASK_STATUS, TASK_PRIORITY]) {
      for (const v of Object.values(m)) {
        expect(v.color).not.toMatch(/#[0-9a-fA-F]{3,8}/)
      }
    }
  })
})

// ============================================================
// 第 3 组：存储键 / 路由 / 其他常量
// ============================================================
describe('第3组：STORAGE_KEYS / ROUTES / 其他', () => {
  it('STORAGE_KEYS 的值全局唯一且带 qm-star- 前缀', () => {
    const values = Object.values(STORAGE_KEYS)

    expect(new Set(values).size).toBe(values.length)
    for (const v of values) expect(v.startsWith('qm-star-')).toBe(true)
  })

  it('ROUTES 全部是以 / 开头的绝对路径且互不重复', () => {
    const values = Object.values(ROUTES)

    expect(new Set(values).size).toBe(values.length)
    for (const v of values) expect(v.startsWith('/')).toBe(true)
  })

  it('AUTOMATION_LEVELS 恰好 5 档（L1-L5）且有标签描述', () => {
    expect(Object.keys(AUTOMATION_LEVELS)).toEqual(['L1', 'L2', 'L3', 'L4', 'L5'])
    for (const v of Object.values(AUTOMATION_LEVELS)) {
      expect(v.label.length).toBeGreaterThan(0)
      expect(v.desc.length).toBeGreaterThan(0)
    }
  })

  it('SHORTCUTS 都是非空字符串', () => {
    for (const v of Object.values(SHORTCUTS)) expect(v.length).toBeGreaterThan(0)
  })

  it('APP.version 由构建期 define 注入，不能是 undefined 字面量', () => {
    expect(typeof APP.version).toBe('string')
    expect(APP.version.length).toBeGreaterThan(0)
    expect(APP.version).not.toBe('undefined')
  })
})
