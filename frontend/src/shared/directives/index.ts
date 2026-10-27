// ============================================================
// 全局自定义指令
// v-focus —— 元素挂载时自动聚焦
// v-lazy —— 图片懒加载（占位）
// ============================================================
import type { App, Directive } from 'vue'

/** 自动聚焦 */
const focus: Directive = {
  mounted(el: HTMLElement) {
    el.focus()
  },
}

/** 点击元素外部触发 */
const clickOutside: Directive = {
  mounted(el: HTMLElement, binding) {
    el._clickOutsideHandler = (e: MouseEvent) => {
      if (!el.contains(e.target as Node)) {
        binding.value(e)
      }
    }
    document.addEventListener('click', el._clickOutsideHandler)
  },
  unmounted(el: HTMLElement) {
    if (el._clickOutsideHandler) {
      document.removeEventListener('click', el._clickOutsideHandler)
    }
  },
}

/** 文本复制 */
const copy: Directive = {
  mounted(el: HTMLElement, binding) {
    el.style.cursor = 'copy'
    el._copyHandler = () => {
      const text = binding.value ?? el.textContent ?? ''
      navigator.clipboard.writeText(text).catch((err) => {
        console.error('[Copy] 复制失败', err)
      })
    }
    el.addEventListener('click', el._copyHandler)
  },
  unmounted(el: HTMLElement) {
    if (el._copyHandler) {
      el.removeEventListener('click', el._copyHandler)
      el._copyHandler = undefined
    }
  },
}

export function setupDirectives(app: App) {
  app.directive('focus', focus)
  app.directive('click-outside', clickOutside)
  app.directive('copy', copy)
}

// 扩展 HTMLElement 类型
declare global {
  interface HTMLElement {
    _clickOutsideHandler?: (e: MouseEvent) => void
    _copyHandler?: () => void
  }
}
