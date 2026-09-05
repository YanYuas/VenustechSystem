<script setup lang="ts">
// ============================================================
// ModalHost —— 命令式弹窗宿主（渲染 useModal().stack）
// 用法: const ok = await useModal().confirm({ title, message, requireInput })
// 挂载: main.ts 中 <ModalHost />
// ============================================================
import { onMounted } from 'vue'
import { modal } from '@/composables/useModal'
import ModalItem from './ModalItem.vue'

onMounted(() => modal.setReady())
</script>

<template>
  <ModalItem
    v-for="m in modal.stack"
    :key="m.id"
    :request="m"
    @confirm="m.onConfirm?.(); modal.close(m.id)"
    @cancel="m.onCancel?.(); modal.close(m.id)"
  />
</template>
