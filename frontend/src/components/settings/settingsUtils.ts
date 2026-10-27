// ============================================================
// 设置页纯逻辑工具（无 DOM、无响应式依赖，便于单测）
//
// 为什么单独成文件：设置页拆分（D-09）后，搜索过滤 / 热键识别 / 同步包
// 大小格式化这三段逻辑原本内联在 SettingsView.vue 里，既无法单独测，
// 也被模板与 DOM 查询搅在一起。抽成纯函数后行为逐字保留：
//   - 搜索：q 为空 → 命中（不过滤）且大小写不敏感
//   - 热键：Ctrl 或 Cmd + 逗号
//   - 大小：Math.round(bytes / 1024)
// ============================================================

/** 归一化搜索词：去首尾空白 + 转小写（原 applySearch 内联逻辑） */
export function normalizeSearchQuery(query: string): string {
  return query.trim().toLowerCase()
}

/**
 * 单个设置项分组是否命中搜索。
 * 原逻辑：`text.includes(q) || cardText.includes(q)`，两者均小写比较。
 */
export function matchesSettingsSearch(groupText: string, cardTitle: string, query: string): boolean {
  const q = normalizeSearchQuery(query)
  if (!q) return true
  return groupText.toLowerCase().includes(q) || cardTitle.toLowerCase().includes(q)
}

/** 是否按下「聚焦设置搜索框」热键（Ctrl + 逗号 / Cmd + 逗号） */
export function isSettingsHotkey(e: Pick<KeyboardEvent, 'ctrlKey' | 'metaKey' | 'key'>): boolean {
  return (e.ctrlKey || e.metaKey) && e.key === ','
}

/** 同步包大小展示值（KB，四舍五入；原模板为 Math.round(p.size / 1024)） */
export function formatSyncSizeKb(bytes: number): number {
  return Math.round(bytes / 1024)
}
