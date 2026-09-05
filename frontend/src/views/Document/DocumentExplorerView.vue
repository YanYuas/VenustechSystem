<script setup lang="ts">
// ============================================================
// 知识资源 —— 列表 + 文档编辑器（点击文档进入编辑）
// 完整功能：文件夹CRUD、层级导航、文档搜索
// ============================================================
import { computed, onMounted, ref } from 'vue'
import dayjs from 'dayjs'
import { useDocument } from '@/composables/useDocument'
import { useToast } from '@/composables/useToast'
import { useModal } from '@/composables/useModal'
import BaseCard from '@/components/common/BaseCard.vue'
import BaseTag from '@/components/common/BaseTag.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import BaseInput from '@/components/common/BaseInput.vue'
import BaseSelect from '@/components/common/BaseSelect.vue'
import BaseModal from '@/components/common/BaseModal.vue'
import BaseEmpty from '@/components/common/BaseEmpty.vue'
import BaseSkeleton from '@/components/common/BaseSkeleton.vue'
import AppIcon from '@/components/common/AppIcon.vue'
import DocumentEditor from './DocumentEditor.vue'
import type { Document, Folder } from '@/types'

const {
  documents, total, folders, loading, query,
  fetchDocuments, fetchFolders, createDocument, deleteDocument,
  createFolder, renameFolder, deleteFolder,
} = useDocument()
const toast = useToast()
const modal = useModal()

onMounted(() => {
  fetchFolders().catch(() => { /* http 层已提示 */ })
  fetchDocuments().catch(() => { /* http 层已提示 */ })
})

const folderOptions = computed(() => [
  { label: '全部文件夹', value: '' },
  ...folders.value.map((f) => ({ label: f.name, value: f.id })),
])

const currentFolderId = ref('')
const searchText = ref('')

function onFolderChange(v: string) {
  currentFolderId.value = v
  query.value.folder_id = v || undefined
  query.value.page = 1
  fetchDocuments().catch(() => { /* http 层已提示 */ })
}

function onPageChange(p: number) {
  query.value.page = p
  fetchDocuments().catch(() => { /* http 层已提示 */ })
}

let searchTimer: ReturnType<typeof setTimeout> | undefined
function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    query.value.search = searchText.value.trim() || undefined
    query.value.page = 1
    fetchDocuments().catch(() => { /* http 层已提示 */ })
  }, 300)
}

// 文档编辑器
const editingDoc = ref<Document | null>(null)
function openEditor(d: Document) {
  editingDoc.value = d
}
function onEditorSaved(updated: Document) {
  const idx = documents.value.findIndex(d => d.id === updated.id)
  if (idx >= 0) documents.value[idx] = updated
}

// 新建文档
const createOpen = ref(false)
const newTitle = ref('')
const newFolderId = ref('')
async function onCreate() {
  const title = newTitle.value.trim()
  if (!title) return toast.warning('请输入文档标题')
  const doc = await createDocument({ title, folder_id: newFolderId.value || undefined })
  toast.success('文档已创建')
  createOpen.value = false
  newTitle.value = ''
  if (doc) openEditor(doc)
}

async function onDelete(d: Document) {
  const ok = await modal.confirm({
    title: '删除文档', message: `确定删除「${d.title}」吗？删除后无法恢复。`, confirmText: '删除',
  })
  if (!ok) return
  await deleteDocument(d.id)
  toast.success('文档已删除')
  if (editingDoc.value?.id === d.id) editingDoc.value = null
}

// ========== 文件夹管理 ==========
const folderModalOpen = ref(false)
const folderModalMode = ref<'create' | 'rename'>('create')
const folderForm = ref({ name: '', parent_id: '' })
const editingFolder = ref<Folder | null>(null)

function openCreateFolder() {
  folderModalMode.value = 'create'
  folderForm.value = { name: '', parent_id: currentFolderId.value || '' }
  folderModalOpen.value = true
}

function openRenameFolder(f: Folder) {
  folderModalMode.value = 'rename'
  editingFolder.value = f
  folderForm.value = { name: f.name, parent_id: '' }
  folderModalOpen.value = true
}

async function onFolderSubmit() {
  const name = folderForm.value.name.trim()
  if (!name) return toast.warning('请输入文件夹名称')
  try {
    if (folderModalMode.value === 'create') {
      await createFolder(name, folderForm.value.parent_id || undefined)
      toast.success('文件夹已创建')
    } else if (editingFolder.value) {
      await renameFolder(editingFolder.value.id, name)
      toast.success('文件夹已重命名')
    }
    folderModalOpen.value = false
  } catch { /* http 层已提示 */ }
}

async function onDeleteFolder(f: Folder) {
  const ok = await modal.confirm({
    title: '删除文件夹',
    message: `确定删除「${f.name}」吗？文件夹内的文档将移至「全部」，删除后无法恢复。`,
    confirmText: '删除',
  })
  if (!ok) return
  try {
    await deleteFolder(f.id)
    if (currentFolderId.value === f.id) {
      currentFolderId.value = ''
      query.value.folder_id = undefined
      fetchDocuments().catch(() => { /* http 层已提示 */ })
    }
    toast.success('文件夹已删除')
  } catch { /* http 层已提示 */ }
}

function fmtTime(v: string) {
  return dayjs(v).format('MM-DD HH:mm')
}
</script>

<template>
  <!-- 文档编辑器视图 -->
  <DocumentEditor
    v-if="editingDoc"
    :document="editingDoc"
    @close="editingDoc = null"
    @saved="onEditorSaved"
  />

  <!-- 文档列表视图 -->
  <div v-else class="docs">
    <div class="docs__head">
      <h1 class="docs__title">知识资源</h1>
      <div class="docs__head-actions">
        <BaseButton variant="secondary" icon="folder-plus" @click="openCreateFolder">新建文件夹</BaseButton>
        <BaseButton variant="primary" icon="plus" @click="createOpen = true">新建文档</BaseButton>
      </div>
    </div>

    <div class="docs__toolbar">
      <div class="docs__tree">
        <button :class="{ 'is-active': !currentFolderId }" @click="onFolderChange('')">全部</button>
        <template v-for="f in folders" :key="f.id">
          <div class="docs__tree-item">
            <button :class="{ 'is-active': currentFolderId === f.id }" @click="onFolderChange(f.id)">
              {{ f.is_inbox ? '📥' : '📁' }} {{ f.name }}
            </button>
            <div class="docs__tree-ops">
              <button class="docs__tree-op" title="重命名" @click.stop="openRenameFolder(f)">
                <AppIcon name="edit" :size="12" />
              </button>
              <button v-if="!f.is_inbox" class="docs__tree-op docs__tree-op--danger" title="删除" @click.stop="onDeleteFolder(f)">
                <AppIcon name="trash" :size="12" />
              </button>
            </div>
          </div>
          <button
            v-for="c in f.children ?? []" :key="c.id"
            class="docs__tree-child"
            :class="{ 'is-active': currentFolderId === c.id }"
            @click="onFolderChange(c.id)"
          >└ {{ c.name }}</button>
        </template>
      </div>
      <BaseInput v-model="searchText" type="search" placeholder="搜索标题 / 内容…" @update:modelValue="onSearch" />
    </div>

    <BaseCard>
      <template v-if="loading">
        <BaseSkeleton variant="list" :rows="5" />
      </template>
      <template v-else-if="documents.length">
        <ul class="docs__list">
          <li v-for="d in documents" :key="d.id" class="docs__item" @click="openEditor(d)">
            <div class="docs__row">
              <AppIcon name="doc" :size="18" class="docs__doc-icon" />
              <span class="docs__name">{{ d.title }}</span>
              <div class="docs__tags">
                <BaseTag v-for="t in d.tags" :key="t" semantic="lilac">{{ t }}</BaseTag>
              </div>
              <span class="docs__meta">{{ fmtTime(d.updated_at) }} · {{ d.word_count }} 字 · v{{ d.version }}</span>
              <button class="docs__del" title="删除" @click.stop="onDelete(d)">
                <AppIcon name="trash" :size="15" />
              </button>
            </div>
            <p v-if="d.summary" class="docs__summary">✨ {{ d.summary }}</p>
          </li>
        </ul>
      </template>
      <template v-else>
        <BaseEmpty title="没有文档" description="换一个文件夹，或创建第一篇笔记吧">
          <template #action>
            <BaseButton variant="primary" icon="plus" @click="createOpen = true">新建文档</BaseButton>
          </template>
        </BaseEmpty>
      </template>
    </BaseCard>

    <!-- 分页 -->
    <BasePagination
      v-if="!loading"
      :total="total"
      :page="query.page ?? 1"
      :page-size="query.page_size ?? 20"
      @change="onPageChange"
    />

    <!-- 新建文档弹窗 -->
    <BaseModal v-model="createOpen" title="新建文档" @confirm="onCreate">
      <div class="docs__form">
        <BaseInput v-model="newTitle" placeholder="文档标题" />
        <BaseSelect v-model="newFolderId" :options="folderOptions" placeholder="所属文件夹" />
      </div>
    </BaseModal>

    <!-- 文件夹管理弹窗 -->
    <BaseModal v-model="folderModalOpen" :title="folderModalMode === 'create' ? '新建文件夹' : '重命名文件夹'" @confirm="onFolderSubmit">
      <div class="docs__form">
        <BaseInput v-model="folderForm.name" placeholder="文件夹名称" />
        <BaseSelect
          v-if="folderModalMode === 'create'"
          v-model="folderForm.parent_id"
          :options="folderOptions"
          placeholder="父文件夹（可选）"
        />
      </div>
    </BaseModal>
  </div>
</template>

<style scoped lang="scss">
.docs {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  max-width: 960px;
  margin: 0 auto;

  &__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  &__head-actions {
    display: flex;
    gap: var(--space-2);
  }
  &__title {
    font-size: var(--text-2xl);
    font-weight: 700;
  }
  &__toolbar {
    display: flex;
    gap: var(--space-3);
    > * {
      flex: 1;
    }
  }
  &__tree {
    display: flex;
    gap: var(--space-2);
    overflow-x: auto;
    padding-bottom: 4px;
    flex-wrap: wrap;
    align-items: center;
    button {
      padding: 5px 14px;
      border: 1px solid var(--line);
      border-radius: var(--radius-pill);
      background: var(--bg-panel);
      color: var(--text-mid);
      font-size: var(--text-sm);
      white-space: nowrap;
      cursor: pointer;
      transition: all 0.15s var(--ease-soft);
      &.is-active {
        background: var(--primary);
        border-color: var(--primary);
        color: #fff;
      }
    }
  }
  &__tree-item {
    display: inline-flex;
    align-items: center;
    gap: 2px;
  }
  &__tree-ops {
    display: none;
    gap: 2px;
  }
  &__tree-item:hover &__tree-ops {
    display: inline-flex;
  }
  &__tree-op {
    padding: 2px;
    border: none;
    background: transparent;
    color: var(--text-low);
    border-radius: 4px;
    cursor: pointer;
    &:hover {
      background: var(--bg-soft, rgba(0, 0, 0, 0.05));
      color: var(--text-hi);
    }
    &--danger:hover {
      color: var(--danger, #ef4444);
    }
  }
  &__tree-child {
    margin-left: var(--space-4);
    opacity: 0.85;
  }

  &__list {
    list-style: none;
    display: flex;
    flex-direction: column;
  }
  &__item {
    border-bottom: 1px solid var(--line);
    &:last-child {
      border-bottom: none;
    }
  }
  &__row {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    cursor: pointer;
    &:hover {
      background: var(--bg-soft, rgba(0, 0, 0, 0.03));
    }
  }
  &__doc-icon {
    color: var(--text-low);
    flex-shrink: 0;
  }
  &__name {
    flex: 1;
    font-size: var(--text-base);
    font-weight: 500;
    color: var(--text-hi);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  &__tags {
    display: flex;
    gap: var(--space-1);
  }
  &__meta {
    font-size: var(--text-sm);
    color: var(--text-low);
    flex-shrink: 0;
  }
  &__del {
    padding: 4px;
    border: none;
    background: transparent;
    color: var(--text-low);
    border-radius: var(--radius-sm);
    cursor: pointer;
    &:hover {
      color: var(--danger, #ef4444);
      background: var(--bg-soft, rgba(0, 0, 0, 0.05));
    }
  }
  &__summary {
    margin: 0 var(--space-4) var(--space-3);
    font-size: var(--text-sm);
    color: var(--lilac-ink, #7c5cff);
    background: var(--lilac-soft, rgba(124, 92, 255, 0.08));
    border-radius: var(--radius-md);
    padding: var(--space-2) var(--space-3);
  }
  &__form {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
}
</style>
