<script setup lang="ts">
// ============================================================
// 项目管理页面 —— 列表/创建/编辑/删除
// ============================================================
import { onMounted, ref } from 'vue'
import { projectApi } from '@/api'
import { useToast } from '@/composables/useToast'
import { useModal } from '@/composables/useModal'
import BaseCard from '@/components/common/BaseCard.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import BaseInput from '@/components/common/BaseInput.vue'
import BaseSelect from '@/components/common/BaseSelect.vue'
import BaseModal from '@/components/common/BaseModal.vue'
import BaseEmpty from '@/components/common/BaseEmpty.vue'
import BaseSkeleton from '@/components/common/BaseSkeleton.vue'
import AppIcon from '@/components/common/AppIcon.vue'
import type { Project, ProjectStatus } from '@/types'
import { useRouter } from 'vue-router'

const router = useRouter()
const toast = useToast()
const modal = useModal()

const projects = ref<Project[]>([])
const loading = ref(true)

const COLORS = ['#7c5cff', '#3ddc97', '#f59e0b', '#ef4444', '#3b82f6', '#ec4899', '#14b8a6', '#f97316']
const statusOptions = [
  { label: '进行中', value: 'active' },
  { label: '已完成', value: 'completed' },
  { label: '已归档', value: 'archived' },
]

async function load() {
  loading.value = true
  try {
    projects.value = await projectApi.list(true)
  } catch {
    toast.error('加载失败', '项目列表加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(load)

// 新建/编辑弹窗
const modalOpen = ref(false)
const editing = ref<Project | null>(null)
const form = ref({ name: '', description: '', color: '#7c5cff', status: 'active' as ProjectStatus, due_date: '' })

function openCreate() {
  editing.value = null
  form.value = { name: '', description: '', color: '#7c5cff', status: 'active', due_date: '' }
  modalOpen.value = true
}

function openEdit(p: Project) {
  editing.value = p
  form.value = {
    name: p.name,
    description: p.description ?? '',
    color: p.color,
    status: p.status,
    due_date: p.due_date ?? '',
  }
  modalOpen.value = true
}

async function onSubmit() {
  if (!form.value.name.trim()) return toast.warning('请输入项目名称')
  try {
    if (editing.value) {
      await projectApi.update(editing.value.id, {
        name: form.value.name,
        description: form.value.description || undefined,
        color: form.value.color,
        status: form.value.status,
        due_date: form.value.due_date || undefined,
      })
      toast.success('项目已更新')
    } else {
      await projectApi.create({
        name: form.value.name,
        description: form.value.description || undefined,
        color: form.value.color,
        status: form.value.status,
        due_date: form.value.due_date || undefined,
      })
      toast.success('项目已创建')
    }
    modalOpen.value = false
    await load()
  } catch (err) {
    toast.error('保存失败', String(err))
  }
}

async function onDelete(p: Project) {
  const ok = await modal.confirm({
    title: '删除项目',
    message: `确定删除「${p.name}」吗？项目下的任务将解除关联，但不会被删除。`,
    confirmText: '删除',
  })
  if (!ok) return
  try {
    await projectApi.remove(p.id)
    toast.success('项目已删除')
    await load()
  } catch {
    toast.error('删除失败')
  }
}

function goTasks(p: Project) {
  router.push(`/tasks?project_id=${p.id}`)
}

function statusLabel(s: ProjectStatus) {
  return { active: '进行中', completed: '已完成', archived: '已归档' }[s] ?? s
}
</script>

<template>
  <div class="projects">
    <div class="projects__head">
      <h1 class="projects__title">项目管理</h1>
      <BaseButton variant="primary" icon="plus" @click="openCreate">新建项目</BaseButton>
    </div>

    <BaseCard>
      <template v-if="loading">
        <BaseSkeleton variant="list" :rows="4" />
      </template>
      <template v-else-if="projects.length">
        <ul class="projects__list">
          <li v-for="p in projects" :key="p.id" class="projects__item">
            <div class="projects__color-dot" :style="{ background: p.color }" />
            <div class="projects__info" @click="goTasks(p)">
              <span class="projects__name">{{ p.name }}</span>
              <span v-if="p.description" class="projects__desc">{{ p.description }}</span>
            </div>
            <div class="projects__stats">
              <div class="projects__progress">
                <div class="projects__bar">
                  <div class="projects__bar-fill" :style="{ width: p.progress + '%', background: p.color }" />
                </div>
                <span class="projects__pct">{{ p.progress }}%</span>
              </div>
              <span class="projects__count">{{ p.completed_count }}/{{ p.task_count }} 任务</span>
            </div>
            <span class="projects__status" :class="`is-${p.status}`">{{ statusLabel(p.status) }}</span>
            <div class="projects__ops">
              <button class="projects__op" title="编辑" @click.stop="openEdit(p)">
                <AppIcon name="edit" :size="16" />
              </button>
              <button class="projects__op projects__op--danger" title="删除" @click.stop="onDelete(p)">
                <AppIcon name="trash" :size="16" />
              </button>
            </div>
          </li>
        </ul>
      </template>
      <template v-else>
        <BaseEmpty title="还没有项目" description="创建第一个项目，把任务组织起来">
          <template #action>
            <BaseButton variant="primary" icon="plus" @click="openCreate">新建项目</BaseButton>
          </template>
        </BaseEmpty>
      </template>
    </BaseCard>

    <BaseModal v-model="modalOpen" :title="editing ? '编辑项目' : '新建项目'" @confirm="onSubmit">
      <div class="projects__form">
        <BaseInput v-model="form.name" placeholder="项目名称（必填）" />
        <BaseInput v-model="form.description" placeholder="项目描述（可选）" />
        <div class="projects__form-row">
          <div class="projects__form-half">
            <label class="projects__label">颜色</label>
            <div class="projects__colors">
              <button
                v-for="c in COLORS" :key="c"
                class="projects__color-btn"
                :class="{ 'is-active': form.color === c }"
                :style="{ background: c }"
                @click="form.color = c"
              />
            </div>
          </div>
          <div class="projects__form-half">
            <label class="projects__label">状态</label>
            <BaseSelect v-model="form.status" :options="statusOptions" />
          </div>
        </div>
        <div class="projects__form-half">
          <label class="projects__label">截止日期（可选）</label>
          <input v-model="form.due_date" type="date" class="projects__date" />
        </div>
      </div>
    </BaseModal>
  </div>
</template>

<style scoped lang="scss">
.projects {
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
  &__title {
    font-size: var(--text-2xl);
    font-weight: 700;
  }
  &__list {
    list-style: none;
    display: flex;
    flex-direction: column;
  }
  &__item {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--line);
    &:last-child { border-bottom: none; }
    &:hover { background: var(--bg-soft, rgba(0,0,0,0.02)); }
  }
  &__color-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  &__info {
    flex: 1;
    min-width: 0;
    cursor: pointer;
  }
  &__name {
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--text-hi);
  }
  &__desc {
    display: block;
    font-size: var(--text-sm);
    color: var(--text-low);
    margin-top: 2px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  &__stats {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 140px;
  }
  &__progress {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  &__bar {
    flex: 1;
    height: 6px;
    border-radius: var(--radius-pill);
    background: var(--bg-inset);
    overflow: hidden;
  }
  &__bar-fill {
    height: 100%;
    border-radius: var(--radius-pill);
    transition: width 0.3s;
  }
  &__pct {
    font-size: var(--text-xs);
    font-weight: 600;
    color: var(--text-mid);
    min-width: 32px;
    text-align: right;
  }
  &__count {
    font-size: var(--text-xs);
    color: var(--text-low);
  }
  &__status {
    font-size: var(--text-xs);
    padding: 2px 8px;
    border-radius: var(--radius-pill);
    flex-shrink: 0;
    &.is-active { background: var(--sky-soft, rgba(59,130,246,0.1)); color: var(--sky, #3b82f6); }
    &.is-completed { background: var(--mint-soft, rgba(61,220,151,0.1)); color: var(--mint, #3ddc97); }
    &.is-archived { background: var(--bg-inset); color: var(--text-low); }
  }
  &__ops {
    display: flex;
    gap: var(--space-1);
    opacity: 0;
    transition: opacity 0.15s;
  }
  &__item:hover &__ops { opacity: 1; }
  &__op {
    padding: 4px;
    border: none;
    background: transparent;
    color: var(--text-mid);
    border-radius: var(--radius-sm);
    cursor: pointer;
    &:hover { background: var(--bg-soft, rgba(0,0,0,0.05)); color: var(--text-hi); }
    &--danger:hover { color: var(--danger, #ef4444); }
  }
  &__form {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  &__form-row {
    display: flex;
    gap: var(--space-3);
  }
  &__form-half {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  &__label {
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--text-hi);
  }
  &__colors {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  &__color-btn {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    border: 2px solid transparent;
    cursor: pointer;
    transition: all 0.15s;
    &.is-active {
      border-color: var(--text-hi);
      transform: scale(1.1);
    }
  }
  &__date {
    padding: 8px 12px;
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    background: var(--bg-panel);
    color: var(--text-hi);
    font-size: var(--text-sm);
  }
}
</style>
