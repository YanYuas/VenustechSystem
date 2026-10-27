// ============================================================
// 设置页纯逻辑工具 —— 单元测试（不测 DOM）
// ============================================================
import { describe, expect, it } from 'vitest'
import {
  formatSyncSizeKb,
  isSettingsHotkey,
  matchesSettingsSearch,
  normalizeSearchQuery,
} from '../settingsUtils'

describe('normalizeSearchQuery', () => {
  it('去首尾空白并转小写', () => {
    expect(normalizeSearchQuery('  主题 ')).toBe('主题')
    expect(normalizeSearchQuery('  Theme ')).toBe('theme')
    expect(normalizeSearchQuery('   ')).toBe('')
  })
})

describe('matchesSettingsSearch', () => {
  const group = '主题包 奶油糖果 / 国风雅集'
  const card = '外观'

  it('空搜索词命中全部（不过滤）', () => {
    expect(matchesSettingsSearch(group, card, '')).toBe(true)
    expect(matchesSettingsSearch(group, card, '   ')).toBe(true)
  })

  it('组文本包含搜索词即命中，大小写不敏感', () => {
    expect(matchesSettingsSearch(group, card, '国风')).toBe(true)
    expect(matchesSettingsSearch('API Key 已配置', card, 'api')).toBe(true)
    expect(matchesSettingsSearch(group, card, '备份')).toBe(false)
  })

  it('组文本未命中但卡片标题命中时也算命中（原逻辑：cardText.includes(q)）', () => {
    expect(matchesSettingsSearch('奶油糖果', '外观', '外')).toBe(true)
    expect(matchesSettingsSearch('奶油糖果', '外观', '备份')).toBe(false)
  })
})

describe('isSettingsHotkey', () => {
  it('Ctrl + 逗号 / Cmd + 逗号 命中', () => {
    expect(isSettingsHotkey({ ctrlKey: true, metaKey: false, key: ',' })).toBe(true)
    expect(isSettingsHotkey({ ctrlKey: false, metaKey: true, key: ',' })).toBe(true)
  })

  it('无修饰键或非逗号不命中', () => {
    expect(isSettingsHotkey({ ctrlKey: false, metaKey: false, key: ',' })).toBe(false)
    expect(isSettingsHotkey({ ctrlKey: true, metaKey: false, key: '.' })).toBe(false)
    expect(isSettingsHotkey({ ctrlKey: true, metaKey: false, key: 'k' })).toBe(false)
  })
})

describe('formatSyncSizeKb', () => {
  it('按 1024 四舍五入（与模板原表达式一致）', () => {
    expect(formatSyncSizeKb(0)).toBe(0)
    expect(formatSyncSizeKb(1024)).toBe(1)
    expect(formatSyncSizeKb(1536)).toBe(2)
    expect(formatSyncSizeKb(500)).toBe(0)
    expect(formatSyncSizeKb(1024 * 1024)).toBe(1024)
  })
})
