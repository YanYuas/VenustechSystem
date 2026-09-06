// ============================================================
// 长期资产库 composable（二期 M10）
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

  async function fetchSOPs(category?: string) {
    loading.value = true
    try { sops.value = await assetApi.listSOPs(category) }
    catch (e: unknown) { error.value = e instanceof Error ? e.message : String(e) }
    finally { loading.value = false }
  }

  async function fetchPrompts(category?: string) {
    loading.value = true
    try { prompts.value = await assetApi.listPrompts(category) }
    catch (e: unknown) { error.value = e instanceof Error ? e.message : String(e) }
    finally { loading.value = false }
  }

  async function fetchSkills() {
    loading.value = true
    try { skills.value = await cachedFetch('asset:skills', () => assetApi.listSkills()) }
    catch (e: unknown) { error.value = e instanceof Error ? e.message : String(e) }
    finally { loading.value = false }
  }

  async function fetchMemories(projectId?: string) {
    loading.value = true
    try { memories.value = await assetApi.listMemories(projectId) }
    catch (e: unknown) { error.value = e instanceof Error ? e.message : String(e) }
    finally { loading.value = false }
  }
  return { loading, error, sops, prompts, skills, memories, fetchSOPs, fetchPrompts, fetchSkills, fetchMemories }
}
