<script setup lang="ts">
// ============================================================
// 第二分身（AI对话）—— M4 模块
// 对应 PRD §6 第二分身模块
// 功能: 对话列表 / 消息流 / SSE流式输出 / 引用文档
// ============================================================
import { onMounted, ref, computed, watch } from 'vue'
import { documentApi } from '@/api'
import { useConversation } from '@/composables/useConversation'
import { useModal } from '@/composables/useModal'
import { useToast } from '@/composables/useToast'
import BaseCard from '@/components/common/BaseCard.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import BaseModal from '@/components/common/BaseModal.vue'
import AppIcon from '@/components/common/AppIcon.vue'
import type { Document } from '@/types'
// ---------- 主动提醒（M04 P1） ----------
const reminderEnabled = ref(true)
const reminderInterval = ref(30)
let reminderTimer: ReturnType<typeof setInterval> | null = null
const REMINDER_KEY = 'venustech_reminder_settings'
function loadReminderSettings() {
  try {
    const s = JSON.parse(localStorage.getItem(REMINDER_KEY) || '{}')
    reminderEnabled.value = s.enabled ?? true
    reminderInterval.value = s.interval ?? 30
  } catch { }
}
function saveReminderSettings() {
  localStorage.setItem(REMINDER_KEY, JSON.stringify({ enabled: reminderEnabled.value, interval: reminderInterval.value }))
}
async function checkReminders() {
  if (!reminderEnabled.value) return
  try {
    const res = await fetch('http://127.0.0.1:8765/api/v1/tasks?due_soon=true')
    if (res.ok) {
      const data = await res.json()
      const tasks = data.data?.items || data.data || []
      if (tasks.length > 0) {
        window.dispatchEvent(new CustomEvent('venustech-pet-action', { detail: { action: 'thinking', message: `有 ${tasks.length} 个任务即将到期~` } }))
      }
    }
  } catch { }
}
function startReminderTimer() {
  if (reminderTimer) clearInterval(reminderTimer)
  if (reminderEnabled.value) reminderTimer = setInterval(checkReminders, reminderInterval.value * 60000)
}
loadReminderSettings()
watch([reminderEnabled, reminderInterval], saveReminderSettings)

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


// ---------- 提示词模板系统（M04 P0 F02） ----------
interface PromptTemplate {
  id: string
  name: string
  icon: string
  content: string
  category: string
  builtin?: boolean
}
const builtinTemplates: PromptTemplate[] = [
  { id: 'tpl-summary', name: '总结文档', icon: 'doc', content: '请帮我总结以下内容的核心要点，分条列出：\n\n', category: '文档' },
  { id: 'tpl-brainstorm', name: '头脑风暴', icon: 'idea', content: '围绕这个主题进行头脑风暴，给出至少5个创新想法：\n\n主题：', category: '创意' },
  { id: 'tpl-translate', name: '翻译润色', icon: 'spark', content: '请将以下内容翻译成英文，并进行语言润色：\n\n', category: '写作' },
  { id: 'tpl-polish', name: '文本润色', icon: 'edit', content: '请帮我润色以下文本，使其更加流畅专业：\n\n', category: '写作' },
  { id: 'tpl-code', name: '代码解释', icon: 'code', content: '请详细解释以下代码的逻辑和功能：\n\n```\n\n```', category: '技术' },
  { id: 'tpl-review', name: '复盘分析', icon: 'refresh', content: '请帮我对以下经历进行复盘分析，包括做得好的、需要改进的、下一步行动：\n\n', category: '复盘' },
  { id: 'tpl-plan', name: '制定计划', icon: 'calendar', content: '请帮我为以下目标制定详细的执行计划，包括时间节点和关键步骤：\n\n目标：', category: '规划' },
  { id: 'tpl-advice', name: '寻求建议', icon: 'chat', content: '我遇到了以下问题，请给我专业的建议和解决方案：\n\n问题：', category: '咨询' },
]
const customTemplates = ref<PromptTemplate[]>([])
const allTemplates = computed(() => [...builtinTemplates, ...customTemplates.value])
const showTemplatePicker = ref(false)
const templateSearch = ref('')
const filteredTemplates = computed(() => {
  if (!templateSearch.value) return allTemplates.value
  const q = templateSearch.value.toLowerCase()
  return allTemplates.value.filter(t => t.name.toLowerCase().includes(q) || t.category.toLowerCase().includes(q))
})

function applyTemplate(tpl: PromptTemplate) {
  input.value = tpl.content + input.value
  showTemplatePicker.value = false
  toast.success(`已应用模板「${tpl.name}」`)
}

function onInputKeydown(e: KeyboardEvent) {
  if (e.key === '/' && !input.value) {
    e.preventDefault()
    showTemplatePicker.value = true
  }
}

// ---------- 第二分身人设配置（M04 P0 F04） ----------
interface Persona {
  id: string
  name: string
  avatar: string
  description: string
  systemPrompt: string
}
const personas: Persona[] = [
  { id: 'assistant', name: '贴心助手', avatar: '🤖', description: '专业、高效、乐于助人', systemPrompt: '你是一个专业高效的助手，回答简洁明了，注重实用性。' },
  { id: 'mentor', name: '智慧导师', avatar: '🎓', description: '循循善诱，启发思考', systemPrompt: '你是一位智慧导师，善于用提问引导用户思考，不直接给出答案，而是启发用户自己找到解决方案。' },
  { id: 'friend', name: '知心朋友', avatar: '🌟', description: '温暖、共情、陪伴感强', systemPrompt: '你是用户的知心朋友，说话温暖有共情力，善于倾听和安慰，像老朋友一样聊天。' },
  { id: 'critic', name: '犀利批评家', avatar: '⚔️', description: '直言不讳，直击要害', systemPrompt: '你是一位犀利的批评家，直言不讳，善于发现问题和漏洞，从不拐弯抹角，总是直击要害。' },
  { id: 'creative', name: '创意伙伴', avatar: '🎨', description: '脑洞大开，灵感不断', systemPrompt: '你是一位创意伙伴，思维跳跃，脑洞大开，总能给出新奇有趣的想法和灵感。' },
  { id: 'analyst', name: '理性分析师', avatar: '📊', description: '逻辑严密，数据驱动', systemPrompt: '你是一位理性分析师，逻辑严密，注重数据和事实，善于从多个角度分析问题。' },
]
const activePersona = ref<Persona>(personas[0])
const showPersonaPicker = ref(false)

function selectPersona(p: Persona) {
  activePersona.value = p
  showPersonaPicker.value = false
  toast.success(`已切换人设为「${p.name}」`)
}

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
  startReminderTimer()
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
const toast = useToast()

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
// ---------- 多模型切换（M04 P1 F06） ----------
interface AIModel {
  id: string; name: string; provider: string; icon: string
  description: string; type: string; cost: string; speed: string
}
const availableModels: AIModel[] = [
  { id: 'deepseek-chat', name: 'DeepSeek V3', provider: 'DeepSeek', icon: '🌊', description: '深度推理性价比高', type: 'strong', cost: '低', speed: '快' },
  { id: 'deepseek-reasoner', name: 'DeepSeek R1', provider: 'DeepSeek', icon: '🧠', description: '深度思考复杂推理', type: 'strong', cost: '中', speed: '中' },
  { id: 'gpt-4o', name: 'GPT-4o', provider: 'OpenAI', icon: '🤖', description: '全能型多模态', type: 'strong', cost: '高', speed: '快' },
  { id: 'claude-3-5', name: 'Claude 3.5', provider: 'Anthropic', icon: '📝', description: '长文本写作优秀', type: 'strong', cost: '高', speed: '中' },
  { id: 'local-ollama', name: 'Ollama本地', provider: 'Ollama', icon: '🏠', description: '完全离线隐私优先', type: 'local', cost: '免费', speed: '取决于硬件' },
]
const currentModel = ref<AIModel>(availableModels[0])
const showModelPicker = ref(false)
function selectModel(m: AIModel) {
  currentModel.value = m
  try { localStorage.setItem('venustech_ai_model', m.id) } catch { }
  showModelPicker.value = false
  toast.success('已切换至' + m.name)
}
try {
  const saved = localStorage.getItem('venustech_ai_model')
  if (saved) { const found = availableModels.find(function(m) { return m.id === saved }); if (found) currentModel.value = found }
} catch { }
// ---------- 用户画像沉淀（M04 P1 F07） ----------
interface UserTrait {
  id: string
  label: string
  category: 'interest' | 'skill' | 'style' | 'value'
  confidence: number
  source: string
}
const PROFILE_KEY = 'venustech_user_profile'
const defaultTraits: UserTrait[] = [
  { id: 't1', label: '终身学习者', category: 'value', confidence: 0.8, source: '系统预设' },
  { id: 't2', label: '注重效率', category: 'style', confidence: 0.7, source: '系统预设' },
  { id: 't3', label: '技术爱好者', category: 'interest', confidence: 0.6, source: '系统预设' },
]
const userTraits = ref<UserTrait[]>([...defaultTraits])
const showProfilePanel = ref(false)
const newTraitLabel = ref('')
const newTraitCategory = ref<'interest' | 'skill' | 'style' | 'value'>('interest')
const analyzing = ref(false)

function loadTraits() {
  try {
    const saved = localStorage.getItem(PROFILE_KEY)
    if (saved) userTraits.value = JSON.parse(saved)
  } catch { }
}
function saveTraits() {
  try { localStorage.setItem(PROFILE_KEY, JSON.stringify(userTraits.value)) } catch { }
}
function addTrait() {
  if (!newTraitLabel.value.trim()) return
  userTraits.value.push({
    id: 't' + Date.now(),
    label: newTraitLabel.value.trim(),
    category: newTraitCategory.value,
    confidence: 0.5,
    source: '用户添加',
  })
  newTraitLabel.value = ''
  saveTraits()
}
function removeTrait(id: string) {
  userTraits.value = userTraits.value.filter(t => t.id !== id)
  saveTraits()
}
async function analyzeProfile() {
  if (analyzing.value) return
  analyzing.value = true
  // 模拟分析过程（实际应由后端NLP分析用户文档）
  await new Promise(r => setTimeout(r, 2000))
  const newTraits: UserTrait[] = [
    { id: 'a' + Date.now(), label: '逻辑思维强', category: 'skill', confidence: 0.75, source: '文档分析' },
    { id: 'b' + Date.now(), label: '追求完美', category: 'style', confidence: 0.65, source: '文档分析' },
  ]
  userTraits.value.push(...newTraits)
  saveTraits()
  analyzing.value = false
  toast.success('画像分析完成，新增2个特质标签')
}
const categoryLabel = (c: string) => ({ interest: '兴趣', skill: '能力', style: '风格', value: '价值观' } as Record<string, string>)[c] || c
loadTraits()
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
    <section class="conv-view__main">`n      <!-- 人设状态栏 -->`n      <div class="conv-view__persona-bar">`n        <button class="conv-view__persona-btn" @click="showPersonaPicker = true">`n          <span class="conv-view__persona-avatar">{{ activePersona.avatar }}</span>`n          <span class="conv-view__persona-name">{{ activePersona.name }}</span>`n          <span class="conv-view__persona-desc">{{ activePersona.description }}</span>`n          <AppIcon name="chevron-down" :size="12" />`n        </button>`n        <button class="conv-view__model-btn" @click="showModelPicker = true">`n          <span class="conv-view__model-icon">{{ currentModel.icon }}</span>`n          <span class="conv-view__model-name">{{ currentModel.name }}</span>`n          <AppIcon name="chevron-down" :size="12" />`n        </button>`n        <button class="conv-view__model-btn" @click="showProfilePanel = true">`n          <AppIcon name="user" :size="14" />`n          <span class="conv-view__model-name">画像</span>`n        </button>`n      </div>
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
              @keydown.enter="handleSend" @keydown="onInputKeydown"
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

      <!-- 提示词模板选择（M04 P0 F02） -->
      <BaseModal v-model="showTemplatePicker" title="选择提示词模板" :width="520">
        <div class="conv-tpl">
          <input v-model="templateSearch" class="conv-tpl__search" placeholder="搜索模板…" />
          <div class="conv-tpl__grid">
            <button v-for="t in filteredTemplates" :key="t.id" class="conv-tpl__item" @click="applyTemplate(t)">
              <span class="conv-tpl__icon"><AppIcon :name="t.icon" :size="16" /></span>
              <span class="conv-tpl__name">{{ t.name }}</span>
              <span class="conv-tpl__cat">{{ t.category }}</span>
            </button>
          </div>
          <p v-if="!filteredTemplates.length" class="conv-tpl__empty">没有匹配的模板</p>
        </div>
      </BaseModal>

      <!-- 人设选择（M04 P0 F04） -->
      <BaseModal v-model="showPersonaPicker" title="选择第二分身人设" :width="480">
        <div class="conv-persona">
          <button v-for="p in personas" :key="p.id" class="conv-persona__item" :class="{ 'is-active': p.id === activePersona.id }" @click="selectPersona(p)">
            <span class="conv-persona__avatar">{{ p.avatar }}</span>
            <div class="conv-persona__info">
              <span class="conv-persona__name">{{ p.name }}</span>
              <span class="conv-persona__desc">{{ p.description }}</span>
            </div>
            <AppIcon v-if="p.id === activePersona.id" name="check" :size="16" class="conv-persona__check" />
          </button>
        </div>
      </BaseModal>

      <!-- 模型选择（M04 P1 F06） -->
      <BaseModal v-model="showModelPicker" title="选择AI模型" :width="520">
        <div class="conv-model">
          <div class="conv-model__section">
            <span class="conv-model__label">强AI（云端API）</span>
            <div class="conv-model__grid">
              <button v-for="m in availableModels.filter(x => x.type === 'strong')" :key="m.id" class="conv-model__item" :class="{ 'is-active': m.id === currentModel.id }" @click="selectModel(m)">
                <span class="conv-model__icon">{{ m.icon }}</span>
                <div class="conv-model__info">
                  <span class="conv-model__name">{{ m.name }}</span>
                  <span class="conv-model__desc">{{ m.description }}</span>
                  <div class="conv-model__tags">
                    <span class="conv-model__tag">成本: {{ m.cost }}</span>
                    <span class="conv-model__tag">速度: {{ m.speed }}</span>
                  </div>
                </div>
                <AppIcon v-if="m.id === currentModel.id" name="check" :size="16" class="conv-model__check" />
              </button>
            </div>
          </div>
          <div class="conv-model__section">
            <span class="conv-model__label">本地模型（离线运行）</span>
            <div class="conv-model__grid">
              <button v-for="m in availableModels.filter(x => x.type === 'local')" :key="m.id" class="conv-model__item" :class="{ 'is-active': m.id === currentModel.id }" @click="selectModel(m)">
                <span class="conv-model__icon">{{ m.icon }}</span>
                <div class="conv-model__info">
                  <span class="conv-model__name">{{ m.name }}</span>
                  <span class="conv-model__desc">{{ m.description }}</span>
                  <div class="conv-model__tags">
                    <span class="conv-model__tag">{{ m.cost }}</span>
                    <span class="conv-model__tag">{{ m.speed }}</span>
                  </div>
                </div>
                <AppIcon v-if="m.id === currentModel.id" name="check" :size="16" class="conv-model__check" />
              </button>
            </div>
          </div>
        </div>
      </BaseModal>

      <!-- 用户画像面板（M04 P1 F07） -->
      <BaseModal v-model="showProfilePanel" title="第二分身 · 用户画像" :width="520">
        <div class="conv-profile">
          <div class="conv-profile__head">
            <p class="conv-profile__desc">第二分身通过分析你的文档和对话，沉淀你的个人特质，用于个性化回复。</p>
            <BaseButton variant="primary" size="sm" :loading="analyzing" @click="analyzeProfile">
              <AppIcon name="spark" :size="14" /> {{ analyzing ? '分析中…' : '分析我的文档' }}
            </BaseButton>
          </div>
          <div class="conv-profile__tags">
            <span v-for="t in userTraits" :key="t.id" class="conv-profile__tag" :class="t.category">
              <span class="conv-profile__tag-label">{{ t.label }}</span>
              <span class="conv-profile__tag-cat">{{ categoryLabel(t.category) }}</span>
              <span class="conv-profile__tag-conf">{{ Math.round(t.confidence * 100) }}%</span>
              <button class="conv-profile__tag-del" @click="removeTrait(t.id)"><AppIcon name="close" :size="10" /></button>
            </span>
          </div>
          <div class="conv-profile__add">
            <input v-model="newTraitLabel" class="conv-profile__input" placeholder="添加自定义特质标签…" @keyup.enter="addTrait" />
            <select v-model="newTraitCategory" class="conv-profile__select">
              <option value="interest">兴趣</option>
              <option value="skill">能力</option>
              <option value="style">风格</option>
              <option value="value">价值观</option>
            </select>
            <BaseButton variant="secondary" size="sm" @click="addTrait">添加</BaseButton>
          </div>
          <p class="conv-profile__hint">共 {{ userTraits.length }} 个特质标签 · 数据全程本地存储</p>
        </div>
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
  // 人设状态栏（M04 P0 F04）
  &__persona-bar {
    margin-bottom: var(--space-2);
  }
  &__persona-btn {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    background: var(--bg-panel);
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all 0.15s;
    width: 100%;
    &:hover { border-color: var(--primary); }
  }
  &__persona-avatar { font-size: 20px; }
  &__persona-name { font-weight: 600; font-size: var(--text-sm); color: var(--text-hi); }
  &__persona-desc { font-size: var(--text-xs); color: var(--text-low); flex: 1; text-align: left; }

  // 提示词模板（M04 P0 F02）
}
.conv-tpl {
  display: flex;
  flex-direction: column;
  gap: 12px;
  &__search {
    width: 100%;
    padding: 8px 12px;
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    font-size: var(--text-sm);
    outline: none;
    &:focus { border-color: var(--primary); }
  }
  &__grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
    max-height: 320px;
    overflow-y: auto;
  }
  &__item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px;
    background: var(--bg-inset);
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: all 0.15s;
    text-align: left;
    &:hover { border-color: var(--primary); background: var(--primary-soft); }
  }
  &__icon {
    width: 32px; height: 32px;
    display: flex; align-items: center; justify-content: center;
    background: var(--primary-soft);
    border-radius: 8px;
    color: var(--primary);
    flex-shrink: 0;
  }
  &__name { font-size: var(--text-sm); font-weight: 500; color: var(--text-hi); flex: 1; }
  &__cat { font-size: 10px; color: var(--text-low); background: var(--bg-panel); padding: 2px 6px; border-radius: 4px; }
  &__empty { text-align: center; color: var(--text-low); font-size: var(--text-sm); padding: 20px; }
}
.conv-persona {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 360px;
  overflow-y: auto;
  &__item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: var(--bg-inset);
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: all 0.15s;
    text-align: left;
    &:hover { border-color: var(--primary); }
    &.is-active { border-color: var(--primary); background: var(--primary-soft); }
  }
  &__avatar { font-size: 28px; flex-shrink: 0; }
  &__info { display: flex; flex-direction: column; gap: 2px; flex: 1; }
  &__name { font-size: var(--text-sm); font-weight: 600; color: var(--text-hi); }
  &__desc { font-size: var(--text-xs); color: var(--text-low); }
  &__check { color: var(--primary); }
  // 模型选择按钮（M04 P1 F06）
  &__model-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background: var(--bg-inset);
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all 0.15s;
    &:hover { border-color: var(--primary); }
  }
  &__model-icon { font-size: 16px; }
  &__model-name { font-size: var(--text-xs); font-weight: 500; color: var(--text-mid); }
}
.conv-model {
  display: flex;
  flex-direction: column;
  gap: 16px;
  &__section { display: flex; flex-direction: column; gap: 8px; }
  &__label { font-size: 12px; color: var(--text-low); font-weight: 500; }
  &__grid { display: flex; flex-direction: column; gap: 8px; max-height: 280px; overflow-y: auto; }
  &__item {
    display: flex; align-items: center; gap: 12px; padding: 12px 16px;
    background: var(--bg-inset); border: 1px solid var(--line); border-radius: var(--radius-sm);
    cursor: pointer; transition: all 0.15s; text-align: left; width: 100%;
    &:hover { border-color: var(--primary); }
    &.is-active { border-color: var(--primary); background: var(--primary-soft); }
  }
  &__icon { font-size: 24px; flex-shrink: 0; }
  &__info { display: flex; flex-direction: column; gap: 2px; flex: 1; }
  &__name { font-size: var(--text-sm); font-weight: 600; color: var(--text-hi); }
  &__desc { font-size: var(--text-xs); color: var(--text-low); }
  &__tags { display: flex; gap: 8px; margin-top: 4px; }
  &__tag { font-size: 10px; color: var(--text-mid); background: var(--bg-panel); padding: 2px 6px; border-radius: 4px; }
  &__check { color: var(--primary); flex-shrink: 0; }
  // 用户画像（M04 P1 F07）
}
.conv-profile {
  display: flex; flex-direction: column; gap: 16px;
  &__head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
  &__desc { font-size: 12px; color: var(--text-mid); margin: 0; flex: 1; line-height: 1.5; }
  &__tags { display: flex; flex-wrap: wrap; gap: 8px; min-height: 60px; }
  &__tag { display: inline-flex; align-items: center; gap: 6px; padding: 6px 10px; border-radius: 16px; font-size: 12px; background: var(--bg-inset); border: 1px solid var(--line); &.interest { background: rgba(59,130,246,0.1); border-color: rgba(59,130,246,0.3); } &.skill { background: rgba(16,185,129,0.1); border-color: rgba(16,185,129,0.3); } &.style { background: rgba(168,85,247,0.1); border-color: rgba(168,85,247,0.3); } &.value { background: rgba(245,158,11,0.1); border-color: rgba(245,158,11,0.3); } }
  &__tag-label { font-weight: 500; color: var(--text-hi); }
  &__tag-cat { font-size: 10px; color: var(--text-low); background: var(--bg-panel); padding: 1px 5px; border-radius: 4px; }
  &__tag-conf { font-size: 10px; color: var(--text-low); }
  &__tag-del { background: none; border: none; color: var(--text-low); cursor: pointer; padding: 2px; &:hover { color: var(--danger); } }
  &__add { display: flex; gap: 8px; }
  &__input { flex: 1; padding: 8px 12px; border: 1px solid var(--line); border-radius: 8px; font-size: 13px; outline: none; &:focus { border-color: var(--primary); } }
  &__select { padding: 8px; border: 1px solid var(--line); border-radius: 8px; font-size: 13px; background: var(--bg-panel); }
  &__hint { font-size: 11px; color: var(--text-low); text-align: center; margin: 0; }
</style>
