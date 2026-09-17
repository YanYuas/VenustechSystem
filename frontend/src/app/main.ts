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

const app = createApp(App)

app.use(createPinia())
app.use(router)

// 全局错误处理
setupErrorHandler(app)

// 全局自定义指令
setupDirectives(app)

app.mount('#app')
