// ============================================================
// 应用入口
// ============================================================
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { setupErrorHandler } from './errorHandler'
import { setupDirectives } from '@/directives'

// 样式：token 体系 → EP 覆盖 → 全局 → 动画
import '@/styles/variables.scss'
import '@/styles/element-plus.scss'
import '@/styles/global.scss'
import '@/styles/animations.scss'
import { setOfflineQueueHandler } from '@/api/http'
import { useOfflineQueueStore } from '@/stores/offlineQueue'

const app = createApp(App)

app.use(createPinia())
app.use(router)

// 全局错误处理
setupErrorHandler(app)

// 全局自定义指令
setupDirectives(app)

// ---------- 离线队列接线（mod-tools F4.3） ----------
// http 层只管"要不要入队"，具体入队动作由这里注册，避免循环依赖。
const offlineQueue = useOfflineQueueStore()
setOfflineQueueHandler((path, method, body, label) => offlineQueue.enqueue(path, method, body, label))
void offlineQueue.init()

app.mount('#app')

// PWA Service Worker（M1：manifest + SW；API 永不缓存，静态资源 cache-first）
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => { /* SW 失败不影响应用 */ })
  })
}

