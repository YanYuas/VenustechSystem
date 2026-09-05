// ============================================================
// Electron 桥 —— 渲染进程访问主进程能力
// 纯 Web 开发（vite dev）时 window.api 缺失，所有调用安全 no-op
// 依据: 技术架构 v2.0 ADR-002（Electron 容器）
// ============================================================

export const electron = {
  get isElectron() {
    return typeof window !== 'undefined' && Boolean(window.api)
  },
  minimize() {
    window.api?.minimize?.()
  },
  maximize() {
    window.api?.maximize?.()
  },
  close() {
    window.api?.close?.()
  },
}
