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
import { useDevice } from '@/composables/useDevice'
import ActionSheet, { type SheetAction } from '@/components/common/ActionSheet.vue'
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

const PAGE_SIZE = 50
const DEBOUNCE_MS = 400

const files = ref<WorkspaceFile[]>([])
const filesTotal = ref(0)
const search = ref('')
const filesLoading = ref(false)
// 分页：files 是"已加载页"的累积；filesPage 是当前已加载到第几页
const filesPage = ref(1)
const loadingMore = ref(false)
const hasMore = computed(() => files.value.length < filesTotal.value)

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

/**
 * 拉取文件列表。
 * append=false（默认）→ 重置到第 1 页；append=true → 追加下一页。
 * 搜索条件变化与切根必须走 append=false，否则会串页。
 */
async function loadFiles(append = false) {
  if (!activeRootId.value) return
  const nextPage = append ? filesPage.value + 1 : 1
  if (append) loadingMore.value = true
  else filesLoading.value = true
  try {
    const res = await workspaceApi.files(activeRootId.value, {
      search: search.value.trim() || undefined,
      page: nextPage,
      page_size: PAGE_SIZE,
    })
    files.value = append ? files.value.concat(res.items) : res.items
    filesTotal.value = res.total
    filesPage.value = nextPage
  } catch { /* http 层已提示 */ } finally {
    filesLoading.value = false
    loadingMore.value = false
  }
}

function loadMore() {
  if (loadingMore.value || !hasMore.value) return
  void loadFiles(true)
}

// 搜索防抖：400ms 内连续输入只发最后一次请求（原来每次按键都发）
let searchTimer: ReturnType<typeof setTimeout> | undefined
function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    searchTimer = undefined
    void loadFiles(false)
  }, DEBOUNCE_MS)
}

function onRefresh() {
  if (searchTimer) clearTimeout(searchTimer)
  void loadFiles(false)
}

// ---------- 扫描（P1-4 异步 + 进度） ----------
const scanningId = ref('')
const scanFound = ref(0)

const SCAN_POLL_MS = 1000
const SCAN_TIMEOUT_MS = 120000 // 2 分钟兜底：超时后停止轮询，避免无限轮询

function replaceRoot(updated: Partial<WorkspaceRoot> & { id: string }) {
  roots.value = roots.value.map((r) => (r.id === updated.id ? { ...r, ...updated } : r))
}

async function onScan(root: WorkspaceRoot) {
  if (scanningId.value) return toast.info('已有扫描在进行中', '请等待当前扫描完成')
  try {
    const started = await workspaceApi.scan(root.id)
    replaceRoot(started)
    scanningId.value = root.id
    scanFound.value = 0
    toast.info('开始扫描', '大目录需要一会儿，可继续做别的事')
    await pollScan(root.id)
  } catch { /* http 层已提示 */ } finally {
    scanningId.value = ''
  }
}

async function pollScan(rootId: string) {
  const deadline = Date.now() + SCAN_TIMEOUT_MS
  // 轮询到终态（ok/error）即止；超时或服务端异常也停止，不做无限循环
  for (;;) {
    await new Promise((r) => setTimeout(r, SCAN_POLL_MS))
    let prog
    try {
      prog = await workspaceApi.scanProgress(rootId)
    } catch {
      return
    }
    scanFound.value = prog.found
    replaceRoot({
      id: rootId,
      scan_status: prog.status,
      scan_error: prog.error,
      file_count: prog.file_count,
    })
    if (prog.status === 'ok') {
      toast.success('扫描完成', `${prog.file_count} 个条目已索引`)
      if (rootId === activeRootId.value) await loadFiles(false)
      return
    }
    if (prog.status === 'error') {
      toast.error('扫描失败', prog.error ?? (prog.interrupted ? '扫描被中断' : '未知原因'))
      return
    }
    if (Date.now() > deadline) {
      toast.warning('扫描仍在进行', '已停止等待，可稍后刷新查看结果')
      return
    }
  }
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
      filesPage.value = 1
    }
    await loadRoots()
  } catch { /* http 层已提示 */ }
}

// ---------- 移动端动作菜单（PRD §5.2） ----------
const { isMobile } = useDevice()
const sheetOpen = ref(false)
const sheetFile = ref<WorkspaceFile | null>(null)

const sheetActions = computed<SheetAction[]>(() => [
  { key: 'terminal', label: '在父目录打开终端', icon: 'command', hint: '白名单动作：只打开目录' },
  { key: 'copy', label: '复制路径', icon: 'copy' },
])

function openSheet(file: WorkspaceFile) {
  sheetFile.value = file
  sheetOpen.value = true
}

function fullPathOf(file: WorkspaceFile): string {
  if (!activeRoot.value) return file.rel_path
  const full = `${activeRoot.value.path}/${file.rel_path}`
  if (file.is_dir) return full
  return full.slice(0, full.lastIndexOf('/')) || activeRoot.value.path
}

async function onSheetSelect(key: string) {
  const file = sheetFile.value
  if (!file) return
  if (key === 'terminal') {
    openFileRoot(file)
  } else if (key === 'copy') {
    const path = fullPathOf(file)
    try {
      await navigator.clipboard.writeText(path)
      toast.success('路径已复制', path)
    } catch {
      // 非安全上下文（http）下 Clipboard API 不可用 → 回退到输入框选择
      toast.error('复制失败', '当前环境不允许访问剪贴板')
    }
  }
  sheetFile.value = null
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
          @click="activeRootId = r.id; loadFiles(false)"
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
            placeholder="按文件名搜索…（输入即搜）"
            @update:model-value="onSearchInput"
          />
          <BaseButton size="sm" variant="secondary" icon="reload" :loading="filesLoading" @click="onRefresh">
            刷新
          </BaseButton>
          <BaseButton
            size="sm"
            variant="secondary"
            icon="command"
            :loading="scanningId === activeRoot.id"
            :disabled="Boolean(scanningId) && scanningId !== activeRoot.id"
            @click="onScan(activeRoot)"
          >
            {{ scanningId === activeRoot.id ? `扫描中 ${scanFound}` : '重新扫描' }}
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
          <span v-if="scanningId === activeRoot.id" class="ws__scan-hint">
            · 正在扫描，已发现 {{ scanFound }} 项
          </span>
          <span class="ws__total-hint">（搜索命中 {{ filesTotal }}）</span>
        </p>

        <div v-if="filesLoading"><BaseSkeleton variant="list" :rows="5" /></div>
        <BaseEmpty v-else-if="files.length === 0" description="没有匹配的条目" />
        <ul v-else class="ws__list">
          <li
            v-for="f in files"
            :key="f.id"
            class="ws__file"
            :tabindex="isMobile ? 0 : -1"
            @dblclick="!isMobile && openFileRoot(f)"
            @click="isMobile && openSheet(f)"
            @keyup.enter="isMobile && openSheet(f)"
          >
            <AppIcon :name="f.is_dir ? 'folder' : 'doc'" :size="14" />
            <span class="ws__file-name">{{ f.name }}</span>
            <span class="ws__file-dir">{{ f.rel_path }}</span>
            <span class="ws__file-size">{{ f.is_dir ? '—' : formatSize(f.size) }}</span>
          </li>
        </ul>
        <div v-if="hasMore && !filesLoading" class="ws__loadmore">
          <BaseButton
            size="sm"
            variant="secondary"
            :loading="loadingMore"
            @click="loadMore"
          >
            加载更多（已显示 {{ files.length }} / {{ filesTotal }}）
          </BaseButton>
        </div>
        <p v-else-if="!hasMore && files.length > 0" class="ws__loadmore-hint">
          已显示全部 {{ filesTotal }} 条
        </p>
        <p class="ws__tip">
          {{ isMobile ? '点击条目选择操作（终端为唯一白名单动作）' : '双击条目可在其所在文件夹打开终端（唯一白名单动作）' }}
        </p>

        <!-- 移动端动作菜单（PRD §5.2：双击在移动端不存在，改为点击弹底部菜单） -->
        <ActionSheet
          v-model="sheetOpen"
          :title="sheetFile?.name ?? ''"
          :actions="sheetActions"
          @select="onSheetSelect"
        />
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

.ws__loadmore {
  display: flex;
  justify-content: center;
  padding: var(--space-3) 0 var(--space-1);
}

.ws__loadmore-hint {
  margin: var(--space-3) 0 0;
  text-align: center;
  font-size: var(--text-xs);
  color: var(--text-low);
}

.ws__scan-hint {
  color: var(--primary-ink);
  font-weight: 600;
}
</style>
