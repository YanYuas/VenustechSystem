<script setup lang="ts">
// ============================================================
// 第二分身（AI对话）—— M4 模块
// 对应 PRD §6 第二分身模块
// 功能: 对话列表 / 消息流 / SSE流式输出 / 引用文档
// ============================================================
import { onMounted, ref } from 'vue'
import { documentApi } from '@/api'
import { useConversation } from '@/composables/useConversation'
import { useModal } from '@/composables/useModal'
import BaseCard from '@/components/common/BaseCard.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import BaseModal from '@/components/common/BaseModal.vue'
import AppIcon from '@/components/common/AppIcon.vue'
import type { Document } from '@/types'

const { conversations, messages, currentId, streaming, streamContent, sendMessage, createConversation, fetchConversations, fetchMessages, stopStreaming, deleteConversation } = useConversation()

const input = ref('')
const thinkMode = ref<'normal' | 'deep' | 'creative' | 'critical' | 'brainstorm'>('normal')
const thinkModes = [
  { value: 'normal', label: '标准', icon: 'chat' },
  { value: 'deep', label: '深度', icon: 'target' },
  { value: 'creative', label: '创意', icon: 'spark' },
  { value: 'critical', label: '批判', icon: 'warning' },
  { value: 'brainstorm', label: '头脑风暴', icon: 'idea' },
]

// 引用文档（最多 3 篇）
const docList = ref<Document[]>([])
const refOpen = ref(false)
const refLoading = ref(false)
const selectedDocs = ref<Document[]>([])

async function loadDocList() {
  if (docList.value.length) return
  refLoading.value = true
  try {
    const res = await documentApi.list({ page_size: 50 })
    docList.value = res.list
  } catch {
    /* 静默 */
  } finally {
    refLoading.value = false
  }
}

function toggleRefDoc(d: Document) {
  const i = selectedDocs.value.findIndex((x) => x.id === d.id)
  if (i >= 0) selectedDocs.value.splice(i, 1)
  else if (selectedDocs.value.length < 3) selectedDocs.value.push(d)
}

function removeRefDoc(id: string) {
  selectedDocs.value = selectedDocs.value.filter((d) => d.id !== id)
}

onMounted(() => {
  fetchConversations().catch(() => { /* http 层已提示 */ })
})

async function handleSend() {
  if (!input.value.trim() || streaming.value) return
  const content = input.value
  input.value = ''
  // 无当前会话时先创建：失败则回填输入框，避免用户消息凭空丢失
  if (!currentId.value) {
    try {
      await createConversation('新对话')
    } catch {
      input.value = content
      return
    }
  }
  await sendMessage({
    content,
    mode: thinkMode.value,
    referenced_doc_ids: selectedDocs.value.map((d) => d.id),
  })
  selectedDocs.value = []
}

async function selectConversation(id: string) {
  currentId.value = id
  fetchMessages(id).catch(() => { /* http 层已提示 */ })
}

/** ISO 时间 → 紧凑显示（MM-DD HH:mm） */
const modal = useModal()

async function onDeleteConversation(id: string, title: string | null) {
  const ok = await modal.confirm({
    title: '删除对话',
    message: `确定删除「${title ?? '新对话'}」吗？删除后无法恢复。`,
    confirmText: '删除',
  })
  if (!ok) return
  try {
    await deleteConversation(id)
  } catch { /* http 层已提示 */ }
}

function fmtTime(iso: string) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div class="conv-view">
    <!-- 会话列表侧栏 -->
    <aside class="conv-view__sidebar">
      <div class="conv-view__sidebar-head">
        <h3 class="conv-view__title">对话</h3>
        <BaseButton variant="primary" size="sm" @click="createConversation('新对话').catch(() => {})">
          新建
        </BaseButton>
      </div>
      <div class="conv-view__list">
        <div
          v-for="c in conversations"
          :key="c.id"
          class="conv-view__item"
          :class="{ 'is-active': c.id === currentId }"
          @click="selectConversation(c.id)"
        >
          <span class="conv-view__item-title">{{ c.title ?? '新对话' }}</span>
          <span class="conv-view__item-time">{{ fmtTime(c.updated_at) }}</span>
          <button class="conv-view__item-del" title="删除" @click.stop="onDeleteConversation(c.id, c.title)">
            <AppIcon name="trash" :size="12" />
          </button>
        </div>
        <p v-if="conversations.length === 0" class="conv-view__empty">暂无对话</p>
      </div>
    </aside>

    <!-- 对话主区 -->
    <section class="conv-view__main">
      <BaseCard class="conv-view__chat" padding="0">
        <div class="conv-view__messages">
          <div
            v-for="m in messages"
            :key="m.id"
            class="conv-view__msg"
            :class="`is-${m.role}`"
          >
            <div class="conv-view__msg-bubble">{{ m.content }}</div>
          </div>
          <div v-if="streaming && streamContent" class="conv-view__msg is-assistant">
            <div class="conv-view__msg-bubble">{{ streamContent }}<span class="conv-view__cursor">▋</span></div>
          </div>
        </div>
        <div class="conv-view__input-bar">
          <div class="conv-view__modes">
            <button
              v-for="m in thinkModes"
              :key="m.value"
              class="conv-view__mode-btn"
              :class="{ 'is-active': thinkMode === m.value }"
              @click="thinkMode = m.value as typeof thinkMode.value"
            >
              <AppIcon :name="m.icon" :size="14" />
              {{ m.label }}
            </button>
            <button
              class="conv-view__mode-btn"
              :class="{ 'is-ref': selectedDocs.length }"
              @click="refOpen = true; loadDocList()"
            >
              <AppIcon name="doc" :size="14" />
              引用{{ selectedDocs.length ? `(${selectedDocs.length})` : '' }}
            </button>
          </div>
          <div v-if="selectedDocs.length" class="conv-view__refs">
            <span v-for="d in selectedDocs" :key="d.id" class="conv-view__ref">
              <AppIcon name="doc" :size="13" />
              {{ d.title }}
              <button class="conv-view__ref-x" type="button" @click="removeRefDoc(d.id)">×</button>
            </span>
          </div>
          <div class="conv-view__input">
            <input
              v-model="input"
              class="conv-view__input-field"
              placeholder="和第二分身聊聊…（Enter发送）"
              @keydown.enter="handleSend"
            />
            <BaseButton
              :variant="streaming ? 'danger' : 'primary'"
              :disabled="!streaming && !input.trim()"
              @click="streaming ? stopStreaming() : handleSend()"
            >
              {{ streaming ? '停止' : '发送' }}
            </BaseButton>
          </div>
        </div>
      </BaseCard>

      <!-- 引用文档选择 -->
      <BaseModal v-model="refOpen" title="引用文档（最多 3 篇）" @confirm="refOpen = false">
        <ul class="conv-view__ref-list">
          <li v-for="d in docList" :key="d.id">
            <label class="conv-view__ref-item">
              <input
                type="checkbox"
                :checked="selectedDocs.some((x) => x.id === d.id)"
                :disabled="!selectedDocs.some((x) => x.id === d.id) && selectedDocs.length >= 3"
                @change="toggleRefDoc(d)"
              />
              <span class="conv-view__ref-item-title">{{ d.title }}</span>
            </label>
          </li>
        </ul>
        <p v-if="!docList.length && refLoading" class="conv-view__ref-empty">加载中…</p>
        <p v-else-if="!docList.length" class="conv-view__ref-empty">暂无文档可引用</p>
      </BaseModal>
    </section>
  </div>
</template>

<style scoped lang="scss">
.conv-view {
  display: flex;
  height: 100%;
  gap: var(--space-4);

  &__sidebar {
    width: 240px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    background: var(--bg-panel);
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
  }
  &__sidebar-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--line);
  }
  &__title {
    font-family: var(--font-cute);
    font-size: var(--text-md);
    font-weight: 600;
  }
  &__list {
    flex: 1;
    overflow-y: auto;
    padding: var(--space-2);
  }
  &__item {
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: background 0.2s var(--ease-soft);
    &:hover { background: var(--bg-inset); }
    &.is-active { background: var(--primary-soft); color: var(--primary); }
  }
  &__item-title {
    display: block;
    font-size: var(--text-sm);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  &__item-time {
    font-size: var(--text-xs);
    color: var(--text-low);
  }
  &__empty {
    text-align: center;
    color: var(--text-low);
    font-size: var(--text-sm);
    padding: var(--space-6);
  }

  &__main {
    flex: 1;
    min-width: 0;
    display: flex;
  }
  &__chat {
    flex: 1;
    display: flex;
    flex-direction: column;
  }
  &__messages {
    flex: 1;
    overflow-y: auto;
    padding: var(--space-5);
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }
  &__msg {
    display: flex;
    &.is-user { justify-content: flex-end; }
    &.is-assistant { justify-content: flex-start; }
  }
  &__msg-bubble {
    max-width: 75%;
    padding: var(--space-3) var(--space-4);
    border-radius: var(--radius-md);
    font-size: var(--text-base);
    line-height: 1.7;
    .is-user & {
      background: var(--primary);
      color: var(--on-primary);
      border-bottom-right-radius: var(--radius-sm);
    }
    .is-assistant & {
      background: var(--bg-inset);
      color: var(--text-hi);
      border-bottom-left-radius: var(--radius-sm);
    }
  }
  &__cursor {
    animation: blink 1s step-end infinite;
    color: var(--primary);
  }
  &__input-bar {
    border-top: 1px solid var(--line);
    padding: var(--space-3) var(--space-4);
  }
  &__modes {
    display: flex;
    gap: var(--space-1);
    margin-bottom: var(--space-2);
    flex-wrap: wrap;
  }
  &__mode-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    border-radius: var(--radius-pill);
    font-size: var(--text-xs);
    color: var(--text-mid);
    background: var(--bg-inset);
    border: 1px solid transparent;
    transition: all 0.2s;
    &.is-active {
      background: var(--primary-soft);
      color: var(--primary);
      border-color: var(--primary);
    }
  }
  &__input {
    display: flex;
    gap: var(--space-3);
  }
  &__input-field {
    flex: 1;
    height: var(--control-h);
    padding: 0 var(--space-4);
    background: var(--bg-inset);
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    outline: none;
    font-size: var(--text-base);
    color: var(--text-hi);
    transition: border-color 0.2s var(--ease-soft);
    &:focus { border-color: var(--primary); background: var(--bg-panel); }
  }

  &__mode-btn.is-ref {
    background: var(--lilac-soft);
    color: var(--lilac-ink);
    border-color: var(--lilac);
  }

  &__refs {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
  }
  &__ref {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 8px;
    border-radius: var(--radius-pill);
    background: var(--lilac-soft);
    color: var(--lilac-ink);
    font-size: var(--text-xs);
  }
  &__ref-x {
    border: none;
    background: transparent;
    color: inherit;
    cursor: pointer;
    font-size: 13px;
    line-height: 1;
    padding: 0 2px;
  }

  &__ref-list {
    list-style: none;
    max-height: 40vh;
    overflow-y: auto;
  }
  &__ref-item {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-sm);
    cursor: pointer;
    &:hover { background: var(--bg-inset); }
    input { accent-color: var(--primary); }
  }
  &__ref-item-title {
    font-size: var(--text-base);
    color: var(--text-hi);
  }
  &__ref-empty {
    padding: var(--space-6);
    text-align: center;
    color: var(--text-low);
    font-size: var(--text-sm);
  }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
</style>
