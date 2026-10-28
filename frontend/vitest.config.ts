// ============================================================
// Vitest 配置（前端单元测试）—— 2026-10-11 新增
//
// 为什么单开一份配置而不是复用 vite.config.ts：
//   应用配置里挂了 AutoImport / Components 两个自动导入插件（会写
//   src/auto-imports.d.ts、src/components.d.ts）。单元测试不需要它们，
//   且让测试跑动时反复改写 .d.ts 会污染工作树。故此处只保留
//   vue 插件 + `@` 别名 + `__APP_VERSION__` define（与运行时一致）。
//
// 运行：
//   npm run test              （= vitest run，单次）
//   npm run test:watch        （监听模式）
//   node_modules/.bin/vitest run src/utils/__tests__/reportHtml.spec.ts
// ============================================================
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  define: {
    // 与 vite.config.ts 保持一致：constants/index.ts 里 APP.version 用到
    __APP_VERSION__: JSON.stringify(process.env.npm_package_version ?? '0.0.0-test'),
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/__tests__/**/*.spec.ts'],
    setupFiles: ['src/shared/test/setup.ts'],
    // 每个用例后还原 spy / mock，避免跨用例串扰
    restoreMocks: true,
    // 不隐藏 console.warn（项目里有意为之的告警要看得见）
    silent: false,
    // 覆盖率：阈值棘轮（只许上调；下调须在 CHANGELOG 说明理由）。
    // 阈值依据（2026-10-28，Phase6 task-30 实测）：lines 20.95 / branches 73.25 /
    // functions 53.65 / statements 20.95。此处各留约 1 个点余量（20/72/52/20）
    // 吸收 CI 环境抖动；上调后覆盖率回退会直接让 CI 的 threshold ratchet 变红。
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary'],
      reportsDirectory: './coverage',
      thresholds: { lines: 20, branches: 72, functions: 52, statements: 20 },
      // 统计 src 下全部实现代码；测试自身与生成物不计入
      include: ['src/**/*.{ts,vue}'],
      exclude: [
        'src/**/*.d.ts',
        'src/main.ts',
        'src/app/main.ts',
        'src/**/views/**',
        'src/**/__tests__/**',
        'src/auto-imports.d.ts',
        'src/components.d.ts',
        'src/env.d.ts',
        'src/shared/styles/**',
        'src/**/README.md',
      ],
    },
  },
})
