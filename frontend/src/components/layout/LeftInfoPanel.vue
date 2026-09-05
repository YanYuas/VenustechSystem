<script setup lang="ts">
// ============================================================
// LeftInfoPanel —— 左侧信息面板（非导航！）
// 对齐参考UI：日期卡片 + 今日状态 + 待办事项 + 系统提醒 + 底部标语
// 数据来源：/api/v1/panel
// ============================================================
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { panelApi } from '@/api'
import { useToast } from '@/composables/useToast'
import AppIcon from '@/components/common/AppIcon.vue'
import type { LeftPanelData, QuickTodo } from '@/types'

const router = useRouter()
const toast = useToast()

const data = ref<LeftPanelData | null>(null)
const loading = ref(true)
const newTodo = ref('')
const showTodoInput = ref(false)

const statItems = [
  { key: 'focus_task', label: '今日最重要', icon: 'star' },
  { key: 'must_do', label: '必须完成', icon: 'target' },
  { key: 'in_progress', label: '进行中项目', icon: 'spin' },
  { key: 'waiting', label: '等待处理', icon: 'clock' },
  { key: 'completed_today', label: '今日完成', icon: 'check' },
] as const

async function load() {
  loading.value = true
  try {
    data.value = await panelApi.get()
  } catch {
    toast.error('加载失败', '左侧面板数据加载失败')
  } finally {
    loading.value = false
  }
}

async function addTodo() {
  if (!newTodo.value.trim()) return
  try {
    await panelApi.createTodo({ title: newTodo.value.trim() })
    newTodo.value = ''
    showTodoInput.value = false
    await load()
  } catch {
    toast.error('创建失败', '待办创建失败')
  }
}

async function toggleTodo(todo: QuickTodo) {
  // 乐观更新：先改本地状态，失败再回滚（勾选不再等待整个面板聚合接口重载）
  const prev = todo.completed
  todo.completed = !prev
  try {
    await panelApi.updateTodo(todo.id, { completed: todo.completed })
  } catch {
    todo.completed = prev
    toast.error('操作失败', '待办状态更新失败')
  }
}

async function deleteTodo(id: string) {
  try {
    await panelApi.deleteTodo(id)
    await load()
  } catch {
    toast.error('删除失败', '待办删除失败')
  }
}

function goTasks() {
  router.push('/tasks')
}

onMounted(load)
</script>

<template>
  <aside class="left-panel">
    <!-- 日期卡片 -->
    <div class="panel-card date-card">
      <div class="date-card__top">
        <span class="date-card__date">{{ data?.date_str ?? '----年--月--日' }}</span>
        <span class="date-card__weekday">{{ data?.weekday ?? '星期--' }}</span>
      </div>
      <div class="date-card__greeting">
        <span class="date-card__sun">☀️</span>
        <span>{{ data?.greeting ?? '你好' }}，启明星！</span>
      </div>
      <p class="date-card__slogan">方向启明，人生推演</p>
      <div class="date-card__pet">
        <AppIcon name="spark" :size="28" />
      </div>
    </div>

    <!-- 今日状态 -->
    <div class="panel-section">
      <h3 class="panel-section__title">
        <AppIcon name="chart" :size="16" />
        今日状态
      </h3>
      <div v-if="loading" class="panel-skeleton">
        <div v-for="i in 5" :key="i" class="skeleton-line" />
      </div>
      <ul v-else class="stat-list">
        <li
          v-for="item in statItems"
          :key="item.key"
          class="stat-item"
          @click="goTasks"
        >
          <AppIcon :name="item.icon" :size="16" class="stat-item__icon" />
          <span class="stat-item__label">{{ item.label }}</span>
          <span class="stat-item__count">{{ data?.stats[item.key] ?? 0 }}项</span>
        </li>
      </ul>
    </div>

    <!-- 待办事项 -->
    <div class="panel-section">
      <div class="panel-section__header">
        <h3 class="panel-section__title">
          <AppIcon name="check-square" :size="16" />
          待办事项
        </h3>
        <button class="panel-section__add" @click="showTodoInput = !showTodoInput">
          <AppIcon name="plus" :size="14" />
        </button>
      </div>

      <div v-if="showTodoInput" class="todo-input">
        <input
          v-model="newTodo"
          class="todo-input__field"
          placeholder="添加待办..."
          @keyup.enter="addTodo"
          @keyup.esc="showTodoInput = false"
          autofocus
        />
      </div>

      <div v-if="loading" class="panel-skeleton">
        <div v-for="i in 3" :key="i" class="skeleton-line" />
      </div>
      <ul v-else class="todo-list">
        <li v-for="todo in data?.quick_todos ?? []" :key="todo.id" class="todo-item">
          <label class="todo-item__check">
            <input
              type="checkbox"
              :checked="todo.completed"
              @change="toggleTodo(todo)"
            />
            <span class="todo-item__checkmark" />
          </label>
          <span class="todo-item__title" :class="{ 'is-done': todo.completed }">
            {{ todo.title }}
          </span>
          <button class="todo-item__delete" @click="deleteTodo(todo.id)">
            <AppIcon name="x" :size="12" />
          </button>
        </li>
        <li v-if="!data?.quick_todos?.length" class="todo-empty">
          暂无待办，点击 + 添加
        </li>
      </ul>
    </div>

    <!-- 系统提醒 -->
    <div class="panel-section">
      <div class="panel-section__header">
        <h3 class="panel-section__title">
          <AppIcon name="bell" :size="16" />
          系统提醒
        </h3>
        <span class="panel-section__more" @click="goTasks">查看全部 ›</span>
      </div>

      <div v-if="loading" class="panel-skeleton">
        <div v-for="i in 2" :key="i" class="skeleton-line" />
      </div>
      <ul v-else class="reminder-list">
        <li v-for="r in data?.reminders ?? []" :key="r.id" class="reminder-item">
          <AppIcon name="alert" :size="14" class="reminder-item__icon" />
          <div class="reminder-item__body">
            <span class="reminder-item__title">{{ r.title }}</span>
            <span v-if="r.remind_at" class="reminder-item__time">{{ r.remind_at }}</span>
          </div>
        </li>
        <li v-if="!data?.reminders?.length" class="reminder-empty">
          暂无提醒
        </li>
      </ul>
    </div>

    <!-- 底部标语 -->
    <div class="panel-footer">
      <div class="panel-footer__slogan">
        <AppIcon name="heart" :size="14" />
        <span>把生活与工作过成作品。</span>
      </div>
      <div class="panel-footer__actions">
        <button class="panel-footer__btn" title="桌宠"><AppIcon name="spark" :size="18" /></button>
        <button class="panel-footer__btn" title="编辑"><AppIcon name="edit" :size="18" /></button>
        <button class="panel-footer__btn" title="设置" @click="router.push('/settings')">
          <AppIcon name="setting" :size="18" />
        </button>
      </div>
    </div>
  </aside>
</template>

<style scoped lang="scss">
.left-panel {
  display: flex;
  flex-direction: column;
  width: 240px;
  flex-shrink: 0;
  background: var(--bg-panel);
  border-right: 1px solid var(--line);
  overflow-y: auto;
  overflow-x: hidden;
  padding: var(--space-3);
  gap: var(--space-3);
}

/* 日期卡片 */
.date-card {
  position: relative;
  background: linear-gradient(135deg, var(--primary-soft), var(--lilac-soft));
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  overflow: hidden;

  &__top {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
  }
  &__date {
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--text-hi);
  }
  &__weekday {
    font-size: var(--text-xs);
    color: var(--text-mid);
  }
  &__greeting {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    margin-top: var(--space-2);
    font-size: var(--text-md);
    font-weight: 700;
    color: var(--text-hi);
    font-family: var(--font-cute);
  }
  &__sun {
    font-size: var(--text-md);
  }
  &__slogan {
    margin-top: var(--space-1);
    font-size: var(--text-xs);
    color: var(--text-mid);
  }
  &__pet {
    position: absolute;
    right: var(--space-3);
    bottom: var(--space-3);
    color: var(--primary);
    opacity: 0.6;
  }
}

/* 面板区块 */
.panel-section {
  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-2);
  }
  &__title {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    font-size: var(--text-sm);
    font-weight: 700;
    color: var(--text-hi);
    font-family: var(--font-cute);
  }
  &__add {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border-radius: var(--radius-sm);
    color: var(--text-mid);
    transition: all 0.2s var(--ease-soft);
    &:hover {
      background: var(--primary-soft);
      color: var(--primary);
    }
  }
  &__more {
    font-size: var(--text-xs);
    color: var(--primary);
    cursor: pointer;
    &:hover {
      text-decoration: underline;
    }
  }
}

/* 状态列表 */
.stat-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.stat-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  height: 32px;
  padding: 0 var(--space-2);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.2s var(--ease-soft);
  &:hover {
    background: var(--bg-inset);
  }
  &__icon {
    color: var(--primary);
    flex-shrink: 0;
  }
  &__label {
    flex: 1;
    font-size: var(--text-xs);
    color: var(--text-mid);
  }
  &__count {
    font-size: var(--text-xs);
    font-weight: 600;
    color: var(--text-hi);
  }
}

/* 待办输入 */
.todo-input {
  margin-bottom: var(--space-2);
  &__field {
    width: 100%;
    height: 30px;
    padding: 0 var(--space-2);
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    font-size: var(--text-xs);
    background: var(--bg-body);
    color: var(--text-hi);
    &:focus {
      outline: none;
      border-color: var(--primary);
      box-shadow: 0 0 0 2px var(--primary-soft);
    }
  }
}

/* 待办列表 */
.todo-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.todo-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  height: 28px;
  padding: 0 var(--space-1);
  border-radius: var(--radius-sm);
  &:hover {
    background: var(--bg-inset);
    .todo-item__delete {
      opacity: 1;
    }
  }
  &__check {
    position: relative;
    display: inline-flex;
    align-items: center;
    cursor: pointer;
    input {
      position: absolute;
      opacity: 0;
      width: 0;
      height: 0;
    }
  }
  &__checkmark {
    display: inline-block;
    width: 16px;
    height: 16px;
    border: 1.5px solid var(--text-low);
    border-radius: 4px;
    transition: all 0.2s var(--ease-soft);
    input:checked + & {
      background: var(--primary);
      border-color: var(--primary);
      &::after {
        content: '';
        position: absolute;
        left: 4px;
        top: 1px;
        width: 4px;
        height: 8px;
        border: solid white;
        border-width: 0 2px 2px 0;
        transform: rotate(45deg);
      }
    }
  }
  &__title {
    flex: 1;
    font-size: var(--text-xs);
    color: var(--text-hi);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    &.is-done {
      text-decoration: line-through;
      color: var(--text-low);
    }
  }
  &__delete {
    opacity: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 4px;
    color: var(--text-low);
    transition: all 0.2s var(--ease-soft);
    &:hover {
      background: var(--strawberry-soft);
      color: var(--strawberry);
    }
  }
}
.todo-empty {
  font-size: var(--text-xs);
  color: var(--text-low);
  text-align: center;
  padding: var(--space-2) 0;
}

/* 提醒列表 */
.reminder-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.reminder-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-1);
  border-radius: var(--radius-sm);
  &:hover {
    background: var(--bg-inset);
  }
  &__icon {
    color: var(--butter);
    margin-top: 2px;
    flex-shrink: 0;
  }
  &__body {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  &__title {
    font-size: var(--text-xs);
    color: var(--text-hi);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  &__time {
    font-size: 10px;
    color: var(--text-low);
  }
}
.reminder-empty {
  font-size: var(--text-xs);
  color: var(--text-low);
  text-align: center;
  padding: var(--space-2) 0;
}

/* 底部 */
.panel-footer {
  margin-top: auto;
  padding-top: var(--space-3);
  border-top: 1px solid var(--line);

  &__slogan {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    font-size: var(--text-xs);
    color: var(--text-mid);
    margin-bottom: var(--space-3);
  }
  &__actions {
    display: flex;
    justify-content: space-around;
  }
  &__btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border-radius: var(--radius-md);
    color: var(--text-mid);
    transition: all 0.2s var(--ease-soft);
    &:hover {
      background: var(--primary-soft);
      color: var(--primary);
    }
  }
}

/* 骨架屏 */
.panel-skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.skeleton-line {
  height: 16px;
  border-radius: 4px;
  background: linear-gradient(90deg, var(--bg-inset) 25%, var(--bg-panel) 50%, var(--bg-inset) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
