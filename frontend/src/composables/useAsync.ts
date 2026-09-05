// ============================================================
// useAsync —— 通用异步请求封装
// 统一管理 loading / error / data / retry
// 用法: const { data, loading, error, execute } = useAsync((id) => api.getDetail(id))
//       execute('123')  // 传参调用
// ============================================================
import { ref, shallowRef, type Ref } from 'vue'

interface UseAsyncOptions<T> {
  immediate?: boolean
  initialValue?: T
  onSuccess?: (data: T) => void
  onError?: (err: Error) => void
  /** immediate 为 true 时使用的默认参数 */
  immediateArgs?: unknown[]
}

// 泛型 Args 约束为 unknown[]（非 any[]）：允许任意参数元组，同时避免显式 any
export function useAsync<T, Args extends unknown[] = []>(
  fn: (...args: Args) => Promise<T>,
  options: UseAsyncOptions<T> = {},
) {
  const { immediate = false, initialValue, onSuccess, onError, immediateArgs = [] } = options
  const data = shallowRef<T | undefined>(initialValue) as Ref<T | undefined>
  const loading = ref(false)
  const error = ref<Error | null>(null)

  async function execute(...args: Args): Promise<T | undefined> {
    loading.value = true
    error.value = null
    try {
      const result = await fn(...args)
      data.value = result
      onSuccess?.(result)
      return result
    } catch (err) {
      const e = err instanceof Error ? err : new Error(String(err))
      error.value = e
      onError?.(e)
      // 向调用方抛出：防止「失败仍提示成功」的假成功（如创建任务失败仍弹已创建）
      // http 层已对 ApiError 统一 toast；未捕获的 rejection 由全局 errorHandler 兜底
      throw e
    } finally {
      loading.value = false
    }
  }

  function reset() {
    data.value = initialValue
    error.value = null
    loading.value = false
  }

  if (immediate) {
    // unknown[] 元组 → 具体 Args：需双断言（运行时仅透传，安全）
    // 错误已写入 error 状态，此处吞掉避免 unhandled rejection
    execute(...(immediateArgs as unknown as Args)).catch(() => { /* error 状态已记录 */ })
  }

  return { data, loading, error, execute, reset }
}
