<script setup lang="ts">
// ============================================================
// 设置页分区 —— 快捷键
// 从 SettingsView.vue 拆出（D-09），模板、文案、class 逐字保留。
// ============================================================
import BaseCard from '@/shared/components/common/BaseCard.vue'

// ---------- 快捷键（M08 P1） ----------
const shortcuts = [
  { keys: 'Ctrl + N', desc: '新建任务/文档' },
  { keys: 'Ctrl + K', desc: '全局搜索' },
  { keys: 'Ctrl + S', desc: '保存当前内容' },
  { keys: 'Ctrl + Shift + P', desc: '命令面板' },
  { keys: 'Ctrl + ,', desc: '打开设置' },
  { keys: 'Ctrl + 1~6', desc: '切换模块' },
  { keys: 'Esc', desc: '关闭弹窗/取消' },
  { keys: 'Ctrl + /', desc: '切换桌宠显示' },
]
</script>

<template>
  <!-- 快捷键 -->
  <BaseCard title="快捷键" icon="keyboard">
    <div class="settings__shortcuts">
      <div v-for="s in shortcuts" :key="s.keys" class="settings__shortcut">
        <kbd class="settings__kbd">{{ s.keys }}</kbd>
        <span class="settings__shortcut-desc">{{ s.desc }}</span>
      </div>
    </div>
  </BaseCard>
</template>
