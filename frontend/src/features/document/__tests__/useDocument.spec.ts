// ============================================================
// features/document/composables/useDocument —— 业务 composable 单元测试
//
// 只 mock 领域 api；覆盖：列表读写状态、写操作后 refetch、
// 空搜索短路（不发请求且返回空结构）、非空搜索委托、文件夹拉取失败向上抛。
// ============================================================
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { PaginatedData } from '@/kernel/http/types'
import { documentApi } from '../api'
import { useDocument } from '../composables/useDocument'
import type { Document, SearchResult } from '../model'

vi.mock('../api', () => ({
  documentApi: {
    list: vi.fn(),
    folders: vi.fn(),
    tags: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    createFolder: vi.fn(),
    renameFolder: vi.fn(),
    deleteFolder: vi.fn(),
    search: vi.fn(),
  },
}))

const list = vi.mocked(documentApi.list)
const create = vi.mocked(documentApi.create)
const remove = vi.mocked(documentApi.remove)
const folders = vi.mocked(documentApi.folders)
const search = vi.mocked(documentApi.search)

function makeDoc(patch: Partial<Document> = {}): Document {
  return {
    id: 'd1',
    title: '文档',
    content: null,
    folder_id: null,
    folder_name: '收集箱',
    project_id: null,
    identity_id: null,
    tags: [],
    summary: null,
    ai_suggested_tags: [],
    version: 1,
    word_count: 0,
    created_at: '2026-01-01T00:00:00',
    updated_at: '2026-01-01T00:00:00',
    ...patch,
  } as unknown as Document
}

function page(docs: Document[]): PaginatedData<Document> {
  return { list: docs, total: docs.length, page: 1, page_size: 20 }
}

const emptySearchResult: SearchResult = {
  tasks: [],
  documents: [],
  conversations: [],
  actions: [],
}

beforeEach(() => {
  vi.clearAllMocks()
  list.mockResolvedValue(page([makeDoc()]))
})

describe('useDocument：读取与写入', () => {
  it('fetchDocuments 成功后写入列表与总数', async () => {
    list.mockResolvedValueOnce(page([makeDoc({ id: 'a' }), makeDoc({ id: 'b' })]))
    const doc = useDocument()

    await doc.fetchDocuments()

    expect(doc.documents.value.map((d) => d.id)).toEqual(['a', 'b'])
    expect(doc.total.value).toBe(2)
    expect(doc.loading.value).toBe(false)
  })

  it('createDocument 成功后会 refetch 列表', async () => {
    create.mockResolvedValueOnce(makeDoc({ id: 'new' }))
    const doc = useDocument()

    await doc.createDocument({ title: '新文档' })

    expect(create).toHaveBeenCalledWith({ title: '新文档' })
    expect(list).toHaveBeenCalledTimes(1)
  })

  it('deleteDocument 成功后会 refetch 列表', async () => {
    remove.mockResolvedValueOnce(undefined)
    const doc = useDocument()

    await doc.deleteDocument('d1')

    expect(remove).toHaveBeenCalledWith('d1')
    expect(list).toHaveBeenCalledTimes(1)
  })
})

describe('useDocument：搜索与文件夹', () => {
  it('空搜索词直接短路：不发请求，返回空结构', async () => {
    const doc = useDocument()

    await expect(doc.search('')).resolves.toEqual(emptySearchResult)
    await expect(doc.search('   ')).resolves.toEqual(emptySearchResult)
    expect(search).not.toHaveBeenCalled()
  })

  it('非空搜索词委托给 api（保留原始 query）', async () => {
    search.mockResolvedValueOnce(emptySearchResult)
    const doc = useDocument()

    await doc.search('  雅思  ')

    expect(search).toHaveBeenCalledWith('  雅思  ')
  })

  it('fetchFolders 失败时向上抛错，不吞异常', async () => {
    folders.mockRejectedValueOnce(new Error('folders down'))
    const doc = useDocument()

    await expect(doc.fetchFolders()).rejects.toThrow('folders down')
    expect(doc.folders.value).toEqual([])
  })
})
