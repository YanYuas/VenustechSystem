// ============================================================
// 快捷键注册 —— 全局键盘监听
// 对应 PRD 附录C：快捷键总表
// ============================================================
import { onMounted, onUnmounted } from 'vue'

export interface ShortcutHandlers {
  // 全局
  'global-search'?: () => void      // Ctrl+K
  'command-palette'?: () => void    // Ctrl+Shift+P
  'new-task'?: () => void           // Ctrl+N
  'new-document'?: () => void       // Ctrl+Shift+N
  'escape'?: () => void             // Esc
  // 模块级（需在对应模块内注册）
  'view-list'?: () => void          // Ctrl+1
  'view-kanban'?: () => void        // Ctrl+2
  'module-search'?: () => void      // Ctrl+F
  'save'?: () => void               // Ctrl+S
  'delete'?: () => void             // Delete
  'close-drawer'?: () => void       // Ctrl+]
}

function isMod(e: KeyboardEvent): boolean {
  return e.metaKey || e.ctrlKey
}

/** 是否在输入框/编辑器中（避免干扰文本输入） */
function isTyping(e: KeyboardEvent): boolean {
  const target = e.target as HTMLElement
  const tag = target.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || target.isContentEditable
}

export function useShortcuts(handlers: ShortcutHandlers) {
  const onKey = (e: KeyboardEvent) => {
    const key = e.key.toLowerCase()

    // Esc —— 全局生效，即使在输入框中也关闭弹窗
    if (e.key === 'Escape') {
      handlers.escape?.()
      return
    }

    // Delete —— 不在输入框中时触发删除
    if (e.key === 'Delete' && !isTyping(e)) {
      handlers.delete?.()
      return
    }

    // 以下快捷键需要修饰键，且不在输入框中（除Ctrl+S保存外）
    if (!isMod(e)) return

    // Ctrl+K —— 全局搜索
    if (!e.shiftKey && key === 'k') {
      e.preventDefault()
      handlers['global-search']?.()
      return
    }

    // Ctrl+Shift+P —— 命令面板
    if (e.shiftKey && key === 'p') {
      e.preventDefault()
      handlers['command-palette']?.()
      return
    }

    // Ctrl+N —— 新建任务（不在输入框中时）
    if (!e.shiftKey && key === 'n' && !isTyping(e)) {
      e.preventDefault()
      handlers['new-task']?.()
      return
    }

    // Ctrl+Shift+N —— 新建文档
    if (e.shiftKey && key === 'n') {
      e.preventDefault()
      handlers['new-document']?.()
      return
    }

    // Ctrl+S —— 保存（在输入框中也生效）
    if (!e.shiftKey && key === 's') {
      e.preventDefault()
      handlers['save']?.()
      return
    }

    // Ctrl+F —— 模块搜索（不在输入框中时）
    if (!e.shiftKey && key === 'f' && !isTyping(e)) {
      e.preventDefault()
      handlers['module-search']?.()
      return
    }

    // Ctrl+1 —— 列表视图
    if (!e.shiftKey && key === '1') {
      e.preventDefault()
      handlers['view-list']?.()
      return
    }

    // Ctrl+2 —— 看板视图
    if (!e.shiftKey && key === '2') {
      e.preventDefault()
      handlers['view-kanban']?.()
      return
    }

    // Ctrl+] —— 收起抽屉
    if (e.key === ']') {
      handlers['close-drawer']?.()
    }
  }

  onMounted(() => window.addEventListener('keydown', onKey))
  onUnmounted(() => window.removeEventListener('keydown', onKey))
}
