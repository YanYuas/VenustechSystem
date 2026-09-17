// ============================================================
// Capacitor 配置（移动端方案 M4 · Android 壳）
//
// 壳里不打包后端：App 是客户端，API 指向 PC 的 Tailscale IP。
// 打包步骤见 docs/management/移动端与DeepSeek语音助理方案-2026-09-17.md §M4
// ============================================================
import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'com.yanyu.qimingxing',
  appName: '启明星',
  webDir: 'dist',
  // 用系统 WebView 的混合内容策略放行 http（流量在 Tailscale 隧道内加密）
  server: {
    androidScheme: 'https',
    cleartext: true,
  },
  android: {
    allowMixedContent: true,
  },
  plugins: {
    SpeechRecognition: {
      language: 'zh-CN',
    },
  },
}

export default config
