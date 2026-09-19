<script setup lang="ts">
// ============================================================
// 离线队列角标 + 面板（mod-tools F4.3）
//
// - 有待同步条目时在右上角显示数字角标；同步中变 spinner
// - 点击角标打开面板：列出条目（标签/方法/时间/重试次数/失败原因）
// - 面板内可「重试全部」「清空失败」
// - 通过 OFFLINE_QUEUE_EVENT 广播弹 toast（入队/离线/同步完成/条目失败）
// ============================================================
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useOfflineQueueStore, OFFLINE_QUEUE_EVENT } from '@/stores/offlineQueue'
import { toast } from '@/composables/useToast'
import AppIcon from '@/components/common/AppIcon.vue'
import BaseButton from '@/components/common/BaseButton.vue'

const store = useOfflineQueueStore()
const panelOpen = ref(false)

const badgeCount = computed(() => store.pending)
const hasFailed = computed(() => store.failed > 0)

function timeText(ts: number): string {
  const d = new Date(ts)
  const pad = (n: number) => `${n}`.padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function onRetryAll() {
  const r = await store.retryAll()
  if (r.sent > 0) toast.success(`已同步 ${r.sent} 条`)
  else if (r.failed > 0) toast.error(`仍有 ${r.failed} 条同步失败`)
}

async function onClearFailed() {
  const n = await store.clearFailed()
  toast.success(n > 0 ? `已清空 ${n} 条失败记录` : '没有失败记录')
}

function onEvent(e: Event) {
  const detail = (e as CustomEvent).detail as {
    kind: string
    pending: number
    sent?: number
    failed?: number
    label?: string
    error?: string
  }
  if (detail.kind === 'offline') {
    toast.error('已离线', '写操作将进入同步队列')
  } else if (detail.kind === 'flushed') {
    if ((detail.sent ?? 0) > 0) toast.success(`${detail.sent} 条操作已同步`)
    if ((detail.failed ?? 0) > 0) toast.error(`${detail.failed} 条同步失败`, '可在队列面板手动重试')
  } else if (detail.kind === 'item-failed' && detail.error) {
    toast.error(`同步失败：${detail.label ?? '写操作'}`, detail.error)
  }
}

onMounted(() => {
  window.addEventListener(OFFLINE_QUEUE_EVENT, onEvent)
})
onBeforeUnmount(() => {
  window.removeEventListener(OFFLINE_QUEUE_EVENT, onEvent)
})
</script>

<template>
  <div class="offline-queue">
    <button
      v-if="store.hasPending || store.flushing"
      class="offline-queue__badge"
      :class="{ 'is-failed': hasFailed, 'is-syncing': store.flushing }"
      type="button"
      :title="store.flushing ? '同步中…' : `${badgeCount} 条待同步`"
      @click="panelOpen = true"
    >
      <AppIcon v-if="store.flushing" name="spin" :size="12" class="spin" />
      <template v-else>{{ badgeCount > 99 ? '99+' : badgeCount }}</template>
    </button>

    <Teleport to="body">
      <Transition name="qsheet">
        <div v-if="panelOpen" class="offline-queue__mask" @click.self="panelOpen = false">
          <section class="offline-queue__sheet">
            <header class="offline-queue__head">
              <h3 class="offline-queue__title">
                待同步队列
                <span class="offline-queue__count">
                  {{ store.pending }} 条{{ hasFailed ? ` · 失败 ${store.failed}` : '' }}
                </span>
              </h3>
              <button class="offline-queue__close" type="button" @click="panelOpen = false">
                <AppIcon name="close" :size="16" />
              </button>
            </header>

            <p v-if="store.items.length === 0" class="offline-queue__empty">队列为空</p>
            <ul v-else class="offline-queue__list">
              <li
                v-for="it in store.items"
                :key="it.id"
                class="offline-queue__item"
                :class="{ 'is-failed': it.retries >= 3 }"
              >
                <div class="offline-queue__item-main">
                  <span class="offline-queue__label">{{ it.label ?? it.path }}</span>
                  <span class="offline-queue__meta">
                    {{ it.method }} · {{ timeText(it.createdAt) }}
                    <template v-if="it.retries > 0"> · 重试 {{ it.retries }}/3</template>
                  </span>
                  <span v-if="it.lastError" class="offline-queue__err">{{ it.lastError }}</span>
                </div>
                <span v-if="it.retries >= 3" class="offline-queue__tag">失败</span>
              </li>
            </ul>

            <footer class="offline-queue__foot">
              <BaseButton size="sm" variant="secondary" :disabled="store.flushing" @click="onRetryAll">
                {{ store.flushing ? '同步中…' : '重试全部' }}
              </BaseButton>
              <BaseButton size="sm" variant="text" @click="onClearFailed">清空失败</BaseButton>
            </footer>
          </section>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped lang="scss">
.offline-queue__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border: none;
  border-radius: var(--radius-pill);
  background: var(--primary);
  color: var(--on-primary);
  font-size: var(--text-xs);
  line-height: 1;
  cursor: pointer;

  &.is-failed {
    background: var(--strawberry);
  }
}

.offline-queue__mask {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  align-items: flex-end;
  background: var(--overlay);
}

.offline-queue__sheet {
  width: 100%;
  max-height: 70vh;
  overflow-y: auto;
  padding: var(--space-4);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  background: var(--surface);
}

.offline-queue__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}

.offline-queue__title {
  margin: 0;
  font-size: var(--text-base);
  color: var(--text-1);
}

.offline-queue__count {
  margin-left: var(--space-2);
  font-size: var(--text-xs);
  color: var(--text-3);
}

.offline-queue__close {
  border: none;
  background: transparent;
  color: var(--text-3);
  cursor: pointer;
}

.offline-queue__empty {
  margin: var(--space-4) 0;
  text-align: center;
  color: var(--text-3);
  font-size: var(--text-sm);
}

.offline-queue__list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.offline-queue__item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--line);

  &.is-failed .offline-queue__label {
    color: var(--straw-ink);
  }
}

.offline-queue__label {
  display: block;
  font-size: var(--text-sm);
  color: var(--text-1);
}

.offline-queue__meta {
  display: block;
  font-size: var(--text-xs);
  color: var(--text-3);
}

.offline-queue__err {
  display: block;
  font-size: var(--text-xs);
  color: var(--straw-ink);
}

.offline-queue__tag {
  flex-shrink: 0;
  padding: 1px var(--space-2);
  border-radius: var(--radius-pill);
  background: var(--straw-soft);
  color: var(--straw-ink);
  font-size: var(--text-xs);
}

.offline-queue__foot {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.qsheet-enter-active,
.qsheet-leave-active {
  transition: opacity 180ms ease;
}
.qsheet-enter-from,
.qsheet-leave-to {
  opacity: 0;
}
</style>
