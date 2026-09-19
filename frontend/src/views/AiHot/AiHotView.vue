<script setup lang="ts">
// ============================================================
// AI 资讯（S6-6 · AI HOT 插件前端出口）
// 三个视图：动态（24h/7d 精选）/ 热点 / 日报。
// 上游不可达时后端降级读缓存，页面只管展示。
// ============================================================
import { onMounted, ref } from 'vue'
import { aihotApi, type AihotItem } from '@/api/aihot'
import BaseCard from '@/components/common/BaseCard.vue'
import BaseSkeleton from '@/components/common/BaseSkeleton.vue'
import BaseEmpty from '@/components/common/BaseEmpty.vue'
import BaseTag from '@/components/common/BaseTag.vue'
import AppIcon from '@/components/common/AppIcon.vue'

type Tab = 'items24' | 'items7d' | 'hot' | 'daily'
const tab = ref<Tab>('items24')
const items = ref<AihotItem[]>([])
const dailyText = ref('')
const loading = ref(false)
const degraded = ref(false)
const error = ref('')

const TABS: Array<{ id: Tab; label: string }> = [
  { id: 'items24', label: '今天' },
  { id: 'items7d', label: '最近 7 天' },
  { id: 'hot', label: '热点' },
  { id: 'daily', label: '日报' },
]

function timeOf(it: AihotItem): string {
  return (it.publishedAt ?? it.discoveredAt ?? '').slice(0, 10)
}

async function load() {
  loading.value = true
  error.value = ''
  items.value = []
  dailyText.value = ''
  try {
    if (tab.value === 'items24' || tab.value === 'items7d') {
      const res = await aihotApi.items({ window: tab.value === 'items24' ? '24h' : '7d' })
      degraded.value = res.degraded === true
      items.value = (res.data?.items ?? []).filter((i): i is AihotItem => Boolean(i?.title))
    } else if (tab.value === 'hot') {
      const res = await aihotApi.hotTopics()
      degraded.value = res.degraded === true
      items.value = (res.data?.items ?? []).filter((i): i is AihotItem => Boolean(i?.title))
    } else {
      const res = await aihotApi.daily()
      degraded.value = res.degraded === true
      dailyText.value = res.data?.report?.content ?? ''
    }
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
}

async function openLink(it: AihotItem) {
  const url = it.links?.aihot ?? it.links?.original
  if (!url) return
  // 移动端（Capacitor 壳）里 window.open 可能被 WebView 拦截，
  // 优先走 @capacitor/browser 打开系统浏览器；Web/PWA 降级为 window.open
  try {
    const { Capacitor } = await import('@capacitor/core')
    if (Capacitor.isNativePlatform()) {
      const { Browser } = await import('@capacitor/browser')
      await Browser.open({ url })
      return
    }
  } catch {
    /* 插件不可用（未 sync 或纯 Web）→ 降级 */
  }
  window.open(url, '_blank', 'noopener')
}

onMounted(load)
</script>

<template>
  <div class="aihot">
    <div class="aihot__head">
      <h1 class="aihot__title">AI 资讯</h1>
      <div class="aihot__tabs">
        <button
          v-for="t in TABS" :key="t.id"
          class="aihot__tab" :class="{ 'is-active': tab === t.id }"
          @click="tab = t.id; load()"
        >{{ t.label }}</button>
      </div>
    </div>

    <p v-if="degraded" class="aihot__degraded">
      AI HOT 暂不可达，展示的是最近一次成功同步的缓存内容。
    </p>
    <p v-if="error" class="aihot__degraded">{{ error }}</p>

    <BaseCard>
      <div v-if="loading"><BaseSkeleton variant="list" :rows="6" /></div>
      <BaseEmpty
        v-else-if="tab === 'daily' && !dailyText"
        title="暂无日报"
        description="AI HOT 的日报每天更新，稍后再试"
      />
      <BaseEmpty v-else-if="items.length === 0" description="暂无内容" />
      <!-- 日报（纯文本展示） -->
      <pre v-else-if="tab === 'daily'" class="aihot__daily">{{ dailyText }}</pre>
      <!-- 动态 / 热点列表 -->
      <ul v-else class="aihot__list">
        <li v-for="(it, i) in items" :key="i" class="aihot__item" @click="openLink(it)">
          <div class="aihot__line">
            <span v-if="tab === 'hot'" class="aihot__rank">{{ i + 1 }}</span>
            <b class="aihot__item-title">{{ it.title }}</b>
            <BaseTag v-if="it.category" semantic="lilac" size="sm">{{ it.category }}</BaseTag>
          </div>
          <p v-if="it.summary" class="aihot__summary">{{ it.summary }}</p>
          <p class="aihot__meta">
            {{ timeOf(it) }}
            <AppIcon name="send" :size="11" />
          </p>
        </li>
      </ul>
    </BaseCard>

    <p class="aihot__footnote">
      内容来自 AI HOT（aihot.virxact.com）· 匿名只读 · 仅作资讯展示，引用请回原文核对
    </p>
  </div>
</template>

<style scoped lang="scss">
.aihot {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-6);
  max-width: 760px;
  margin: 0 auto;
}
.aihot__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.aihot__title {
  margin: 0;
  font-size: var(--text-xl);
  color: var(--text-hi);
}
.aihot__tabs { display: flex; gap: var(--space-1); }
.aihot__tab {
  padding: 5px 14px;
  border: none;
  border-radius: var(--radius-pill);
  background: transparent;
  color: var(--text-mid);
  font-size: var(--text-sm);
  cursor: pointer;
  &:hover { background: var(--bg-inset); }
  &.is-active { background: var(--primary); color: var(--on-primary); }
}
.aihot__degraded {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--butter-soft);
  color: var(--text-hi);
  font-size: var(--text-xs);
}
.aihot__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.aihot__item {
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--line);
  cursor: pointer;
  &:last-child { border-bottom: none; }
  &:hover .aihot__item-title { color: var(--primary-ink); }
}
.aihot__line {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.aihot__rank {
  font-size: var(--text-sm);
  color: var(--primary-ink);
  font-weight: 700;
}
.aihot__item-title {
  font-size: var(--text-sm);
  color: var(--text-hi);
}
.aihot__summary {
  margin: var(--space-1) 0 0;
  font-size: var(--text-xs);
  color: var(--text-mid);
  line-height: 1.7;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.aihot__meta {
  margin: var(--space-1) 0 0;
  font-size: var(--text-xs);
  color: var(--text-low);
  display: flex;
  align-items: center;
  gap: var(--space-1);
}
.aihot__daily {
  margin: 0;
  font-family: inherit;
  font-size: var(--text-sm);
  color: var(--text-mid);
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}
.aihot__footnote {
  margin: 0;
  font-size: var(--text-xs);
  color: var(--text-low);
  text-align: center;
}

/* ---------- 移动端适配（PRD-模块-tools §5.2） ---------- */
@media (max-width: 767px) {
  .aihot {
    padding: var(--space-3);
  }

  // 标题字号 --text-md（15px）；摘要保持 2 行截断
  .aihot__title {
    font-size: var(--text-md);
  }

  // Tab 横滑（F3.2 规格）
  .aihot__tabs {
    overflow-x: auto;
    flex-wrap: nowrap;
    scrollbar-width: none;

    &::-webkit-scrollbar { display: none; }
  }

  // 日报纯文本：行高 1.8、字号 --text-sm
  .aihot__digest {
    line-height: 1.8;
    font-size: var(--text-sm);
  }

  // 列表项触摸反馈
  .aihot__item {
    min-height: 64px;

    &:active {
      transform: scale(0.99);
    }
  }

  .aihot__list {
    overscroll-behavior: contain; // 防橡皮筋穿透
  }
}
</style>
