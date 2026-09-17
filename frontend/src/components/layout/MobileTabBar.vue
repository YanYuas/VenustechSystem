<script setup lang="ts">
// ============================================================
// MobileTabBar —— 移动端底部导航栏
// 仅在 < 768px 时显示，对应桌面端的顶部6维度导航
// ============================================================
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from '@/components/common/AppIcon.vue'
import { MAIN_NAV_ITEMS, getDimensionByRoute } from '@/constants/dimensions'

const route = useRoute()
const router = useRouter()

const activeId = computed(() => {
  const dim = getDimensionByRoute(route.path)
  return dim?.id ?? ''
})

function goTab(item: { id: string; route?: string }) {
  if (item.route && item.route !== route.path) {
    router.push(item.route)
  }
}
</script>

<template>
  <nav class="mobile-tabbar">
    <button
      v-for="item in MAIN_NAV_ITEMS"
      :key="item.id"
      class="mobile-tabbar__item"
      :class="{ 'is-active': item.id === activeId }"
      type="button"
      @click="goTab(item)"
    >
      <AppIcon :name="item.icon ?? 'dot'" :size="20" />
      <span class="mobile-tabbar__label">{{ item.label }}</span>
    </button>
  </nav>
</template>

<style scoped lang="scss">
.mobile-tabbar {
  display: none;

  @media (max-width: 767px) {
    display: flex;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 56px;
    background: var(--bg-panel);
    border-top: 1px solid var(--line);
    z-index: 100;
    padding-bottom: env(safe-area-inset-bottom);
    box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.08);
  }

  &__item {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    border: none;
    background: transparent;
    color: var(--text-low);
    cursor: pointer;
    transition: color 0.2s;

    &:active {
      background: var(--bg-inset);
    }

    &.is-active {
      color: var(--primary);
    }
  }

  &__label {
    font-size: 10px;
    font-family: var(--font-cute);
    line-height: 1;
  }
}
</style>
