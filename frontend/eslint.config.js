// ============================================================
// ESLint 9 Flat Config —— 正确性优先 + ADR-0007 分层边界强制
//
// 核心目标不是"风格统一"（那由 Prettier 负责），而是把
// docs/architecture/ADR/0007-frontend-feature-architecture.md 的依赖规则
// 变成 CI 里会变红的硬约束：
//   1. kernel/   无业务语义技术底座：不得 import shared / features / 过渡期按类型目录
//   2. shared/   设计系统与壳：不得 import features / 过渡期按类型目录
//   3. features/ 领域包：不得 import 过渡期按类型目录（api/views/composables/stores/components），
//                跨领域只允许 `@/features/<other>` 入口，禁止深链内部文件
//
// 过渡期说明：P4 正在删除 api/ views/ composables/ stores/ components/ 等旧目录；
// 上述"过渡期目录"规则会在 P4 清空后自然变成"不存在路径"的防护网。
//
// 运行：npm run lint（= eslint src --max-warnings=0）
// ============================================================
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import pluginVue from 'eslint-plugin-vue'
import vueParser from 'vue-eslint-parser'
import prettier from 'eslint-config-prettier'

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), 'src')

/** 运行时枚举 features/ 下的领域目录：跨领域"深链"规则需要其它领域的清单 */
function readDirs(dir) {
  try {
    return fs
      .readdirSync(path.join(SRC, dir), { withFileTypes: true })
      .filter((d) => d.isDirectory())
      .map((d) => d.name)
      .sort()
  } catch {
    return []
  }
}

const FEATURES = readDirs('features')

/** ADR-0007 过渡期按类型目录（P4 清空中；不得被 kernel/shared/features 反问引用） */
const LEGACY_TYPE_DIRS = ['api', 'views', 'composables', 'stores', 'components']

/** no-restricted-imports 规则构造：[glob, message] 列表 → ESLint 配置 */
function restricted(groups) {
  return [
    'error',
    {
      patterns: groups.map(([glob, message]) => ({ group: [glob], message })),
    },
  ]
}

/**
 * 禁止"目录入口及其全部子路径"：no-restricted-imports 的 patterns 采用
 * gitignore 语义 —— 一条 `@/features` 会同时命中 `@/features/pet`，
 * 因此每个目录只写一条，避免同一 import 被报重复错误。
 */
function dirAndChildren(base) {
  return [base]
}

/** 过渡期按类型目录的禁止模式（一条 `@/api` 同时覆盖 `@/api/task` 等子路径） */
function legacyPatterns(message) {
  return LEGACY_TYPE_DIRS.map((d) => [`@/${d}`, message])
}

const KERNEL_MSG_SHARED = 'ADR-0007：kernel 是纯技术底座，不得 import shared（公共层），依赖只能 kernel ← 上层'
const KERNEL_MSG_FEATURES = 'ADR-0007：kernel 不得 import features（领域层），依赖方向只能是 features → kernel'
const KERNEL_MSG_LEGACY = 'ADR-0007：kernel 不得 import 过渡期按类型目录，技术能力请放进 kernel/'
const SHARED_MSG_FEATURES = 'ADR-0007：shared 只能依赖 kernel，不得 import features（领域层）'
const SHARED_MSG_LEGACY = 'ADR-0007：shared 不得 import 过渡期按类型目录，请改用 kernel/ 或 shared/ 内模块'
const FEATURE_MSG_LEGACY = 'ADR-0007：features 不得 import 过渡期按类型目录（api/views/composables/stores/components 正在清空），请走 @/kernel 或 @/shared'

export default tseslint.config(
  // ---------- 忽略：产物 / 原生工程 / 生成文件 ----------
  {
    ignores: [
      'dist/**',
      'android/**',
      'node_modules/**',
      'public/**',
      'coverage/**',
      'src/auto-imports.d.ts',
      'src/components.d.ts',
      'src/env.d.ts',
    ],
  },

  // ---------- 基础：JS recommended + TS（非类型检查子集） + Vue3 essential ----------
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...pluginVue.configs['flat/essential'],

  // .vue：用 vue-eslint-parser，<script> 部分交给 typescript-eslint 解析
  {
    files: ['**/*.vue'],
    languageOptions: {
      parser: vueParser,
      parserOptions: {
        parser: tseslint.parser,
        ecmaVersion: 'latest',
        sourceType: 'module',
        extraFileExtensions: ['.vue'],
      },
    },
  },

  // TS 项目惯例：未定义全局交给 TypeScript 检查，避免与 DOM/Node 全局及
  // unplugin-auto-import 注入的符号打架（本项目 auto-imports.d.ts 为空，仍保持该惯例）
  {
    files: ['**/*.{ts,vue}'],
    rules: {
      'no-undef': 'off',
      // App.vue 等应用壳文件是单词组件名，属框架惯例，不参与该规则
      'vue/multi-word-component-names': 'off',

      // 未使用变量：与 eslint 核心默认对齐（catch 绑定不报，忽略以 _ 开头的占位），
      // 并允许 `const { checked, ...rest }` 这类"解构丢弃字段"的写法
      '@typescript-eslint/no-unused-vars': [
        'error',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
          caughtErrors: 'none',
          ignoreRestSiblings: true,
        },
      ],

      // 全角空格（U+3000）在本项目的模板/模板字符串里是**有意的中文排版**
      // （如 `clarifications.join('　')`、计划文本的缩进），不是笔误
      'no-irregular-whitespace': [
        'error',
        { skipStrings: true, skipTemplates: true, skipComments: true, skipRegExps: true },
      ],

      // 生成的打印 HTML 里保留 `<\/script>`：防止内联解析提前闭合；
      // JS 语义上与 `</script>` 等价，但被本规则判为"多余转义"，故关闭
      'no-useless-escape': 'off',
    },
  },

  // ---------- ADR-0007 ①：kernel 不得依赖 shared / features / 过渡期目录 ----------
  {
    files: ['src/kernel/**/*.{ts,vue}'],
    rules: {
      'no-restricted-imports': restricted([
        ...dirAndChildren('@/shared').map((g) => [g, KERNEL_MSG_SHARED]),
        ...dirAndChildren('@/features').map((g) => [g, KERNEL_MSG_FEATURES]),
        ...legacyPatterns(KERNEL_MSG_LEGACY),
      ]),
    },
  },

  // ---------- ADR-0007 ②：shared 不得依赖 features / 过渡期目录 ----------
  {
    files: ['src/shared/**/*.{ts,vue}'],
    rules: {
      'no-restricted-imports': restricted([
        ...dirAndChildren('@/features').map((g) => [g, SHARED_MSG_FEATURES]),
        ...legacyPatterns(SHARED_MSG_LEGACY),
      ]),
    },
  },

  // ---------- ADR-0007 ③：features 不得回头引用过渡目录 / 跨领域深链 ----------
  // 每个领域单独一块：允许自身内部任意路径，禁止深链到其它领域的内部文件
  ...FEATURES.map((feature) => ({
    files: [`src/features/${feature}/**/*.{ts,vue}`],
    rules: {
      'no-restricted-imports': restricted([
        ...legacyPatterns(FEATURE_MSG_LEGACY),
        ...FEATURES.filter((other) => other !== feature).map((other) => [
          `@/features/${other}/**`,
          `ADR-0007：跨领域只允许 import '@/features/${other}'（对方 index.ts 唯一出口），禁止深链内部文件`,
        ]),
      ]),
    },
  })),

  // ---------- 关闭与 Prettier 冲突的格式规则（必须放最后） ----------
  prettier,
)
