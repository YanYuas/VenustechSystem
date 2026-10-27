# ADR-0008 请求体中的 `null` 语义：显式 null = 清空，省略 = 不改

- 状态：**已采纳**（2026-10-27）
- 相关：[ARCHITECTURE.md](../../../ARCHITECTURE.md) §4.2、`backend/app/services/*_service.py`、`frontend/src/types/*.ts`

## 背景

Phase 1 契约对齐时留了一个悬而未决的问题：后端 Update 类 schema 普遍是
`field: T | None = None`，而前端请求类型写成 `field?: T`（只表达"可省略"）。
两者差在**显式 null** 的语义：

- `{}` —— 字段缺席；
- `{"project_id": null}` —— 字段存在且为 null。

后端实际实现（已核实）：

```python
payload = data.model_dump(exclude_unset=True)   # 只取"客户端真正发来的字段"
...
if "project_id" in payload:
    doc.project_id = payload["project_id"]      # None = 解除关联（清空）
```

即：**省略 = 不改；显式 null = 清空**。UI 也确实依赖这个语义
（文档/任务的"清除项目""移除文件夹"就是发 null）。前端类型却写不出 null（TS 会报错），
只能靠 `as any` 或干脆不清空 —— 这是类型在撒谎。

## 决策

1. **后端语义不变**：`exclude_unset=True` + 字段存在即写入，null 表示清空。
2. **前端请求类型如实建模**：凡后端声明 `T | None = None` 且 service 按"存在即赋值"处理的
   可空字段，前端写 `field?: T | null`。
3. **响应类型保持非可选**（后端保证返回时一定有条目；可空用 `T | null` 而不是 `?`）。
4. **输入/输出分离**：`XxxRequest` 与 `Xxx` 允许字段可选性不同，不再强求"一个类型两用"。
5. 代码注释中必须写明"null = 清空"，避免下一个人把它当 bug"修掉"。

本轮落地范围（Phase 1 审计列出的 24 处）：Task / Document / BatchTask / ConvertTask /
Project 等 Update/Create 请求的可空字段。实现随 P3 领域迁移一并完成（类型要搬家，一次改到位）。

## 后果

- ✅ 前端可以类型安全地表达"清除关联"，不再依赖 `as any`。
- ✅ 契约与后端真实行为一致，避免"类型窄于实现"的隐性 bug。
- ⚠️ 调用方需要**显式选择**：不确定是否要清空时不要传 null（传了就是清空）。
- ⚠️ 响应侧若出现 `undefined` 与 `null` 混用，属于后端 bug，不应在前端类型里兼容。

## 替代方案

- **让后端把 null 当省略**：会破坏"清除关联"能力，UI 得新增专用 clear 接口。否决。
- **保持 `field?: T` 不变**：类型与实现不符，等于默许 `as any`。否决。
- **用独立 ClearXXX 接口**：接口数量翻倍，收益不足。否决。
