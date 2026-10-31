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
    // jsdom + @vue/test-utils 组件测试内存占用高：默认按 CPU 核数并发在 16+ 文件时会 OOM
    // （本机 16 核曾出现 `FATAL ERROR: Zone Allocation failed`）。显式限并发，
    // 使本地与 2 核 CI runner 行为一致。
    maxWorkers: 2,
    // 不隐藏 console.warn（项目里有意为之的告警要看得见）
    silent: false,
    // 覆盖率：阈值棘轮（只许上调；下调须在 CHANGELOG 说明理由）。
    // 阈值依据（2026-10-31，Phase11 task-46 实测）：lines 82.4 / branches 89.92 /
    // functions 46.36 / statements 82.4。
    // ⚠️ 统计面变化说明：Phase11 的 router lazy-loader 测试会真实 await 24 个 view
    // 模块 → 这些模块首次进入统计面：functions 分母 382→591（+209）、已覆盖函数 260→274
    //（绝对值仍上升），因此 functions 阈值按**新口径**重算为 45（不是回退）。
    // lines/branches 大幅上升（44.01→82.4 / 82.36→89.92）并各留约 1pp 余量（81/88）。
    // 上调历史：{12,65,40,12}（Phase5）→ {20,72,52,20}（Phase6）→ {31,76,59,31}（Phase7）
    //           → {36,78,63,36}（Phase8）→ {40,79,64,40}（Phase9）→ {43,81,67,43}（Phase10）→ 当前。
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary'],
      reportsDirectory: './coverage',
      thresholds: { lines: 81, branches: 88, functions: 45, statements: 81 },
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
