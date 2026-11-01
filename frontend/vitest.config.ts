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
    // ⚠️ 口径 v2（2026-11-01 Phase18 task-66，vite 8 + vitest 5 迁移）：
    // coverage-v8 5 内部把 remapper 从 v8-to-istanbul 换成 ast-v8-to-istanbul（AST-aware），
    // 统计粒度改变（同一份源码 + 同一批 578 条测试）：
    //   lines 分母 7464→3022、branches 分母 1403→1849、functions 分母 649→1079（AST 计数更细）；
    //   百分比 84.79→71.01 / 89.95→65.38 / 52.85→49.95（statements 84.79→70.41）。
    // 反证漂移来源（逐项隔离实验，均用同一批测试跑 --coverage）：
    //   vite 8.3.5 + plugin-vue 6.0.10 + vitest 5 → lines 2146/3022
    //   vite 7.3.7 + plugin-vue 6.0.10 + vitest 5 → 2146/3022（完全相同）
    //   vite 6.4.5 + plugin-vue 5.2.4 + vitest 5 → 2146/3022（完全相同）
    //   → 与 vite 内核 / plugin-vue 版本无关，纯 vitest/coverage-v8 5 的 remapper 变化。
    // 无法通过配置恢复等价口径（v8-to-istanbul 路径已移除，`experimentalAstAwareRemapping` 不复存在），
    // 故做**显式重校准**：新口径实测（连跑两次一致）lines 71.01 / branches 65.38 /
    // functions 49.95 / statements 70.41，阈值按"实测留约 1pp"设为 {70,64,49,69}；
    // 逐文件 diff 与双口径记录见 docs/guides/frontend.md §九「覆盖率口径 v2」。
    // 口径 v1（至 Phase17）阈值为 {83,89,51,83}（lines covered/total 6329/7464）；
    // 口径 v1 内上调历史：{12,65,40,12}（Phase5）→ {20,72,52,20}（Phase6）→ {31,76,59,31}（Phase7）
    //   → {36,78,63,36}（Phase8）→ {40,79,64,40}（Phase9）→ {43,81,67,43}（Phase10）
    //   → {81,88,45,81}（Phase11）→ {81,88,48,81}（Phase12/13）→ {83,89,51,83}（Phase16）。
    // 口径 v2 起：{70,64,49,69}（Phase18）→ 当前（新口径内继续只许上调）。
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary'],
      reportsDirectory: './coverage',
      thresholds: { lines: 70, branches: 64, functions: 49, statements: 69 },
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
