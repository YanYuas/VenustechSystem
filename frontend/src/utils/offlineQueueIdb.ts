// ============================================================
// IndexedDB 队列存储（mod-tools F4.3）
//
// 库名 venustech_offline_queue / 表名 queue / 主键 id（自增）
// 只暴露 QueueStorage 契约需要的五个方法，保持实现可替换
// （单测里换成内存实现即可）。
// ============================================================
import type { QueueEntry, QueueStorage } from './offlineQueueCore'

const DB_NAME = 'venustech_offline_queue'
const STORE = 'queue'
const DB_VERSION = 1

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error ?? new Error('IndexedDB 打开失败'))
  })
}

async function withStore<T>(
  mode: IDBTransactionMode,
  fn: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  const db = await openDb()
  return new Promise<T>((resolve, reject) => {
    const tx = db.transaction(STORE, mode)
    const req = fn(tx.objectStore(STORE))
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error ?? new Error('IndexedDB 操作失败'))
    tx.oncomplete = () => db.close()
  })
}

export function createIndexedDbStorage(): QueueStorage {
  return {
    async add(entry: QueueEntry) {
      const id = await withStore<IDBValidKey>('readwrite', (s) => s.add(entry))
      return Number(id)
    },
    async all() {
      return (await withStore<QueueEntry[]>('readonly', (s) => s.getAll())) ?? []
    },
    async update(entry: QueueEntry) {
      await withStore('readwrite', (s) => s.put(entry))
    },
    async remove(id: number) {
      await withStore('readwrite', (s) => s.delete(id))
    },
    async removeFailed(maxRetries: number) {
      const items = await withStore<QueueEntry[]>('readonly', (s) => s.getAll())
      let n = 0
      for (const it of items ?? []) {
        if (it.retries >= maxRetries && it.id !== undefined) {
          await withStore('readwrite', (s) => s.delete(it.id as number))
          n += 1
        }
      }
      return n
    },
  }
}
