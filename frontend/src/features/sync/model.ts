// ============================================================
// features/sync/model.ts —— sync 领域模型（迁移批次 P3，ADR-0007）
// ============================================================

// ---------- 从 api.ts 收编的内联类型 ----------
export interface SyncPolicyOut {
  policy: Record<string, string>
  synced_tables: string[]
}

export interface SyncPackage {
  name: string
  path: string
  size: number
  modified_at: number
}

export interface SyncImportStats {
  ops: number
  insert: number
  update: number
  skipped: number
}
