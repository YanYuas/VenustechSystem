// ============================================================
// 资源中心 composable（二期 M7）
// ============================================================
import { ref } from 'vue'
import { resourceApi } from '@/api'
import type { InboxItem, Template, Domain } from '@/types'

export function useResource() {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const inboxItems = ref<InboxItem[]>([])
  const templates = ref<Template[]>([])
  const domains = ref<Domain[]>([])

  async function fetchInbox(status?: string) {
    loading.value = true
    try {
      inboxItems.value = await resourceApi.listInbox(status)
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchTemplates(category?: string) {
    loading.value = true
    try {
      templates.value = await resourceApi.listTemplates(category)
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchDomains() {
    loading.value = true
    try {
      domains.value = await resourceApi.listDomains()
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }
  return { loading, error, inboxItems, templates, domains, fetchInbox, fetchTemplates, fetchDomains }
}
