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
    strictPort: false,
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
    // 代码分割策略
    rollupOptions: {
      output: {
        // 第三方依赖单独打包
        manualChunks: {
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
          // element-plus 已按需引入（unplugin）、dayjs 未直接引用，均无需预分组
        },
        // 资源文件命名
        chunkFileNames: 'assets/js/[name]-[hash].js',
        entryFileNames: 'assets/js/[name]-[hash].js',
        assetFileNames: 'assets/[ext]/[name]-[hash].[ext]',
      },
    },
    // 压缩配置（esbuild，无需额外依赖）
    minify: 'esbuild',
    esbuild: {
      drop: mode === 'production' ? ['console', 'debugger'] : [],
    },
    //  chunk 大小警告阈值
    chunkSizeWarningLimit: 1000,
  },
  // 依赖预构建优化
  optimizeDeps: {
    include: ['vue', 'vue-router', 'pinia', 'element-plus', '@element-plus/icons-vue', 'dayjs'],
  },
}))
