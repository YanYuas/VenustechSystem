// ============================================================
// 长期资产库 composable（二期 M10 P0）
// ============================================================
import { ref } from 'vue'
import { useDataCache } from './useDataCache'
import { assetApi } from '@/api'
import type { SOP, PromptTemplate, Skill, ProjectMemory } from '@/types'

export function useAsset() {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const { cachedFetch } = useDataCache()
  const sops = ref<SOP[]>([])
  const prompts = ref<PromptTemplate[]>([])
  const skills = ref<Skill[]>([])
  const memories = ref<ProjectMemory[]>([])

  async function fetchSOPs() {
    loading.value = true
    try {
      const data = await cachedFetch('asset:sops', () => assetApi.listSOPs({ page: 1, page_size: 50 }))
      sops.value = data.list
    } catch (e: unknown) { error.value = e instanceof Error ? e.message : String(e) }
    finally { loading.value = false }
  }

  async function fetchPrompts() {
    loading.value = true
    try {
      const data = await assetApi.listPrompts({ page: 1, page_size: 50 })
      prompts.value = data.list
    } catch (e: unknown) { error.value = e instanceof Error ? e.message : String(e) }
    finally { loading.value = false }
  }

  async function fetchSkills() {
    loading.value = true
    try {
      const data = await assetApi.listSkills({ page: 1, page_size: 50 })
      skills.value = data.list
    } catch (e: unknown) { error.value = e instanceof Error ? e.message : String(e) }
    finally { loading.value = false }
  }

  async function fetchMemories() {
    loading.value = true
    try {
      const data = await assetApi.listMemories({ page: 1, page_size: 50 })
      memories.value = data.list
    } catch (e: unknown) { error.value = e instanceof Error ? e.message : String(e) }
    finally { loading.value = false }
  }

  return { loading, error, sops, prompts, skills, memories, fetchSOPs, fetchPrompts, fetchSkills, fetchMemories }
}
