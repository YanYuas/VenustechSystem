import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import { fileURLToPath, URL } from 'node:url'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [
    vue(),
    // Element Plus 按需引入（ep 组件/API 用到才打包，替代全量 app.use）
    AutoImport({
      resolvers: [ElementPlusResolver()],
      dts: 'src/auto-imports.d.ts',
    }),
    Components({
      resolvers: [ElementPlusResolver()],
      // P3 起组件散落在 shared / features / app 三处（components/ 过渡目录已清空）。
      // 用 globs 而不是 dirs：避免 deep 扫描把 features/*/views 也注册成全局组件。
      globs: [
        'src/shared/components/**/*.vue',
        'src/features/*/components/**/*.vue',
        'src/app/layout/*.vue',
      ],
      dts: 'src/components.d.ts',
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  define: {
    __APP_VERSION__: JSON.stringify(process.env.npm_package_version ?? '0.1.0'),
  },
  server: {
    port: 5173,
    // 显式占用端口：ops/start.ps1 -Mode dev -Verify 以 5173 为就绪判据，
    // 若允许静默换端口（strictPort:false）会导致 -Verify 超时（windows-startup 门禁）。
    // 冲突时直接失败，比"起来了但没人连得上"更易诊断。
    strictPort: true,
    host: true,
    // 开发环境代理后端API，避免跨域
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
    },
  },
  css: {
    preprocessorOptions: {
      scss: {
        // token 通过 :root 自定义属性存在，不注入全局变量避免重复输出
        additionalData: '',
      },
    },
  },
  build: {
    target: 'es2020',
    outDir: 'dist',
    assetsDir: 'assets',
    // 生产环境关闭 sourcemap 减小体积
    sourcemap: mode !== 'production',
    // vite 8 默认打包器换成 Rolldown：原 manualChunks(object) 迁移为
    // output.codeSplitting.groups（对象写法在 rolldown 不支持，只有函数/分组两种）。
    // 保留原三组分包意图：vue 生态 / element-plus / jszip。
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            {
              name: 'vue-vendor',
              // 推荐用 [\\/] 匹配路径分隔符，避免 Windows 反斜杠问题（rolldown 文档）
              test: /node_modules[\\/](?:vue|vue-router|pinia)[\\/]/,
            },
            {
              name: 'element-vendor',
              test: (id: string) => /node_modules[\\/](?:element-plus|@element-plus[\\/])/.test(id),
            },
            {
              name: 'editor-vendor',
              test: /node_modules[\\/]jszip[\\/]/,
            },
          ],
        },
        // 资源文件命名
        chunkFileNames: 'assets/js/[name]-[hash].js',
        entryFileNames: 'assets/js/[name]-[hash].js',
        assetFileNames: 'assets/[ext]/[name]-[hash].[ext]',
        // vite 8 的 oxc 压缩：原 esbuild.drop 语义迁移到 rolldown output.minify.compress
        minify: {
          compress: {
            dropConsole: mode === 'production',
            dropDebugger: mode === 'production',
          },
        },
      },
    },
    // 压缩器换成 oxc（vite 8 默认；不再依赖 esbuild service）
    minify: 'oxc',
    //  chunk 大小警告阈值
    chunkSizeWarningLimit: 1000,
  },
  // 依赖预构建优化
  optimizeDeps: {
    include: ['vue', 'vue-router', 'pinia', 'element-plus', '@element-plus/icons-vue', 'dayjs'],
    // 开发环境预构建，减少冷启动时间
    force: false,
  },
}))
