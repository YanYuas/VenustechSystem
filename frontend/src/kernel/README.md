# kernel/ —— 无业务语义的技术底座（ADR-0007）

`kernel/` 只放「任何领域都会用、且不知道业务存在」的基础设施。**不得** import
`shared/`、`features/`，也不得 import 已删除的旧过渡目录（`api/ views/ composables/
stores/ types/ utils/ components/ constants/ directives/`）。该规则由
`scripts/audit_architecture.py` 的 **R14** 强制（P4 起无 WARN 豁免，直接 ERROR）。

## 模块职责

```
kernel/
├── http/          HTTP 单点漏斗（唯一网络出口）
│   ├── index.ts       # 唯一公开出口（只 re-export，不写实现）
│   ├── client.ts      # baseURL / token / 超时常量 / 重试参数 / Capacitor 环境探测
│   ├── errors.ts      # ApiError / ApiUnreachableError / OfflineQueuedError / isNetworkFailure
│   ├── request.ts     # request / doRequest（信封解包、错误映射、重试、离线入队钩子）+ http 对象
│   ├── sse.ts         # sseRequest（SSE 流式）
│   ├── types.ts       # 统一响应信封 ApiResponse / 分页 / ApiErrorCode / SSE 事件类型
│   └── connectivity.ts# 后端连通性状态（http 与 toast 共享，避免循环依赖）
├── ui/
│   ├── index.ts       # ui 层公开出口
│   ├── toast.ts       # 命令式轻提示（含后端不可达时的错误提示收敛）
│   ├── modal.ts       # 命令式弹窗栈（BaseModal/ModalHost 读取 stack）
│   ├── useShortcuts.ts# 全局快捷键注册
│   └── types.ts       # ToastItem / ToastType
├── offline/
│   ├── offlineQueue.ts     # Pinia store：pending/failed/flushing + online 自动重放
│   ├── offlineQueueCore.ts # 队列核心（FIFO/失败计数/重试/持久化接口）
│   └── offlineQueueIdb.ts  # IndexedDB 存储实现
├── async/useAsync.ts       # 异步状态包装（loading/error/execute）
├── device/useDevice.ts     # 设备/平台探测
└── electron.ts             # Electron 壳能力探测
```

## http 的公开 API（P4 拆分后与拆分前完全一致）

值：`http`、`getApiBase`、`setApiBase`、`getApiToken`、`setApiToken`、
`ApiError`、`ApiUnreachableError`、`OfflineQueuedError`、`setOfflineQueueHandler`、`sseRequest`
类型：`OfflineEnqueueHandler`

行为契约（拆分时逐字保留，改动需过行为脚本）：

- 常规超时 15s；已判定不可达时 4s 快速失败；SSE 首包 60s；
- 幂等请求（GET/HEAD/PUT/DELETE）网络失败重试 1 次、间隔 2s；`ApiUnreachableError` 不重试；
- 写操作（POST/PATCH/PUT/DELETE）在网络失败/离线时交给离线队列重放；
  `postForm`（FormData 上传）**永不入队**且不手写 Content-Type；
- 502/503/504 归为「后端不可达」，触发 toast 节流提示与连通性自愈。

## 边界纪律

1. `kernel` 只能依赖 `kernel` 自身与第三方库（vue/pinia 等）。
2. 需要 UI 反馈时 import `kernel/ui`；需要网络时 import `kernel/http`；不允许绕过。
3. 业务语义（任务/复盘/桌宠…）不得进入 `kernel`；领域逻辑归 `features/<domain>`。
4. 新增 kernel 模块时同步更新本 README 的目录表，并跑 `python scripts/audit_architecture.py --strict`。
