// ============================================================
// kernel/http —— HTTP 客户端（kernel 唯一公开出口，ADR-0007）
//
// P4 起本文件**只做公开导出**，实现按职责拆分：
//   client.ts    baseURL / token / 超时与重试参数 / 环境探测
//   errors.ts    ApiError / ApiUnreachableError / OfflineQueuedError / 网络失败分类
//   request.ts   request / doRequest（信封解包、错误映射、重试、离线入队）与 http 对象
//   sse.ts       sseRequest（流式）
//   types.ts     统一响应信封 / 分页 / SSE 事件类型
//   connectivity.ts  后端连通性状态（http 与 toast 共享）
//
// 公开 API 与行为与拆分前完全一致（P4 验收脚本做过导出列表 diff）。
// 依赖边界：kernel 不得 import shared / features / api / views。
// ============================================================

// ---------- 请求客户端（含表单上传 postForm） ----------
export { http, setOfflineQueueHandler } from './request'
export type { OfflineEnqueueHandler } from './request'

// ---------- 运行时配置（服务地址 / 访问令牌） ----------
export { getApiBase, getApiToken, setApiBase, setApiToken } from './client'

// ---------- 错误类型 ----------
export { ApiError, ApiUnreachableError, OfflineQueuedError } from './errors'

// ---------- SSE 流式请求 ----------
export { sseRequest } from './sse'
