// ============================================================
// 知识资源模块 API
// 对应 PRD §13.4
// ============================================================
import { http } from './http'
import type {
  Folder, Document, DocumentVersion, DocumentListQuery,
  CreateDocumentRequest, UpdateDocumentRequest, SearchResult, PaginatedData,
} from '@/types'

export const documentApi = {
  // 文件夹
  folders() {
    return http.get<Folder[]>('/folders')
  },
  createFolder(name: string, parent_id?: string) {
    return http.post<Folder>('/folders', { name, parent_id })
  },
  renameFolder(id: string, name: string) {
    return http.patch<Folder>(`/folders/${id}`, { name })
  },
  deleteFolder(id: string) {
    return http.delete<void>(`/folders/${id}`)
  },
  // 文档
  list(params?: DocumentListQuery) {
    return http.get<PaginatedData<Document>>('/documents', params as Record<string, unknown>)
  },
  create(data: CreateDocumentRequest) {
    return http.post<Document>('/documents', data)
  },
  detail(id: string) {
    return http.get<Document>(`/documents/${id}`)
  },
  update(id: string, data: UpdateDocumentRequest) {
    return http.patch<Document>(`/documents/${id}`, data)
  },
  remove(id: string) {
    return http.delete<void>(`/documents/${id}`)
  },
  versions(id: string) {
    return http.get<DocumentVersion[]>(`/documents/${id}/versions`)
  },
  versionDetail(id: string, ver: number) {
    return http.get<DocumentVersion>(`/documents/${id}/versions/${ver}`)
  },
  restoreVersion(id: string, ver: number) {
    return http.post<Document>(`/documents/${id}/versions/${ver}/restore`)
  },
  backlinks(id: string) {
    return http.get<Array<{ source_doc_id: string; source_title: string }>>(`/documents/${id}/backlinks`)
  },
  tags() {
    return http.get<string[]>('/tags')
  },
  search(q: string, type?: string) {
    return http.get<SearchResult>('/search', { q, type })
  },
}
