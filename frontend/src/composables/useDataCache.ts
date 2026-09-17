// ============================================================
// 数据缓存 composable（避免重复API请求）
// 用于composables层：相同参数的请求在TTL内直接返回缓存
// ============================================================

interface CacheEntry<T> {
  data: T
  timestamp: number
}

const cacheStore = new Map<string, CacheEntry<unknown>>()
const DEFAULT_TTL = 30_000 // 30秒

export function useDataCache() {
  function getCache<T>(key: string): T | null {
    const entry = cacheStore.get(key)
    if (!entry) return null
    if (Date.now() - entry.timestamp > DEFAULT_TTL) {
      cacheStore.delete(key)
      return null
    }
    return entry.data as T
  }

  function setCache<T>(key: string, data: T): void {
    cacheStore.set(key, { data, timestamp: Date.now() })
  }

  function invalidate(key: string): void {
    cacheStore.delete(key)
  }

  function invalidatePrefix(prefix: string): void {
    for (const key of cacheStore.keys()) {
      if (key.startsWith(prefix)) cacheStore.delete(key)
    }
  }

  function clear(): void {
    cacheStore.clear()
  }

  /**
   * 带缓存的异步请求
   * @param key 缓存键
   * @param fetcher 请求函数
   * @param force 是否强制刷新
   */
  async function cachedFetch<T>(
    key: string,
    fetcher: () => Promise<T>,
    force = false,
  ): Promise<T> {
    if (!force) {
      const cached = getCache<T>(key)
      if (cached !== null) return cached
    }
    const data = await fetcher()
    setCache(key, data)
    return data
  }

  return { getCache, setCache, invalidate, invalidatePrefix, clear, cachedFetch }
}
