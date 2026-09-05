// ============================================================
// Vite 环境变量类型声明
// 对应 .env.development / .env.production
// ============================================================
/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 应用标题 */
  readonly VITE_APP_TITLE: string
  /** 运行环境 */
  readonly VITE_APP_ENV: 'development' | 'production'
  /** 后端API基础地址（可选，开发环境可通过proxy代理） */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

// Electron 渲染进程桥（由主进程 preload 注入；纯 Web 开发时缺失则优雅降级）
// __APP_VERSION__ 由 vite.config.ts define 注入
declare global {
  interface Window {
    api?: {
      minimize?: () => void
      maximize?: () => void
      close?: () => void
      on?: (channel: string, cb: (...args: unknown[]) => void) => void
    }
  }
  const __APP_VERSION__: string
}

export {}
