<script setup lang="ts">
// ============================================================
// 首页仪表盘 —— 丰富模块版（对齐参考UI BetterLife AI）
// 已实现模块显示真实数据，待开发模块灰度显示+标注"待开发"
// ============================================================
import dayjs from 'dayjs'
import { computed, ref } from 'vue'
import type { TagSemantic } from '@/types/common'
import type { ModuleStatus } from '@/types'
import { useDashboard } from '@/composables/useDashboard'
import { useTask } from '@/composables/useTask'
import { useToast } from '@/composables/useToast'
import { useRouter } from 'vue-router'
import BaseCard from '@/components/common/BaseCard.vue'
import BaseTag from '@/components/common/BaseTag.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import BaseEmpty from '@/components/common/BaseEmpty.vue'
import BaseSkeleton from '@/components/common/BaseSkeleton.vue'
import AppIcon from '@/components/common/AppIcon.vue'

const { data, loading } = useDashboard()
const { updateTask } = useTask()
const toast = useToast()
const router = useRouter()


// ---------- 卡片拖拽排序（M01 P2 F08） ----------
const CARD_ORDER_KEY = 'venustech_dashboard_card_order'
const defaultOrder = ['focus', 'execution', 'projects', 'resources', 'learning', 'recent', 'life', 'quick', 'ai', 'assets']
const cardOrder = ref<string[]>([...defaultOrder])
const dragOverCard = ref<string | null>(null)

function onDragStart(e: DragEvent, cardId: string) {
  e.dataTransfer?.setData('text/plain', cardId)
  e.dataTransfer!.effectAllowed = 'move'
}
function onDragOver(e: DragEvent, cardId: string) {
  e.preventDefault()
  dragOverCard.value = cardId
}
function onDragLeave() { dragOverCard.value = null }
function onDrop(e: DragEvent, targetId: string) {
  e.preventDefault()
  const sourceId = e.dataTransfer?.getData('text/plain')
  dragOverCard.value = null
  if (!sourceId || sourceId === targetId) return
  const fromIdx = cardOrder.value.indexOf(sourceId)
  const toIdx = cardOrder.value.indexOf(targetId)
  if (fromIdx < 0 || toIdx < 0) return
  cardOrder.value.splice(fromIdx, 1)
  cardOrder.value.splice(toIdx, 0, sourceId)
  try { localStorage.setItem(CARD_ORDER_KEY, JSON.stringify(cardOrder.value)) } catch { /* ignore */ }
}

const STATUS_SEMANTIC: Record<string, TagSemantic> = {
  pending: 'default',
  in_progress: 'butter',
  waiting: 'lilac',
  completed: 'mint',
}
const statusSemantic = (s: string): TagSemantic => STATUS_SEMANTIC[s] ?? 'default'

function fmtTime(v: string) {
  return dayjs(v).format('MM-DD HH:mm')
}

function statusBadge(status: ModuleStatus) {
  if (status === 'ready') return null
  if (status === 'beta') return { text: '内测', semantic: 'butter' as TagSemantic }
  return { text: '待开发', semantic: 'default' as TagSemantic }
}

function isPlanned(status: ModuleStatus) {
  return status === 'planned'
}

async function submitFocusTask() {
  if (!data.value?.focus_task) return
  try {
    await updateTask(data.value.focus_task.id, { status: 'completed' })
    toast.success('提交成果', '任务已标记完成 🎉')
  } catch {
    toast.error('操作失败', '请稍后重试')
  }
}

function handleQuickAction(action: string) {
  if (action.startsWith('/')) {
    router.push(action)
  } else {
    toast.info('功能开发中', '该功能将在后续版本上线')
  }
}

function greetingText() {
  return data.value?.user.greeting ?? '你好'
}

const executionGroups = computed(() => data.value?.today_execution.groups ?? [])
const projects = computed(() => data.value?.projects.items ?? [])
const resourceCategories = computed(() => data.value?.resource_center.categories ?? [])
const lifeCategories = computed(() => data.value?.life.categories ?? [])
const assetCategories = computed(() => data.value?.assets.categories ?? [])
const quickActions = computed(() => data.value?.quick_actions.items ?? [])
</script>

<template>
  <div class="dash">
    <!-- Banner 大标题区 -->
    <section class="dash__hero">
      <div class="dash__hero-text">
        <h1 class="dash__hero-title">专注当下，持续创造真实成果</h1>
        <p class="dash__hero-sub">
          {{ greetingText() }}，{{ data?.user.nickname ?? '启明星用户' }} · 你的人生与项目，由你主导；系统记住一切，帮你推进一步。
        </p>
      </div>
      <div class="dash__hero-art">
        <AppIcon name="spark" :size="48" class="dash__hero-star" />
      </div>
    </section>

    <!-- 今日最重要任务大卡片 -->
    <BaseCard class="dash__focus">
      <template #title>
        <div class="dash__card-head">
          <span class="dash__card-title">⭐ 今日最重要</span>
          <BaseTag v-if="data?.focus_task" :semantic="statusSemantic(data.focus_task.status)">
            {{ data.focus_task.status === 'completed' ? '已完成' : data.focus_task.stage }}
          </BaseTag>
        </div>
      </template>

      <template v-if="loading">
        <BaseSkeleton variant="list" :rows="2" />
      </template>
      <template v-else-if="data?.focus_task">
        <h2 class="dash__focus-title">{{ data.focus_task.title }}</h2>
        <p class="dash__focus-meta">
          <span v-if="data.focus_task.project_tag" class="dash__chip">{{ data.focus_task.project_tag }}</span>
          <span class="dash__muted">下一步：{{ data.focus_task.next_step || '继续推进' }}</span>
        </p>
        <div class="dash__bar">
          <div class="dash__bar-fill" :style="{ width: data.focus_task.progress + '%' }" />
        </div>
        <p class="dash__bar-label">进度 {{ data.focus_task.progress }}%</p>
        <div class="dash__actions">
          <BaseButton variant="primary" @click="router.push('/tasks')">继续工作</BaseButton>
          <BaseButton variant="secondary" @click="submitFocusTask">提交成果</BaseButton>
        </div>
      </template>
      <template v-else>
        <BaseEmpty title="今天还没有设定最重要的任务" description="去任务模块选一个吧，让今天有焦点">
          <template #action>
            <BaseButton variant="primary" icon="plus" @click="router.push('/tasks')">去任务模块</BaseButton>
          </template>
        </BaseEmpty>
      </template>
    </BaseCard>

    <!-- 第一行三列：今日执行 | 当前项目 | 资源中心 -->
    <div class="dash__grid-3">
      <!-- 今日执行 -->
      <BaseCard :style="{ order: cardOrder.indexOf('execution') }" scroll draggable="true" @dragstart="onDragStart($event, 'execution')" @dragover="onDragOver($event, 'execution')" @dragleave="onDragLeave" @drop="onDrop($event, 'execution')" :class="{ 'is-drag-over': dragOverCard === 'execution' }">
        <template #title>
          <div class="dash__card-head">
            <h3 class="dash__card-title">📋 今日执行</h3>
            <BaseTag semantic="mint">{{ data?.today_execution.total ?? 0 }} 项</BaseTag>
          </div>
        </template>
        <template v-if="loading">
          <BaseSkeleton variant="list" :rows="3" />
        </template>
        <template v-else>
          <div class="dash__exec">
            <div v-for="g in executionGroups" :key="g.status" class="dash__exec-group">
              <div class="dash__exec-head">
                <AppIcon :name="g.status === 'pending' ? 'target' : g.status === 'in_progress' ? 'spin' : 'dot'" :size="14" />
                <span class="dash__exec-label">{{ g.label }}</span>
                <span class="dash__exec-count">{{ g.count }} 项</span>
              </div>
              <ul v-if="g.tasks.length" class="dash__exec-list">
                <li v-for="t in g.tasks" :key="t.id" class="dash__exec-item" @click="router.push('/tasks')">
                  <span class="dash__exec-dot" :class="`is-${t.priority}`" />
                  <span class="dash__exec-title">{{ t.title }}</span>
                </li>
              </ul>
              <p v-else class="dash__exec-empty">暂无任务</p>
            </div>
          </div>
        </template>
      </BaseCard>

      <!-- 当前项目 -->
      <BaseCard :class="{ 'is-planned': isPlanned(data?.projects.status ?? 'ready'), 'is-drag-over': dragOverCard === 'projects' }" :style="{ order: cardOrder.indexOf('projects') }" scroll draggable="true" @dragstart="onDragStart($event, 'projects')" @dragover="onDragOver($event, 'projects')" @dragleave="onDragLeave" @drop="onDrop($event, 'projects')">
        <template #title>
          <div class="dash__card-head">
            <h3 class="dash__card-title">📁 当前项目</h3>
            <BaseTag v-if="statusBadge(data?.projects.status ?? 'ready')"
              :semantic="statusBadge(data?.projects.status ?? 'ready')!.semantic">
              {{ statusBadge(data?.projects.status ?? 'ready')!.text }}
            </BaseTag>
          </div>
        </template>
        <template v-if="loading">
          <BaseSkeleton variant="list" :rows="3" />
        </template>
        <template v-else-if="projects.length">
          <div class="dash__projects">
            <div v-for="p in projects" :key="p.id" class="dash__project" @click="router.push(`/projects/${p.id}`)">
              <div class="dash__project-head">
                <span class="dash__project-name">{{ p.name }}</span>
                <span class="dash__project-pct">{{ p.progress }}%</span>
              </div>
              <div class="dash__bar dash__bar--sm">
                <div class="dash__bar-fill" :style="{ width: p.progress + '%' }" />
              </div>
              <p class="dash__project-meta">{{ p.completed_count }}/{{ p.task_count }} 任务完成</p>
            </div>
          </div>
        </template>
        <template v-else>
          <BaseEmpty title="还没有项目" description="去项目管理创建第一个项目">
            <template #action><BaseButton variant="primary" size="sm" @click="router.push('/projects')">创建项目</BaseButton></template>
          </BaseEmpty>
        </template>
      </BaseCard>

      <!-- 资源中心（待开发） -->
      <BaseCard :class="{ 'is-planned': isPlanned(data?.resource_center.status ?? 'planned'), 'is-drag-over': dragOverCard === 'resources' }" :style="{ order: cardOrder.indexOf('resources') }" scroll draggable="true" @dragstart="onDragStart($event, 'resources')" @dragover="onDragOver($event, 'resources')" @dragleave="onDragLeave" @drop="onDrop($event, 'resources')">
        <template #title>
          <div class="dash__card-head">
            <h3 class="dash__card-title">🗂️ 资源中心</h3>
            <BaseTag v-if="statusBadge(data?.resource_center.status ?? 'planned')"
              :semantic="statusBadge(data?.resource_center.status ?? 'planned')!.semantic">
              {{ statusBadge(data?.resource_center.status ?? 'planned')!.text }}
            </BaseTag>
          </div>
        </template>
        <div class="dash__resources">
          <div v-for="c in resourceCategories" :key="c.id" class="dash__resource"
            @click="router.push('/resource-center')">
            <AppIcon :name="c.icon" :size="16" class="dash__resource-icon" />
            <span class="dash__resource-name">{{ c.name }}</span>
            <span class="dash__resource-count">{{ c.count }}</span>
          </div>
        </div>
      </BaseCard>
    </div>

    <!-- 第二行三列：学习与成长 | 最近沉淀 | 生活与自我 -->
    <div class="dash__grid-3">
      <!-- 学习与成长（待开发） -->
      <BaseCard :class="{ 'is-planned': isPlanned(data?.learning.status ?? 'planned'), 'is-drag-over': dragOverCard === 'learning' }" :style="{ order: cardOrder.indexOf('learning') }" scroll draggable="true" @dragstart="onDragStart($event, 'learning')" @dragover="onDragOver($event, 'learning')" @dragleave="onDragLeave" @drop="onDrop($event, 'learning')">
        <template #title>
          <div class="dash__card-head">
            <h3 class="dash__card-title">📚 学习与成长</h3>
            <BaseTag v-if="statusBadge(data?.learning.status ?? 'planned')"
              :semantic="statusBadge(data?.learning.status ?? 'planned')!.semantic">
              {{ statusBadge(data?.learning.status ?? 'planned')!.text }}
            </BaseTag>
          </div>
        </template>
        <div class="dash__learning">
          <div class="dash__learning-item">
            <span class="dash__learning-label">今日学习</span>
            <div class="dash__bar dash__bar--sm"><div class="dash__bar-fill" style="width: 0%" /></div>
            <span class="dash__learning-pct">0%</span>
          </div>
          <div class="dash__learning-item">
            <span class="dash__learning-label">学习计划</span>
            <span class="dash__learning-value">进行中 0 项</span>
          </div>
          <div class="dash__learning-item">
            <span class="dash__learning-label">知识卡片</span>
            <span class="dash__learning-value">今日复习 0 张</span>
          </div>
          <p class="dash__learning-enter" @click="router.push('/learning')">进入学习中心 →</p>
        </div>
      </BaseCard>

      <!-- 最近沉淀（已实现） -->
      <BaseCard scroll draggable="true" @dragstart="onDragStart($event, 'recent')" @dragover="onDragOver($event, 'recent')" @dragleave="onDragLeave" @drop="onDrop($event, 'recent')" :class="{ 'is-drag-over': dragOverCard === 'recent' }" :style="{ order: cardOrder.indexOf('recent') }">
        <template #title><h3 class="dash__card-title">📝 最近沉淀</h3></template>
        <template v-if="loading">
          <BaseSkeleton variant="list" :rows="3" />
        </template>
        <template v-else-if="data?.recent_documents.length">
          <ul class="dash__docs">
            <li v-for="d in data.recent_documents" :key="d.id" class="dash__doc" @click="router.push('/documents')">
              <AppIcon name="doc" :size="16" class="dash__doc-icon" />
              <span class="dash__doc-title">{{ d.title }}</span>
              <span class="dash__doc-time">{{ fmtTime(d.updated_at) }}</span>
              <BaseTag v-for="t in d.tags.slice(0, 2)" :key="t" semantic="lilac">{{ t }}</BaseTag>
            </li>
          </ul>
        </template>
        <template v-else>
          <BaseEmpty title="还没有文档" description="创建第一篇笔记吧" />
        </template>
      </BaseCard>

      <!-- 生活与自我（待开发） -->
      <BaseCard :class="{ 'is-planned': isPlanned(data?.life.status ?? 'planned'), 'is-drag-over': dragOverCard === 'life' }" :style="{ order: cardOrder.indexOf('life') }" scroll draggable="true" @dragstart="onDragStart($event, 'life')" @dragover="onDragOver($event, 'life')" @dragleave="onDragLeave" @drop="onDrop($event, 'life')">
        <template #title>
          <div class="dash__card-head">
            <h3 class="dash__card-title">💚 生活与自我</h3>
            <BaseTag v-if="statusBadge(data?.life.status ?? 'planned')"
              :semantic="statusBadge(data?.life.status ?? 'planned')!.semantic">
              {{ statusBadge(data?.life.status ?? 'planned')!.text }}
            </BaseTag>
          </div>
        </template>
        <div class="dash__life">
          <div v-for="c in lifeCategories" :key="c.id" class="dash__life-item"
            @click="router.push('/life')">
            <AppIcon :name="c.icon" :size="16" class="dash__life-icon" />
            <div class="dash__life-text">
              <span class="dash__life-name">{{ c.name }}</span>
              <span class="dash__life-value">{{ c.value }}</span>
            </div>
          </div>
          <p class="dash__life-enter" @click="router.push('/life')">记录生活，自我觉察 →</p>
        </div>
      </BaseCard>
    </div>

    <!-- 第三行三列：快速入口 | AI助手 | 长期资产库 -->
    <div class="dash__grid-3">
      <!-- 快速入口 -->
      <BaseCard scroll draggable="true" @dragstart="onDragStart($event, 'quick')" @dragover="onDragOver($event, 'quick')" @dragleave="onDragLeave" @drop="onDrop($event, 'quick')" :class="{ 'is-drag-over': dragOverCard === 'quick' }" :style="{ order: cardOrder.indexOf('quick') }">
        <template #title><h3 class="dash__card-title">⚡ 工作台 · 快速入口</h3></template>
        <div class="dash__quick">
          <button v-for="a in quickActions" :key="a.id" class="dash__quick-item"
            :class="{ 'is-planned': isPlanned(a.status) }"
            @click="handleQuickAction(a.action)">
            <AppIcon :name="a.icon" :size="20" class="dash__quick-icon" />
            <span class="dash__quick-name">{{ a.name }}</span>
            <BaseTag v-if="statusBadge(a.status)" :semantic="statusBadge(a.status)!.semantic" size="sm">
              {{ statusBadge(a.status)!.text }}
            </BaseTag>
          </button>
        </div>
      </BaseCard>

      <!-- AI协作小助手 -->
      <BaseCard scroll draggable="true" @dragstart="onDragStart($event, 'ai')" @dragover="onDragOver($event, 'ai')" @dragleave="onDragLeave" @drop="onDrop($event, 'ai')" :class="{ 'is-drag-over': dragOverCard === 'ai' }" :style="{ order: cardOrder.indexOf('ai') }">
        <template #title>
          <div class="dash__card-head">
            <h3 class="dash__card-title">🤖 AI 协作小助手</h3>
            <BaseTag :semantic="data?.ai_assistant.enabled ? 'mint' : 'default'">
              {{ data?.ai_assistant.enabled ? '已连接' : '未配置' }}
            </BaseTag>
          </div>
        </template>
        <div class="dash__ai">
          <p class="dash__ai-desc">我是你的 AI 协作伙伴，随时帮你聊天、头脑风暴、写作助手、知识问答</p>
          <div class="dash__ai-prompts">
            <button v-for="p in data?.ai_assistant.quick_prompts ?? []" :key="p"
              class="dash__ai-prompt" @click="router.push('/conversation')">
              {{ p }}
            </button>
          </div>
          <BaseButton variant="primary" block @click="router.push('/conversation')">开始对话</BaseButton>
        </div>
      </BaseCard>

      <!-- 长期资产库（待开发） -->
      <BaseCard :class="{ 'is-planned': isPlanned(data?.assets.status ?? 'planned'), 'is-drag-over': dragOverCard === 'assets' }" :style="{ order: cardOrder.indexOf('assets') }" scroll draggable="true" @dragstart="onDragStart($event, 'assets')" @dragover="onDragOver($event, 'assets')" @dragleave="onDragLeave" @drop="onDrop($event, 'assets')">
        <template #title>
          <div class="dash__card-head">
            <h3 class="dash__card-title">💎 长期资产库</h3>
            <BaseTag v-if="statusBadge(data?.assets.status ?? 'planned')"
              :semantic="statusBadge(data?.assets.status ?? 'planned')!.semantic">
              {{ statusBadge(data?.assets.status ?? 'planned')!.text }}
            </BaseTag>
          </div>
        </template>
        <div class="dash__assets">
          <div v-for="c in assetCategories" :key="c.id" class="dash__asset"
            @click="router.push('/assets')">
            <AppIcon :name="c.icon" :size="18" class="dash__asset-icon" />
            <span class="dash__asset-name">{{ c.name }}</span>
            <span class="dash__asset-count">{{ c.count }}</span>
          </div>
          <p class="dash__assets-enter" @click="router.push('/assets')">查看全部资产 →</p>
        </div>
      </BaseCard>
    </div>
  </div>
</template>

<style scoped lang="scss">
.dash {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  height: 100%;
  min-height: 0;
  overflow: hidden;
  padding: 0;

  /* 压缩卡片内部间距，一屏适配 */
  :deep(.card) {
    padding: var(--space-3);
  }
  :deep(.card__head) {
    margin-bottom: var(--space-2);
  }
  :deep(.card__title) {
    font-size: var(--text-sm);
  }

  &__hero {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
    padding: var(--space-2) var(--space-4);
    border-radius: var(--radius-lg);
    background: linear-gradient(135deg, var(--primary-soft), var(--lilac-soft));
    overflow: hidden;
  }
  &__hero-text {
    flex: 1;
    min-width: 0;
  }
  &__hero-title {
    font-size: var(--text-xl);
    font-weight: 800;
    color: var(--text-hi);
    font-family: var(--font-cute);
    animation: slide-in-up 0.5s var(--ease-soft);
  }
  &__hero-sub {
    margin-top: var(--space-1);
    font-size: var(--text-xs);
    color: var(--text-mid);
    line-height: 1.5;
  }
  &__hero-art {
    flex-shrink: 0;
    margin-left: var(--space-4);
  }
  &__hero-star {
    color: var(--primary);
    opacity: 0.6;
    animation: sparkle 2s var(--ease-soft) infinite;
  }

  &__card-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  &__card-title {
    font-size: var(--text-md);
    font-weight: 600;
    color: var(--text-hi);
  }

  // 今日最重要
  &__focus {
    flex-shrink: 0;
  }
  &__focus-title {
    font-size: var(--text-lg);
    font-weight: 700;
    color: var(--text-hi);
    margin: var(--space-1) 0;
  }
  &__focus-meta {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-2);
  }
  &__chip {
    padding: 2px 10px;
    border-radius: var(--radius-pill);
    background: var(--primary-soft);
    color: var(--primary);
    font-size: var(--text-xs);
  }
  &__muted { color: var(--text-mid); font-size: var(--text-xs); }
  &__bar {
    height: 6px;
    border-radius: var(--radius-pill);
    background: var(--bg-inset);
    overflow: hidden;
    &--sm { height: 4px; }
  }
  &__bar-fill {
    height: 100%;
    border-radius: var(--radius-pill);
    background: var(--primary);
    transition: width 0.5s var(--ease-soft);
  }
  &__bar-label {
    margin-top: var(--space-1);
    font-size: var(--text-xs);
    color: var(--text-mid);
  }
  &__actions {
    display: flex;
    gap: var(--space-3);
    margin-top: var(--space-2);
  }

  // 三列网格（弹性行高，一屏适配）
  &__grid-3 {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-3);
  }

  // 待开发灰度
  .is-planned {
    opacity: 0.55;
    filter: grayscale(0.3);
    pointer-events: none;
    & * { pointer-events: auto; }
  }

  // 今日执行
  &__exec { display: flex; flex-direction: column; gap: var(--space-3); }
  &__exec-group { display: flex; flex-direction: column; gap: var(--space-2); }
  &__exec-head {
    display: flex; align-items: center; gap: var(--space-2);
    font-size: var(--text-sm); color: var(--text-mid);
  }
  &__exec-label { font-weight: 600; color: var(--text-hi); }
  &__exec-count { margin-left: auto; }
  &__exec-list { list-style: none; display: flex; flex-direction: column; gap: var(--space-1); }
  &__exec-item {
    display: flex; align-items: center; gap: var(--space-2);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-size: var(--text-sm);
    &:hover { background: var(--bg-inset); }
  }
  &__exec-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--text-low);
    &.is-urgent { background: var(--strawberry); }
    &.is-high { background: var(--butter); }
    &.is-medium { background: var(--sky); }
    &.is-low { background: var(--mint); }
  }
  &__exec-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  &__exec-empty { font-size: var(--text-sm); color: var(--text-low); padding-left: var(--space-4); }

  // 当前项目
  &__projects { display: flex; flex-direction: column; gap: var(--space-3); }
  &__project { display: flex; flex-direction: column; gap: var(--space-1); cursor: pointer; border-radius: var(--radius-sm); padding: 4px; margin: -4px; transition: background 0.15s; }
  &__project:hover { background: var(--bg-soft, rgba(0,0,0,0.03)); }
  &__project-head { display: flex; justify-content: space-between; align-items: center; }
  &__project-name { font-size: var(--text-base); font-weight: 600; color: var(--text-hi); }
  &__project-pct { font-size: var(--text-sm); color: var(--primary); font-weight: 600; }
  &__project-meta { font-size: var(--text-xs); color: var(--text-low); }

  // 资源中心
  &__resources { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-2); }
  &__resource {
    display: flex; align-items: center; gap: var(--space-2);
    padding: var(--space-2);
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-size: var(--text-sm);
    &:hover { background: var(--bg-inset); }
  }
  &__resource-icon { color: var(--primary); }
  &__resource-name { flex: 1; color: var(--text-hi); }
  &__resource-count { color: var(--text-low); font-weight: 600; }

  // 学习
  &__learning { display: flex; flex-direction: column; gap: var(--space-3); }
  &__learning-item {
    display: flex; align-items: center; gap: var(--space-2);
    font-size: var(--text-sm);
  }
  &__learning-label { color: var(--text-mid); min-width: 60px; }
  &__learning-value { color: var(--text-hi); margin-left: auto; }
  &__learning-pct { color: var(--primary); font-weight: 600; }
  &__learning-enter {
    margin-top: var(--space-2);
    font-size: var(--text-sm);
    color: var(--primary);
    cursor: pointer;
    text-align: center;
  }

  // 最近沉淀
  &__docs { list-style: none; display: flex; flex-direction: column; gap: var(--space-2); }
  &__doc {
    display: flex; align-items: center; gap: var(--space-3);
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: background-color 0.15s;
    &:hover { background: var(--bg-inset); }
  }
  &__doc-icon { color: var(--text-low); }
  &__doc-title { flex: 1; font-size: var(--text-base); color: var(--text-hi); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  &__doc-time { font-size: var(--text-sm); color: var(--text-low); }

  // 生活
  &__life { display: flex; flex-direction: column; gap: var(--space-2); }
  &__life-item {
    display: flex; align-items: center; gap: var(--space-3);
    padding: var(--space-2);
    border-radius: var(--radius-sm);
    cursor: pointer;
    &:hover { background: var(--bg-inset); }
  }
  &__life-icon { color: var(--mint); }
  &__life-text { display: flex; flex-direction: column; }
  &__life-name { font-size: var(--text-sm); font-weight: 600; color: var(--text-hi); }
  &__life-value { font-size: var(--text-xs); color: var(--text-mid); }
  &__life-enter {
    margin-top: var(--space-2);
    font-size: var(--text-sm);
    color: var(--primary);
    cursor: pointer;
    text-align: center;
  }

  // 快速入口
  &__quick { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-2); }
  &__quick-item {
    display: flex; flex-direction: column; align-items: center; gap: var(--space-1);
    padding: var(--space-3) var(--space-2);
    border-radius: var(--radius-md);
    border: 1px solid var(--line);
    background: var(--bg-panel);
    cursor: pointer;
    transition: transform 0.15s, background-color 0.15s;
    &:hover { transform: translateY(-2px); background: var(--bg-inset); }
  }
  &__quick-icon { color: var(--primary); }
  &__quick-name { font-size: var(--text-xs); color: var(--text-hi); }

  // AI助手
  &__ai { display: flex; flex-direction: column; gap: var(--space-3); }
  &__ai-desc { font-size: var(--text-sm); color: var(--text-mid); line-height: 1.6; }
  &__ai-prompts { display: flex; flex-wrap: wrap; gap: var(--space-2); }
  &__ai-prompt {
    padding: var(--space-1) var(--space-3);
    border-radius: var(--radius-pill);
    background: var(--primary-soft);
    color: var(--primary);
    font-size: var(--text-sm);
    cursor: pointer;
    border: none;
    &:hover { background: var(--bg-inset); }
  }

  // 资产库
  &__assets { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-2); }
  &__asset {
    display: flex; align-items: center; gap: var(--space-2);
    padding: var(--space-2);
    border-radius: var(--radius-sm);
    cursor: pointer;
    &:hover { background: var(--bg-inset); }
  }
  &__asset-icon { color: var(--gold); }
  &__asset-name { flex: 1; font-size: var(--text-sm); color: var(--text-hi); }
  &__asset-count { color: var(--text-low); font-weight: 600; }
  &__assets-enter {
    grid-column: 1 / -1;
    font-size: var(--text-sm);
    color: var(--primary);
    cursor: pointer;
    text-align: center;
    margin-top: var(--space-2);
  }
}

@media (max-width: 1024px) {
  .dash__grid-3 { grid-template-columns: 1fr; }
}
</style>
