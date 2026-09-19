<script setup lang="ts">
// ============================================================
// AI 行程助理（移动端方案 M3 · 移动优先）
// 语音双通道：App 内原生 STT（Capacitor 插件）/ 浏览器 Web Speech API。
// AI 只产建议 —— 用户勾选确认后才 apply 落库。
// ============================================================
import { computed, onMounted, ref } from 'vue'
import { assistantApi, taskApi } from '@/api'
import { useToast } from '@/composables/useToast'
import BaseCard from '@/components/common/BaseCard.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import BaseSkeleton from '@/components/common/BaseSkeleton.vue'
import BaseEmpty from '@/components/common/BaseEmpty.vue'
import BaseTag from '@/components/common/BaseTag.vue'
import AppIcon from '@/components/common/AppIcon.vue'
import type { Task } from '@/types'

const toast = useToast()

// ---------- 语音双通道 ----------
/* eslint-disable @typescript-eslint/no-explicit-any */
const isNative = computed(() => Boolean((window as any).Capacitor?.isNativePlatform?.()))
const listening = ref(false)
const transcript = ref('')

function startVoice() {
  if (isNative.value) return startNativeVoice()
  startWebVoice()
}

function startWebVoice() {
  const SR = (window as any).SpeechRecognition ?? (window as any).webkitSpeechRecognition
  if (!SR) {
    toast.info('此浏览器不支持语音识别', '请直接在下方文本框输入')
    return
  }
  const rec = new SR()
  rec.lang = 'zh-CN'
  rec.interimResults = false
  listening.value = true
  rec.onresult = (e: any) => {
    transcript.value = (transcript.value + ' ' + (e.results[e.results.length - 1][0].transcript ?? '')).trim()
  }
  rec.onerror = () => { listening.value = false; toast.warning('语音识别失败', '请用文本输入') }
  rec.onend = () => { listening.value = false }
  rec.start()
}

async function startNativeVoice() {
  let settled = false
  const finish = (t: string) => {
    if (settled) return
    settled = true
    if (t.trim()) transcript.value = (transcript.value + ' ' + t.trim()).trim()
    listening.value = false
  }
  try {
    // 动态 import：PWA 构建永远不加载原生插件分包。
    // 插件类型定义与实际 API 有出入，统一 any 走官方事件模型。
    /* eslint-disable @typescript-eslint/no-explicit-any */
    const mod: any = await import('@capacitor-community/speech-recognition')
    const SR: any = mod.SpeechRecognition
    await SR.requestPermissions()
    listening.value = true
    let text = ''
    const stateSub = await SR.addListener('listeningState', async (d: { status: string }) => {
      if (d.status === 'stopped') {
        await SR.stopListening().catch(() => undefined)
        stateSub.remove()
        partSub.remove()
        finish(text)
      }
    })
    const partSub = await SR.addListener('partialResults', (d: { matches: string[] }) => {
      text = d.matches?.[d.matches.length - 1] ?? text
    })
    await SR.startListening({ language: 'zh-CN', maxResults: 1, partialResults: true, popup: true })
    // 20s 兜底：超时自动停并交出已识别文本
    setTimeout(async () => {
      try {
        const st = await SR.isListening()
        if (st.listening) await SR.stopListening()
      } catch { /* ignore */ }
      finish(text)
    }, 20000)
  } catch {
    toast.warning('语音识别失败', '请用文本输入')
    listening.value = false
  }
}

// ---------- 解析与确认 ----------
interface Suggestion {
  kind: 'task' | 'reminder' | 'note'
  title: string
  deadline: string | null
  people: string[]
  location: string | null
  priority: 'high' | 'medium' | 'low'
  notes: string | null
  checked: boolean
}
const suggestions = ref<Suggestion[]>([])
const clarifications = ref<string[]>([])
const source = ref<'deepseek' | 'local' | null>(null)
const parsing = ref(false)

async function onParse() {
  if (!transcript.value.trim()) return toast.warning('说点什么或输入点什么')
  parsing.value = true
  suggestions.value = []
  clarifications.value = []
  try {
    const res = await assistantApi.parse(transcript.value)
    source.value = res.source
    suggestions.value = res.items.map((i) => ({ ...i, checked: true }))
    clarifications.value = res.clarifications ?? []
    if (res.degraded) toast.info('AI 暂不可达，已用本地简化解析')
  } catch { /* http 层已提示 */ } finally {
    parsing.value = false
  }
}

const applying = ref(false)
const KIND_LABEL: Record<string, string> = { task: '任务', reminder: '提醒', note: '备忘' }

function fmtDeadline(s: string | null): string {
  if (!s) return ''
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return ''
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

async function onApply() {
  const picked = suggestions.value.filter((s) => s.checked && s.title.trim())
  if (picked.length === 0) return toast.warning('没有勾选任何条目')
  applying.value = true
  try {
    const res = await assistantApi.apply(picked)
    toast.success(`已加入 ${res.applied} 条`, `任务 ${res.by_kind.task ?? 0} · 备忘 ${res.by_kind.note ?? 0}`)
    suggestions.value = []
    transcript.value = ''
    await loadTodos()
  } catch { /* http 层已提示 */ } finally {
    applying.value = false
  }
}

// ---------- 我的待办（逾期 / 今天 / 之后） ----------
const todos = ref<Task[]>([])
const todosLoading = ref(false)
const groups = computed(() => {
  const today = new Date(); today.setHours(0, 0, 0, 0)
  const g: Record<'overdue' | 'today' | 'later', Task[]> = { overdue: [], today: [], later: [] }
  for (const t of todos.value) {
    if (t.status === 'completed') continue
    if (!t.due_date) { g.today.push(t); continue }
    const d = new Date(t.due_date); d.setHours(0, 0, 0, 0)
    if (d < today) g.overdue.push(t)
    else if (d.getTime() === today.getTime()) g.today.push(t)
    else g.later.push(t)
  }
  return g
})
const GROUP_META: Array<{ id: 'overdue' | 'today' | 'later'; label: string; tone: string }> = [
  { id: 'overdue', label: '逾期', tone: 'danger' },
  { id: 'today', label: '今天', tone: 'primary' },
  { id: 'later', label: '之后', tone: 'default' },
]

async function loadTodos() {
  todosLoading.value = true
  try {
    const res = await taskApi.list({ page: 1, page_size: 50 })
    todos.value = res.list ?? []
  } catch { /* http 层已提示 */ } finally {
    todosLoading.value = false
  }
}

async function completeTask(t: Task) {
  try {
    await taskApi.update(t.id, { status: 'completed' })
    await loadTodos()
  } catch { /* http 层已提示 */ }
}

onMounted(loadTodos)
</script>

<template>
  <div class="assistant">
    <div class="assistant__head">
      <h1 class="assistant__title">AI 行程助理</h1>
      <BaseTag :semantic="source === 'local' ? 'default' : 'mint'" size="sm">
        {{ source === 'deepseek' ? 'DeepSeek' : source === 'local' ? '简化解析' : '待命' }}
      </BaseTag>
    </div>

    <!-- 语音/文字输入 -->
    <BaseCard>
      <button
        class="assistant__mic" :class="{ 'is-listening': listening }"
        @click="startVoice"
      >
        <AppIcon :name="listening ? 'reload' : 'mic'" :size="26" />
        <span>{{ listening ? '正在听…' : '按一下，说事情' }}</span>
      </button>
      <textarea
        v-model="transcript" class="assistant__text" rows="3"
        placeholder="也可以直接打字：明天下午3点找老师谈开题，然后买高铁票…"
      />
      <BaseButton variant="primary" block :loading="parsing" @click="onParse">
        ✨ 帮我整理成待办
      </BaseButton>
    </BaseCard>

    <!-- AI 建议（确认后才落库） -->
    <BaseCard v-if="suggestions.length">
      <template #title><h3 class="assistant__card-title">建议（{{ suggestions.length }} 条 · 勾选后加入）</h3></template>
      <div class="assistant__clarify" v-if="clarifications.length">
        ❓ {{ clarifications.join('　') }}
      </div>
      <ul class="assistant__suggestions">
        <li v-for="(s, i) in suggestions" :key="i" class="assistant__suggestion">
          <input v-model="s.checked" type="checkbox" class="assistant__check" />
          <div class="assistant__sug-main">
            <div class="assistant__sug-line">
              <BaseTag :semantic="s.priority === 'high' ? 'straw' : 'default'" size="sm">
                {{ KIND_LABEL[s.kind] }}
              </BaseTag>
              <input v-model="s.title" class="assistant__sug-title" />
            </div>
            <p v-if="s.notes && s.notes !== s.title" class="assistant__sug-notes">{{ s.notes }}</p>
          </div>
          <span v-if="s.deadline" class="assistant__sug-time">{{ fmtDeadline(s.deadline) }}</span>
        </li>
      </ul>
      <BaseButton variant="primary" block :loading="applying" @click="onApply">
        全部加入待办
      </BaseButton>
    </BaseCard>

    <!-- 我的待办 -->
    <BaseCard>
      <template #title><h3 class="assistant__card-title">我的待办</h3></template>
      <div v-if="todosLoading"><BaseSkeleton variant="list" :rows="4" /></div>
      <BaseEmpty v-else-if="todos.length === 0" description="待办空空 —— 对着麦克风说一件吧" />
      <div v-else class="assistant__groups">
        <section v-for="g in GROUP_META" :key="g.id" class="assistant__group">
          <template v-if="groups[g.id].length">
            <h4 class="assistant__group-title">
              {{ g.label }}（{{ groups[g.id].length }}）
            </h4>
            <ul class="assistant__todos">
              <li v-for="t in groups[g.id]" :key="t.id" class="assistant__todo">
                <button class="assistant__done" :title="'完成'" @click="completeTask(t)">✓</button>
                <span class="assistant__todo-title">{{ t.title }}</span>
                <span v-if="t.due_date" class="assistant__todo-date">{{ fmtDeadline(t.due_date) }}</span>
              </li>
            </ul>
          </template>
        </section>
      </div>
    </BaseCard>

    <p class="assistant__footnote">
      AI 只整理建议，勾选确认后才会写入待办 · 数据保存在你自己的电脑上
    </p>
  </div>
</template>

<style scoped lang="scss">
.assistant {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-4);
  max-width: 560px;
  margin: 0 auto;
  padding-bottom: max(var(--space-6), env(safe-area-inset-bottom));
}
.assistant__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.assistant__title {
  margin: 0;
  font-size: var(--text-lg);
  color: var(--text-hi);
}
.assistant__card-title {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--text-hi);
}

.assistant__mic {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  width: 100%;
  min-height: 96px;
  margin-bottom: var(--space-3);
  border: 2px dashed var(--primary);
  border-radius: var(--radius-lg);
  background: var(--primary-soft);
  color: var(--primary-ink);
  font-size: var(--text-sm);
  font-family: var(--font-cute);
  cursor: pointer;
  transition: transform 0.2s var(--ease-soft);
  &:active { transform: scale(0.97); }
  &.is-listening { animation: assistant-pulse 1.2s infinite; }
}
@keyframes assistant-pulse {
  0%, 100% { box-shadow: 0 0 0 0 var(--primary-soft); }
  50% { box-shadow: 0 0 0 10px transparent; }
}
.assistant__text {
  width: 100%;
  margin-bottom: var(--space-3);
  padding: var(--space-3);
  border: none;
  border-radius: var(--radius-md);
  background: var(--bg-inset);
  color: var(--text-hi);
  font-size: var(--text-sm);
  resize: vertical;
  outline: none;
  &:focus { box-shadow: var(--focus-ring); }
}

.assistant__clarify {
  margin-bottom: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--butter-soft);
  color: var(--text-hi);
  font-size: var(--text-xs);
}
.assistant__suggestions {
  list-style: none;
  margin: 0 0 var(--space-3);
  padding: 0;
}
.assistant__suggestion {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--line);
  &:last-child { border-bottom: none; }
}
.assistant__check { flex: none; width: 18px; height: 18px; accent-color: var(--primary); }
.assistant__sug-main { flex: 1; min-width: 0; }
.assistant__sug-line {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.assistant__sug-title {
  flex: 1;
  min-width: 0;
  border: none;
  border-bottom: 1px dashed var(--line);
  background: transparent;
  color: var(--text-hi);
  font-size: var(--text-sm);
  outline: none;
  &:focus { border-bottom-color: var(--primary); }
}
.assistant__sug-notes {
  margin: 2px 0 0;
  font-size: var(--text-xs);
  color: var(--text-low);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.assistant__sug-time {
  flex: none;
  font-size: var(--text-xs);
  color: var(--primary-ink);
}

.assistant__groups { display: flex; flex-direction: column; gap: var(--space-3); }
.assistant__group-title {
  margin: 0 0 var(--space-1);
  font-size: var(--text-xs);
  color: var(--text-low);
}
.assistant__todos {
  list-style: none;
  margin: 0;
  padding: 0;
}
.assistant__todo {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--line);
  &:last-child { border-bottom: none; }
}
.assistant__done {
  flex: none;
  width: 26px;
  height: 26px;
  border: 1.5px solid var(--line);
  border-radius: var(--radius-pill);
  background: transparent;
  color: transparent;
  font-size: var(--text-xs);
  cursor: pointer;
  &:hover { color: var(--mint-ink); border-color: var(--mint); }
}
.assistant__todo-title {
  flex: 1;
  min-width: 0;
  font-size: var(--text-sm);
  color: var(--text-hi);
}
.assistant__todo-date {
  flex: none;
  font-size: var(--text-xs);
  color: var(--text-low);
}
.assistant__footnote {
  margin: 0;
  font-size: var(--text-xs);
  color: var(--text-low);
  text-align: center;
}

/* ---------- 移动端适配（PRD-模块-tools §5.2） ---------- */
@media (max-width: 767px) {
  // 麦克风按钮：保持 96px 高，左右边距 --space-4
  .asst__mic {
    height: 96px;
    margin-left: var(--space-4);
    margin-right: var(--space-4);
  }

  // 建议条目：勾选框 24×24、时间右对齐
  .asst__item-check,
  .asst__check {
    width: 24px;
    height: 24px;
    min-width: 24px;
  }

  .asst__item-time,
  .asst__time {
    margin-left: auto;
    text-align: right;
  }

  // 待办分组：完成勾选保持 26px、标题 --text-sm
  .asst__todo-check {
    width: 26px;
    height: 26px;
  }

  .asst__todo-title {
    font-size: var(--text-sm);
  }

  // 文本输入：自适应高度（rows=3）、宽度 100%
  .asst__text-input,
  textarea.asst__text-input {
    width: 100%;
    min-height: calc(var(--control-h) * 3);
    resize: vertical;
  }

  // 列表滚动不穿透 + 触摸反馈
  .asst__list,
  .asst__todos {
    overscroll-behavior: contain;
  }

  .asst__item:active,
  .asst__todo:active {
    transform: scale(0.97);
  }
}
</style>
