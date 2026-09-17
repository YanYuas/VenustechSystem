<script setup lang="ts">
// ============================================================
// Breadcrumb —— 面包屑导航
// 根据路由 meta.crumbs 自动生成
// 显示在 DimensionTabs 下方、内容区上方
// ============================================================
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from '@/components/common/AppIcon.vue'
import { getDimensionByRoute } from '@/constants/dimensions'

const route = useRoute()
const router = useRouter()

/** 当前维度 */
const dimension = computed(() => getDimensionByRoute(route.path))

/** 面包屑项：维度名 + 路由meta.crumbs */
const crumbs = computed(() => {
  const items: { label: string; route?: string }[] = []
  // 第一项：首页（始终可点击）
  items.push({ label: '首页', route: '/dashboard' })
  // 第二项：当前维度（如果不是首页）
  if (dimension.value && dimension.value.id !== 'dashboard') {
    items.push({ label: dimension.value.label, route: dimension.value.defaultRoute })
  }
  // 后续项：路由meta.crumbs（去掉第一个，因为第一个通常是模块名，已由维度名覆盖）
  const routeCrumbs = (route.meta.crumbs as string[]) ?? []
  if (routeCrumbs.length > 0) {
    // 如果维度名和第一个crumb相同，跳过第一个
    const startIdx = (dimension.value && routeCrumbs[0] === dimension.value.label) ? 1 : 0
    for (let i = startIdx; i < routeCrumbs.length; i++) {
      items.push({ label: routeCrumbs[i] })
    }
  }
  return items
})

function goCrumb(item: { label: string; route?: string }) {
  if (item.route && item.route !== route.path) {
    router.push(item.route)
  }
}
</script>

<template>
  <div class="breadcrumb">
    <div class="breadcrumb__inner">
      <template v-for="(item, idx) in crumbs" :key="idx">
        <span v-if="idx > 0" class="breadcrumb__sep">
          <AppIcon name="dot" :size="10" />
        </span>
        <button
          v-if="item.route && idx < crumbs.length - 1"
          class="breadcrumb__item breadcrumb__item--link"
          type="button"
          @click="goCrumb(item)"
        >
          {{ item.label }}
        </button>
        <span v-else class="breadcrumb__item breadcrumb__item--current">
          {{ item.label }}
        </span>
      </template>
    </div>
  </div>
</template>

<style scoped lang="scss">
.breadcrumb {
  flex-shrink: 0;
  background: var(--bg-body);
  border-bottom: 1px solid var(--line);
  padding: 0 var(--space-6);

  &__inner {
    display: flex;
    align-items: center;
    height: 32px;
    gap: var(--space-2);
  }

  &__sep {
    color: var(--text-low);
    opacity: 0.5;
    display: inline-flex;
  }

  &__item {
    font-size: var(--text-xs);
    font-family: var(--font-cute);

    &--link {
      color: var(--text-mid);
      cursor: pointer;
      border: none;
      background: transparent;
      padding: 2px 4px;
      border-radius: var(--radius-sm);
      transition: all 0.15s;

      &:hover {
        color: var(--primary);
        background: var(--primary-soft);
      }
    }

    &--current {
      color: var(--text-hi);
      font-weight: 600;
    }
  }
}
</style>
