// ============================================================
// features/auth/model.ts —— auth 领域模型（迁移批次 P3，ADR-0007）
// auth 是 API-only 领域（无专属页面）：请求/响应类型统一复用 shared/types/user。
// ============================================================
export type {
  UserConfig,
  InitRequest,
  UpdateConfigRequest,
  ApiVerifyResult,
} from '@/shared/types/user'
