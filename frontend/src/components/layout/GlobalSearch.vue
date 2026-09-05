<script setup lang="ts">
// ============================================================
// A04 GlobalSearch —— 全局搜索面板（Cmd+K）· 真实数据版
// 数据: /api/v1/search（任务/文档/对话），空词显示最近搜索历史
// 交互: ↑↓ 导航 / Enter 跳转 / Esc 关闭 / 输入防抖 200ms
// ============================================================
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { documentApi } from '@/api'
import AppIcon from '@/components/common/AppIcon.vue'
import type { SearchResultItem } from '@/types/common'
import type { SearchResult } from '@/types'

const props = withDefaults(defineProps<{ modelValue?: boolean }>(), {
  modelValue: false,
})

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'select', item: SearchResultItem): void
}>()

const HISTORY_KEY = 'qmx:search-history'

const query = ref('')
const debounced = ref('')
const results = ref<SearchResultItem[]>([])
const loading = ref(false)
const highlight = ref(0)
const inputEl = ref<HTMLInputElement | null>(null)
let debounceTimer: number | null = null

const history = ref<string[]>(
  typeof localStorage !== 'undefined'
    ? JSON.parse(localStorage.getItem(HISTORY_KEY) ?? '[]')
    : [],
)

const TYPE_META: Record<SearchResultItem['type'], { icon: string; color: string }> = {
  task: { icon: 'check', color: 'var(--primary)' },
  doc: { icon: 'doc', color: 'var(--lilac)' },
  conv: { icon: 'send', color: 'var(--sky)' },
  action: { icon: 'command', color: 'var(--butter)' },
}

const GROUPS: SearchResultItem['type'][] = ['task', 'doc', 'conv', 'action']

/** 后端 SearchResult → 面板条目 */
function mapResult(data: SearchResult): SearchResultItem[] {
  const items: SearchResultItem[] = []
  for (const t of data.tasks) items.push({ type: 'task', title: t.title, path: t.status || '任务', id: t.id })
  for (const d of data.documents) items.push({ type: 'doc', title: d.title, path: d.snippet ? d.snippet.slice(0, 40) : '文档', id: d.id })
  for (const c of data.conversations) items.push({ type: 'conv', title: c.title, path: '对话', id: c.id })
  // 操作项（前端固定）：新建任务 / 新建文档
  items.push({ type: 'action', title: '新建任务', path: '操作', id: 'action-new-task' })
  items.push({ type: 'action', title: '新建文档', path: '操作', id: 'action-new-doc' })
  return items
}

async function doSearch(q: string) {
  if (!q.trim()) {
    results.value = []
    return
  }
  loading.value = true
  try {
    const data = await documentApi.search(q)
    results.value = mapResult(data)
  } catch {
    results.value = []
  } finally {
    loading.value = false
  }
}

function byType(g: SearchResultItem['type']) {
  return results.value.filter((r) => r.type === g)
}

const flatList = computed(() => GROUPS.flatMap((g) => byType(g)))
const hasAny = computed(() => flatList.value.length > 0)

/** 高亮匹配词 —— 返回 vnode 片段 */
function hl(text: string) {
  const q = debounced.value.trim()
  if (!q) return text
  const i = text.toLowerCase().indexOf(q.toLowerCase())
  if (i < 0) return text
  return [
    text.slice(0, i),
    { m: text.slice(i, i + q.length), k: `hl${i}` },
    text.slice(i + q.length),
  ]
}

function saveHistory(q: string) {
  if (!q.trim()) return
  const h = [q, ...history.value.filter((x) => x !== q)].slice(0, 5)
  history.value = h
  localStorage.setItem(HISTORY_KEY, JSON.stringify(h))
}

function close() {
  emit('update:modelValue', false)
}

function onInput() {
  if (debounceTimer) window.clearTimeout(debounceTimer)
  debounceTimer = window.setTimeout(() => {
    debounced.value = query.value
    highlight.value = 0
    void doSearch(debounced.value)
  }, 200)
}

function onPickHistory(h: string) {
  query.value = h
  debounced.value = h
  highlight.value = 0
  void doSearch(h)
}

function pick(item: SearchResultItem) {
  saveHistory(item.title)
  emit('select', item)
  close()
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    highlight.value = Math.min(highlight.value + 1, flatList.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    highlight.value = Math.max(highlight.value - 1, 0)
  } else if (e.key === 'Enter') {
    e.preventDefault()
    const item = flatList.value[highlight.value]
    if (item) pick(item)
  } else if (e.key === 'Escape') {
    close()
  }
}

watch(
  () => props.modelValue,
  async (v) => {
    if (v) {
      query.value = ''
      debounced.value = ''
      results.value = []
      highlight.value = 0
      await nextTick()
      inputEl.value?.focus()
    }
  },
)

onBeforeUnmount(() => {
  if (debounceTimer) window.clearTimeout(debounceTimer)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="global">
      <div v-if="modelValue" class="gsearch" @keydown="onKeydown" @click.self="close">
        <div class="gsearch__panel" role="dialog" aria-modal="true">
          <div class="gsearch__input-row">
            <AppIcon name="search" :size="20" class="gsearch__search-icon" />
            <input
              ref="inputEl"
              v-model="query"
              class="gsearch__input"
              placeholder="输入关键词搜索任务、文档、对话…"
              @input="onInput"
            />
            <kbd class="gsearch__esc">ESC</kbd>
          </div>

          <div class="gsearch__body">
            <!-- 最近搜索（空词时） -->
            <section v-if="!debounced.trim() && history.length" class="gsearch__group">
              <p class="gsearch__group-title">最近搜索</p>
              <button
                v-for="(h, i) in history"
                :key="h"
                class="gsearch__result"
                :style="{ '--i': i }"
                type="button"
                @click="onPickHistory(h)"
              >
                <span class="gsearch__result-icon" style="color: var(--text-low)">
                  <AppIcon name="reload" :size="16" />
                </span>
                <span class="gsearch__result-text">{{ h }}</span>
              </button>
            </section>

            <!-- 加载中 -->
            <div v-if="loading" class="gsearch__loading">
              <AppIcon name="spin" :size="28" class="gsearch__loading-icon" />
              <p>搜索中…</p>
            </div>

            <!-- 结果分组 -->
            <template v-else>
              <section v-for="g in GROUPS" :key="g" v-show="!debounced.trim() || byType(g).length">
                <template v-if="byType(g).length">
                  <p class="gsearch__group-title">
                    {{ g === 'task' ? '任务' : g === 'doc' ? '文档' : g === 'conv' ? '对话' : '操作' }}
                  </p>
                  <button
                    v-for="(r, i) in byType(g)"
                    :key="r.id"
                    class="gsearch__result"
                    :style="{ '--i': i }"
                    :class="{ 'is-active': r === flatList[highlight] }"
                    type="button"
                    @click="pick(r)"
                  >
                    <span class="gsearch__result-icon" :style="{ color: TYPE_META[r.type].color }">
                      <AppIcon :name="TYPE_META[r.type].icon" :size="16" />
                    </span>
                    <span class="gsearch__result-text">
                      <template v-for="(part, idx) in hl(r.title)" :key="idx">
                        <mark v-if="typeof part === 'object' && 'm' in part" class="gsearch__mark">{{ part.m }}</mark>
                        <template v-else>{{ part }}</template>
                      </template>
                    </span>
                    <span class="gsearch__result-path">{{ r.path }}</span>
                  </button>
                </template>
              </section>

              <div v-if="debounced.trim() && !hasAny" class="gsearch__empty">
                <AppIcon name="search" :size="32" class="gsearch__empty-icon" />
                <p>没有找到相关内容</p>
              </div>
            </template>
          </div>

          <footer class="gsearch__foot">
            <span><kbd>↑↓</kbd> 导航</span>
            <span><kbd>↵</kbd> 打开</span>
            <span><kbd>esc</kbd> 关闭</span>
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped lang="scss">
.gsearch {
  position: fixed;
  inset: 0;
  z-index: 2100;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 14vh;
  background: var(--overlay);

  &__panel {
    width: 560px;
    max-width: calc(100vw - 48px);
    max-height: 60vh;
    display: flex;
    flex-direction: column;
    background: var(--bg-raised);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-raise);
    overflow: hidden;
    animation: gudu 0.45s var(--ease-spring);
  }

  &__input-row {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-4) var(--space-5);
    border-bottom: 1px solid var(--line);
  }
  &__search-icon {
    color: var(--text-low);
  }
  &__input {
    flex: 1;
    min-width: 0;
    border: none;
    outline: none;
    background: transparent;
    font-family: var(--font-cute);
    font-size: var(--text-xl);
    color: var(--text-hi);
    &::placeholder {
      color: var(--text-low);
    }
  }
  &__esc {
    padding: 2px 8px;
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--text-low);
  }

  &__body {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: var(--space-3);
  }
  &__group {
    margin-bottom: var(--space-2);
  }
  &__group-title {
    padding: var(--space-1) var(--space-2) var(--space-1);
    font-size: var(--text-xs);
    color: var(--text-low);
  }
  &__result {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    width: 100%;
    height: 44px;
    padding: 0 var(--space-3);
    border-radius: var(--radius-sm);
    animation: slide-in-up 0.3s var(--ease-soft);
    animation-delay: calc(var(--i) * 30ms);
    animation-fill-mode: backwards;
    text-align: left;
    &:hover,
    &.is-active {
      background: var(--bg-inset);
    }
  }
  &__result-icon {
    display: inline-flex;
    flex-shrink: 0;
  }
  &__result-text {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: var(--text-base);
    color: var(--text-hi);
  }
  &__mark {
    background: var(--butter-soft);
    color: var(--butter-ink);
    border-radius: 2px;
    padding: 0 1px;
  }
  &__result-path {
    font-size: var(--text-xs);
    color: var(--text-low);
    flex-shrink: 0;
    max-width: 180px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-8);
    color: var(--text-low);
    font-size: var(--text-base);
  }
  &__loading-icon {
    color: var(--primary);
    animation: spin 1s linear infinite;
  }

  &__empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-8);
    color: var(--text-low);
    font-size: var(--text-base);
  }
  &__empty-icon {
    color: var(--text-low);
    opacity: 0.5;
    animation: floaty 4s ease-in-out infinite;
  }

  &__foot {
    display: flex;
    align-items: center;
    gap: var(--space-5);
    padding: var(--space-3) var(--space-5);
    border-top: 1px solid var(--line);
    font-size: var(--text-xs);
    color: var(--text-low);
    kbd {
      padding: 1px 5px;
      border: 1px solid var(--line);
      border-radius: 4px;
      background: var(--bg-inset);
      font-family: var(--font-mono);
      font-size: 10px;
    }
  }
}
</style>

<style lang="scss">
.global-enter-active,
.global-leave-active {
  transition: opacity 0.2s var(--ease-soft);
}
.global-enter-from,
.global-leave-to {
  opacity: 0;
}
</style>
