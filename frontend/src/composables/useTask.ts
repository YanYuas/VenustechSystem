// ============================================================
// useTask —— 任务模块业务逻辑
// ============================================================
import { ref, computed } from 'vue'
import { taskApi } from '@/api'
import { useAsync } from './useAsync'
import type { Task, TaskListQuery, CreateTaskRequest, UpdateTaskRequest } from '@/types'

export function useTask() {
  const tasks = ref<Task[]>([])
  const total = ref(0)
  const query = ref<TaskListQuery>({ page: 1, page_size: 20 })

  const { loading, execute: fetchTasks } = useAsync(
    async () => {
      const res = await taskApi.list(query.value)
      tasks.value = res.list
      total.value = res.total
      return res
    },
    // 不再 immediate：视图 onMounted 会按 URL 参数（project_id）组装 query 后统一发起唯一一次请求，
    // 避免首屏无过滤请求与带过滤请求竞态导致列表被旧数据覆盖
  )

  const { execute: createTask } = useAsync(
    async (data: CreateTaskRequest) => taskApi.create(data),
    { onSuccess: () => fetchTasks() },
  )

  const { execute: updateTask } = useAsync(
    async (id: string, data: UpdateTaskRequest) => taskApi.update(id, data),
    { onSuccess: () => fetchTasks() },
  )

  const { execute: deleteTask } = useAsync(
    async (id: string) => taskApi.remove(id),
    { onSuccess: () => fetchTasks() },
  )

  async function toggleStatus(task: Task) {
    const next = task.status === 'completed' ? 'pending' : 'completed'
    await updateTask(task.id, { status: next })
  }

  async function setFocus(task: Task) {
    if (task.is_focus) {
      await taskApi.cancelFocus(task.id)
    } else {
      await taskApi.setFocus(task.id)
    }
    await fetchTasks()
  }

  /** 当前页任务状态分布（注意：分页时仅反映当前页数据） */
  const pageStats = computed(() => ({
    pending: tasks.value.filter((t) => t.status === 'pending').length,
    in_progress: tasks.value.filter((t) => t.status === 'in_progress').length,
    waiting: tasks.value.filter((t) => t.status === 'waiting').length,
    completed: tasks.value.filter((t) => t.status === 'completed').length,
  }))

  return {
    tasks,
    total,
    query,
    loading,
    pageStats,
    fetchTasks,
    createTask,
    updateTask,
    deleteTask,
    toggleStatus,
    setFocus,
  }
}
