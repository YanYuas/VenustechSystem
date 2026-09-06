<script setup lang="ts">
// ============================================================
// 项目详情页 —— M06 F01/F02/F03/F08
// 顶部信息 + 统计（环形进度/分布/趋势/健康度）+ 五 Tab
// （任务/文档/对话/复盘/里程碑）+ 任务内联添加 + 文档内联创建
// ============================================================
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs from 'dayjs'
import JSZip from 'jszip'
import { projectApi, taskApi, documentApi, conversationApi } from '@/api'
import { useToast } from '@/composables/useToast'
import { useModal } from '@/composables/useModal'
import BaseCard from '@/components/common/BaseCard.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import BaseInput from '@/components/common/BaseInput.vue'
import BaseTag from '@/components/common/BaseTag.vue'
import BaseModal from '@/components/common/BaseModal.vue'
import BaseEmpty from '@/components/common/BaseEmpty.vue'
import BaseSkeleton from '@/components/common/BaseSkeleton.vue'
import AppIcon from '@/components/common/AppIcon.vue'
import type { ProjectDetail, ProjectStats, Milestone, TaskStatus } from '@/types'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const modal = useModal()

const projectId = route.params.id as string

const detail = ref<ProjectDetail | null>(null)
const stats = ref<ProjectStats | null>(null)
const loading = ref(true)

async function load() {
  loading.value = true
  try {
    const [d, s] = await Promise.all([
      projectApi.detail(projectId),
      projectApi.stats(projectId).catch(() => null),
    ])
    detail.value = d
    stats.value = s
  } catch {
    toast.error('加载失败', '项目不存在或已被删除')
    router.replace('/projects')
  } finally {
    loading.value = false
  }
}

onMounted(load)

// ---------- 顶部信息与操作 ----------

const STATUS_META: Record<string, { label: string; semantic: 'mint' | 'default' | 'butter' }> = {
  active: { label: '进行中', semantic: 'mint' },
  archived: { label: '已归档', semantic: 'default' },
  completed: { label: '已完成', semantic: 'butter' },
}

const HEALTH_META: Record<string, { label: string; semantic: 'mint' | 'butter' | 'straw'; icon: string }> = {
  good: { label: '状态健康', semantic: 'mint', icon: 'check' },
  warning: { label: '进度滞后', semantic: 'butter', icon: 'warning' },
  risk: { label: '存在逾期', semantic: 'straw', icon: 'warning' },
}

const statusMeta = computed(() => STATUS_META[detail.value?.status ?? 'active'] ?? STATUS_META.active)
const healthMeta = computed(() => HEALTH_META[stats.value?.health ?? 'good'] ?? HEALTH_META.good)
const isArchived = computed(() => detail.value?.status === 'archived')

async function onArchiveToggle() {
  try {
    if (isArchived.value) {
      await projectApi.restore(projectId)
      toast.success('项目已恢复')
    } else {
      const ok = await modal.confirm({
        title: '归档项目',
        message: `归档「${detail.value?.name}」后其任务将变为只读，可随时恢复。`,
        confirmText: '归档',
      })
      if (!ok) return
      await projectApi.archive(projectId)
      toast.success('项目已归档')
    }
    await load()
  } catch { /* http 层已提示 */ }
}

async function onDelete() {
  const ok = await modal.confirm({
    title: '删除项目',
    message: `确定删除「${detail.value?.name}」吗？项目内任务/文档不会被删除，仅解除关联。`,
    confirmText: '删除',
  })
  if (!ok) return
  try {
    await projectApi.remove(projectId)
    toast.success('项目已删除')
    router.replace('/projects')
  } catch { /* http 层已提示 */ }
}


// ---------- 时间线（M06 F05） ----------
const timeline = ref<Array<{ type: string; title: string; time: string; icon: string }>>([])
const timelineLoading = ref(false)

async function loadTimeline() {
  timelineLoading.value = true
  try {
    timeline.value = await projectApi.timeline(projectId)
  } catch { /* http层已提示 */ } finally {
    timelineLoading.value = false
  }
}

// ---------- 项目导出（M06 F07） ----------
const exporting = ref(false)
async function onExport() {
  if (exporting.value) return
  exporting.value = true
  try {
    const data = await projectApi.exportData(projectId)
    const zip = new JSZip()
    const folder = zip.folder(data.project.name || 'project')!
    // 元数据
    folder.file('project.json', JSON.stringify(data.project, null, 2))
    // 任务
    folder.file('tasks.json', JSON.stringify(data.tasks, null, 2))
    // 文档（MD）
    const docFolder = folder.folder('documents')!
    for (const d of data.documents) {
      const safeName = (d.title || 'untitled').replace(/[\\/:*?"<>|]/g, '_')
      docFolder.file(`${safeName}.md`, `# ${d.title}\n\n${d.content || ''}\n`)
    }
    // 对话
    folder.file('conversations.json', JSON.stringify(data.conversations, null, 2))
    // 复盘（MD）
    const reviewFolder = folder.folder('reviews')!
    for (const r of data.reviews) {
      const safeName = (r.title || 'review').replace(/[\\/:*?"<>|]/g, '_')
      reviewFolder.file(`${safeName}.md`, `# ${r.title || '复盘'}\n\n${r.content || ''}\n`)
    }
    const blob = await zip.generateAsync({ type: 'blob' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${data.project.name || 'project'}-export.zip`
    a.click()
    URL.revokeObjectURL(url)
    toast.success('导出成功', `共 ${data.tasks.length} 任务 / ${data.documents.length} 文档`)
  } catch {
    toast.error('导出失败')
  } finally {
    exporting.value = false
  }
}
// ---------- 统计区（M06 F02） ----------

const circumference = 2 * Math.PI * 40
const ringDash = computed(() => {
  const p = stats.value?.progress ?? 0
  return `${(p / 100) * circumference} ${circumference}`
})

const STATUS_LABELS: Record<string, string> = {
  pending: '待办', in_progress: '进行中', waiting: '等待', completed: '已完成',
}
const distribution = computed(() =>
  Object.entries(stats.value?.status_distribution ?? {}).map(([k, v]) => ({
    key: k, label: STATUS_LABELS[k] ?? k, count: v,
  })),
)
const maxTrend = computed(() =>
  Math.max(1, ...(stats.value?.weekly_trend ?? []).map((t) => t.completed)),
)

// ---------- Tab 切换 ----------

type TabKey = 'tasks' | 'documents' | 'conversations' | 'reviews' | 'milestones' | 'timeline'
const TABS: Array<{ key: TabKey; label: string; icon: string }> = [
  { key: 'tasks', label: '任务', icon: 'check' },
  { key: 'documents', label: '文档', icon: 'doc' },
  { key: 'conversations', label: '对话', icon: 'send' },
  { key: 'reviews', label: '复盘', icon: 'refresh' },
  { key: 'milestones', label: '里程碑', icon: 'target' },
  { key: 'timeline', label: '动态', icon: 'clock' },
]
const activeTab = ref<TabKey>('tasks')
function onTabChange(key: TabKey) {
  activeTab.value = key
  if (key === 'timeline' && !timeline.value.length) loadTimeline()
}

// ---------- 任务 Tab：勾选 + 内联添加（M06 F08） ----------

const newTaskTitle = ref('')
const addingTask = ref(false)

async function addTask() {
  const title = newTaskTitle.value.trim()
  if (!title) return
  addingTask.value = true
  try {
    await taskApi.create({ title, project_id: projectId })
    newTaskTitle.value = ''
    toast.success('任务已添加')
    await load()
  } catch { /* http 层已提示 */ } finally {
    addingTask.value = false
  }
}

async function toggleTask(taskId: string, current: string) {
  const next: TaskStatus = current === 'completed' ? 'pending' : 'completed'
  try {
    await taskApi.update(taskId, { status: next })
    await load()
  } catch { /* http 层已提示 */ }
}

function goTasks() {
  router.push({ path: '/tasks', query: { project_id: projectId } })
}

// ---------- 文档 Tab：内联创建（M06 F08） ----------

const newDocTitle = ref('')
const addingDoc = ref(false)

async function addDoc() {
  const title = newDocTitle.value.trim()
  if (!title) return
  addingDoc.value = true
  try {
    await documentApi.create({ title, project_id: projectId })
    newDocTitle.value = ''
    toast.success('文档已创建', '到知识模块编辑内容')
    await load()
  } catch { /* http 层已提示 */ } finally {
    addingDoc.value = false
  }
}

function goDoc(docId: string) {
  router.push({ path: '/documents', query: { open: docId } })
}

// ---------- 对话 Tab：快速发起项目对话（M06 F08） ----------

async function startConversation() {
  try {
    await conversationApi.create(`项目：${detail.value?.name ?? ''}`, projectId)
    router.push('/conversation')
  } catch { /* http 层已提示 */ }
}

// ---------- 里程碑 Tab：CRUD（M06 F03） ----------

const msModalOpen = ref(false)
const msForm = ref({ name: '', description: '', target_date: '' })
const editingMs = ref<Milestone | null>(null)

function openMsCreate() {
  editingMs.value = null
  msForm.value = { name: '', description: '', target_date: '' }
  msModalOpen.value = true
}

function openMsEdit(m: Milestone) {
  editingMs.value = m
  msForm.value = {
    name: m.name,
    description: m.description ?? '',
    target_date: m.target_date ?? '',
  }
  msModalOpen.value = true
}

async function onMsSubmit() {
  const name = msForm.value.name.trim()
  if (!name) return toast.warning('请输入里程碑名称')
  try {
    if (editingMs.value) {
      await projectApi.updateMilestone(editingMs.value.id, {
        name,
        description: msForm.value.description || undefined,
        target_date: msForm.value.target_date || undefined,
      })
      toast.success('里程碑已更新')
    } else {
      await projectApi.createMilestone(projectId, {
        name,
        description: msForm.value.description || undefined,
        target_date: msForm.value.target_date || undefined,
      })
      toast.success('里程碑已创建')
    }
    msModalOpen.value = false
    await load()
  } catch { /* http 层已提示 */ }
}

async function toggleMs(m: Milestone) {
  try {
    await projectApi.updateMilestone(m.id, { completed: !m.completed })
    await load()
  } catch { /* http 层已提示 */ }
}

async function deleteMs(m: Milestone) {
  const ok = await modal.confirm({
    title: '删除里程碑', message: `确定删除「${m.name}」吗？`, confirmText: '删除',
  })
  if (!ok) return
  try {
    await projectApi.removeMilestone(m.id)
    toast.success('里程碑已删除')
    await load()
  } catch { /* http 层已提示 */ }
}

const msProgress = computed(() => {
  const list = detail.value?.milestones ?? []
  if (!list.length) return 0
  return Math.round((list.filter((m) => m.completed).length / list.length) * 100)
})

// ---------- 工具 ----------

function fmtDateTime(v: string | null): string {
  return v ? dayjs(v).format('MM-DD HH:mm') : ''
}
</script>

<template>
  <div class="pd">
    <template v-if="loading">
      <BaseSkeleton variant="card" :rows="6" />
    </template>

    <template v-else-if="detail">
      <!-- 顶部信息区 -->
      <div class="pd__hero" :style="{ '--project-color': detail.color }">
        <div class="pd__hero-main">
          <div class="pd__hero-title-row">
            <span class="pd__color-dot" />
            <h1 class="pd__title">{{ detail.name }}</h1>
            <BaseTag :semantic="statusMeta.semantic">{{ statusMeta.label }}</BaseTag>
            <BaseTag v-if="stats" :semantic="healthMeta.semantic">
              <AppIcon :name="healthMeta.icon" :size="12" /> {{ healthMeta.label }}
            </BaseTag>
          </div>
          <p v-if="detail.description" class="pd__desc">{{ detail.description }}</p>
          <div class="pd__meta">
            <span v-if="detail.due_date"><AppIcon name="calendar" :size="13" /> 截止 {{ detail.due_date }}</span>
            <span><AppIcon name="check" :size="13" /> {{ detail.completed_count }}/{{ detail.task_count }} 任务完成</span>
            <span v-if="stats?.overdue_count" class="pd__overdue">
              <AppIcon name="warning" :size="13" /> {{ stats.overdue_count }} 项逾期
            </span>
            <span>创建于 {{ fmtDateTime(detail.created_at) }}</span>
          </div>
        </div>
        <div class="pd__hero-actions">
          <BaseButton variant="secondary" size="sm" @click="router.push('/projects')">
            <AppIcon name="arrow-left" :size="14" /> 返回列表
          </BaseButton>
          <BaseButton variant="secondary" size="sm" :loading="exporting" @click="onExport"><AppIcon name="download" :size="14" /> 导出</BaseButton>`n          <BaseButton variant="secondary" size="sm" @click="onArchiveToggle">
            {{ isArchived ? '恢复项目' : '归档' }}
          </BaseButton>
          <BaseButton variant="danger" size="sm" @click="onDelete">删除</BaseButton>
        </div>
      </div>

      <!-- 统计区（M06 F02） -->
      <div v-if="stats" class="pd__stats">
        <BaseCard class="pd__stat-ring">
          <svg viewBox="0 0 100 100" class="pd__ring">
            <circle cx="50" cy="50" r="40" class="pd__ring-bg" />
            <circle
              cx="50" cy="50" r="40" class="pd__ring-fill"
              :stroke-dasharray="ringDash"
              :stroke="detail.color"
            />
          </svg>
          <div class="pd__ring-center">
            <span class="pd__ring-num">{{ stats.progress }}%</span>
            <span class="pd__ring-label">完成率</span>
          </div>
        </BaseCard>

        <BaseCard class="pd__stat-block">
          <h4 class="pd__stat-title">任务分布</h4>
          <div class="pd__dist">
            <div v-for="d in distribution" :key="d.key" class="pd__dist-item">
              <span class="pd__dist-label">{{ d.label }}</span>
              <div class="pd__dist-bar">
                <div
                  class="pd__dist-fill"
                  :style="{ width: `${(d.count / Math.max(1, stats.task_count)) * 100}%` }"
                />
              </div>
              <span class="pd__dist-count">{{ d.count }}</span>
            </div>
            <p v-if="!distribution.length" class="pd__muted">暂无任务</p>
          </div>
        </BaseCard>

        <BaseCard class="pd__stat-block">
          <h4 class="pd__stat-title">近 7 天完成趋势</h4>
          <div class="pd__trend">
            <div v-for="t in stats.weekly_trend" :key="t.date" class="pd__trend-col">
              <div class="pd__trend-bar-wrap">
                <div
                  class="pd__trend-bar"
                  :style="{ height: `${(t.completed / maxTrend) * 100}%` }"
                  :title="`${t.date}：完成 ${t.completed}`"
                />
              </div>
              <span class="pd__trend-day">{{ t.date.slice(5) }}</span>
            </div>
          </div>
        </BaseCard>

        <BaseCard class="pd__stat-block">
          <h4 class="pd__stat-title">里程碑</h4>
          <p class="pd__ms-big">{{ stats.milestone_completed }}/{{ stats.milestone_count }}</p>
          <div class="pd__bar"><div class="pd__bar-fill" :style="{ width: msProgress + '%' }" /></div>
          <p class="pd__muted">已完成里程碑占比</p>
        </BaseCard>
      </div>

      <!-- Tab 导航 -->
      <div class="pd__tabs">
        <button
          v-for="t in TABS" :key="t.key"
          class="pd__tab" :class="{ 'is-active': activeTab === t.key }"
          @click="onTabChange(t.key)"
        >
          <AppIcon :name="t.icon" :size="14" />
          {{ t.label }}
          <span class="pd__tab-count">
            {{ t.key === 'timeline' ? timeline.length : (detail[t.key as Exclude<TabKey, 'timeline'> ] as unknown[]).length }}
          </span>
        </button>
      </div>

      <!-- 任务 Tab -->
      <BaseCard v-if="activeTab === 'tasks'">
        <div v-if="!isArchived" class="pd__inline-add">
          <BaseInput
            v-model="newTaskTitle"
            placeholder="快速添加任务（自动归属本项目）…"
            :disabled="addingTask"
            @keyup.enter="addTask"
          />
          <BaseButton variant="primary" size="sm" :loading="addingTask" @click="addTask">添加</BaseButton>
        </div>
        <ul v-if="detail.tasks.length" class="pd__list">
          <li v-for="t in detail.tasks" :key="t.id" class="pd__task">
            <button class="pd__check" :class="{ 'is-checked': t.status === 'completed' }" @click="toggleTask(t.id, t.status)">
              <AppIcon v-if="t.status === 'completed'" name="check" :size="12" />
            </button>
            <span class="pd__task-title" :class="{ 'is-done': t.status === 'completed' }">{{ t.title }}</span>
            <BaseTag v-if="t.is_focus" semantic="gold" size="sm">焦点</BaseTag>
            <span v-if="t.due_date" class="pd__task-due">{{ t.due_date }}</span>
          </li>
        </ul>
        <BaseEmpty v-else title="项目内暂无任务" description="在上方快速添加第一个任务">
          <template #action>
            <BaseButton variant="secondary" size="sm" @click="goTasks">到任务模块查看全部</BaseButton>
          </template>
        </BaseEmpty>
      </BaseCard>

      <!-- 文档 Tab -->
      <BaseCard v-else-if="activeTab === 'documents'">
        <div v-if="!isArchived" class="pd__inline-add">
          <BaseInput
            v-model="newDocTitle"
            placeholder="快速创建项目文档…"
            :disabled="addingDoc"
            @keyup.enter="addDoc"
          />
          <BaseButton variant="primary" size="sm" :loading="addingDoc" @click="addDoc">创建</BaseButton>
        </div>
        <ul v-if="detail.documents.length" class="pd__list">
          <li v-for="d in detail.documents" :key="d.id" class="pd__row" @click="goDoc(d.id)">
            <AppIcon name="doc" :size="16" class="pd__row-icon" />
            <span class="pd__row-title">{{ d.title }}</span>
            <span class="pd__row-meta">{{ d.word_count }} 字 · {{ fmtDateTime(d.updated_at) }}</span>
          </li>
        </ul>
        <BaseEmpty v-else title="项目内暂无文档" description="在上方快速创建，或到知识模块编辑时选择归属项目" />
      </BaseCard>

      <!-- 对话 Tab -->
      <BaseCard v-else-if="activeTab === 'conversations'">
        <ul v-if="detail.conversations.length" class="pd__list">
          <li v-for="c in detail.conversations" :key="c.id" class="pd__row" @click="router.push('/conversation')">
            <AppIcon name="send" :size="16" class="pd__row-icon" />
            <span class="pd__row-title">{{ c.title }}</span>
            <span class="pd__row-meta">{{ fmtDateTime(c.updated_at) }}</span>
          </li>
        </ul>
        <BaseEmpty v-else title="暂无项目相关对话" description="发起一个带项目上下文的对话，让第二分身帮你推进">
          <template #action>
            <BaseButton variant="primary" size="sm" @click="startConversation">发起对话</BaseButton>
          </template>
        </BaseEmpty>
      </BaseCard>

      <!-- 复盘 Tab -->
      <BaseCard v-else-if="activeTab === 'reviews'">
        <ul v-if="detail.reviews.length" class="pd__list">
          <li v-for="r in detail.reviews" :key="r.id" class="pd__row" @click="router.push('/review')">
            <AppIcon name="refresh" :size="16" class="pd__row-icon" />
            <span class="pd__row-title">{{ r.review_date }} 复盘</span>
            <span v-if="r.mood" class="pd__row-meta">心情 {{ '★'.repeat(r.mood) }}</span>
            <span class="pd__row-meta pd__row-summary">{{ r.summary || '（未填写收获）' }}</span>
          </li>
        </ul>
        <BaseEmpty v-else title="暂无项目相关复盘" description="写复盘时可关联本项目" />
      </BaseCard>

      <!-- 里程碑 Tab -->
      <BaseCard v-else-if="activeTab === 'milestones'">
        <div class="pd__inline-add">
          <p class="pd__muted" style="flex:1">里程碑：{{ msProgress }}% 完成（{{ detail.milestones.filter(m => m.completed).length }}/{{ detail.milestones.length }}）</p>
          <BaseButton variant="primary" size="sm" icon="plus" @click="openMsCreate">新建里程碑</BaseButton>
        </div>
        <ul v-if="detail.milestones.length" class="pd__list">
          <li v-for="m in detail.milestones" :key="m.id" class="pd__ms">
            <button class="pd__check" :class="{ 'is-checked': m.completed }" @click="toggleMs(m)">
              <AppIcon v-if="m.completed" name="check" :size="12" />
            </button>
            <div class="pd__ms-body">
              <div class="pd__ms-head">
                <span class="pd__ms-name" :class="{ 'is-done': m.completed }">{{ m.name }}</span>
                <span v-if="m.target_date" class="pd__ms-date" :class="{ 'is-overdue': !m.completed && m.target_date < dayjs().format('YYYY-MM-DD') }">
                  <AppIcon name="calendar" :size="12" /> {{ m.target_date }}
                </span>
              </div>
              <p v-if="m.description" class="pd__ms-desc">{{ m.description }}</p>
              <p v-if="m.completed_at" class="pd__muted">完成于 {{ fmtDateTime(m.completed_at) }}</p>
            </div>
            <div class="pd__ms-ops">
              <button class="pd__op" title="编辑" @click="openMsEdit(m)"><AppIcon name="edit" :size="14" /></button>
              <button class="pd__op pd__op--danger" title="删除" @click="deleteMs(m)"><AppIcon name="trash" :size="14" /></button>
            </div>
          </li>
        </ul>
        <BaseEmpty v-else title="暂无里程碑" description="为项目设定关键节点，追踪重要进展">
          <template #action>
            <BaseButton variant="primary" size="sm" @click="openMsCreate">创建第一个里程碑</BaseButton>
          </template>
        </BaseEmpty>
      </BaseCard>
    </template>

    <!-- 里程碑新建/编辑弹窗 -->
    <BaseModal
      v-model="msModalOpen"
      :title="editingMs ? '编辑里程碑' : '新建里程碑'"
      @confirm="onMsSubmit"
    >
      <div class="pd__form">
        <BaseInput v-model="msForm.name" placeholder="里程碑名称（必填）" />
        <input v-model="msForm.target_date" type="date" class="pd__date" />
        <textarea v-model="msForm.description" class="pd__textarea" placeholder="描述（可选）" rows="3" />
      </div>
    </BaseModal>
  </div>
</template>

<style scoped lang="scss">
.pd {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  max-width: 960px;
  margin: 0 auto;

  &__hero {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
    padding: var(--space-5);
    background: linear-gradient(135deg, color-mix(in srgb, var(--project-color, #7c5cff) 12%, transparent), var(--bg-panel));
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
  }
  &__hero-main { flex: 1; min-width: 0; }
  &__hero-title-row { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
  &__color-dot {
    width: 14px; height: 14px; border-radius: 50%;
    background: var(--project-color, #7c5cff); flex-shrink: 0;
  }
  &__title { font-size: var(--text-2xl); font-weight: 700; font-family: var(--font-cute); }
  &__desc { margin-top: var(--space-2); color: var(--text-mid); line-height: 1.6; }
  &__meta {
    display: flex; flex-wrap: wrap; gap: var(--space-4); margin-top: var(--space-3);
    font-size: var(--text-sm); color: var(--text-low);
    span { display: inline-flex; align-items: center; gap: 4px; }
  }
  &__overdue { color: var(--strawberry); }
  &__hero-actions { display: flex; flex-direction: column; gap: var(--space-2); flex-shrink: 0; }

  &__stats {
    display: grid;
    grid-template-columns: 200px repeat(3, 1fr);
    gap: var(--space-3);
  }
  &__stat-ring { position: relative; display: flex; align-items: center; justify-content: center; }
  &__ring { width: 130px; height: 130px; transform: rotate(-90deg); }
  &__ring-bg { fill: none; stroke: var(--bg-inset); stroke-width: 10; }
  &__ring-fill {
    fill: none; stroke-width: 10; stroke-linecap: round;
    transition: stroke-dasharray 0.6s var(--ease-soft);
  }
  &__ring-center {
    position: absolute; display: flex; flex-direction: column; align-items: center;
  }
  &__ring-num { font-size: var(--text-xl); font-weight: 700; color: var(--text-hi); }
  &__ring-label { font-size: var(--text-xs); color: var(--text-low); }
  &__stat-block { display: flex; flex-direction: column; }
  &__stat-title { font-size: var(--text-sm); font-weight: 600; color: var(--text-hi); margin-bottom: var(--space-2); }
  &__ms-big { font-size: var(--text-xl); font-weight: 700; color: var(--primary); }
  &__bar {
    height: 6px; border-radius: var(--radius-pill);
    background: var(--bg-inset); overflow: hidden; margin: var(--space-2) 0 var(--space-1);
  }
  &__bar-fill { height: 100%; background: var(--primary); border-radius: var(--radius-pill); transition: width 0.4s; }
  &__muted { font-size: var(--text-xs); color: var(--text-low); }

  &__dist { display: flex; flex-direction: column; gap: var(--space-2); }
  &__dist-item { display: flex; align-items: center; gap: var(--space-2); }
  &__dist-label { font-size: var(--text-xs); color: var(--text-mid); width: 40px; flex-shrink: 0; }
  &__dist-bar { flex: 1; height: 6px; border-radius: var(--radius-pill); background: var(--bg-inset); overflow: hidden; }
  &__dist-fill { height: 100%; background: var(--primary); transition: width 0.4s; }
  &__dist-count { font-size: var(--text-xs); color: var(--text-hi); width: 24px; text-align: right; }

  &__trend { display: flex; align-items: flex-end; gap: var(--space-1); flex: 1; }
  &__trend-col { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; }
  &__trend-bar-wrap { height: 60px; width: 100%; display: flex; align-items: flex-end; justify-content: center; }
  &__trend-bar {
    width: 60%; min-height: 2px; border-radius: 2px 2px 0 0;
    background: var(--primary); opacity: 0.75; transition: height 0.4s;
  }
  &__trend-day { font-size: 10px; color: var(--text-low); }

  &__tabs { display: flex; gap: var(--space-2); flex-wrap: wrap; }
  &__tab {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 6px 16px; border-radius: var(--radius-pill);
    border: 1px solid var(--line); background: var(--bg-panel);
    color: var(--text-mid); font-size: var(--text-sm); cursor: pointer;
    transition: all 0.15s var(--ease-soft);
    &:hover { border-color: var(--primary); color: var(--primary); }
    &.is-active { background: var(--primary); border-color: var(--primary); color: #fff; }
  }
  &__tab-count {
    font-size: var(--text-xs); padding: 0 6px; border-radius: var(--radius-pill);
    background: var(--bg-inset);
    .is-active & { background: rgba(255,255,255,0.2); }
  }

  &__inline-add { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); }

  &__list { list-style: none; display: flex; flex-direction: column; }
  &__task { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-2) var(--space-3); border-bottom: 1px solid var(--line); &:last-child { border-bottom: none; } }
  &__task-title { flex: 1; min-width: 0; font-size: var(--text-base); color: var(--text-hi); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; &.is-done { text-decoration: line-through; color: var(--text-low); } }
  &__task-due { font-size: var(--text-xs); color: var(--text-low); flex-shrink: 0; }
  &__check {
    width: 20px; height: 20px; border-radius: 50%; border: 2px solid var(--line);
    background: transparent; display: flex; align-items: center; justify-content: center;
    color: #fff; cursor: pointer; flex-shrink: 0;
    &.is-checked { background: var(--mint, #3ddc97); border-color: var(--mint, #3ddc97); }
  }

  &__row {
    display: flex; align-items: center; gap: var(--space-3);
    padding: var(--space-2) var(--space-3); border-bottom: 1px solid var(--line);
    cursor: pointer; &:last-child { border-bottom: none; }
    &:hover { background: var(--bg-soft, rgba(0,0,0,0.03)); }
  }
  &__row-icon { color: var(--text-low); flex-shrink: 0; }
  &__row-title { font-size: var(--text-base); color: var(--text-hi); }
  &__row-meta { font-size: var(--text-xs); color: var(--text-low); flex-shrink: 0; }
  &__row-summary {
    flex: 1; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    max-width: 300px;
  }

  &__ms { display: flex; align-items: flex-start; gap: var(--space-3); padding: var(--space-3); border-bottom: 1px solid var(--line); &:last-child { border-bottom: none; } }
  &__ms-body { flex: 1; min-width: 0; }
  &__ms-head { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
  &__ms-name { font-size: var(--text-base); font-weight: 500; color: var(--text-hi); &.is-done { text-decoration: line-through; color: var(--text-low); } }
  &__ms-date {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: var(--text-xs); color: var(--text-low);
    &.is-overdue { color: var(--strawberry); }
  }
  &__ms-desc { margin-top: 4px; font-size: var(--text-sm); color: var(--text-mid); }
  &__ms-ops { display: flex; gap: var(--space-1); }
  &__op {
    padding: 4px; border: none; background: transparent; color: var(--text-low);
    border-radius: var(--radius-sm); cursor: pointer;
    &:hover { background: var(--bg-inset); color: var(--text-hi); }
    &--danger:hover { color: var(--strawberry); }
  }

  &__form { display: flex; flex-direction: column; gap: var(--space-3); }
  &__date {
    padding: 8px 12px; border: 1px solid var(--line); border-radius: var(--radius-sm);
    background: var(--bg-panel); color: var(--text-hi); font-size: var(--text-sm);
  }
  &__textarea {
    padding: 8px 12px; border: 1px solid var(--line); border-radius: var(--radius-sm);
    background: var(--bg-panel); color: var(--text-hi); font-size: var(--text-sm);
    resize: vertical; font-family: inherit;
  }
}

@media (max-width: 1024px) {
  .pd__stats { grid-template-columns: repeat(2, 1fr); }
  .pd__stat-ring { grid-column: span 2; }
}
  // 时间线（M06 F05）
  &__timeline {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding: var(--space-2) 0;
  }
  &__tl-item {
    display: flex;
    gap: var(--space-3);
    align-items: flex-start;
  }
  &__tl-dot {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: var(--primary-soft);
    color: var(--primary);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    margin-top: 2px;
  }
  &__tl-content {
    display: flex;
    flex-direction: column;
    gap: 2px;
    flex: 1;
    padding-bottom: var(--space-2);
    border-bottom: 1px dashed var(--line);
  }
  &__tl-title {
    font-size: var(--text-sm);
    color: var(--text-hi);
  }
  &__tl-time {
    font-size: var(--text-xs);
    color: var(--text-low);
  }
</style>
