// ============================================================
// useDocument —— 知识资源模块业务逻辑
// ============================================================
import { ref } from 'vue'
import { documentApi } from '@/api'
import { useAsync } from './useAsync'
import type { Document, Folder, DocumentListQuery, CreateDocumentRequest, UpdateDocumentRequest, SearchResult } from '@/types'

export function useDocument() {
  const documents = ref<Document[]>([])
  const total = ref(0)
  const folders = ref<Folder[]>([])
  const tags = ref<string[]>([])
  const query = ref<DocumentListQuery>({ page: 1, page_size: 20 })

  const { loading, execute: fetchDocuments } = useAsync(
    async () => {
      const res = await documentApi.list(query.value)
      documents.value = res.list
      total.value = res.total
      return res
    },
  )

  const { execute: fetchFolders } = useAsync(
    async () => {
      folders.value = await documentApi.folders()
      return folders.value
    },
  )

  const { execute: fetchTags } = useAsync(
    async () => {
      tags.value = await documentApi.tags()
      return tags.value
    },
  )

  const { execute: createDocument } = useAsync(
    async (data: CreateDocumentRequest) => documentApi.create(data),
    { onSuccess: () => fetchDocuments() },
  )

  const { execute: updateDocument } = useAsync(
    async (id: string, data: UpdateDocumentRequest) => documentApi.update(id, data),
  )

  const { execute: deleteDocument } = useAsync(
    async (id: string) => documentApi.remove(id),
    { onSuccess: () => fetchDocuments() },
  )

  const { execute: createFolder } = useAsync(
    async (name: string, parent_id?: string) => documentApi.createFolder(name, parent_id),
    { onSuccess: () => fetchFolders() },
  )

  const { execute: renameFolder } = useAsync(
    async (id: string, name: string) => documentApi.renameFolder(id, name),
    { onSuccess: () => fetchFolders() },
  )

  const { execute: deleteFolder } = useAsync(
    async (id: string) => documentApi.deleteFolder(id),
    { onSuccess: () => { fetchFolders(); fetchDocuments() } },
  )

  async function search(q: string): Promise<SearchResult> {
    if (!q.trim()) return { tasks: [], documents: [], conversations: [], actions: [] }
    return documentApi.search(q)
  }

  return {
    documents,
    total,
    folders,
    tags,
    query,
    loading,
    fetchDocuments,
    fetchFolders,
    fetchTags,
    createDocument,
    updateDocument,
    deleteDocument,
    createFolder,
    renameFolder,
    deleteFolder,
    search,
  }
}
