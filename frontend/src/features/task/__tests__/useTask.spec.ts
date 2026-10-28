// ============================================================
// features/task/composables/useTask —— 业务 composable 单元测试
//
// 只 mock 领域 api（不碰 kernel/http/fetch），验证"状态编排"这一层：
//   成功写状态 / 失败向上抛且不破坏旧数据 / 写操作成功后自动 refetch /
//   toggleStatus 取反 / setFocus 走 focus 与 cancelFocus 两条分支 / pageStats 统计。
// ============================================================
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { PaginatedData } from '@/kernel/http/types'
import { taskApi } from '../api'
import { useTask } from '../composables/useTask'
import type { Task } from '../model'

vi.mock('../api', () => ({
  taskApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    setFocus: vi.fn(),
    cancelFocus: vi.fn(),
  },
}))

const list = vi.mocked(taskApi.list)
const create = vi.mocked(taskApi.create)
const update = vi.mocked(taskApi.update)
const setFocusApi = vi.mocked(taskApi.setFocus)
const cancelFocus = vi.mocked(taskApi.cancelFocus)

function makeTask(patch: Partial<Task> = {}): Task {
  return {
    id: 't1',
    title: '任务',
    description: null,
    status: 'pending',
    priority: 'medium',
    project_tag: null,
    project_id: null,
    project_name: null,
    identity_id: null,
    due_date: null,
    is_focus: false,
    progress: 0,
    subtasks_count: 0,
    subtasks_completed: 0,
    completed_at: null,
    reminder_time: null,
    recurrence: null,
    focus_duration: 0,
    estimated_minutes: null,
    acceptance_criteria: null,
    created_at: '2026-01-01T00:00:00',
    updated_at: '2026-01-01T00:00:00',
    ...patch,
  }
}

function page(tasks: Task[]): PaginatedData<Task> {
  return { list: tasks, total: tasks.length, page: 1, page_size: 20 }
}

beforeEach(() => {
  vi.clearAllMocks()
  list.mockResolvedValue(page([makeTask()]))
})

describe('useTask：读取', () => {
  it('fetchTasks 成功后写入列表与总数，并统计当前页状态分布', async () => {
    list.mockResolvedValueOnce(
      page([
        makeTask({ id: 'a', status: 'pending' }),
        makeTask({ id: 'b', status: 'completed' }),
        makeTask({ id: 'c', status: 'pending' }),
      ]),
    )
    const task = useTask()

    await task.fetchTasks()

    expect(task.tasks.value).toHaveLength(3)
    expect(task.total.value).toBe(3)
    expect(task.pageStats.value.pending).toBe(2)
    expect(task.pageStats.value.completed).toBe(1)
    expect(task.loading.value).toBe(false)
  })

  it('fetchTasks 失败时向上抛错、loading 复位，且不污染已有列表', async () => {
    const task = useTask()
    await task.fetchTasks()
    const before = task.tasks.value.map((t) => t.id)

    list.mockRejectedValueOnce(new Error('boom'))

    await expect(task.fetchTasks()).rejects.toThrow('boom')
    expect(task.loading.value).toBe(false)
    expect(task.tasks.value.map((t) => t.id)).toEqual(before)
  })
})

describe('useTask：写入后自动刷新', () => {
  it('createTask 成功后会 refetch 列表（保证本地状态与后端一致）', async () => {
    create.mockResolvedValueOnce(makeTask({ id: 'new' }))
    const task = useTask()

    await task.createTask({ title: '新任务' })

    expect(create).toHaveBeenCalledWith({ title: '新任务' })
    expect(list).toHaveBeenCalledTimes(1)
  })

  it('toggleStatus 依据当前状态取反：pending → completed，completed → pending', async () => {
    update.mockResolvedValue(makeTask({ status: 'completed' }))
    const task = useTask()

    await task.toggleStatus(makeTask({ id: 'a', status: 'pending' }))
    expect(update).toHaveBeenLastCalledWith('a', { status: 'completed' })

    await task.toggleStatus(makeTask({ id: 'b', status: 'completed' }))
    expect(update).toHaveBeenLastCalledWith('b', { status: 'pending' })
  })

  it('setFocus 按 is_focus 走 cancelFocus / setFocus 两条分支，并刷新列表', async () => {
    vi.mocked(taskApi.cancelFocus).mockResolvedValue(undefined)
    setFocusApi.mockResolvedValue(undefined)
    const task = useTask()

    await task.setFocus(makeTask({ id: 'f1', is_focus: true }))
    expect(cancelFocus).toHaveBeenCalledWith('f1')

    await task.setFocus(makeTask({ id: 'f2', is_focus: false }))
    expect(setFocusApi).toHaveBeenCalledWith('f2')

    expect(list).toHaveBeenCalledTimes(2)
  })
})
