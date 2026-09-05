<script setup lang="ts">
// ============================================================
// 桌面桌宠 —— 启明星助手（一期基础版）
// 功能: 二次元平面形象 + 多种动作 + 点击互动 + 任务完成庆祝
// ============================================================
import { ref, computed, onMounted, onUnmounted } from 'vue'
import AppIcon from '@/components/common/AppIcon.vue'
import { PET_ACTION_EVENT } from '@/composables/usePetEvent'

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

export type PetAction = 'idle' | 'happy' | 'thinking' | 'working' | 'celebrate' | 'sleep'
const action = ref<PetAction>('idle')
const message = ref('')
const showMessage = ref(false)
const dragging = ref(false)
const pos = ref({ ...props.position })
const dragOffset = { x: 0, y: 0 }

const MESSAGES: Record<PetAction, string[]> = {
  idle: ['今天也要加油哦~', '有什么我可以帮你的吗？', '记得休息一下眼睛~', '专注当下，你可以的！'],
  happy: ['太棒了！', '做得好！', '继续保持！'],
  thinking: ['让我想想...', '嗯...这个问题...', '我在认真思考哦'],
  working: ['努力工作中...', '正在帮你处理~', '加油加油！'],
  celebrate: ['任务完成！', '太厉害了！', '你是最棒的！'],
  sleep: ['Zzz...', '好困哦...', '休息一下吧~'],
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
})

onUnmounted(() => {
  if (idleTimer) clearInterval(idleTimer)
  if (messageTimer) clearTimeout(messageTimer)
  if (actionTimer) clearTimeout(actionTimer)
  window.removeEventListener(PET_ACTION_EVENT, onPetAction)
})

defineExpose({ setAction, celebrate: () => setAction('celebrate', 3000) })

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
    @click.stop="onClick"
  >
    <Transition name="bubble">
      <div v-if="showMessage" class="pet__bubble">{{ message }}</div>
    </Transition>

    <div class="pet__body">
      <svg viewBox="0 0 120 140" class="pet__svg">
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

      <div v-if="action === 'celebrate'" class="pet__confetti">
        <span v-for="i in 8" :key="i" class="pet__confetti-piece" :style="{ '--i': i }" />
      </div>
    </div>

    <div class="pet__status">
      <AppIcon :name="action === 'working' ? 'loading' : 'spark'" :size="12" />
    </div>
  </div>
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
</style>
