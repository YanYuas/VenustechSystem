<script setup lang="ts">
// ============================================================
// FocusTimer —— 番茄钟（M02 F08）
// 25 分钟专注 + 提示；开始时后端记 start，停止/结束时结算 duration
// ============================================================
import { ref, computed, onBeforeUnmount } from 'vue'
import { taskApi } from '@/api'
import { useToast } from '@/composables/useToast'
import { emitPetAction } from '@/composables/usePetEvent'
import BaseButton from '@/components/common/BaseButton.vue'
import AppIcon from '@/components/common/AppIcon.vue'

const props = defineProps<{
  taskId: string
  /** 单轮时长（分钟），默认 25 */
  minutes?: number
}>()

const emit = defineEmits<{
  (e: 'finished'): void
}>()

const toast = useToast()

const FOCUS_MINUTES = props.minutes ?? 25
const totalSeconds = FOCUS_MINUTES * 60

const running = ref(false)
const remaining = ref(totalSeconds)
const sessionId = ref<string | null>(null)
let timer: ReturnType<typeof setInterval> | null = null

const display = computed(() => {
  const m = Math.floor(remaining.value / 60)
  const s = remaining.value % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
})

const progress = computed(() =>
  Math.round(((totalSeconds - remaining.value) / totalSeconds) * 100),
)

async function start() {
  if (running.value) return
  try {
    const session = await taskApi.focusStart(props.taskId)
    sessionId.value = session.id
    running.value = true
    emitPetAction('working', 0)
    timer = setInterval(async () => {
      remaining.value -= 1
      if (remaining.value <= 0) {
        await stop(true)
        emit('finished')
      }
    }, 1000)
  } catch { /* http 层已提示 */ }
}

async function stop(completed = false) {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
  running.value = false
  if (sessionId.value) {
    try {
      await taskApi.focusStop(sessionId.value)
      sessionId.value = null
      if (completed) {
        toast.success('专注完成！', `${FOCUS_MINUTES} 分钟番茄钟结束，休息一下吧`)
        emitPetAction('celebrate', 3000)
      }
      emit('finished')
    } catch { /* http 层已提示 */ }
  }
  remaining.value = totalSeconds
}

onBeforeUnmount(() => {
  // 组件卸载时兜底结算在途会话
  if (timer) clearInterval(timer)
  if (sessionId.value) {
    taskApi.focusStop(sessionId.value).catch(() => { /* ignore */ })
  }
})
</script>

<template>
  <div class="ft" :class="{ 'is-running': running }">
    <div class="ft__ring">
      <svg viewBox="0 0 44 44" class="ft__svg">
        <circle cx="22" cy="22" r="19" class="ft__bg" />
        <circle
          cx="22" cy="22" r="19" class="ft__fill"
          :stroke-dasharray="`${(progress / 100) * 119.4} 119.4`"
        />
      </svg>
      <span class="ft__time">{{ display }}</span>
    </div>
    <BaseButton
      :variant="running ? 'danger' : 'primary'"
      size="sm"
      @click="running ? stop() : start()"
    >
      <AppIcon :name="running ? 'close' : 'target'" :size="14" />
      {{ running ? '结束专注' : '开始专注' }}
    </BaseButton>
  </div>
</template>

<style scoped lang="scss">
.ft {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border: 1px dashed var(--line);
  border-radius: var(--radius-md);

  &.is-running { border-color: var(--primary); border-style: solid; }

  &__ring { position: relative; width: 48px; height: 48px; }
  &__svg { width: 100%; height: 100%; transform: rotate(-90deg); }
  &__bg { fill: none; stroke: var(--bg-inset); stroke-width: 3.5; }
  &__fill {
    fill: none; stroke: var(--primary); stroke-width: 3.5; stroke-linecap: round;
    transition: stroke-dasharray 0.9s linear;
  }
  &__time {
    position: absolute; inset: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 11px; font-weight: 700; color: var(--text-hi);
    font-variant-numeric: tabular-nums;
  }
}
</style>
