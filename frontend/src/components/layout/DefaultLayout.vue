<script setup lang="ts">
// ============================================================
// DefaultLayout —— 应用壳布局（三栏式，对齐参考UI）
// 结构: TopNav(顶部水平导航·固定) + LeftInfoPanel(左侧信息面板·固定) + 主内容区(可滚动)
// 原左侧垂直导航已移除，导航移至顶部
// ============================================================
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from '@/composables/useToast'
import { useShortcuts } from '@/composables/useShortcuts'
import { useTheme } from '@/composables/useTheme'
import { useReminderWatcher } from '@/composables/useReminderWatcher'
import AppTitleBar from './AppTitleBar.vue'
import TopNav from './TopNav.vue'
import LeftInfoPanel from './LeftInfoPanel.vue'
import GlobalSearch from './GlobalSearch.vue'
import CommandPalette from './CommandPalette.vue'
import DesktopPet from '@/components/pet/DesktopPet.vue'
import DimensionTabs from './DimensionTabs.vue'
import Breadcrumb from './Breadcrumb.vue'
import MobileTabBar from './MobileTabBar.vue'
import { useDevice } from '@/composables/useDevice'
import type { SearchResultItem } from '@/types/common'

const router = useRouter()
const toast = useToast()
const { toggleMode, cyclePack } = useTheme()
useReminderWatcher() // 启动提醒到期监控
const { isMobile } = useDevice()

const searchOpen = ref(false)
const paletteOpen = ref(false)
const petPosition = { x: typeof window !== 'undefined' ? window.innerWidth - 160 : 1600, y: typeof window !== 'undefined' ? window.innerHeight - 200 : 800 }

function onGlobalSelect(result: SearchResultItem) {
  if (result.type === 'task') {
    router.push('/tasks')
  } else if (result.type === 'conv') {
    router.push('/conversation')
  } else if (result.type === 'doc') {
    router.push('/documents')
  } else if (result.id === 'action-new-task') {
    router.push('/tasks')
  } else if (result.id === 'action-new-doc') {
    router.push('/documents')
  } else {
    toast.info('操作', result.title)
  }
}

function onExec(cmd: { id: string; name: string }) {
  if (cmd.id === 'theme-toggle') {
    toggleMode()
    toast.success('外观', '已切换明暗模式')
  } else if (cmd.id === 'theme-cycle') {
    cyclePack()
    toast.success('外观', '已切换主题包')
  } else if (cmd.id === 'settings') {
    router.push('/settings')
  } else {
    toast.info('命令', cmd.name)
  }
}

useShortcuts({
  'global-search': () => (searchOpen.value = true),
  'command-palette': () => (paletteOpen.value = true),
  escape: () => {
    searchOpen.value = false
    paletteOpen.value = false
  },
})
</script>

<template>
  <div class="shell" :class="{ 'is-mobile': isMobile }">
    <AppTitleBar v-if="!isMobile" />
    <TopNav
      @open-search="searchOpen = true"
      @open-user-menu="router.push('/settings')"
    />
    <DimensionTabs />
    <Breadcrumb v-if="!isMobile" />
    <div class="shell__body">
      <LeftInfoPanel v-if="!isMobile" />
      <main class="shell__content">
        <router-view />
      </main>
    </div>

    <GlobalSearch v-model="searchOpen" @select="onGlobalSelect" />
    <CommandPalette v-model="paletteOpen" @exec="onExec" />
    <DesktopPet :position="petPosition" />
    <MobileTabBar />
  </div>
</template>

<style scoped lang="scss">
.shell {
  display: flex;
  flex-direction: column;
  height: 100%;

  &__body {
    flex: 1;
    min-height: 0;
    display: flex;
  }
  &__content {
    flex: 1;
    min-width: 0;
    overflow-y: auto;
    overflow-x: hidden;
    padding: var(--space-4) var(--space-6);
    background: var(--bg-body);
  }

  // 移动端适配
  &.is-mobile {
    .shell__content {
      padding: var(--space-3);
      padding-bottom: 72px; // 底部TabBar空间
    }
  }
}

// 移动端全局适配
@media (max-width: 767px) {
  .shell__content {
    padding: var(--space-3) !important;
    padding-bottom: 72px !important;
  }
}
</style>
