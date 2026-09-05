<script setup lang="ts">
// ============================================================
// 应用根组件 —— 挂载全局服务宿主（Toast / 命令式弹窗）
// ============================================================
import BaseToast from '@/components/common/BaseToast.vue'
import ModalHost from '@/components/common/ModalHost.vue'

import { useTheme } from '@/composables/useTheme'

useTheme()
</script>

<template>
  <router-view />
  <BaseToast />
  <ModalHost />
</template>
