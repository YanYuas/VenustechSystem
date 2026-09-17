<script setup lang="ts">
// ============================================================
// DimensionTabs —— 维度二级Tab栏
// 显示在内容区顶部，用于切换当前维度下的子模块
// 首页维度无Tab，不显示本组件
// 可选功能Tab（如工作区）显示虚线边框+可选标记
// ============================================================
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from '@/components/common/AppIcon.vue'
import { getDimensionByRoute } from '@/constants/dimensions'
import type { DimensionTab } from '@/constants/dimensions'

const route = useRoute()
const router = useRouter()

/** 当前维度 */
const dimension = computed(() => getDimensionByRoute(route.path))

/** 是否显示Tab栏（首页不显示） */
const visible = computed(() => dimension.value && dimension.value.tabs.length > 0)

/** 当前激活的Tab */
const activeTabId = computed(() => {
  if (!dimension.value) return ''
  const tab = dimension.value.tabs.find(t => route.path === t.route || route.path.startsWith(t.route + '/'))
  return tab?.id ?? ''
})

function goTab(tab: DimensionTab) {
  if (tab.route !== route.path) {
    router.push(tab.route)
  }
}
</script>

<template>
  <div v-if="visible" class="dim-tabs">
    <div class="dim-tabs__inner">
      <button
        v-for="tab in dimension!.tabs"
        :key="tab.id"
        class="dim-tabs__item"
        :class="{ 'is-active': tab.id === activeTabId, 'is-optional': tab.optional }"
        type="button"
        @click="goTab(tab)"
      >
        <AppIcon :name="tab.icon" :size="14" />
        <span>{{ tab.label }}</span>
        <span v-if="tab.optional" class="dim-tabs__optional-badge">可选</span>
      </button>
    </div>
  </div>
</template>

<style scoped lang="scss">
.dim-tabs {
  flex-shrink: 0;
  background: var(--bg-panel);
  border-bottom: 1px solid var(--line);
  padding: 0 var(--space-6);

  &__inner {
    display: flex;
    align-items: center;
    gap: 2px;
    height: 40px;
    overflow-x: auto;
    scrollbar-width: none;
    &::-webkit-scrollbar { display: none; }
  }

  &__item {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    height: 30px;
    padding: 0 var(--space-3);
    border: none;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--text-mid);
    font-size: var(--text-sm);
    font-family: var(--font-cute);
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.2s var(--ease-soft);

    &:hover {
      background: var(--bg-inset);
      color: var(--text-hi);
    }

    &.is-active {
      color: var(--primary);
      background: var(--primary-soft);
      font-weight: 600;
    }

    // 可选功能：虚线边框+浅色
    &.is-optional {
      border: 1px dashed var(--line);
      background: transparent;

      &:hover {
        border-color: var(--primary);
        background: var(--primary-soft);
      }

      &.is-active {
        border-style: solid;
        border-color: var(--primary);
      }
    }
  }

  &__optional-badge {
    font-size: 9px;
    padding: 1px 5px;
    border-radius: var(--radius-pill);
    background: var(--bg-inset);
    color: var(--text-low);
    font-weight: 500;
    line-height: 1.4;
  }
}

// 移动端：横向滑动，不换行不隐藏
@media (max-width: 767px) {
  .dim-tabs {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    &::-webkit-scrollbar { display: none; }
  }
  .dim-tabs__scroll,
  .dim-tabs__inner {
    flex-wrap: nowrap;
  }
  .dim-tabs__tab {
    flex-shrink: 0;
    padding: 6px var(--space-2);
  }
  .dim-tabs__optional-badge { display: none; }
}
</style>
