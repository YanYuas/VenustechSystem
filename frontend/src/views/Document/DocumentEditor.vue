<script setup lang="ts">
// ============================================================
// 文档编辑器 —— M03 深度开发
// Markdown 工具栏 + 编辑/预览/阅读三模式 + 双向链接面板
// + 版本历史（含对比）+ 自动保存 + 标签管理 + MD 导出
// ============================================================
import { ref, watch, computed, onMounted, onBeforeUnmount } from 'vue'
import dayjs from 'dayjs'
import { marked } from 'marked'
import { documentApi } from '@/api'
import { useAutoSave } from '@/composables/useAutoSave'
import { useToast } from '@/composables/useToast'
import BaseButton from '@/components/common/BaseButton.vue'
import BaseTag from '@/components/common/BaseTag.vue'
import BaseDrawer from '@/components/common/BaseDrawer.vue'
import MarkdownToolbar from '@/components/document/MarkdownToolbar.vue'
import AppIcon from '@/components/common/AppIcon.vue'
import type { Document, DocumentVersion } from '@/types'

/** 反向链接来源（后端 BacklinkSourceOut 契约） */
interface BacklinkSource {
  source_doc_id: string
  source_title: string
}

const props = defineProps<{
  document: Document
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'saved', doc: Document): void
}>()

const toast = useToast()

const title = ref(props.document.title)
const content = ref(props.document.content ?? '')
const tags = ref<string[]>([...(props.document.tags ?? [])])
const tagInput = ref('')
const saving = ref(false)

const wordCount = computed(() => content.value.replace(/\s/g, '').length)

async function doSave(data: { title: string; content: string; tags: string[] }) {
  saving.value = true
  try {
    const updated = await documentApi.update(props.document.id, {
      title: data.title,
      content: data.content,
      tags: data.tags,
    })
    emit('saved', updated)
  } catch (err) {
    toast.error('保存失败', String(err))
  } finally {
    saving.value = false
  }
}

const { dirty, lastSaved, save, scheduleSave } = useAutoSave(
  () => ({ title: title.value, content: content.value, tags: tags.value }),
  { onSave: doSave, debounce: 1000, interval: 30000 },
)

/** 恢复历史版本时跳过自动保存触发，避免刚恢复的内容立即生成新版本 */
let suppressAutoSave = 0
watch([title, content], () => {
  if (suppressAutoSave > 0) {
    suppressAutoSave--
    return
  }
  scheduleSave()
})

// ---------- 编辑模式：edit / preview / read（M03 F02/F08） ----------
type EditorMode = 'edit' | 'preview' | 'read'
const mode = ref<EditorMode>('edit')

/** marked 渲染（同步） */
const renderedHtml = computed(() => {
  try {
    return marked.parse(content.value || '（空文档）', { async: false }) as string
  } catch {
    return '<p>渲染失败</p>'
  }
})

/** 阅读模式目录（按 ## / ### 标题生成） */
const toc = computed(() => {
  const items: Array<{ level: number; text: string; id: string }> = []
  content.value.split('\n').forEach((line) => {
    const m = /^(#{2,3})\s+(.+)$/.exec(line.trim())
    if (m) {
      const text = m[2].trim()
      items.push({ level: m[1].length, text, id: `toc-${items.length}` })
    }
  })
  return items
})

// ---------- 工具栏与快捷键（M03 F02） ----------
const textareaRef = ref<HTMLTextAreaElement | null>(null)

function onToolbarInsert(payload: {
  text: string
  replaceStart: number
  replaceEnd: number
  selectionStart?: number
  selectionEnd?: number
}) {
  const ta = textareaRef.value
  if (!ta) return
  // 按 toolbar 计算的替换区间写入（行前缀模式区间会扩展到行首）
  content.value =
    content.value.slice(0, payload.replaceStart) +
    payload.text +
    content.value.slice(payload.replaceEnd)
  scheduleSave()
  requestAnimationFrame(() => {
    ta.focus()
    const ns = payload.selectionStart ?? payload.replaceStart + payload.text.length
    const ne = payload.selectionEnd ?? ns
    ta.setSelectionRange(ns, ne)
  })
}

function onEditorKeydown(e: KeyboardEvent) {
  if (!(e.ctrlKey || e.metaKey)) return
  const ta = textareaRef.value
  if (!ta) return
  const key = e.key.toLowerCase()
  const toolMap: Record<string, [string, string]> = {
    b: ['**', '**'],
    i: ['*', '*'],
    k: ['[', '](https://)'],
  }
  if (toolMap[key]) {
    e.preventDefault()
    const [before, after] = toolMap[key]
    const s = ta.selectionStart
    const epos = ta.selectionEnd
    const selected = content.value.slice(s, epos)
    content.value = content.value.slice(0, s) + before + selected + after + content.value.slice(epos)
    scheduleSave()
    requestAnimationFrame(() => {
      ta.focus()
      ta.setSelectionRange(s + before.length, s + before.length + selected.length)
    })
  }
}

function addTag() {
  const t = tagInput.value.trim()
  if (!t) return
  if (tags.value.includes(t)) {
    tagInput.value = ''
    return
  }
  if (tags.value.length >= 10) {
    toast.warning('最多10个标签')
    return
  }
  tags.value.push(t)
  tagInput.value = ''
  scheduleSave()
}

function removeTag(t: string) {
  tags.value = tags.value.filter(x => x !== t)
  scheduleSave()
}

function formatTime(d: Date | null): string {
  if (!d) return ''
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

// ---------- 双向链接面板（M03 F05，后端已就绪） ----------
const backlinks = ref<BacklinkSource[]>([])
const backlinkOpen = ref(false)
const backlinkLoading = ref(false)

async function loadBacklinks() {
  backlinkLoading.value = true
  try {
    backlinks.value = await documentApi.backlinks(props.document.id)
  } catch { /* http 层已提示 */ } finally {
    backlinkLoading.value = false
  }
}

function toggleBacklinks() {
  backlinkOpen.value = !backlinkOpen.value
  if (backlinkOpen.value) loadBacklinks()
}

// ---------- 版本历史 + 对比（M03 F04） ----------
const historyOpen = ref(false)
const versions = ref<DocumentVersion[]>([])
const verLoading = ref(false)
const compareId = ref<string | null>(null)
const compareContent = ref<string>('')

async function loadVersions() {
  verLoading.value = true
  try {
    versions.value = await documentApi.versions(props.document.id)
  } catch {
    toast.error('加载失败', '版本历史加载失败')
  } finally {
    verLoading.value = false
  }
}

function openHistory() {
  historyOpen.value = true
  compareId.value = null
  loadVersions()
}

/** 简易行级 diff：旧版本行标记删除、新版本行标记新增 */
const versionDiff = computed(() => {
  if (!compareId.value) return null
  const oldLines = compareContent.value.split('\n')
  const newLines = (content.value || '').split('\n')
  const oldSet = new Set(oldLines)
  const newSet = new Set(newLines)
  const rows: Array<{ type: 'same' | 'add' | 'del'; text: string }> = []
  for (const line of oldLines) {
    if (!newSet.has(line)) rows.push({ type: 'del', text: line })
  }
  for (const line of newLines) {
    if (!oldSet.has(line)) rows.push({ type: 'add', text: line })
  }
  return rows
})

async function openCompare(v: DocumentVersion) {
  try {
    const detail = await documentApi.versionDetail(props.document.id, v.version)
    compareId.value = v.id
    compareContent.value = detail.content
  } catch {
    toast.error('加载失败', '版本内容获取失败')
  }
}

async function restoreVersion(v: DocumentVersion) {
  try {
    const doc = await documentApi.restoreVersion(props.document.id, v.version)
    suppressAutoSave = 2 // 赋值 title + content 各触发一次 watch
    content.value = doc.content ?? ''
    title.value = doc.title
    emit('saved', doc)
    toast.success('已恢复版本', `内容恢复到 v${v.version}`)
    historyOpen.value = false
  } catch {
    toast.error('恢复失败', '请稍后重试')
  }
}

// ---------- 导出 MD（M03 F06 第一阶段） ----------
function exportMarkdown() {
  const md = `# ${title.value}\n\n${content.value}\n`
  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${title.value || '未命名文档'}.md`
  a.click()
  URL.revokeObjectURL(url)
  toast.success('已导出', `${title.value}.md`)
}

onMounted(() => {
  window.addEventListener('keydown', onEditorKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onEditorKeydown)
})
</script>

<template>
  <div class="editor" :class="`editor--${mode}`">
    <!-- 顶部工具栏 -->
    <div class="editor__toolbar">
      <button class="editor__back" @click="emit('close')">
        <AppIcon name="arrow-left" :size="18" />
        <span>返回</span>
      </button>
      <div class="editor__status">
        <span v-if="saving" class="editor__status-item"><AppIcon name="spin" :size="14" class="spin" /> 保存中...</span>
        <span v-else-if="dirty" class="editor__status-item editor__status--dirty">未保存</span>
        <span v-else class="editor__status-item editor__status--saved">
          <AppIcon name="check" :size="14" /> 已保存 {{ formatTime(lastSaved) }}
        </span>
        <span class="editor__status-item">{{ wordCount }} 字</span>
        <span class="editor__status-item">v{{ document.version }}</span>
      </div>
      <div class="editor__toolbar-actions">
        <div class="editor__mode-switch">
          <button :class="{ 'is-active': mode === 'edit' }" title="编辑" @click="mode = 'edit'">编辑</button>
          <button :class="{ 'is-active': mode === 'preview' }" title="预览" @click="mode = 'preview'">预览</button>
          <button :class="{ 'is-active': mode === 'read' }" title="阅读模式" @click="mode = 'read'">
            <AppIcon name="eye" :size="13" />
          </button>
        </div>
        <BaseButton size="sm" variant="secondary" @click="toggleBacklinks">双向链接</BaseButton>
        <BaseButton size="sm" variant="secondary" @click="openHistory">历史版本</BaseButton>
        <BaseButton size="sm" variant="secondary" @click="exportMarkdown">导出 MD</BaseButton>
        <BaseButton v-if="mode === 'edit'" size="sm" @click="save">手动保存</BaseButton>
      </div>
    </div>

    <!-- 编辑模式 -->
    <template v-if="mode === 'edit'">
      <!-- 标题 -->
      <input
        v-model="title"
        class="editor__title"
        placeholder="无标题文档"
      />

      <!-- 标签 -->
      <div class="editor__tags">
        <BaseTag v-for="t in tags" :key="t" semantic="lilac" closable @close="removeTag(t)">{{ t }}</BaseTag>
        <input
          v-model="tagInput"
          class="editor__tag-input"
          placeholder="添加标签..."
          @keyup.enter="addTag"
        />
      </div>

      <!-- AI 摘要 -->
      <div v-if="document.summary" class="editor__summary">
        <AppIcon name="spark" :size="16" />
        <span>{{ document.summary }}</span>
      </div>

      <!-- AI 建议标签 -->
      <div v-if="document.ai_suggested_tags?.length" class="editor__ai-tags">
        <span class="editor__ai-label">AI建议:</span>
        <button
          v-for="t in document.ai_suggested_tags"
          :key="t"
          class="editor__ai-tag"
          @click="tags.push(t); scheduleSave()"
        >+ {{ t }}</button>
      </div>

      <!-- Markdown 工具栏 + 正文 -->
      <div class="editor__content-wrap">
        <MarkdownToolbar :target="textareaRef" @insert="onToolbarInsert" />
        <textarea
          ref="textareaRef"
          v-model="content"
          class="editor__content"
          placeholder="开始写作... 支持 Markdown 与 [[双向链接]]"
        />
      </div>
    </template>

    <!-- 预览模式（编辑/预览对照由工具栏切换承担，此处为纯预览） -->
    <template v-else-if="mode === 'preview'">
      <input v-model="title" class="editor__title" placeholder="无标题文档" />
      <div class="editor__markdown md-preview" v-html="renderedHtml" />
    </template>

    <!-- 阅读模式（M03 F08：居中排版 + 目录 + 无编辑UI） -->
    <template v-else>
      <div class="editor__read">
        <aside v-if="toc.length" class="editor__toc">
          <h4>目录</h4>
          <a
            v-for="item in toc" :key="item.id"
            class="editor__toc-item"
            :class="{ 'is-h3': item.level === 3 }"
            :href="`#${item.id}`"
          >{{ item.text }}</a>
        </aside>
        <article class="editor__read-body">
          <h1 class="editor__read-title">{{ title }}</h1>
          <div class="editor__markdown md-preview" v-html="renderedHtml" />
        </article>
      </div>
    </template>

    <!-- 双向链接面板（M03 F05） -->
    <Transition name="slide">
      <aside v-if="backlinkOpen" class="editor__backlinks">
        <div class="editor__backlinks-head">
          <h4>反向链接（{{ backlinks.length }}）</h4>
          <button class="editor__backlinks-close" @click="backlinkOpen = false">
            <AppIcon name="close" :size="14" />
          </button>
        </div>
        <p v-if="backlinkLoading" class="editor__backlinks-empty">加载中…</p>
        <p v-else-if="!backlinks.length" class="editor__backlinks-empty">
          暂无其他文档链接到本文档
        </p>
        <ul v-else class="editor__backlinks-list">
          <li v-for="bl in backlinks" :key="bl.source_doc_id" class="editor__backlink">
            <AppIcon name="doc" :size="14" />
            <span :title="bl.source_doc_id">{{ bl.source_title || '（已删除的文档）' }}</span>
          </li>
        </ul>
      </aside>
    </Transition>

    <!-- 版本历史抽屉 -->
    <BaseDrawer v-model="historyOpen" title="历史版本" :width="560">
      <div class="editor__versions">
        <p v-if="verLoading" class="editor__ver-empty">加载中…</p>
        <p v-else-if="!versions.length" class="editor__ver-empty">
          暂无历史版本（当前版本 v{{ document.version }}）
        </p>
        <template v-else>
          <div v-for="v in versions" :key="v.id" class="editor__ver-item">
            <div class="editor__ver-head">
              <span class="editor__ver-version">v{{ v.version }}</span>
              <span class="editor__ver-time">{{ dayjs(v.created_at).format('MM-DD HH:mm') }}</span>
              <span class="editor__ver-count">{{ v.word_count }} 字</span>
            </div>
            <div class="editor__ver-ops">
              <BaseButton size="sm" variant="secondary" @click="openCompare(v)">
                {{ compareId === v.id ? '收起对比' : '对比当前' }}
              </BaseButton>
              <BaseButton size="sm" variant="secondary" @click="restoreVersion(v)">恢复此版本</BaseButton>
            </div>
            <!-- 版本对比（M03 F04） -->
            <div v-if="compareId === v.id && versionDiff" class="editor__diff">
              <div
                v-for="(row, i) in versionDiff" :key="i"
                class="editor__diff-row"
                :class="`is-${row.type}`"
              >
                <span class="editor__diff-mark">{{ row.type === 'add' ? '+' : '−' }}</span>
                <span class="editor__diff-text">{{ row.text || '（空行）' }}</span>
              </div>
              <p v-if="!versionDiff.length" class="editor__ver-empty">与当前版本无差异</p>
            </div>
          </div>
        </template>
      </div>
    </BaseDrawer>
  </div>
</template>

<style scoped lang="scss">
.editor {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: var(--space-4) var(--space-6);
  max-width: 860px;
  margin: 0 auto;

  &__toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding-bottom: var(--space-3);
    border-bottom: 1px solid var(--line);
    margin-bottom: var(--space-4);
  }

  &__toolbar-actions {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  &__mode-switch {
    display: flex;
    border: 1px solid var(--line);
    border-radius: var(--radius-pill);
    overflow: hidden;
    button {
      padding: 4px 12px; border: none; background: var(--bg-panel);
      color: var(--text-mid); font-size: var(--text-sm); cursor: pointer;
      display: inline-flex; align-items: center; gap: 4px;
      transition: background 0.15s, color 0.15s;
      &.is-active { background: var(--primary); color: #fff; }
    }
  }

  &__back {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    color: var(--text-mid);
    font-size: var(--text-sm);
    &:hover { color: var(--primary); }
  }

  &__status {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  &__status-item {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: var(--text-xs);
    color: var(--text-low);
    &--dirty { color: var(--gold); }
    &--saved { color: var(--mint); }
  }

  &__title {
    font-size: var(--text-2xl);
    font-weight: 700;
    font-family: var(--font-cute);
    color: var(--text-hi);
    border: none;
    outline: none;
    background: transparent;
    margin-bottom: var(--space-3);
    &::placeholder { color: var(--text-low); }
  }

  &__tags {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
  }

  &__tag-input {
    border: none;
    outline: none;
    background: transparent;
    font-size: var(--text-sm);
    color: var(--text-hi);
    width: 100px;
    &::placeholder { color: var(--text-low); }
  }

  &__summary {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    background: var(--lilac-soft, rgba(124,92,255,0.08));
    border-radius: var(--radius-md);
    color: var(--lilac-ink, #7c5cff);
    font-size: var(--text-sm);
    line-height: 1.6;
    margin-bottom: var(--space-3);
  }

  &__ai-tags {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
  }

  &__ai-label { font-size: var(--text-xs); color: var(--text-low); }
  &__ai-tag {
    padding: 2px 8px;
    border: 1px dashed var(--lilac, #7c5cff);
    border-radius: var(--radius-pill);
    font-size: var(--text-xs);
    color: var(--lilac, #7c5cff);
    background: transparent;
    &:hover { background: var(--lilac-soft, rgba(124,92,255,0.08)); }
  }

  &__content-wrap {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  &__content {
    flex: 1;
    border: 1px solid var(--line);
    border-radius: 0 var(--radius-sm) var(--radius-sm) var(--radius-sm);
    outline: none;
    background: var(--bg-panel);
    font-size: var(--text-base);
    line-height: 1.8;
    color: var(--text-hi);
    resize: none;
    padding: var(--space-3) var(--space-4);
    font-family: inherit;
    &::placeholder { color: var(--text-low); }
    &:focus { border-color: var(--primary); }
  }

  &__markdown {
    flex: 1;
    overflow-y: auto;
    line-height: 1.8;
    color: var(--text-hi);
  }

  // ---------- 阅读模式 ----------
  &__read {
    flex: 1;
    display: flex;
    gap: var(--space-6);
    min-height: 0;
  }
  &__toc {
    width: 180px;
    flex-shrink: 0;
    overflow-y: auto;
    border-right: 1px solid var(--line);
    padding-right: var(--space-4);
    h4 { font-size: var(--text-sm); font-weight: 600; color: var(--text-mid); margin-bottom: var(--space-2); }
  }
  &__toc-item {
    display: block;
    padding: 4px 0;
    font-size: var(--text-sm);
    color: var(--text-mid);
    text-decoration: none;
    &:hover { color: var(--primary); }
    &.is-h3 { padding-left: var(--space-4); font-size: var(--text-xs); }
  }
  &__read-body {
    flex: 1;
    min-width: 0;
    overflow-y: auto;
    max-width: 720px;
    margin: 0 auto;
  }
  &__read-title {
    font-size: var(--text-2xl);
    font-weight: 700;
    font-family: var(--font-cute);
    color: var(--text-hi);
    margin-bottom: var(--space-4);
  }

  // ---------- 双向链接侧栏 ----------
  &__backlinks {
    position: absolute;
    top: 70px; right: var(--space-2); bottom: var(--space-4);
    width: 240px;
    background: var(--bg-raised);
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-raise);
    padding: var(--space-3);
    overflow-y: auto;
    z-index: 20;
  }
  &__backlinks-head {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: var(--space-2);
    h4 { font-size: var(--text-sm); font-weight: 600; color: var(--text-hi); }
  }
  &__backlinks-close {
    border: none; background: transparent; color: var(--text-low);
    cursor: pointer; padding: 2px; border-radius: var(--radius-sm);
    &:hover { color: var(--text-hi); background: var(--bg-inset); }
  }
  &__backlinks-empty { font-size: var(--text-sm); color: var(--text-low); text-align: center; padding: var(--space-4) 0; }
  &__backlinks-list { list-style: none; display: flex; flex-direction: column; gap: var(--space-1); }
  &__backlink {
    display: flex; align-items: center; gap: var(--space-2);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    font-size: var(--text-sm);
    color: var(--text-hi);
    &:hover { background: var(--bg-inset); }
    .is-dangling { color: var(--text-low); font-style: italic; }
  }
  &__backlink-flag {
    margin-left: auto;
    font-size: 10px;
    padding: 1px 6px;
    border-radius: var(--radius-pill);
    background: var(--bg-inset);
    color: var(--text-low);
  }

  // ---------- 版本历史 ----------
  &__versions {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  &__ver-empty {
    padding: var(--space-6);
    text-align: center;
    color: var(--text-low);
    font-size: var(--text-sm);
  }
  &__ver-item {
    padding: var(--space-3);
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    &:hover { border-color: var(--primary); }
  }
  &__ver-head {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-2);
  }
  &__ver-version { font-size: var(--text-base); font-weight: 700; color: var(--primary); }
  &__ver-time, &__ver-count { font-size: var(--text-xs); color: var(--text-low); }
  &__ver-ops { display: flex; gap: var(--space-2); }

  // ---------- 版本对比 diff ----------
  &__diff {
    margin-top: var(--space-2);
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    background: var(--bg-panel);
    max-height: 260px;
    overflow-y: auto;
    font-family: monospace;
    font-size: 12px;
  }
  &__diff-row {
    display: flex;
    gap: var(--space-2);
    padding: 1px 8px;
    &.is-add { background: rgba(61, 220, 151, 0.12); color: var(--mint, #3ddc97); }
    &.is-del { background: rgba(239, 68, 68, 0.10); color: var(--strawberry, #ef4444); text-decoration: line-through; }
    &.is-same { color: var(--text-mid); }
  }
  &__diff-mark { flex-shrink: 0; width: 14px; font-weight: 700; }
  &__diff-text { white-space: pre-wrap; word-break: break-all; }
}

.spin { animation: spin 1s linear infinite; }
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.slide-enter-active, .slide-leave-active { transition: transform 0.25s var(--ease-soft), opacity 0.25s; }
.slide-enter-from, .slide-leave-to { transform: translateX(20px); opacity: 0; }
</style>

<!-- Markdown 渲染样式（非 scoped：v-html 内容） -->
<style lang="scss">
.md-preview {
  h1, h2, h3, h4 { font-weight: 700; color: var(--text-hi); margin: 1em 0 0.5em; }
  h1 { font-size: 1.5em; }
  h2 { font-size: 1.3em; }
  h3 { font-size: 1.15em; }
  p { margin: 0.6em 0; }
  ul, ol { padding-left: 1.5em; margin: 0.6em 0; }
  li { margin: 0.25em 0; }
  code {
    padding: 2px 6px;
    border-radius: 4px;
    background: var(--bg-inset);
    font-family: monospace;
    font-size: 0.9em;
  }
  pre {
    padding: var(--space-3);
    border-radius: var(--radius-sm);
    background: var(--bg-inset);
    overflow-x: auto;
    code { padding: 0; background: transparent; }
  }
  blockquote {
    margin: 0.8em 0;
    padding: var(--space-2) var(--space-4);
    border-left: 3px solid var(--primary);
    background: var(--bg-inset);
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    color: var(--text-mid);
  }
  table { border-collapse: collapse; margin: 0.8em 0; }
  th, td { border: 1px solid var(--line); padding: 6px 12px; }
  th { background: var(--bg-inset); font-weight: 600; }
  a { color: var(--primary); }
  img { max-width: 100%; border-radius: var(--radius-sm); }
  hr { border: none; border-top: 1px solid var(--line); margin: 1.2em 0; }
}
</style>
