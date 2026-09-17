// ============================================================
// 身份组合式（三期 B · 横切标签）
//
// 全局单例：身份列表加载一次，筛选器 / 任务页 / 管理页共享同一份。
// 用法: const { identities, identityOptions, loadIdentities, colorVar } = useIdentity()
// ============================================================
import { ref, computed } from 'vue'
import { identityApi } from '@/api'
import type { Identity } from '@/types'

// 全局单例状态（模块级，非组件级）
const identities = ref<Identity[]>([])
const loaded = ref(false)
const loading = ref(false)

/** 身份调色板：token 名 → CSS 变量（与 variables.scss 色板一一对应） */
const COLOR_VARS: Record<string, string> = {
  primary: 'var(--primary)',
  mint: 'var(--mint)',
  butter: 'var(--butter)',
  sky: 'var(--sky)',
  lilac: 'var(--lilac)',
  strawberry: 'var(--strawberry)',
  gold: 'var(--gold)',
}

export function useIdentity() {
  async function loadIdentities(force = false) {
    if (loading.value) return
    if (loaded.value && !force) return
    loading.value = true
    try {
      identities.value = await identityApi.list()
      loaded.value = true
    } catch { /* http 层已提示 */ } finally {
      loading.value = false
    }
  }

  /** 下拉选项（首项「未归类」）；excludeArchived 用于新建表单（归档身份不再分配新任务） */
  function identityOptions(excludeArchived = false) {
    return [
      { label: '未归类', value: '' },
      ...identities.value
        .filter((i) => (excludeArchived ? i.is_active : true))
        .map((i) => ({ label: i.name, value: i.id })),
    ]
  }

  /** 只读的活跃身份（筛选器/徽章用） */
  const activeIdentities = computed(() => identities.value.filter((i) => i.is_active))

  function byId(id: string | null | undefined): Identity | undefined {
    if (!id) return undefined
    return identities.value.find((i) => i.id === id)
  }

  /** token → CSS 变量；未登记的 token 回退到 primary */
  function colorVar(token: string | null | undefined): string {
    return COLOR_VARS[token ?? ''] ?? 'var(--primary)'
  }

  return {
    identities,
    activeIdentities,
    identityOptions,
    loaded,
    loadIdentities,
    byId,
    colorVar,
  }
}
