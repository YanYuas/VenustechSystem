<script setup lang="ts">
// ============================================================
// 文档编辑器 —— 全屏编辑 + 自动保存 + 标签管理
// ============================================================
import { ref, watch, computed } from 'vue'
import dayjs from 'dayjs'
import { documentApi } from '@/api'
import { useAutoSave } from '@/composables/useAutoSave'
import { useToast } from '@/composables/useToast'
import BaseButton from '@/components/common/BaseButton.vue'
import BaseTag from '@/components/common/BaseTag.vue'
import BaseDrawer from '@/components/common/BaseDrawer.vue'
import AppIcon from '@/components/common/AppIcon.vue'
import type { Document, DocumentVersion } from '@/types'

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

watch([title, content], () => scheduleSave())

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

// 版本历史
const historyOpen = ref(false)
const versions = ref<DocumentVersion[]>([])
const verLoading = ref(false)

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
  loadVersions()
}

async function restoreVersion(v: DocumentVersion) {
  try {
    const doc = await documentApi.restoreVersion(props.document.id, v.version)
    content.value = doc.content ?? ''
    title.value = doc.title
    emit('saved', doc)
    toast.success('已恢复版本', `内容恢复到 v${v.version}`)
    historyOpen.value = false
  } catch {
    toast.error('恢复失败', '请稍后重试')
  }
}
</script>

<template>
  <div class="editor">
    <!-- 顶部工具栏 -->
    <div class="editor__toolbar">
      <button class="editor__back" @click="emit('close')">
        <AppIcon name="arrow-left" :size="18" />
        <span>返回</span>
      </button>
      <div class="editor__status">
        <span v-if="saving" class="editor__status-item"><AppIcon name="loading" :size="14" class="spin" /> 保存中...</span>
        <span v-else-if="dirty" class="editor__status-item editor__status--dirty">未保存</span>
        <span v-else class="editor__status-item editor__status--saved">
          <AppIcon name="check" :size="14" /> 已保存 {{ formatTime(lastSaved) }}
        </span>
        <span class="editor__status-item">{{ wordCount }} 字</span>
        <span class="editor__status-item">v{{ document.version }}</span>
      </div>
      <div class="editor__toolbar-actions">
        <BaseButton size="sm" variant="secondary" @click="openHistory">历史版本</BaseButton>
        <BaseButton size="sm" @click="save">手动保存</BaseButton>
      </div>
    </div>

    <!-- 标题 -->
    <input
      v-model="title"
      class="editor__title"
      placeholder="无标题文档"
      @input="scheduleSave"
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

    <!-- 正文编辑区 -->
    <textarea
      v-model="content"
      class="editor__content"
      placeholder="开始写作..."
      @input="scheduleSave"
    />

    <!-- 版本历史抽屉 -->
    <BaseDrawer v-model="historyOpen" title="历史版本">
      <div class="editor__versions">
        <p v-if="verLoading" class="editor__ver-empty">加载中…</p>
        <p v-else-if="!versions.length" class="editor__ver-empty">
          暂无历史版本（当前版本 v{{ document.version }}）
        </p>
        <div v-for="v in versions" :key="v.id" class="editor__ver-item">
          <div class="editor__ver-head">
            <span class="editor__ver-version">v{{ v.version }}</span>
            <span class="editor__ver-time">{{ dayjs(v.created_at).format('MM-DD HH:mm') }}</span>
            <span class="editor__ver-count">{{ v.word_count }} 字</span>
          </div>
          <BaseButton size="sm" variant="secondary" @click="restoreVersion(v)">恢复此版本</BaseButton>
        </div>
      </div>
    </BaseDrawer>
  </div>
</template>

<style scoped lang="scss">
.editor {
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
    padding-bottom: var(--space-3);
    border-bottom: 1px solid var(--line);
    margin-bottom: var(--space-4);
  }

  &__toolbar-actions {
    display: flex;
    gap: var(--space-2);
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

  &__ai-label {
    font-size: var(--text-xs);
    color: var(--text-low);
  }

  &__ai-tag {
    padding: 2px 8px;
    border: 1px dashed var(--lilac, #7c5cff);
    border-radius: var(--radius-pill);
    font-size: var(--text-xs);
    color: var(--lilac, #7c5cff);
    background: transparent;
    &:hover { background: var(--lilac-soft, rgba(124,92,255,0.08)); }
  }

  &__content {
    flex: 1;
    border: none;
    outline: none;
    background: transparent;
    font-size: var(--text-base);
    line-height: 1.8;
    color: var(--text-hi);
    resize: none;
    font-family: inherit;
    &::placeholder { color: var(--text-low); }
  }

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
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-3);
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    &:hover { border-color: var(--primary); }
  }
  &__ver-head {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  &__ver-version {
    font-size: var(--text-base);
    font-weight: 700;
    color: var(--primary);
  }
  &__ver-time,
  &__ver-count {
    font-size: var(--text-xs);
    color: var(--text-low);
  }
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
