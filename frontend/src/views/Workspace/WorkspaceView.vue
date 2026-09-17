<script setup lang="ts">
// ============================================================
// 工作区（三期 C · 档案库）
// 已登记根的浏览 / 重扫 / 开终端 + 文件索引检索
// 若功能未启用或没有任何根 → 引导去设置页
// ============================================================
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { workspaceApi } from '@/api'
import { useIdentity } from '@/composables/useIdentity'
import { useModal } from '@/composables/useModal'
import { useToast } from '@/composables/useToast'
import BaseCard from '@/components/common/BaseCard.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import BaseInput from '@/components/common/BaseInput.vue'
import BaseEmpty from '@/components/common/BaseEmpty.vue'
import BaseSkeleton from '@/components/common/BaseSkeleton.vue'
import AppIcon from '@/components/common/AppIcon.vue'
import type { WorkspaceFile, WorkspaceRoot } from '@/types'

const router = useRouter()
const toast = useToast()
const modal = useModal()
const { loadIdentities, colorVar, byId } = useIdentity()

const roots = ref<WorkspaceRoot[]>([])
const enabled = ref(true)
const loading = ref(true)

const activeRootId = ref('')
const activeRoot = computed(() => roots.value.find((r) => r.id === activeRootId.value) ?? null)

const files = ref<WorkspaceFile[]>([])
const filesTotal = ref(0)
const search = ref('')
const filesLoading = ref(false)

async function loadRoots() {
  loading.value = true
  try {
    const status = await workspaceApi.status()
    enabled.value = status.enabled
    roots.value = await workspaceApi.roots()
    if (!activeRootId.value && roots.value.length) {
      activeRootId.value = roots.value[0].id
      await loadFiles()
    }
  } catch { /* http 层已提示 */ } finally {
    loading.value = false
  }
}

async function loadFiles() {
  if (!activeRootId.value) return
  filesLoading.value = true
  try {
    const res = await workspaceApi.files(activeRootId.value, {
      search: search.value.trim() || undefined,
    })
    files.value = res.items
    filesTotal.value = res.total
  } catch { /* http 层已提示 */ } finally {
    filesLoading.value = false
  }
}

async function onScan(root: WorkspaceRoot) {
  try {
    const updated = await workspaceApi.scan(root.id)
    roots.value = roots.value.map((r) => (r.id === root.id ? updated : r))
    toast.success('扫描完成', `${updated.file_count} 个条目已索引`)
    if (root.id === activeRootId.value) await loadFiles()
  } catch { /* http 层已提示 */ }
}

async function onOpenTerminal(root: WorkspaceRoot) {
  try {
    await workspaceApi.openTerminal(root.path)
    toast.success('终端已打开', root.path)
  } catch { /* http 层已提示（含白名单拦截原因） */ }
}

async function onRemove(root: WorkspaceRoot) {
  const ok = await modal.confirm({
    title: '移除工作区',
    message: `移除「${root.label ?? root.path}」？只清除启明星里的索引，磁盘上的文件不会被删除。`,
    confirmText: '移除',
  })
  if (!ok) return
  try {
    await workspaceApi.removeRoot(root.id)
    toast.success('已移除', '磁盘文件未受影响')
    if (activeRootId.value === root.id) {
      activeRootId.value = ''
      files.value = []
      filesTotal.value = 0
    }
    await loadRoots()
  } catch { /* http 层已提示 */ }
}

function openFileRoot(file: WorkspaceFile) {
  if (!activeRoot.value) return
  const full = activeRoot.value.path + '/' + file.rel_path
  // 打开所在文件夹 = 在父目录开终端（唯一白名单动作，后端校验）
  const dir = file.is_dir ? full : full.slice(0, full.lastIndexOf('/')) || activeRoot.value.path
  workspaceApi.openTerminal(dir).then(() => {
    toast.success('终端已打开', dir)
  }).catch(() => { /* http 层已提示 */ })
}

function formatSize(n: number) {
  if (n < 1024) return `${n} B`
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 ** 2).toFixed(1)} MB`
}

const identityName = (id: string | null) => byId(id)?.name ?? '未归类'

onMounted(async () => {
  loadIdentities()
  await loadRoots()
})
</script>

<template>
  <div class="ws">
    <div class="ws__head">
      <h1 class="ws__title">工作区</h1>
      <BaseButton variant="primary" icon="plus" @click="router.push('/workspace/setup')">
        添加 / 引导设置
      </BaseButton>
    </div>

    <div v-if="loading"><BaseSkeleton variant="list" :rows="4" /></div>

    <BaseEmpty
      v-else-if="!enabled || roots.length === 0"
      title="工作区还没设置"
      description="用引导向导登记你的文件夹（或按身份生成目录骨架），让启明星与磁盘上的产出对上号"
    >
      <template #action>
        <BaseButton variant="primary" @click="router.push('/workspace/setup')">打开引导向导</BaseButton>
      </template>
    </BaseEmpty>

    <template v-else>
      <!-- 根列表 -->
      <div class="ws__roots">
        <button
          v-for="r in roots" :key="r.id"
          class="ws__root" :class="{ 'is-active': r.id === activeRootId }"
          type="button"
          @click="activeRootId = r.id; loadFiles()"
        >
          <AppIcon name="folder" :size="15" />
          <span class="ws__root-label">{{ r.label ?? r.path }}</span>
          <span class="ws__root-meta">
            {{ r.scan_status === 'ok' ? `${r.file_count} 项` : '未扫描' }}
          </span>
        </button>
      </div>

      <!-- 选中根详情 -->
      <BaseCard v-if="activeRoot">
        <template #title>
          <div class="ws__card-head">
            <span class="ws__root-full">{{ activeRoot.path }}</span>
            <span
              v-if="activeRoot.identity_id"
              class="ws__identity-dot"
              :style="{ background: colorVar(byId(activeRoot.identity_id)?.color_token ?? null) }"
            />
            <span class="ws__identity-name">{{ identityName(activeRoot.identity_id) }}</span>
          </div>
        </template>

        <div class="ws__ops">
          <BaseInput
            v-model="search"
            placeholder="按文件名搜索…"
            @update:model-value="loadFiles"
          />
          <BaseButton size="sm" variant="secondary" icon="reload" :loading="filesLoading" @click="loadFiles">
            刷新
          </BaseButton>
          <BaseButton size="sm" variant="secondary" icon="command" @click="onScan(activeRoot)">
            重新扫描
          </BaseButton>
          <BaseButton size="sm" variant="primary" icon="command" @click="onOpenTerminal(activeRoot)">
            打开终端
          </BaseButton>
          <BaseButton size="sm" variant="danger" icon="trash" @click="onRemove(activeRoot)">
            移除
          </BaseButton>
        </div>

        <p class="ws__stats">
          索引 {{ activeRoot.file_count }} 项 · {{ formatSize(activeRoot.total_size) }}
          <template v-if="activeRoot.last_scanned_at">
            · 上次扫描 {{ activeRoot.last_scanned_at.slice(0, 16).replace('T', ' ') }}
          </template>
          <template v-if="activeRoot.scan_status === 'error'">
            · <span class="ws__error">上次扫描出错：{{ activeRoot.scan_error }}</span>
          </template>
          <span class="ws__total-hint">（搜索命中 {{ filesTotal }}）</span>
        </p>

        <div v-if="filesLoading"><BaseSkeleton variant="list" :rows="5" /></div>
        <BaseEmpty v-else-if="files.length === 0" description="没有匹配的条目" />
        <ul v-else class="ws__list">
          <li v-for="f in files" :key="f.id" class="ws__file" @dblclick="openFileRoot(f)">
            <AppIcon :name="f.is_dir ? 'folder' : 'doc'" :size="14" />
            <span class="ws__file-name">{{ f.name }}</span>
            <span class="ws__file-dir">{{ f.rel_path }}</span>
            <span class="ws__file-size">{{ f.is_dir ? '—' : formatSize(f.size) }}</span>
          </li>
        </ul>
        <p class="ws__tip">双击条目可在其所在文件夹打开终端（唯一白名单动作）</p>
      </BaseCard>
    </template>
  </div>
</template>

<style scoped lang="scss">
.ws {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-6);
}
.ws__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.ws__title {
  margin: 0;
  font-size: var(--text-xl);
  color: var(--text-hi);
}
.ws__roots {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.ws__root {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--bg-panel);
  color: var(--text-mid);
  cursor: pointer;
  transition: border-color 0.15s, background-color 0.15s;
  &:hover { border-color: var(--primary); }
  &.is-active { border-color: var(--primary); background: var(--primary-soft); }
}
.ws__root-label {
  font-size: var(--text-sm);
  color: var(--text-hi);
}
.ws__root-meta { font-size: var(--text-xs); color: var(--text-low); }

.ws__card-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}
.ws__root-full {
  font-size: var(--text-xs);
  color: var(--text-mid);
  font-family: var(--font-mono);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ws__identity-dot {
  flex: none;
  width: 8px;
  height: 8px;
  border-radius: var(--radius-pill);
}
.ws__identity-name { font-size: var(--text-xs); color: var(--text-mid); }

.ws__ops {
  display: flex;
  gap: var(--space-2);
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: var(--space-3);
  :first-child { flex: 1; min-width: 180px; }
}
.ws__stats {
  margin: 0 0 var(--space-3);
  font-size: var(--text-xs);
  color: var(--text-low);
}
.ws__total-hint { margin-left: var(--space-2); }
.ws__error { color: var(--straw-ink); }

.ws__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.ws__file {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px var(--space-2);
  border-radius: var(--radius-sm);
  color: var(--text-mid);
  cursor: default;
  &:hover { background: var(--bg-inset); }
}
.ws__file-name {
  font-size: var(--text-sm);
  color: var(--text-hi);
}
.ws__file-dir {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--text-xs);
  color: var(--text-low);
  font-family: var(--font-mono);
}
.ws__file-size {
  flex: none;
  font-size: var(--text-xs);
  color: var(--text-low);
}
.ws__tip {
  margin: var(--space-3) 0 0;
  font-size: var(--text-xs);
  color: var(--text-low);
}
</style>
