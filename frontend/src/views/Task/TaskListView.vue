<script setup lang="ts">
// ============================================================
// 任务列表 —— 深化版（详情抽屉 + 子任务管理 + 完整编辑）
// ============================================================
import { ref, computed, onMounted } from 'vue'
import { useTask } from '@/composables/useTask'
import { useToast } from '@/composables/useToast'
import { useModal } from '@/composables/useModal'
import { emitPetAction } from '@/composables/usePetEvent'
import { taskApi, projectApi } from '@/api'
import { useRoute } from 'vue-router'
import BaseCard from '@/components/common/BaseCard.vue'
import BaseTag from '@/components/common/BaseTag.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import BaseInput from '@/components/common/BaseInput.vue'
import BaseSelect from '@/components/common/BaseSelect.vue'
import BaseModal from '@/components/common/BaseModal.vue'
import BaseDrawer from '@/components/common/BaseDrawer.vue'
import BaseEmpty from '@/components/common/BaseEmpty.vue'
import BaseSkeleton from '@/components/common/BaseSkeleton.vue'
import BasePagination from '@/components/common/BasePagination.vue'
import FocusTimer from '@/components/task/FocusTimer.vue'
import AppIcon from '@/components/common/AppIcon.vue'
import type { Task, TaskStatus, TaskPriority, Subtask } from '@/types'
import type { TagSemantic } from '@/types/common'

const { tasks, total, loading, query, fetchTasks, createTask, updateTask, deleteTask, setFocus } = useTask()
const toast = useToast()
const modal = useModal()
const route = useRoute()

const projects = ref<Array<{ id: string; name: string; color: string }>>([])
const projectOptions = computed(() => [
  { label: '不归属项目', value: '' },
  ...projects.value.map(p => ({ label: p.name, value: p.id })),
])
async function loadProjects() {
  try {
    const list = await projectApi.list()
    projects.value = list.map(p => ({ id: p.id, name: p.name, color: p.color }))
  } catch { /* ignore */ }
}

onMounted(() => {
  loadProjects()
  // 按 URL 参数组装 query 后统一发起唯一一次请求（避免双请求竞态）
  const urlProject = route.query.project_id as string
  if (urlProject) query.value.project_id = urlProject
  fetchTasks().catch(() => { /* http 层已提示 */ })
})

const STATUS_TABS: Array<{ value: TaskStatus | ''; label: string }> = [
  { value: '', label: '全部' },
  { value: 'pending', label: '待办' },
  { value: 'in_progress', label: '进行中' },
  { value: 'waiting', label: '等待' },
  { value: 'completed', label: '已完成' },
]

const STATUS_SEMANTIC: Record<string, TagSemantic> = {
  pending: 'default', in_progress: 'butter', waiting: 'lilac', completed: 'mint',
}
const PRIORITY_SEMANTIC: Record<string, TagSemantic> = {
  low: 'default', medium: 'sky', high: 'butter', urgent: 'straw',
}
const statusSemantic = (s: TaskStatus): TagSemantic => STATUS_SEMANTIC[s] ?? 'default'
const prioritySemantic = (p: string): TagSemantic => PRIORITY_SEMANTIC[p] ?? 'default'
const statusLabel = (s: TaskStatus) =>
  ({ pending: '待办', in_progress: '进行中', waiting: '等待', completed: '已完成' } as const)[s] ?? s
const priorityLabel = (p: TaskPriority) =>
  ({ low: '低', medium: '中', high: '高', urgent: '紧急' } as const)[p] ?? p

const statusOptions = STATUS_TABS.filter(t => t.value !== '').map(t => ({ label: t.label, value: t.value }))
const priorityOptions = [
  { label: '低', value: 'low' }, { label: '中', value: 'medium' },
  { label: '高', value: 'high' }, { label: '紧急', value: 'urgent' },
]

function switchTab(v: TaskStatus | '') {
  query.value.status = v || undefined
  query.value.page = 1
  fetchTasks().catch(() => { /* http 层已提示 */ })
}

// 视图切换：列表 / 看板
const viewMode = ref<'list' | 'kanban'>('list')
const draggingId = ref<string | null>(null)
const dragOverStatus = ref<TaskStatus | null>(null)

const KANBAN_COLS: Array<{ value: TaskStatus; label: string }> = [
  { value: 'pending', label: '待办' },
  { value: 'in_progress', label: '进行中' },
  { value: 'waiting', label: '等待' },
  { value: 'completed', label: '已完成' },
]

function switchView(mode: 'list' | 'kanban') {
  viewMode.value = mode
  if (mode === 'kanban') {
    query.value.status = undefined
    query.value.page = 1
    // 看板需展示各状态全量分组：临时放大分页（此前只显示当前页 20 条，列不全）
    query.value.page_size = 200
    fetchTasks().catch(() => { /* http 层已提示 */ })
  } else {
    query.value.page_size = 20
  }
}

function onPageChange(p: number) {
  query.value.page = p
  fetchTasks().catch(() => { /* http 层已提示 */ })
}

const kanbanGroups = computed(() => {
  const map: Record<TaskStatus, Task[]> = { pending: [], in_progress: [], waiting: [], completed: [] }
  for (const t of tasks.value) {
    if (t.status in map) map[t.status as TaskStatus].push(t)
  }
  return map
})

function onDragStart(t: Task) {
  draggingId.value = t.id
}

async function onDrop(status: TaskStatus) {
  const id = draggingId.value
  draggingId.value = null
  dragOverStatus.value = null
  if (!id) return
  try {
    await updateTask(id, { status })
    toast.success('已移至', KANBAN_COLS.find((c) => c.value === status)?.label ?? status)
  } catch {
    toast.error('状态流转失败', '请检查任务状态是否合法')
  }
}

// 新建任务
const createOpen = ref(false)
const newTitle = ref('')
const newPriority = ref<TaskPriority>('medium')
const newDueDate = ref('')
const newProjectId = ref('')

async function onCreate() {
  const title = newTitle.value.trim()
  if (!title) return toast.warning('请输入任务标题')
  try {
    await createTask({
      title,
      priority: newPriority.value,
      due_date: newDueDate.value || undefined,
      project_id: newProjectId.value || undefined,
    })
    toast.success('任务已创建')
    createOpen.value = false
    newTitle.value = ''
    newDueDate.value = ''
    newProjectId.value = ''
  } catch {
    // 创建失败：保留弹窗与用户输入，错误提示由 http 层统一处理
  }
}

async function onToggleStatus(t: Task) {
  const next = t.status === 'completed' ? 'pending' : 'completed'
  try {
    await updateTask(t.id, { status: next })
    emitPetAction(next === 'completed' ? 'celebrate' : 'thinking', 2500)
  } catch { /* http 层已提示 */ }
}

async function onSetFocus(t: Task) {
  try {
    await setFocus(t)
    // t.is_focus 为切换前的旧值：旧值为焦点→现在取消（sleep）；旧值非焦点→现在设为焦点（happy）
    emitPetAction(t.is_focus ? 'sleep' : 'happy', 2000)
    toast.success(t.is_focus ? '已取消今日最重要' : '已设为今日最重要')
  } catch { /* http 层已提示 */ }
}

async function onDelete(t: Task) {
  const ok = await modal.confirm({
    title: '删除任务', message: `确定删除「${t.title}」吗？删除后无法恢复。`, confirmText: '删除',
  })
  if (!ok) return
  try {
    await deleteTask(t.id)
    toast.success('任务已删除')
    if (detailTask.value?.id === t.id) detailOpen.value = false
  } catch { /* http 层已提示 */ }
}

// ========== 任务详情抽屉 ==========
const detailOpen = ref(false)
const detailTask = ref<Task | null>(null)
const detailLoading = ref(false)
const subtasks = ref<Subtask[]>([])
const newSubtask = ref('')
const editForm = ref({
  title: '', description: '', status: 'pending' as TaskStatus,
  priority: 'medium' as TaskPriority, project_tag: '', project_id: '', due_date: '',
  reminder_time: '', recurrence_type: '' as '' | 'daily' | 'weekly' | 'monthly',
})

const RECURRENCE_OPTIONS = [
  { label: '不重复', value: '' },
  { label: '每天', value: 'daily' },
  { label: '每周', value: 'weekly' },
  { label: '每月', value: 'monthly' },
]

/** ISO → datetime-local（yyyy-MM-ddTHH:mm） */
function toLocalInput(iso: string | null): string {
  if (!iso) return ''
  return iso.slice(0, 16)
}

let detailSeq = 0
async function openDetail(t: Task) {
  detailTask.value = t
  detailOpen.value = true
  detailLoading.value = true
  const mySeq = ++detailSeq
  editForm.value = {
    title: t.title, description: t.description ?? '',
    status: t.status, priority: t.priority,
    project_tag: t.project_tag ?? '', project_id: t.project_id ?? '', due_date: t.due_date ?? '',
    reminder_time: toLocalInput(t.reminder_time),
    recurrence_type: t.recurrence?.type ?? '',
  }
  try {
    const detail = await taskApi.detail(t.id)
    // 过期响应守卫：快速连点两个任务时，丢弃后到的旧详情
    if (mySeq !== detailSeq || detailTask.value?.id !== t.id) return
    subtasks.value = detail.subtasks ?? []
  } catch { /* ignore */ } finally {
    if (mySeq === detailSeq) detailLoading.value = false
  }
}

async function saveDetail() {
  if (!detailTask.value) return
  const t = detailTask.value
  const rec = editForm.value.recurrence_type
    ? { type: editForm.value.recurrence_type }
    : null
  try {
    await updateTask(t.id, {
      title: editForm.value.title,
      description: editForm.value.description,
      status: editForm.value.status,
      priority: editForm.value.priority,
      project_tag: editForm.value.project_tag || undefined,
      project_id: editForm.value.project_id || undefined,
      due_date: editForm.value.due_date || undefined,
      reminder_time: editForm.value.reminder_time || undefined,
      recurrence: rec,
    })
    detailTask.value = { ...t, ...editForm.value, description: editForm.value.description || null, project_tag: editForm.value.project_tag || null, due_date: editForm.value.due_date || null }
    toast.success('已保存')
  } catch { /* http 层已提示 */ }
}

// 抽屉内删除（M02 F03：删除按钮 + 二次确认）
async function deleteFromDetail() {
  if (!detailTask.value) return
  const t = detailTask.value
  const ok = await modal.confirm({
    title: '删除任务', message: `确定删除「${t.title}」吗？删除后无法恢复。`, confirmText: '删除',
  })
  if (!ok) return
  try {
    await deleteTask(t.id)
    detailOpen.value = false
  } catch { /* http 层已提示 */ }
}

async function addSubtask() {
  if (!detailTask.value || !newSubtask.value.trim()) return
  try {
    const sub = await taskApi.addSubtask(detailTask.value.id, newSubtask.value.trim())
    subtasks.value.push(sub)
    newSubtask.value = ''
  } catch { /* http 层已提示 */ }
}

async function toggleSubtask(sub: Subtask) {
  try {
    await taskApi.updateSubtask(detailTask.value!.id, sub.id, { completed: !sub.completed })
    sub.completed = !sub.completed
  } catch { /* http 层已提示 */ }
}

async function deleteSubtask(sub: Subtask) {
  try {
    await taskApi.removeSubtask(detailTask.value!.id, sub.id)
    subtasks.value = subtasks.value.filter(s => s.id !== sub.id)
  } catch { /* http 层已提示 */ }
}

// 子任务标题编辑（M02 F01：双击进入编辑）
const editingSubId = ref<string | null>(null)
const editingSubTitle = ref('')

function startEditSubtask(sub: Subtask) {
  editingSubId.value = sub.id
  editingSubTitle.value = sub.title
}

async function saveSubtaskEdit() {
  const subId = editingSubId.value
  if (!subId) return
  const title = editingSubTitle.value.trim()
  if (!title) {
    editingSubId.value = null
    return
  }
  const sub = subtasks.value.find(s => s.id === subId)
  try {
    await taskApi.updateSubtask(detailTask.value!.id, subId, { title })
    if (sub) sub.title = title
  } catch { /* http 层已提示 */ } finally {
    editingSubId.value = null
  }
}

// 子任务上移/下移排序（M02 F01：sort_order 调整）
async function moveSubtask(sub: Subtask, dir: -1 | 1) {
  const idx = subtasks.value.findIndex(s => s.id === sub.id)
  const target = idx + dir
  if (idx < 0 || target < 0 || target >= subtasks.value.length) return
  const list = [...subtasks.value]
  ;[list[idx], list[target]] = [list[target], list[idx]]
  try {
    // 两个受影响的子任务都提交新 sort_order
    await Promise.all([
      taskApi.updateSubtask(detailTask.value!.id, list[target].id, { sort_order: target }),
      taskApi.updateSubtask(detailTask.value!.id, list[idx].id, { sort_order: idx }),
    ])
    subtasks.value = list
  } catch { /* http 层已提示 */ }
}

// 番茄钟完成回调：刷新列表以更新 focus_duration
function onFocusFinished() {
  fetchTasks().catch(() => { /* http 层已提示 */ })
}

// ========== 批量操作（M02 F07） ==========
const batchMode = ref(false)
const selectedIds = ref<Set<string>>(new Set())

function toggleSelect(id: string) {
  const s = new Set(selectedIds.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  selectedIds.value = s
}

const allSelected = computed(() =>
  tasks.value.length > 0 && tasks.value.every(t => selectedIds.value.has(t.id)),
)

function toggleSelectAll() {
  if (allSelected.value) {
    selectedIds.value = new Set()
  } else {
    selectedIds.value = new Set(tasks.value.map(t => t.id))
  }
}

async function runBatch(action: 'complete' | 'delete' | 'move_project' | 'set_priority', extra?: { project_id?: string; priority?: TaskPriority }) {
  if (!selectedIds.value.size) return
  if (action === 'delete') {
    const ok = await modal.confirm({
      title: '批量删除',
      message: `确定删除选中的 ${selectedIds.value.size} 个任务吗？删除后无法恢复。`,
      confirmText: '删除',
    })
    if (!ok) return
  }
  try {
    const res = await taskApi.batch({
      task_ids: [...selectedIds.value],
      action,
      ...extra,
    })
    toast.success('批量操作完成', `成功 ${res.affected} 个${res.failed ? `，失败 ${res.failed} 个` : ''}`)
    selectedIds.value = new Set()
    batchMode.value = false
    fetchTasks().catch(() => { /* http 层已提示 */ })
  } catch { /* http 层已提示 */ }
}

const subtaskProgress = computed(() => {
  if (!subtasks.value.length) return 0
  const done = subtasks.value.filter(s => s.completed).length
  return Math.round((done / subtasks.value.length) * 100)
})

function formatDate(iso: string | null): string {
  if (!iso) return ''
  return iso.split('T')[0]
}
</script>

<template>
  <div class="tasks">
    <div class="tasks__head">
      <h1 class="tasks__title">任务</h1>
      <BaseButton variant="primary" icon="plus" @click="createOpen = true">新建任务</BaseButton>
    </div>

    <div class="tasks__tabs">
      <button
        v-for="tab in STATUS_TABS" :key="tab.value"
        class="tasks__tab" :class="{ 'is-active': (query.status ?? '') === tab.value }"
        @click="switchTab(tab.value)"
      >{{ tab.label }}</button>
      <div class="tasks__viewswitch">
        <button :class="{ 'is-active': viewMode === 'list' }" @click="switchView('list')">列表</button>
        <button :class="{ 'is-active': viewMode === 'kanban' }" @click="switchView('kanban')">看板</button>
        <button
          v-if="viewMode === 'list'"
          :class="{ 'is-active': batchMode }"
          @click="batchMode = !batchMode; selectedIds = new Set()"
        >批量</button>
      </div>
    </div>

    <BaseCard>
      <template v-if="loading"><BaseSkeleton variant="list" :rows="5" /></template>
      <template v-else-if="viewMode === 'kanban'">
        <div class="tasks__kanban">
          <div
            v-for="col in KANBAN_COLS" :key="col.value"
            class="tasks__col" :class="{ 'is-over': dragOverStatus === col.value }"
            @dragover.prevent="dragOverStatus = col.value"
            @dragleave="dragOverStatus = null"
            @drop.prevent="onDrop(col.value)"
          >
            <div class="tasks__col-head">
              <span>{{ col.label }}</span>
              <span class="tasks__col-count">{{ kanbanGroups[col.value].length }}</span>
            </div>
            <div class="tasks__col-body">
              <div
                v-for="t in kanbanGroups[col.value]" :key="t.id"
                class="tasks__card" draggable="true"
                :class="{ 'is-dragging': draggingId === t.id }"
                @dragstart="onDragStart(t)" @dragend="draggingId = null"
                @click="openDetail(t)"
              >
                <div class="tasks__card-line">
                  <span class="tasks__card-title">{{ t.title }}</span>
                  <BaseTag :semantic="prioritySemantic(t.priority)" size="sm">{{ priorityLabel(t.priority) }}</BaseTag>
                </div>
                <div v-if="t.subtasks_count" class="tasks__card-sub">
                  {{ t.progress }}% · {{ t.subtasks_completed }}/{{ t.subtasks_count }} 子任务
                </div>
              </div>
              <p v-if="!kanbanGroups[col.value].length" class="tasks__col-empty">拖拽任务到这里</p>
            </div>
          </div>
        </div>
      </template>
      <template v-else-if="tasks.length">
        <!-- 批量模式：全选行 -->
        <div v-if="batchMode" class="tasks__select-all">
          <label class="tasks__select-label">
            <input type="checkbox" :checked="allSelected" @change="toggleSelectAll" />
            全选（已选 {{ selectedIds.size }}/{{ tasks.length }}）
          </label>
        </div>
        <ul class="tasks__list">
          <li v-for="t in tasks" :key="t.id" class="tasks__item" :class="{ 'is-done': t.status === 'completed', 'is-selected': selectedIds.has(t.id) }">
            <input
              v-if="batchMode"
              type="checkbox"
              class="tasks__batch-check"
              :checked="selectedIds.has(t.id)"
              @change="toggleSelect(t.id)"
            />
            <button v-else class="tasks__check" :class="{ 'is-checked': t.status === 'completed' }" @click="onToggleStatus(t)">
              <AppIcon v-if="t.status === 'completed'" name="check" :size="14" />
            </button>
            <div class="tasks__main" @click="openDetail(t)">
              <div class="tasks__line">
                <span class="tasks__name">{{ t.title }}</span>
                <BaseTag v-if="t.is_focus" semantic="gold">今日最重要</BaseTag>
                <BaseTag v-if="t.project_name" semantic="lilac" size="sm">{{ t.project_name }}</BaseTag>
                <BaseTag :semantic="prioritySemantic(t.priority)">{{ priorityLabel(t.priority) }}</BaseTag>
                <BaseTag :semantic="statusSemantic(t.status)">{{ statusLabel(t.status) }}</BaseTag>
                <span v-if="t.recurrence" class="tasks__due" title="重复任务">
                  <AppIcon name="refresh" :size="12" />
                </span>
                <span v-if="t.reminder_time" class="tasks__due" title="已设提醒">
                  <AppIcon name="bell" :size="12" />
                </span>
                <span v-if="t.due_date" class="tasks__due">
                  <AppIcon name="calendar" :size="12" /> {{ formatDate(t.due_date) }}
                </span>
              </div>
              <p v-if="t.description" class="tasks__desc">{{ t.description }}</p>
              <div v-if="t.subtasks_count" class="tasks__sub">
                <div class="tasks__bar"><div class="tasks__bar-fill" :style="{ width: t.progress + '%' }" /></div>
                <span class="tasks__sub-num">{{ t.progress }}% · {{ t.subtasks_completed }}/{{ t.subtasks_count }} 子任务</span>
              </div>
            </div>
            <div class="tasks__ops">
              <button class="tasks__op" title="设为今日最重要" @click.stop="onSetFocus(t)">
                <AppIcon name="target" :size="16" :class="{ 'is-focus': t.is_focus }" />
              </button>
              <button class="tasks__op" title="编辑" @click.stop="openDetail(t)">
                <AppIcon name="edit" :size="16" />
              </button>
              <button class="tasks__op" title="删除" @click.stop="onDelete(t)">
                <AppIcon name="trash" :size="16" />
              </button>
            </div>
          </li>
        </ul>
      </template>
      <template v-else>
        <BaseEmpty title="没有符合条件的任务" description="点击右上角「新建任务」创建第一个吧">
          <template #action><BaseButton variant="primary" icon="plus" @click="createOpen = true">新建任务</BaseButton></template>
        </BaseEmpty>
      </template>
    </BaseCard>

    <!-- 分页（仅列表视图；看板展示当前页分组） -->
    <BasePagination
      v-if="viewMode === 'list' && !loading"
      :total="total"
      :page="query.page ?? 1"
      :page-size="query.page_size ?? 20"
      @change="onPageChange"
    />

    <!-- 批量操作栏（M02 F07） -->
    <Transition name="batchbar">
      <div v-if="batchMode && selectedIds.size" class="tasks__batchbar">
        <span class="tasks__batchbar-count">已选 {{ selectedIds.size }} 项</span>
        <BaseButton size="sm" variant="primary" @click="runBatch('complete')">批量完成</BaseButton>
        <BaseButton size="sm" variant="danger" @click="runBatch('delete')">批量删除</BaseButton>
        <BaseSelect
          class="tasks__batchbar-select"
          :options="projectOptions"
          placeholder="移动到项目…"
          @update:model-value="(v: string) => v && runBatch('move_project', { project_id: v })"
        />
        <BaseSelect
          class="tasks__batchbar-select"
          :options="priorityOptions"
          placeholder="改为优先级…"
          @update:model-value="(v: string) => v && runBatch('set_priority', { priority: v as TaskPriority })"
        />
      </div>
    </Transition>

    <!-- 新建任务弹窗 -->
    <BaseModal v-model="createOpen" title="新建任务" @confirm="onCreate">
      <div class="tasks__form">
        <BaseInput v-model="newTitle" placeholder="任务标题（必填）" />
        <div class="tasks__form-row">
          <BaseSelect v-model="newPriority" :options="priorityOptions" placeholder="优先级" class="tasks__form-half" />
          <input v-model="newDueDate" type="date" class="tasks__date" />
        </div>
        <BaseSelect v-model="newProjectId" :options="projectOptions" placeholder="归属项目（可选）" />
      </div>
    </BaseModal>

    <!-- 任务详情抽屉 -->
    <BaseDrawer v-model="detailOpen" title="任务详情" :width="480">
      <div v-if="detailTask" class="tasks__detail">
        <div class="tasks__detail-section">
          <label class="tasks__detail-label">标题</label>
          <BaseInput v-model="editForm.title" placeholder="任务标题" />
        </div>
        <div class="tasks__detail-section">
          <label class="tasks__detail-label">描述</label>
          <textarea v-model="editForm.description" class="tasks__textarea" placeholder="任务描述..." rows="3" />
        </div>
        <div class="tasks__detail-row">
          <div class="tasks__detail-section">
            <label class="tasks__detail-label">状态</label>
            <BaseSelect v-model="editForm.status" :options="statusOptions" />
          </div>
          <div class="tasks__detail-section">
            <label class="tasks__detail-label">优先级</label>
            <BaseSelect v-model="editForm.priority" :options="priorityOptions" />
          </div>
        </div>
        <div class="tasks__detail-row">
          <div class="tasks__detail-section">
            <label class="tasks__detail-label">截止日期</label>
            <input v-model="editForm.due_date" type="date" class="tasks__date" />
          </div>
          <div class="tasks__detail-section">
            <label class="tasks__detail-label">归属项目</label>
            <BaseSelect v-model="editForm.project_id" :options="projectOptions" />
            <label class="tasks__detail-label" style="margin-top:8px">标签（可选）</label>
            <BaseInput v-model="editForm.project_tag" placeholder="如：工作/学习" />
          </div>
        </div>

        <!-- 提醒与重复（M02 F05/F06） -->
        <div class="tasks__detail-row">
          <div class="tasks__detail-section">
            <label class="tasks__detail-label">提醒时间</label>
            <input
              v-model="editForm.reminder_time"
              type="datetime-local"
              class="tasks__date"
            />
          </div>
          <div class="tasks__detail-section">
            <label class="tasks__detail-label">重复</label>
            <BaseSelect v-model="editForm.recurrence_type" :options="RECURRENCE_OPTIONS" />
          </div>
        </div>

        <!-- 番茄钟（M02 F08） -->
        <div class="tasks__detail-section">
          <label class="tasks__detail-label">专注（番茄钟）</label>
          <div class="tasks__focus-row">
            <FocusTimer :task-id="detailTask.id" @finished="onFocusFinished" />
            <span v-if="detailTask.focus_duration" class="tasks__focus-total">
              累计专注 {{ Math.round(detailTask.focus_duration / 60) }} 分钟
            </span>
          </div>
        </div>

        <!-- 子任务 -->
        <div class="tasks__detail-section">
          <div class="tasks__detail-head">
            <label class="tasks__detail-label">子任务</label>
            <span v-if="subtasks.length" class="tasks__detail-progress">{{ subtaskProgress }}%</span>
          </div>
          <div v-if="subtasks.length" class="tasks__bar tasks__bar--full">
            <div class="tasks__bar-fill" :style="{ width: subtaskProgress + '%' }" />
          </div>
          <ul class="tasks__sub-list">
            <li v-for="(sub, i) in subtasks" :key="sub.id" class="tasks__sub-item" :class="{ 'is-done': sub.completed }">
              <button class="tasks__check tasks__check--sm" @click="toggleSubtask(sub)">
                <AppIcon v-if="sub.completed" name="check" :size="10" />
              </button>
              <!-- 双击编辑标题（M02 F01） -->
              <input
                v-if="editingSubId === sub.id"
                v-model="editingSubTitle"
                class="tasks__sub-edit"
                autofocus
                @keyup.enter="saveSubtaskEdit"
                @keyup.esc="editingSubId = null"
                @blur="saveSubtaskEdit"
              />
              <span v-else class="tasks__sub-title" @dblclick="startEditSubtask(sub)" title="双击编辑">{{ sub.title }}</span>
              <span class="tasks__sub-move">
                <button :disabled="i === 0" title="上移" @click="moveSubtask(sub, -1)"><AppIcon name="chevron-up" :size="12" /></button>
                <button :disabled="i === subtasks.length - 1" title="下移" @click="moveSubtask(sub, 1)"><AppIcon name="chevron-down" :size="12" /></button>
              </span>
              <button class="tasks__sub-del" @click="deleteSubtask(sub)"><AppIcon name="close" :size="12" /></button>
            </li>
          </ul>
          <div class="tasks__sub-add">
            <BaseInput v-model="newSubtask" placeholder="添加子任务..." @keyup.enter="addSubtask" />
            <BaseButton size="sm" @click="addSubtask">添加</BaseButton>
          </div>
        </div>

        <!-- 创建时间（M02 F03） -->
        <p v-if="detailTask.created_at" class="tasks__detail-meta">
          创建于 {{ new Date(detailTask.created_at).toLocaleString('zh-CN') }}
        </p>

        <div class="tasks__detail-actions">
          <BaseButton variant="danger" size="sm" @click="deleteFromDetail">删除任务</BaseButton>
          <BaseButton variant="secondary" @click="detailOpen = false">取消</BaseButton>
          <BaseButton variant="primary" @click="saveDetail">保存修改</BaseButton>
        </div>
      </div>
    </BaseDrawer>
  </div>
</template>

<style scoped lang="scss">
.tasks {
  display: flex; flex-direction: column; gap: var(--space-4);
  max-width: 960px; margin: 0 auto;

  &__head { display: flex; align-items: center; justify-content: space-between; }
  &__title { font-size: var(--text-2xl); font-weight: 700; font-family: var(--font-cute); }
  &__tabs { display: flex; gap: var(--space-2); align-items: center; }
  &__viewswitch {
    display: flex; margin-left: auto;
    border: 1px solid var(--line); border-radius: var(--radius-pill); overflow: hidden;
    button {
      padding: 6px 14px; border: none; background: var(--bg-panel);
      color: var(--text-mid); font-size: var(--text-sm); cursor: pointer;
      transition: background 0.15s, color 0.15s;
      &.is-active { background: var(--primary); color: #fff; }
    }
  }
  &__tab {
    padding: 6px 16px; border-radius: var(--radius-pill); border: 1px solid var(--line);
    background: var(--bg-panel); color: var(--text-mid); font-size: var(--text-sm);
    cursor: pointer; transition: all 0.15s var(--ease-soft);
    &.is-active { background: var(--primary); border-color: var(--primary); color: #fff; }
  }
  &__list { list-style: none; display: flex; flex-direction: column; }
  &__item {
    display: flex; align-items: flex-start; gap: var(--space-3);
    padding: var(--space-3) var(--space-4); border-bottom: 1px solid var(--line);
    &:last-child { border-bottom: none; }
    &:hover .tasks__ops { opacity: 1; }
    &.is-done .tasks__name { text-decoration: line-through; color: var(--text-low); }
    &.is-selected { background: var(--primary-soft); }
  }
  &__batch-check { margin-top: 4px; accent-color: var(--primary); flex-shrink: 0; }
  &__select-all {
    padding: var(--space-2) var(--space-4);
    border-bottom: 1px solid var(--line);
  }
  &__select-label {
    display: inline-flex; align-items: center; gap: var(--space-2);
    font-size: var(--text-sm); color: var(--text-mid); cursor: pointer;
    input { accent-color: var(--primary); }
  }
  &__batchbar {
    position: sticky; bottom: var(--space-3); z-index: 10;
    display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap;
    padding: var(--space-3) var(--space-4);
    background: var(--bg-raised);
    border: 1px solid var(--primary);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-raise);
  }
  &__batchbar-count { font-size: var(--text-sm); font-weight: 600; color: var(--text-hi); margin-right: auto; }
  &__batchbar-select { min-width: 140px; }
  &__check {
    width: 22px; height: 22px; border-radius: 50%; border: 2px solid var(--line);
    background: transparent; display: flex; align-items: center; justify-content: center;
    color: #fff; cursor: pointer; flex-shrink: 0; margin-top: 2px;
    &.is-checked { background: var(--mint, #3ddc97); border-color: var(--mint, #3ddc97); }
    &--sm { width: 16px; height: 16px; margin-top: 0; }
  }
  &__main { flex: 1; min-width: 0; cursor: pointer; }
  &__line { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-2); }
  &__name { font-size: var(--text-base); font-weight: 500; color: var(--text-hi); }
  &__desc { font-size: var(--text-sm); color: var(--text-mid); margin-top: 4px; line-height: 1.5; }
  &__due { display: inline-flex; align-items: center; gap: 4px; font-size: var(--text-xs); color: var(--text-low); }
  &__sub { display: flex; align-items: center; gap: var(--space-3); margin-top: var(--space-2); }
  &__bar {
    width: 120px; height: 6px; border-radius: var(--radius-pill);
    background: var(--bg-soft, rgba(0,0,0,0.06)); overflow: hidden;
    &--full { width: 100%; margin: var(--space-2) 0; }
  }
  &__bar-fill { height: 100%; border-radius: var(--radius-pill); background: var(--primary); transition: width 0.3s; }
  &__sub-num { font-size: var(--text-sm); color: var(--text-low); }
  &__ops { display: flex; gap: var(--space-2); opacity: 0; transition: opacity 0.15s; }
  &__op {
    padding: 4px; border-radius: var(--radius-sm); color: var(--text-mid);
    background: transparent; border: none; cursor: pointer;
    &:hover { background: var(--bg-soft, rgba(0,0,0,0.05)); color: var(--text-hi); }
    .is-focus { color: var(--gold, #f59e0b); }
  }
  &__form { display: flex; flex-direction: column; gap: var(--space-3); }
  &__form-row { display: flex; gap: var(--space-3); }
  &__form-half { flex: 1; }
  &__date {
    flex: 1; padding: 8px 12px; border: 1px solid var(--line); border-radius: var(--radius-sm);
    background: var(--bg-panel); color: var(--text-hi); font-size: var(--text-sm);
  }
  /* 详情抽屉 */
  &__detail { display: flex; flex-direction: column; gap: var(--space-4); padding: var(--space-2); }
  &__detail-section { display: flex; flex-direction: column; gap: var(--space-2); flex: 1; }
  &__detail-row { display: flex; gap: var(--space-3); }
  &__detail-label { font-size: var(--text-sm); font-weight: 600; color: var(--text-hi); }
  &__detail-head { display: flex; align-items: center; justify-content: space-between; }
  &__detail-progress { font-size: var(--text-sm); font-weight: 600; color: var(--primary); }
  &__textarea {
    padding: 8px 12px; border: 1px solid var(--line); border-radius: var(--radius-sm);
    background: var(--bg-panel); color: var(--text-hi); font-size: var(--text-sm); resize: vertical;
    font-family: inherit;
  }
  &__sub-list { list-style: none; display: flex; flex-direction: column; gap: 4px; }
  &__sub-item {
    display: flex; align-items: center; gap: var(--space-2); padding: 6px 8px;
    border-radius: var(--radius-sm); &:hover { background: var(--bg-inset); }
    &.is-done .tasks__sub-title { text-decoration: line-through; color: var(--text-low); }
  }
  &__sub-title { flex: 1; font-size: var(--text-sm); color: var(--text-hi); }
  &__sub-edit {
    flex: 1; padding: 2px 6px; border: 1px solid var(--primary); border-radius: var(--radius-sm);
    background: var(--bg-panel); color: var(--text-hi); font-size: var(--text-sm);
    outline: none;
  }
  &__sub-move {
    display: flex; flex-direction: column;
    button {
      padding: 1px; border: none; background: transparent; color: var(--text-low);
      cursor: pointer; border-radius: 2px;
      &:hover:not(:disabled) { color: var(--text-hi); background: var(--bg-soft, rgba(0,0,0,0.06)); }
      &:disabled { opacity: 0.3; cursor: not-allowed; }
    }
  }
  &__sub-del { color: var(--text-low); padding: 2px; &:hover { color: var(--strawberry); } }
  &__sub-add { display: flex; gap: var(--space-2); margin-top: var(--space-2); }
  &__focus-row { display: flex; align-items: center; gap: var(--space-3); }
  &__focus-total { font-size: var(--text-sm); color: var(--text-mid); }
  &__detail-meta { font-size: var(--text-xs); color: var(--text-low); }
  &__detail-actions { display: flex; align-items: center; gap: var(--space-3); padding-top: var(--space-3); border-top: 1px solid var(--line); justify-content: flex-end; }

  /* 看板视图 */
  &__kanban { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-3); }
  &__col {
    display: flex; flex-direction: column; min-height: 260px;
    border: 1px solid var(--line); border-radius: var(--radius-md); background: var(--bg-panel);
    transition: border-color 0.2s, background-color 0.2s;
    &.is-over { border-color: var(--primary); background: var(--primary-soft); }
  }
  &__col-head {
    display: flex; align-items: center; justify-content: space-between;
    padding: var(--space-2) var(--space-3); border-bottom: 1px solid var(--line);
    font-size: var(--text-sm); font-weight: 600; color: var(--text-hi);
  }
  &__col-count {
    font-size: var(--text-xs); color: var(--text-low);
    background: var(--bg-inset); border-radius: var(--radius-pill); padding: 1px 8px;
  }
  &__col-body {
    flex: 1; min-height: 0; display: flex; flex-direction: column; gap: var(--space-2);
    padding: var(--space-2); overflow-y: auto;
  }
  &__card {
    padding: var(--space-3); border: 1px solid var(--line); border-radius: var(--radius-sm);
    background: var(--bg-raised); cursor: grab;
    transition: box-shadow 0.2s, border-color 0.2s;
    &:hover { border-color: var(--primary); box-shadow: var(--shadow-raise); }
    &.is-dragging { opacity: 0.5; }
  }
  &__card-line { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
  &__card-title {
    font-size: var(--text-sm); font-weight: 500; color: var(--text-hi);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  &__card-sub { margin-top: 4px; font-size: var(--text-xs); color: var(--text-low); }
  &__col-empty {
    text-align: center; color: var(--text-low); font-size: var(--text-xs);
    padding: var(--space-6) 0; border: 1px dashed var(--line); border-radius: var(--radius-sm);
  }
}
</style>
