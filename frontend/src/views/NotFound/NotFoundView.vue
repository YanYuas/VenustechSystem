<script setup lang="ts">
// ============================================================
// 404 页面 —— 路由兜底
// ============================================================
import { useRouter } from 'vue-router'
import BaseButton from '@/components/common/BaseButton.vue'

const router = useRouter()
</script>

<template>
  <div class="not-found">
    <div class="not-found__code">404</div>
    <h2 class="not-found__title">这片海域还未探索</h2>
    <p class="not-found__desc">你访问的页面不存在或已被移动。</p>
    <div class="not-found__actions">
      <BaseButton variant="primary" @click="router.push('/dashboard')">
        返回首页
      </BaseButton>
      <BaseButton variant="secondary" @click="router.back()">
        返回上一页
      </BaseButton>
    </div>
  </div>
</template>

<style scoped lang="scss">
.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: var(--space-4);
  text-align: center;

  &__code {
    font-family: var(--font-cute);
    font-size: 96px;
    font-weight: 700;
    color: var(--primary);
    line-height: 1;
    animation: gudu 0.5s var(--ease-spring);
  }
  &__title {
    font-family: var(--font-cute);
    font-size: var(--text-xl);
    color: var(--text-hi);
  }
  &__desc {
    font-size: var(--text-base);
    color: var(--text-mid);
    max-width: 320px;
  }
  &__actions {
    display: flex;
    gap: var(--space-3);
    margin-top: var(--space-4);
  }
}
</style>
