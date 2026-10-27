<script setup lang="ts">
// ============================================================
// ModalHost —— 命令式弹窗宿主（渲染 useModal().stack）
// 用法: const ok = await useModal().confirm({ title, message, requireInput })
// 挂载: main.ts 中 <ModalHost />
// ============================================================
import { onMounted } from 'vue'
import { modal, type ModalRequest } from '@/kernel/ui/modal'
import ModalItem from './ModalItem.vue'

// 处理器抽成命名函数：Prettier(semi:false) 会把模板里的多语句内联处理器
// 打印成换行分隔，Vue 表达式解析失败（task-19）。一次函数调用则格式化稳定。
function onModalConfirm(m: ModalRequest) {
  m.onConfirm?.()
  modal.close(m.id)
}
function onModalCancel(m: ModalRequest) {
  m.onCancel?.()
  modal.close(m.id)
}

onMounted(() => modal.setReady())
</script>

<template>
  <ModalItem
    v-for="m in modal.stack"
    :key="m.id"
    :request="m"
    @confirm="onModalConfirm(m)"
    @cancel="onModalCancel(m)"
  />
</template>
