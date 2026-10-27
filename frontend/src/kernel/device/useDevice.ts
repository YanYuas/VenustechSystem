// ============================================================
// useDevice —— 设备检测 composable
// 检测是否为移动端/平板，提供响应式断点
// ============================================================
import { ref, onMounted, onUnmounted } from 'vue'

const isMobile = ref(false)
const isTablet = ref(false)
const isDesktop = ref(true)

function update() {
  const w = window.innerWidth
  isMobile.value = w < 768
  isTablet.value = w >= 768 && w < 1024
  isDesktop.value = w >= 1024
}

let initialized = false

export function useDevice() {
  if (!initialized) {
    initialized = true
    update()
    window.addEventListener('resize', update)
    onMounted(update)
    onUnmounted(() => {
      window.removeEventListener('resize', update)
      initialized = false
    })
  }
  return { isMobile, isTablet, isDesktop }
}
