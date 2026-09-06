<script setup lang="ts">
// ============================================================
// MarkdownToolbar —— Markdown 格式化工具栏（M03 F02）
// 操作目标：外部传入的 textarea ref（选区包裹/行前缀插入）
// 无专用图标，采用文字按钮（markdown 编辑器惯例）
// ============================================================
const props = defineProps<{
  /** 目标 textarea */
  target?: HTMLTextAreaElement | null
}>()

const emit = defineEmits<{
  (e: 'insert', payload: {
    text: string
    /** 原文中被替换的区间 */
    replaceStart: number
    replaceEnd: number
    /** 替换后的光标/选区 */
    selectionStart?: number
    selectionEnd?: number
  }): void
}>()

interface ToolAction {
  label: string
  title: string
  /** 包裹式：选中文字前后加标记 */
  wrap?: [string, string]
  /** 行前缀式：每行行首加标记（标题/列表/引用） */
  linePrefix?: string
  /** 插入块（光标处插入多行文本） */
  block?: string
}

const TOOLS: ToolAction[] = [
  { label: 'B', title: '加粗 (Ctrl+B)', wrap: ['**', '**'] },
  { label: 'I', title: '斜体 (Ctrl+I)', wrap: ['*', '*'] },
  { label: 'S', title: '删除线', wrap: ['~~', '~~'] },
  { label: 'H', title: '标题', linePrefix: '## ' },
  { label: '•', title: '无序列表', linePrefix: '- ' },
  { label: '1.', title: '有序列表', linePrefix: '1. ' },
  { label: '☑', title: '任务列表', linePrefix: '- [ ] ' },
  { label: '❝', title: '引用', linePrefix: '> ' },
  { label: '`', title: '行内代码', wrap: ['`', '`'] },
  { label: '🔗', title: '链接 (Ctrl+K)', wrap: ['[', '](https://)'] },
  { label: '🖼', title: '图片', block: '![图片描述](https://)' },
  { label: '▦', title: '表格', block: '\n| 列1 | 列2 | 列3 |\n| --- | --- | --- |\n| 内容 | 内容 | 内容 |\n' },
  { label: '{ }', title: '代码块', block: '\n```ts\n\n```\n' },
  { label: '―', title: '分隔线', block: '\n---\n' },
]

/** 对 target textarea 应用操作 */
function apply(tool: ToolAction) {
  const ta = props.target
  if (!ta) return

  const start = ta.selectionStart
  const end = ta.selectionEnd
  const value = ta.value
  const selected = value.slice(start, end)

  if (tool.wrap) {
    const [before, after] = tool.wrap
    const next = `${before}${selected}${after}`
    emit('insert', {
      text: next,
      replaceStart: start,
      replaceEnd: end,
      selectionStart: start + before.length,
      selectionEnd: start + before.length + selected.length,
    })
  } else if (tool.linePrefix) {
    // 行首插入：替换区间扩展到选区首行行首
    const lineStart = value.lastIndexOf('\n', start - 1) + 1
    const selectedText = value.slice(lineStart, end)
    const prefixed = selectedText
      .split('\n')
      .map((line) => (line.startsWith(tool.linePrefix!) ? line : tool.linePrefix! + line))
      .join('\n')
    emit('insert', {
      text: prefixed,
      replaceStart: lineStart,
      replaceEnd: end,
      selectionStart: lineStart + prefixed.length,
      selectionEnd: lineStart + prefixed.length,
    })
  } else if (tool.block) {
    emit('insert', {
      text: tool.block,
      replaceStart: start,
      replaceEnd: end,
      selectionStart: start + tool.block.length,
      selectionEnd: start + tool.block.length,
    })
  }
}

defineExpose({ apply })
</script>

<template>
  <div class="md-toolbar">
    <button
      v-for="t in TOOLS" :key="t.title"
      class="md-toolbar__btn" type="button" :title="t.title"
      @mousedown.prevent
      @click="apply(t)"
    >{{ t.label }}</button>
  </div>
</template>

<style scoped lang="scss">
.md-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--line);
  border-bottom: none;
  border-radius: var(--radius-sm) var(--radius-sm) 0 0;
  background: var(--bg-panel);

  &__btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 28px; height: 28px;
    padding: 0 6px;
    border: none; border-radius: var(--radius-sm);
    background: transparent; color: var(--text-mid);
    font-size: 13px; font-weight: 600;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
    &:hover { background: var(--bg-inset); color: var(--text-hi); }
  }
}
</style>
