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
import AppIcon from '@/components/common/AppIcon.vue'
import type { Task, TaskStatus, TaskPriority, Subtask } from '@/types'
import type { TagSemantic } from '@/types/common'

const { tasks, loading, query, fetchTasks, createTask, updateTask, deleteTask, setFocus } = useTask()
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
  const urlProject = route.query.project_id as string
  if (urlProject) {
    query.value.project_id = urlProject
    fetchTasks()
  }
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
  fetchTasks()
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
    fetchTasks()
  }
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

async function onCreate() {
  const title = newTitle.value.trim()
  if (!title) return toast.warning('请输入任务标题')
  await createTask({
    title,
    priority: newPriority.value,
    due_date: newDueDate.value || undefined,
  })
  toast.success('任务已创建')
  createOpen.value = false
  newTitle.value = ''
  newDueDate.value = ''
}

async function onToggleStatus(t: Task) {
  const next = t.status === 'completed' ? 'pending' : 'completed'
  await updateTask(t.id, { status: next })
  emitPetAction(next === 'completed' ? 'celebrate' : 'thinking', 2500)
}

async function onSetFocus(t: Task) {
  await setFocus(t)
  emitPetAction(t.is_focus ? 'happy' : 'sleep', 2000)
  toast.success(t.is_focus ? '已取消今日最重要' : '已设为今日最重要')
}

async function onDelete(t: Task) {
  const ok = await modal.confirm({
    title: '删除任务', message: `确定删除「${t.title}」吗？删除后无法恢复。`, confirmText: '删除',
  })
  if (!ok) return
  await deleteTask(t.id)
  toast.success('任务已删除')
  if (detailTask.value?.id === t.id) detailOpen.value = false
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
})

async function openDetail(t: Task) {
  detailTask.value = t
  detailOpen.value = true
  detailLoading.value = true
  editForm.value = {
    title: t.title, description: t.description ?? '',
    status: t.status, priority: t.priority,
    project_tag: t.project_tag ?? '', project_id: t.project_id ?? '', due_date: t.due_date ?? '',
  }
  try {
    const detail = await taskApi.detail(t.id)
    subtasks.value = detail.subtasks ?? []
  } catch { /* ignore */ } finally {
    detailLoading.value = false
  }
}

async function saveDetail() {
  if (!detailTask.value) return
  const t = detailTask.value
  await updateTask(t.id, {
    title: editForm.value.title,
    description: editForm.value.description,
    status: editForm.value.status,
    priority: editForm.value.priority,
    project_tag: editForm.value.project_tag || undefined,
    project_id: editForm.value.project_id || undefined,
    due_date: editForm.value.due_date || undefined,
  })
  detailTask.value = { ...t, ...editForm.value, description: editForm.value.description || null, project_tag: editForm.value.project_tag || null, due_date: editForm.value.due_date || null }
  toast.success('已保存')
}

async function addSubtask() {
  if (!detailTask.value || !newSubtask.value.trim()) return
  const sub = await taskApi.addSubtask(detailTask.value.id, newSubtask.value.trim())
  subtasks.value.push(sub)
  newSubtask.value = ''
}

async function toggleSubtask(sub: Subtask) {
  await taskApi.updateSubtask(detailTask.value!.id, sub.id, { completed: !sub.completed })
  sub.completed = !sub.completed
}

async function deleteSubtask(sub: Subtask) {
  await taskApi.removeSubtask(detailTask.value!.id, sub.id)
  subtasks.value = subtasks.value.filter(s => s.id !== sub.id)
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
        <ul class="tasks__list">
          <li v-for="t in tasks" :key="t.id" class="tasks__item" :class="{ 'is-done': t.status === 'completed' }">
            <button class="tasks__check" :class="{ 'is-checked': t.status === 'completed' }" @click="onToggleStatus(t)">
              <AppIcon v-if="t.status === 'completed'" name="check" :size="14" />
            </button>
            <div class="tasks__main" @click="openDetail(t)">
              <div class="tasks__line">
                <span class="tasks__name">{{ t.title }}</span>
                <BaseTag v-if="t.is_focus" semantic="gold">今日最重要</BaseTag>
                <BaseTag :semantic="prioritySemantic(t.priority)">{{ priorityLabel(t.priority) }}</BaseTag>
                <BaseTag :semantic="statusSemantic(t.status)">{{ statusLabel(t.status) }}</BaseTag>
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

    <!-- 新建任务弹窗 -->
    <BaseModal v-model="createOpen" title="新建任务" @confirm="onCreate">
      <div class="tasks__form">
        <BaseInput v-model="newTitle" placeholder="任务标题（必填）" />
        <div class="tasks__form-row">
          <BaseSelect v-model="newPriority" :options="priorityOptions" placeholder="优先级" class="tasks__form-half" />
          <input v-model="newDueDate" type="date" class="tasks__date" />
        </div>
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
            <li v-for="sub in subtasks" :key="sub.id" class="tasks__sub-item" :class="{ 'is-done': sub.completed }">
              <button class="tasks__check tasks__check--sm" @click="toggleSubtask(sub)">
                <AppIcon v-if="sub.completed" name="check" :size="10" />
              </button>
              <span class="tasks__sub-title">{{ sub.title }}</span>
              <button class="tasks__sub-del" @click="deleteSubtask(sub)"><AppIcon name="close" :size="12" /></button>
            </li>
          </ul>
          <div class="tasks__sub-add">
            <BaseInput v-model="newSubtask" placeholder="添加子任务..." @keyup.enter="addSubtask" />
            <BaseButton size="sm" @click="addSubtask">添加</BaseButton>
          </div>
        </div>

        <div class="tasks__detail-actions">
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
  }
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
  &__sub-del { color: var(--text-low); padding: 2px; &:hover { color: var(--strawberry); } }
  &__sub-add { display: flex; gap: var(--space-2); margin-top: var(--space-2); }
  &__detail-actions { display: flex; justify-content: flex-end; gap: var(--space-3); padding-top: var(--space-3); border-top: 1px solid var(--line); }

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
