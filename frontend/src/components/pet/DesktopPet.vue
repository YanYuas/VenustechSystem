<script setup lang="ts">
// ============================================================
// 桌面桌宠 —— 启明星助手（一期基础版）
// 功能: 二次元平面形象 + 多种动作 + 点击互动 + 任务完成庆祝
// ============================================================
import { ref, computed, onMounted, onUnmounted } from 'vue'
import AppIcon from '@/components/common/AppIcon.vue'
import { PET_ACTION_EVENT } from '@/composables/usePetEvent'
import { petApi } from '@/api'

const props = withDefaults(defineProps<{
  position?: { x: number; y: number }
  topmost?: boolean
}>(), {
  position: () => ({ x: 100, y: 100 }),
  topmost: false,
})

const emit = defineEmits<{
  (e: 'click'): void
  (e: 'move', pos: { x: number; y: number }): void
}>()

export type PetAction = 'idle' | 'happy' | 'thinking' | 'working' | 'celebrate' | 'sleep' | 'wave' | 'dance' | 'read' | 'run' | 'shy' | 'surprised'
const action = ref<PetAction>('idle')
const message = ref('')
const showMessage = ref(false)
const dragging = ref(false)
const pos = ref({ ...props.position })
const dragOffset = { x: 0, y: 0 }

const MESSAGES: Record<PetAction, string[]> = {
  idle: ['今天也要加油哦~', '有什么我可以帮你的吗？', '记得休息一下眼睛~', '专注当下，你可以的！', '我在你身边呢~'],
  happy: ['太棒了！', '做得好！', '继续保持！', '好开心呀~'],
  thinking: ['让我想想...', '嗯...这个问题...', '我在认真思考哦', '有思路了！'],
  working: ['努力工作中...', '正在帮你处理~', '加油加油！', '专注模式启动！'],
  celebrate: ['任务完成！', '太厉害了！', '你是最棒的！', '恭喜恭喜~'],
  sleep: ['Zzz...', '好困哦...', '休息一下吧~', '晚安...'],
  wave: ['你好呀~', '嗨！', '欢迎回来！', '见到你真高兴~'],
  dance: ['一起跳舞吧~', '动起来！', '心情超好~', '啦啦啦~'],
  read: ['正在阅读...', '这本书真有趣', '知识就是力量！', '让我看看...'],
  run: ['冲鸭！', '快速前进~', '等等我！', '活力满满！'],
  shy: ['哎呀...', '人家害羞了~', '不要这样看着我嘛', '脸红了...'],
  surprised: ['诶？！', '真的吗？', '太意外了！', '哇哦~'],
}

let messageTimer: ReturnType<typeof setTimeout> | null = null
let actionTimer: ReturnType<typeof setTimeout> | null = null

function randomMessage() {
  const msgs = MESSAGES[action.value]
  message.value = msgs[Math.floor(Math.random() * msgs.length)]
  showMessage.value = true
  if (messageTimer) clearTimeout(messageTimer)
  messageTimer = setTimeout(() => { showMessage.value = false }, 3000)
}

function setAction(a: PetAction, duration = 0) {
  action.value = a
  randomMessage()
  if (duration > 0) {
    if (actionTimer) clearTimeout(actionTimer)
    actionTimer = setTimeout(() => { action.value = 'idle' }, duration)
  }
}

/** 拖拽发生过位移后吞掉紧跟的 click，避免拖完随机播放动作 */
let dragMoved = false
function onClick() {
  if (dragMoved) {
    dragMoved = false
    return
  }
  const actions: PetAction[] = ['happy', 'thinking', 'celebrate']
  setAction(actions[Math.floor(Math.random() * actions.length)], 2000)
  emit('click')
}

function onDragStart(e: MouseEvent) {
  dragging.value = true
  dragMoved = false
  dragOffset.x = e.clientX - pos.value.x
  dragOffset.y = e.clientY - pos.value.y
  document.addEventListener('mousemove', onDragMove)
  document.addEventListener('mouseup', onDragEnd)
}

// rAF 合帧：mousemove 事件频率（可达 125Hz+）远高于渲染帧率，逐事件写 ref 会造成多余重渲染
let rafId = 0
let pendingPos = { x: 0, y: 0 }
function onDragMove(e: MouseEvent) {
  if (!dragging.value) return
  dragMoved = true
  pendingPos = { x: e.clientX - dragOffset.x, y: e.clientY - dragOffset.y }
  if (!rafId) {
    rafId = requestAnimationFrame(() => {
      rafId = 0
      pos.value = { ...pendingPos }
    })
  }
}

function onDragEnd() {
  dragging.value = false
  if (rafId) {
    cancelAnimationFrame(rafId)
    rafId = 0
  }
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
  emit('move', pos.value)
}

let idleTimer: ReturnType<typeof setInterval> | null = null

/** 监听业务事件：任务完成→celebrate、设为焦点→happy 等 */
function onPetAction(e: Event) {
  const detail = (e as CustomEvent).detail as { action: PetAction; duration?: number } | undefined
  if (!detail || !detail.action) return
  setAction(detail.action, detail.duration ?? 0)
}

onMounted(() => {
  idleTimer = setInterval(() => {
    if (action.value === 'idle' && Math.random() > 0.7) randomMessage()
  }, 8000)
  setTimeout(() => randomMessage(), 1000)
  window.addEventListener(PET_ACTION_EVENT, onPetAction)
  startDecay()
})

onUnmounted(() => {
  if (idleTimer) clearInterval(idleTimer)
  if (messageTimer) clearTimeout(messageTimer)
  if (actionTimer) clearTimeout(actionTimer)
  window.removeEventListener(PET_ACTION_EVENT, onPetAction)
  if (decayTimer) clearInterval(decayTimer)
})


// ---------- 形态切换（桌宠/人形） ----------
type PetForm = 'pet' | 'human'
const form = ref<PetForm>('pet')
const switching = ref(false)
const FORM_KEY = 'venustech_pet_form'

function loadForm() {
  try {
    const saved = localStorage.getItem(FORM_KEY)
    if (saved === 'human' || saved === 'pet') form.value = saved
  } catch { }
}
function toggleForm() {
  switching.value = true
  setTimeout(() => {
    form.value = form.value === 'pet' ? 'human' : 'pet'
    try { localStorage.setItem(FORM_KEY, form.value) } catch { }
    setAction('wave', 1500)
    setTimeout(() => { switching.value = false }, 300)
  }, 300)
}
loadForm()

// ---------- 右键菜单 ----------
const showMenu = ref(false)
const menuPos = ref({ x: 0, y: 0 })
const menuActions: Array<{ action: PetAction; label: string; icon: string }> = [
  { action: 'wave', label: '打招呼', icon: '👋' },
  { action: 'dance', label: '跳舞', icon: '💃' },
  { action: 'read', label: '阅读', icon: '📖' },
  { action: 'run', label: '奔跑', icon: '🏃' },
  { action: 'shy', label: '害羞', icon: '😊' },
  { action: 'surprised', label: '惊讶', icon: '😮' },
  { action: 'sleep', label: '睡觉', icon: '😴' },
  { action: 'celebrate', label: '庆祝', icon: '🎉' },
]

function onContextMenu(e: MouseEvent) {
  e.preventDefault()
  menuPos.value = { x: e.clientX, y: e.clientY }
  showMenu.value = true
}
function doMenuAction(a: PetAction) {
  setAction(a, 2000)
  showMenu.value = false
}
function closeMenu() { showMenu.value = false }


// ---------- 状态系统（M07 P1） ----------
// S6-2：数值从 localStorage 迁入数据库（后端 /pet/stats）。
// 这样它才会进备份、换设备不归零、清缓存不丢 —— 陪伴数据是用户投入
// 时间最多、最不可再生的那部分，不该放在易失存储里。
interface PetStats {
  intimacy: number    // 亲密度 0-100
  satiety: number     // 饱食度 0-100（旧代码叫 hunger，语义取反容易读错）
  mood: number        // 心情 0-100
  energy: number      // 精力 0-100
}
const stats = ref<PetStats>({ intimacy: 60, satiety: 60, mood: 60, energy: 60 })

// 注：数值的上下限收敛(0-100)由后端负责（见 pet_service.update_stats），
// 前端不再本地 clamp —— 否则又会出现两套边界规则。

/** 从后端拉取数值（后端会按经过时间做惰性衰减后返回） */
async function loadStats() {
  try {
    const res = await petApi.getStats()
    stats.value = {
      intimacy: res.intimacy,
      satiety: res.satiety,
      mood: res.mood,
      energy: res.energy,
    }
  } catch {
    // 静默：桌宠是陪伴型 UI，接口失败时不该弹错或消失，
    // 保留上一次的数值继续可用。
  }
}

/** 互动：把**增量**提交给后端，用返回值刷新（后端会先衰减再叠加） */
async function applyStats(delta: Partial<PetStats>) {
  try {
    const res = await petApi.updateStats(delta)
    stats.value = {
      intimacy: res.intimacy,
      satiety: res.satiety,
      mood: res.mood,
      energy: res.energy,
    }
  } catch {
    // 失败时也保留本地反馈（动作/气泡已播放），不让互动"毫无响应"
  }
}

// 衰减由后端在读取时惰性计算（见 growth_service.apply_stat_decay），
// 前端不再自己递减 —— 否则前后端两套衰减规则会互相打架。
let decayTimer: ReturnType<typeof setInterval> | null = null
function startDecay() {
  decayTimer = setInterval(loadStats, 60000)
}

// ---------- 互动系统（M07 P1） ----------
// 每次互动只提交**增量**，由后端叠加并回写（后端会先应用衰减再叠加，
// 保证"隔几天没打开，回来摸一下"不会把衰减掉的部分凭空补回来）。
function pet() {
  // 抚摸：增加亲密度和心情
  setAction('happy', 1500)
  void applyStats({ intimacy: 2, mood: 3 })
}
function feed() {
  if (stats.value.satiety >= 95) {
    message.value = '人家吃饱啦~'
    showMessage.value = true
    setTimeout(() => { showMessage.value = false }, 2000)
    return
  }
  setAction('happy', 2000)
  message.value = '好好吃~ 谢谢你！'
  showMessage.value = true
  setTimeout(() => { showMessage.value = false }, 2500)
  void applyStats({ satiety: 25, mood: 5 })
}
function play() {
  if (stats.value.energy < 20) {
    message.value = '好累哦...想休息一下...'
    showMessage.value = true
    setTimeout(() => { showMessage.value = false }, 2000)
    setAction('sleep', 2000)
    return
  }
  setAction('dance', 2500)
  void applyStats({ mood: 10, energy: -10, intimacy: 3 })
}
function rest() {
  setAction('sleep', 3000)
  message.value = 'Zzz... 休息一下~'
  showMessage.value = true
  setTimeout(() => { showMessage.value = false }, 3000)
  void applyStats({ energy: 30, mood: 5 })
}

// 状态影响消息
function getMoodLabel() {
  if (stats.value.mood >= 80) return '超开心'
  if (stats.value.mood >= 60) return '心情不错'
  if (stats.value.mood >= 40) return '一般般'
  if (stats.value.mood >= 20) return '有点低落'
  return '需要陪伴'
}

loadStats()


// ---------- 自定义形象配置（M07 P2） ----------
interface PetAppearance {
  primaryColor: string
  secondaryColor: string
  eyeColor: string
  preset: string
}
const APPEARANCE_KEY = 'venustech_pet_appearance'
const appearancePresets = [
  { id: 'default', name: '默认', primary: '#FFB6C1', secondary: '#87CEEB', eye: '#4A4A4A' },
  { id: 'ocean', name: '海洋', primary: '#6BB5D6', secondary: '#2E9D8F', eye: '#1A3A4A' },
  { id: 'sunset', name: '落日', primary: '#FFA07A', secondary: '#FF6B6B', eye: '#5A2A2A' },
  { id: 'forest', name: '森林', primary: '#90EE90', secondary: '#228B22', eye: '#1A3A1A' },
  { id: 'cosmic', name: '星辰', primary: '#9B7ED8', secondary: '#E8C547', eye: '#2A1A4A' },
]
const appearance = ref<PetAppearance>({
  primaryColor: '#FFB6C1',
  secondaryColor: '#87CEEB',
  eyeColor: '#4A4A4A',
  preset: 'default',
})
function loadAppearance() {
  try {
    const saved = localStorage.getItem(APPEARANCE_KEY)
    if (saved) appearance.value = JSON.parse(saved)
  } catch { }
}
function saveAppearance() {
  localStorage.setItem(APPEARANCE_KEY, JSON.stringify(appearance.value))
}
function applyPreset(presetId: string) {
  const preset = appearancePresets.find(p => p.id === presetId)
  if (preset) {
    appearance.value = {
      primaryColor: preset.primary,
      secondaryColor: preset.secondary,
      eyeColor: preset.eye,
      preset: presetId,
    }
    saveAppearance()
  }
}
loadAppearance()

defineExpose({ appearance, appearancePresets, applyPreset, setAction, celebrate: () => setAction('celebrate', 3000), toggleForm, form, stats, pet, feed, play, rest })

const petClass = computed(() => ({
  'pet--idle': action.value === 'idle',
  'pet--happy': action.value === 'happy',
  'pet--thinking': action.value === 'thinking',
  'pet--working': action.value === 'working',
  'pet--celebrate': action.value === 'celebrate',
  'pet--sleep': action.value === 'sleep',
}))
</script>

<template>
  <div
    class="pet"
    :class="petClass"
    :style="{ transform: `translate3d(${pos.x}px, ${pos.y}px, 0)`, zIndex: topmost ? 9999 : 100 }"
    @mousedown="onDragStart"
    @click.stop="onClick" @contextmenu.prevent="onContextMenu" @dblclick.stop="toggleForm"
  >
    <Transition name="bubble">
      <div v-if="showMessage" class="pet__bubble">{{ message }}</div>
    </Transition>

    <div class="pet__body">
      <svg v-if="form === 'pet'" viewBox="0 0 120 140" class="pet__svg">
        <ellipse cx="60" cy="95" rx="35" ry="38" fill="url(#bodyGrad)" />
        <circle cx="60" cy="50" r="32" fill="url(#headGrad)" />
        <path d="M28 45 Q30 20 60 18 Q90 20 92 45 Q85 30 60 28 Q35 30 28 45" fill="#8B7355" />
        <g class="pet__eyes">
          <ellipse cx="48" cy="52" rx="5" ry="7" fill="#333" />
          <ellipse cx="72" cy="52" rx="5" ry="7" fill="#333" />
          <circle cx="50" cy="49" r="2" fill="#fff" />
          <circle cx="74" cy="49" r="2" fill="#fff" />
        </g>
        <ellipse cx="40" cy="62" rx="6" ry="4" fill="#FFB6C1" opacity="0.6" />
        <ellipse cx="80" cy="62" rx="6" ry="4" fill="#FFB6C1" opacity="0.6" />
        <path class="pet__mouth" d="M52 65 Q60 72 68 65" stroke="#333" stroke-width="2" fill="none" stroke-linecap="round" />
        <g class="pet__stars">
          <path d="M95 30 L97 35 L102 35 L98 38 L100 43 L95 40 L90 43 L92 38 L88 35 L93 35 Z" fill="#FFD700" />
        </g>
        <defs>
          <linearGradient id="bodyGrad" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#E8D5F5" />
            <stop offset="100%" stop-color="#C9A8E8" />
          </linearGradient>
          <linearGradient id="headGrad" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#FFF5E6" />
            <stop offset="100%" stop-color="#FFE4C4" />
          </linearGradient>
        </defs>
      </svg>


      <!-- 人形形象 -->
      <svg v-if="form === 'human'" viewBox="0 0 120 160" class="pet__svg pet__svg--human">
        <!-- 头发 -->
        <path d="M30 45 Q28 15 60 12 Q92 15 90 45 Q85 25 60 23 Q35 25 30 45" fill="#4A3728" />
        <!-- 脸 -->
        <ellipse cx="60" cy="50" rx="26" ry="28" fill="url(#skinGrad)" />
        <!-- 眼睛 -->
        <g class="pet__eyes">
          <ellipse cx="50" cy="52" rx="4" ry="6" fill="#333" />
          <ellipse cx="70" cy="52" rx="4" ry="6" fill="#333" />
          <circle cx="51" cy="50" r="1.5" fill="#fff" />
          <circle cx="71" cy="50" r="1.5" fill="#fff" />
        </g>
        <!-- 腮红 -->
        <ellipse cx="42" cy="60" rx="5" ry="3" fill="#FFB6C1" opacity="0.5" />
        <ellipse cx="78" cy="60" rx="5" ry="3" fill="#FFB6C1" opacity="0.5" />
        <!-- 嘴巴 -->
        <path class="pet__mouth" d="M54 64 Q60 69 66 64" stroke="#333" stroke-width="1.5" fill="none" stroke-linecap="round" />
        <!-- 脖子 -->
        <rect x="55" y="75" width="10" height="10" fill="url(#skinGrad)" />
        <!-- 身体（衣服） -->
        <path d="M35 85 Q30 82 35 130 L85 130 Q90 82 85 85 Q75 80 60 80 Q45 80 35 85" fill="url(#clothGrad)" />
        <!-- 手臂 -->
        <ellipse cx="28" cy="100" rx="8" ry="20" fill="url(#clothGrad)" class="pet__arm pet__arm--left" />
        <ellipse cx="92" cy="100" rx="8" ry="20" fill="url(#clothGrad)" class="pet__arm pet__arm--right" />
        <!-- 手 -->
        <circle cx="28" cy="120" r="6" fill="url(#skinGrad)" />
        <circle cx="92" cy="120" r="6" fill="url(#skinGrad)" />
        <!-- 星星装饰 -->
        <path d="M85 30 L86.5 34 L91 34 L87.5 37 L89 42 L85 39 L81 42 L82.5 37 L79 34 L83.5 34 Z" fill="#FFD700" />
        <defs>
          <linearGradient id="skinGrad" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#FFE4C4" />
            <stop offset="100%" stop-color="#FFDAB9" />
          </linearGradient>
          <linearGradient id="clothGrad" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#C9A8E8" />
            <stop offset="100%" stop-color="#9B7FD4" />
          </linearGradient>
        </defs>
      </svg>

      <div v-if="action === 'celebrate'" class="pet__confetti">
        <span v-for="i in 8" :key="i" class="pet__confetti-piece" :style="{ '--i': i }" />
      </div>
    </div>

    <div class="pet__status">
      <AppIcon :name="action === 'working' ? 'loading' : 'spark'" :size="12" />
    </div>

    <!-- 右键菜单 -->
    <Teleport to="body">
      <Transition name="menu">
        <div v-if="showMenu" class="pet__menu" :style="{ left: menuPos.x + 'px', top: menuPos.y + 'px' }" @click.stop>
          <div class="pet__menu-header">
            <span>{{ form === 'pet' ? '桌宠模式' : '人形模式' }}</span>
            <button class="pet__menu-switch" @click="toggleForm">切换形态</button>
          </div>
          <div class="pet__menu-divider" />
          <div class="pet__menu-actions">
            <button v-for="m in menuActions" :key="m.action" class="pet__menu-item" @click="doMenuAction(m.action)">
              <span class="pet__menu-icon">{{ m.icon }}</span>
              <span>{{ m.label }}</span>
            </button>
          </div>
          <div class="pet__menu-divider" />
          <div class="pet__menu-actions">
            <button class="pet__menu-item" @click="feed"><span class="pet__menu-icon">🍖</span><span>喂食</span><span class="pet__menu-val">{{ Math.round(stats.satiety) }}%</span></button>
            <button class="pet__menu-item" @click="play"><span class="pet__menu-icon">🎾</span><span>玩耍</span><span class="pet__menu-val">{{ Math.round(stats.energy) }}%</span></button>
            <button class="pet__menu-item" @click="rest"><span class="pet__menu-icon">💤</span><span>休息</span><span class="pet__menu-val">{{ Math.round(stats.mood) }}%</span></button>
          </div>
          <div class="pet__menu-divider" />
          <div class="pet__menu-stats">
            <div class="pet__stat-row"><span>亲密度</span><div class="pet__stat-bar"><div class="pet__stat-fill" style="background:#FF6B9D" :style="{width: stats.intimacy + '%'}"></div></div><span>{{ Math.round(stats.intimacy) }}</span></div>
            <div class="pet__stat-row"><span>心情</span><div class="pet__stat-bar"><div class="pet__stat-fill" style="background:#FFD93D" :style="{width: stats.mood + '%'}"></div></div><span>{{ getMoodLabel() }}</span></div>
          </div>
          pet__menu-divider" />
          <div class="pet__menu-footer">
            <span class="pet__menu-hint">双击切换形态 · 拖拽移动 · 单击抚摸</span>
          </div>
        </div>
      </Transition>
    </Teleport>
    <div v-if="showMenu" class="pet__menu-overlay" @click="closeMenu" />  </div>
</template>

<style scoped lang="scss">
.pet {
  position: fixed;
  left: 0;
  top: 0;
  width: 100px;
  cursor: grab;
  user-select: none;
  /* 定位走 transform（合成层，不触发重排）；hover 缩放在 __body 上，避免与定位 transform 冲突 */
  will-change: transform;
  &:active { cursor: grabbing; }
  &:hover .pet__body { transform: scale(1.05); }

  &__bubble {
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translateX(-50%);
    padding: 8px 14px;
    background: var(--bg-raised);
    border-radius: var(--radius-md);
    font-size: var(--text-sm);
    color: var(--text-hi);
    white-space: nowrap;
    box-shadow: var(--shadow-raise);
    margin-bottom: 8px;
    &::after {
      content: '';
      position: absolute;
      top: 100%;
      left: 50%;
      transform: translateX(-50%);
      border: 6px solid transparent;
      border-top-color: var(--bg-raised);
    }
  }
  &__body {
    position: relative;
    width: 100px;
    height: 120px;
    transition: transform 0.3s var(--ease-spring);
  }
  &__svg { width: 100%; height: 100%; filter: drop-shadow(0 4px 12px rgba(0,0,0,0.15)); }

  &--idle .pet__svg { animation: idle-bounce 2s ease-in-out infinite; }
  &--happy .pet__svg { animation: happy-jump 0.5s ease-in-out infinite; }
  &--thinking .pet__eyes { animation: blink 3s ease-in-out infinite; }
  /* 抖动放 __body：根元素 transform 用于定位，CSS 动画会覆盖内联样式导致跳位 */
  &--working .pet__body { animation: working-shake 0.3s ease-in-out infinite; }
  &--celebrate .pet__svg { animation: celebrate-spin 0.6s ease-in-out; }
  &--sleep .pet__eyes { opacity: 0.3; }
  &--wave .pet__arm--right { animation: wave-arm 0.5s ease-in-out infinite; }
  &--dance .pet__body { animation: dance-move 0.4s ease-in-out infinite; }
  &--read .pet__svg { animation: read-sway 2s ease-in-out infinite; }
  &--run .pet__body { animation: run-bounce 0.2s ease-in-out infinite; }
  &--shy .pet__svg { animation: shy-shift 1.5s ease-in-out infinite; }
  &--surprised .pet__svg { animation: surprised-pop 0.3s ease-out; }
  &--switching { opacity: 0; transform: scale(0.5) rotate(180deg); transition: all 0.3s ease; }
  &.is-human { width: 90px; .pet__body { height: 140px; } }

  &__confetti { position: absolute; inset: 0; pointer-events: none; }
  &__confetti-piece {
    position: absolute;
    width: 8px; height: 8px;
    background: hsl(calc(var(--i) * 45), 80%, 60%);
    border-radius: 2px;
    animation: confetti-fall 1s ease-out forwards;
    animation-delay: calc(var(--i) * 0.05s);
    left: 50%; top: 20%;
  }
  &__status {
    position: absolute; bottom: 0; right: 0;
    width: 20px; height: 20px;
    display: flex; align-items: center; justify-content: center;
    background: var(--primary); color: #fff;
    border-radius: 50%; font-size: 10px;
  }
}

@keyframes idle-bounce { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-5px)} }
@keyframes happy-jump { 0%,100%{transform:translateY(0) rotate(0)} 25%{transform:translateY(-10px) rotate(-5deg)} 75%{transform:translateY(-10px) rotate(5deg)} }
@keyframes blink { 0%,90%,100%{transform:scaleY(1)} 95%{transform:scaleY(0.1)} }
@keyframes working-shake { 0%,100%{transform:translateX(0)} 25%{transform:translateX(-2px)} 75%{transform:translateX(2px)} }
@keyframes celebrate-spin { 0%{transform:rotate(0) scale(1)} 50%{transform:rotate(180deg) scale(1.2)} 100%{transform:rotate(360deg) scale(1)} }
@keyframes confetti-fall { 0%{transform:translate(0,0) rotate(0);opacity:1} 100%{transform:translate(calc((var(--i) - 4) * 20px),80px) rotate(360deg);opacity:0} }

.bubble-enter-active, .bubble-leave-active { transition: all 0.3s var(--ease-spring); }
.bubble-enter-from, .bubble-leave-to { opacity: 0; transform: translateX(-50%) translateY(8px); }

.pet {
  // 右键菜单
  &__menu {
    position: fixed; z-index: 10000; min-width: 160px;
    background: var(--bg-raised); border: 1px solid var(--line);
    border-radius: var(--radius-md); box-shadow: var(--shadow-raise);
    padding: 8px 0; font-size: 13px;
  }
  &__menu-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 8px 14px; font-weight: 600; color: var(--text-hi);
  }
  &__menu-switch {
    background: var(--primary-soft); color: var(--primary); border: none;
    padding: 4px 10px; border-radius: 6px; font-size: 11px; cursor: pointer;
    &:hover { opacity: 0.8; }
  }
  &__menu-divider { height: 1px; background: var(--line); margin: 4px 0; }
  &__menu-actions { display: flex; flex-direction: column; }
  &__menu-item {
    display: flex; align-items: center; gap: 10px; padding: 8px 14px;
    background: none; border: none; cursor: pointer; color: var(--text-mid);
    font-size: 13px; text-align: left; width: 100%;
    &:hover { background: var(--primary-soft); color: var(--primary); }
  }
  &__menu-icon { font-size: 16px; }
  &__menu-footer { padding: 6px 14px; }
  &__menu-hint { font-size: 10px; color: var(--text-low); }
  &__menu-overlay { position: fixed; inset: 0; z-index: 9999; }
}

@keyframes wave-arm { 0%,100%{transform:rotate(0)} 50%{transform:rotate(-30deg)} }
@keyframes dance-move { 0%,100%{transform:translateY(0) rotate(0)} 25%{transform:translateY(-8px) rotate(-5deg)} 75%{transform:translateY(-8px) rotate(5deg)} }
@keyframes read-sway { 0%,100%{transform:rotate(-2deg)} 50%{transform:rotate(2deg)} }
@keyframes run-bounce { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-4px)} }
@keyframes shy-shift { 0%,100%{transform:translateX(0)} 50%{transform:translateX(3px)} }
@keyframes surprised-pop { 0%{transform:scale(1)} 50%{transform:scale(1.15)} 100%{transform:scale(1)} }

.menu-enter-active, .menu-leave-active { transition: all 0.15s ease; }
.menu-enter-from, .menu-leave-to { opacity: 0; transform: scale(0.95); }

.pet {
  &__menu-val { margin-left: auto; font-size: 11px; color: var(--text-low); }
  &__menu-stats { padding: 8px 14px; display: flex; flex-direction: column; gap: 6px; }
  &__stat-row { display: flex; align-items: center; gap: 8px; font-size: 11px; color: var(--text-mid); }
  &__stat-bar { flex: 1; height: 6px; background: var(--bg-inset); border-radius: 3px; overflow: hidden; }
  &__stat-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
}
</style>
