<script setup lang="ts">
// ============================================================
// 生活记录（二期 M9 P0）
// 习惯打卡 + 心情记录 + 日记
// ============================================================
import { ref, onMounted } from 'vue'
import { lifeApi } from '@/api'
import { useToast } from '@/composables'
import { useIdentity } from '@/composables/useIdentity'
import type { Habit, MoodLog, Diary } from '@/types'
import BaseCard from '@/components/common/BaseCard.vue'

const toast = useToast()

const activeTab = ref<'habits' | 'mood' | 'diary'>('habits')
const tabs = [
  { key: 'habits', label: '习惯打卡', icon: '✅' },
  { key: 'mood', label: '心情记录', icon: '😊' },
  { key: 'diary', label: '日记', icon: '📔' },
] as const

// ==================== 习惯打卡 ====================
const habits = ref<(Habit & { checked_today: boolean; current_streak: number })[]>([])
const habitsLoading = ref(false)
const showHabitForm = ref(false)
const habitForm = ref({ name: '', icon: '🎯', color: '#FF6B6B', goal_days: undefined as number | undefined })
const selectedHabitId = ref<string | null>(null)
const calendarData = ref<{ day: number; date: string; checked: boolean; is_today: boolean }[]>([])
const calendarMeta = ref({ current_streak: 0, total_checkins: 0 })
const calendarMonth = ref(new Date())

const moodEmojis = ['😢', '😔', '😐', '😊', '😄']
const moodLabels = ['很差', '不好', '一般', '不错', '很好']

async function fetchHabits() {
  habitsLoading.value = true
  try {
    const data = await lifeApi.listHabits({ page: 1, page_size: 50 })
    habits.value = data.list
  } catch (e) {
    toast.error('加载习惯失败')
  } finally {
    habitsLoading.value = false
  }
}

async function createHabit() {
  if (!habitForm.value.name) { toast.warning('请填写习惯名称'); return }
  try {
    await lifeApi.createHabit(habitForm.value)
    toast.success('习惯已创建')
    habitForm.value = { name: '', icon: '🎯', color: '#FF6B6B', goal_days: undefined }
    showHabitForm.value = false
    fetchHabits()
  } catch (e) { toast.error('创建失败') }
}

async function toggleCheckin(habit: Habit & { checked_today: boolean }) {
  try {
    if (habit.checked_today) {
      await lifeApi.uncheckHabit(habit.id)
      toast.info('已取消打卡')
    } else {
      await lifeApi.checkinHabit(habit.id)
      toast.success('打卡成功！')
    }
    fetchHabits()
    if (selectedHabitId.value === habit.id) fetchCalendar(habit.id)
  } catch (e) { toast.error('操作失败') }
}

async function deleteHabit(id: string) {
  try {
    await lifeApi.deleteHabit(id)
    toast.success('已删除')
    if (selectedHabitId.value === id) { selectedHabitId.value = null; calendarData.value = [] }
    fetchHabits()
  } catch (e) { toast.error('删除失败') }
}

async function fetchCalendar(habitId: string) {
  selectedHabitId.value = habitId
  const y = calendarMonth.value.getFullYear()
  const m = calendarMonth.value.getMonth() + 1
  try {
    const data = await lifeApi.habitCalendar(habitId, y, m)
    calendarData.value = data.calendar.filter((d): d is NonNullable<typeof d> => d !== null)
    calendarMeta.value = { current_streak: data.current_streak, total_checkins: data.total_checkins }
  } catch (e) { toast.error('加载日历失败') }
}

function prevMonth() {
  calendarMonth.value = new Date(calendarMonth.value.getFullYear(), calendarMonth.value.getMonth() - 1, 1)
  if (selectedHabitId.value) fetchCalendar(selectedHabitId.value)
}
function nextMonth() {
  calendarMonth.value = new Date(calendarMonth.value.getFullYear(), calendarMonth.value.getMonth() + 1, 1)
  if (selectedHabitId.value) fetchCalendar(selectedHabitId.value)
}

const weekDays = ['一', '二', '三', '四', '五', '六', '日']

// ==================== 心情记录 ====================
const moods = ref<MoodLog[]>([])
const moodsLoading = ref(false)
const moodScore = ref(3)
const moodContent = ref('')
const moodTags = ref('')
const moodStats = ref<{ avg_score: number; count: number; distribution: Record<string, number>; trend: string } | null>(null)

async function fetchMoods() {
  moodsLoading.value = true
  try {
    const data = await lifeApi.listMoods({ page: 1, page_size: 20 })
    moods.value = data.list
    moodStats.value = await lifeApi.moodStats(30)
  } catch (e) { toast.error('加载心情失败') }
  finally { moodsLoading.value = false }
}

async function submitMood() {
  try {
    const tags = moodTags.value.split(/[,，\s]+/).filter(Boolean)
    await lifeApi.createMood({ score: moodScore.value, content: moodContent.value, tags })
    toast.success('心情已记录')
    moodContent.value = ''
    moodTags.value = ''
    moodScore.value = 3
    fetchMoods()
  } catch (e) { toast.error('记录失败') }
}

async function deleteMood(id: string) {
  try { await lifeApi.deleteMood(id); toast.success('已删除'); fetchMoods() }
  catch (e) { toast.error('删除失败') }
}

// ==================== 日记 ====================
const diaries = ref<Diary[]>([])
const diariesLoading = ref(false)
const showDiaryEditor = ref(false)
const editingDiary = ref<Diary | null>(null)
const diaryForm = ref({ title: '', content: '', dimension: 'growth' as string, tags: '', identity_id: '' })
const { activeIdentities, loadIdentities } = useIdentity()

const dimensions = [
  { key: 'family', label: '家庭', icon: '👨‍👩‍👧' },
  { key: 'health', label: '健康', icon: '💪' },
  { key: 'energy', label: '精力', icon: '⚡' },
  { key: 'growth', label: '成长', icon: '🌱' },
]

async function fetchDiaries() {
  diariesLoading.value = true
  try {
    const data = await lifeApi.listDiaries({ page: 1, page_size: 50 })
    diaries.value = data.list
  } catch (e) { toast.error('加载日记失败') }
  finally { diariesLoading.value = false }
}

function openNewDiary() {
  editingDiary.value = null
  diaryForm.value = { title: '', content: '', dimension: 'growth', tags: '', identity_id: '' }
  showDiaryEditor.value = true
}

function openEditDiary(d: Diary) {
  editingDiary.value = d
  diaryForm.value = { title: d.title || '', content: d.content || '', dimension: d.dimension || 'growth', tags: (d.tags || []).join(','), identity_id: (d as Diary & { identity_id?: string }).identity_id ?? '' }
  showDiaryEditor.value = true
}

async function saveDiary() {
  try {
    const tags = diaryForm.value.tags.split(/[,，\s]+/).filter(Boolean)
    const payload = { ...diaryForm.value, tags, identity_id: diaryForm.value.identity_id || undefined }
    if (editingDiary.value) {
      await lifeApi.updateDiary(editingDiary.value.id, payload)
      toast.success('日记已更新')
    } else {
      await lifeApi.createDiary(payload)
      toast.success('日记已创建')
    }
    showDiaryEditor.value = false
    fetchDiaries()
  } catch (e) { toast.error('保存失败') }
}

async function deleteDiary(id: string) {
  try { await lifeApi.deleteDiary(id); toast.success('已删除'); fetchDiaries() }
  catch (e) { toast.error('删除失败') }
}

function switchTab(tab: 'habits' | 'mood' | 'diary') {
  activeTab.value = tab
  if (tab === 'habits') fetchHabits()
  if (tab === 'mood') fetchMoods()
  if (tab === 'diary') fetchDiaries()
}

onMounted(() => { loadIdentities(); fetchHabits() })
</script>

<template>
  <div class="life-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">生活记录</h1>
        <p class="page-sub">习惯养成 · 心情追踪 · 日记沉淀</p>
      </div>
    </div>

    <!-- Tab导航 -->
    <div class="tab-nav">
      <button v-for="tab in tabs" :key="tab.key" class="tab-btn" :class="{ active: activeTab === tab.key }" @click="switchTab(tab.key)">
        <span class="tab-icon">{{ tab.icon }}</span>
        <span>{{ tab.label }}</span>
      </button>
    </div>

    <!-- ==================== 习惯打卡 ==================== -->
    <div v-if="activeTab === 'habits'" class="tab-content">
      <div class="content-toolbar">
        <span class="count-text">共 {{ habits.length }} 个习惯</span>
        <button class="btn-primary" @click="showHabitForm = !showHabitForm">{{ showHabitForm ? '取消' : '+ 新建习惯' }}</button>
      </div>

      <BaseCard v-if="showHabitForm" class="form-card">
        <div class="form-row">
          <input v-model="habitForm.name" class="form-input" placeholder="习惯名称（如：早起）" />
          <input v-model="habitForm.icon" class="form-input icon-input" placeholder="图标" maxlength="2" />
          <input v-model="habitForm.color" type="color" class="form-color" />
          <input v-model.number="habitForm.goal_days" type="number" class="form-input" placeholder="目标天数" min="1" />
        </div>
        <button class="btn-primary" @click="createHabit">创建</button>
      </BaseCard>

      <div v-if="habitsLoading" class="loading">加载中...</div>
      <div v-else-if="habits.length === 0" class="empty-state">
        <div class="empty-icon">🎯</div>
        <p>还没有习惯，创建第一个开始打卡吧</p>
      </div>

      <div v-else class="habits-layout">
        <!-- 习惯列表 -->
        <div class="habit-list">
          <BaseCard
            v-for="habit in habits" :key="habit.id"
            class="habit-item"
            :class="{ active: selectedHabitId === habit.id, checked: habit.checked_today }"
            @click="fetchCalendar(habit.id)"
          >
            <div class="habit-icon" :style="{ background: (habit.color || '#FF6B6B') + '20', color: habit.color || '#FF6B6B' }">{{ habit.icon }}</div>
            <div class="habit-info">
              <h3 class="habit-name">{{ habit.name }}</h3>
              <div class="habit-meta">
                <span>🔥 连续 {{ habit.current_streak }} 天</span>
                <span v-if="habit.goal_days">目标 {{ habit.goal_days }} 天</span>
              </div>
            </div>
            <button class="checkin-btn" :class="{ done: habit.checked_today }" @click.stop="toggleCheckin(habit)">
              {{ habit.checked_today ? '✓' : '打卡' }}
            </button>
            <button class="btn-sm btn-danger" @click.stop="deleteHabit(habit.id)">删</button>
          </BaseCard>
        </div>

        <!-- 打卡日历 -->
        <BaseCard v-if="selectedHabitId" class="calendar-card">
          <div class="calendar-header">
            <button class="nav-btn" @click="prevMonth">‹</button>
            <h3 class="calendar-title">{{ calendarMonth.getFullYear() }}年{{ calendarMonth.getMonth() + 1 }}月</h3>
            <button class="nav-btn" @click="nextMonth">›</button>
          </div>
          <div class="calendar-stats">
            <span>🔥 连续 {{ calendarMeta.current_streak }} 天</span>
            <span>📊 累计 {{ calendarMeta.total_checkins }} 次</span>
          </div>
          <div class="calendar-grid">
            <div v-for="w in weekDays" :key="w" class="cal-weekday">{{ w }}</div>
            <div
              v-for="(day, i) in calendarData" :key="i"
              class="cal-day"
              :class="{ checked: day.checked, today: day.is_today }"
              :title="day.date + (day.checked ? ' ✓' : '')"
            >
              {{ day.day }}
            </div>
          </div>
        </BaseCard>
      </div>
    </div>

    <!-- ==================== 心情记录 ==================== -->
    <div v-if="activeTab === 'mood'" class="tab-content">
      <!-- 快速记录 -->
      <BaseCard class="mood-quick-card">
        <h3 class="section-title">今天心情如何？</h3>
        <div class="mood-selector">
          <button
            v-for="(emoji, i) in moodEmojis" :key="i"
            class="mood-btn" :class="{ active: moodScore === i + 1 }"
            @click="moodScore = i + 1"
          >
            <span class="mood-emoji">{{ emoji }}</span>
            <span class="mood-label">{{ moodLabels[i] }}</span>
          </button>
        </div>
        <textarea v-model="moodContent" class="form-textarea" placeholder="记录一下此刻的想法..." rows="2" />
        <div class="form-row">
          <input v-model="moodTags" class="form-input" placeholder="标签（逗号分隔）" />
          <button class="btn-primary" @click="submitMood">记录心情</button>
        </div>
      </BaseCard>

      <!-- 统计 -->
      <div v-if="moodStats" class="stats-row">
        <BaseCard class="stat-card">
          <div class="stat-value">{{ moodStats.avg_score }}</div>
          <div class="stat-label">30天平均心情</div>
        </BaseCard>
        <BaseCard class="stat-card">
          <div class="stat-value">{{ moodStats.count }}</div>
          <div class="stat-label">记录次数</div>
        </BaseCard>
        <BaseCard class="stat-card">
          <div class="stat-value trend-icon">{{ moodStats.trend === 'up' ? '📈' : moodStats.trend === 'down' ? '📉' : '➡️' }}</div>
          <div class="stat-label">{{ moodStats.trend === 'up' ? '上升' : moodStats.trend === 'down' ? '下降' : '稳定' }}</div>
        </BaseCard>
      </div>

      <!-- 心情分布 -->
      <BaseCard v-if="moodStats" class="distribution-card">
        <h3 class="section-title">心情分布</h3>
        <div class="distribution-bars">
          <div v-for="i in 5" :key="i" class="dist-item">
            <span class="dist-emoji">{{ moodEmojis[i - 1] }}</span>
            <div class="dist-bar-bg">
              <div class="dist-bar-fill" :style="{ width: (moodStats.distribution[i] || 0) / Math.max(moodStats.count, 1) * 100 + '%' }" />
            </div>
            <span class="dist-count">{{ moodStats.distribution[i] || 0 }}</span>
          </div>
        </div>
      </BaseCard>

      <!-- 历史记录 -->
      <h3 class="section-title" style="margin-top: 16px;">历史记录</h3>
      <div v-if="moodsLoading" class="loading">加载中...</div>
      <div v-else class="mood-list">
        <BaseCard v-for="mood in moods" :key="mood.id" class="mood-item">
          <span class="mood-item-emoji">{{ moodEmojis[mood.score - 1] }}</span>
          <div class="mood-item-info">
            <p v-if="mood.content" class="mood-item-content">{{ mood.content }}</p>
            <div class="mood-item-tags">
              <span v-for="tag in mood.tags" :key="tag" class="tag">{{ tag }}</span>
            </div>
          </div>
          <span class="mood-item-date">{{ mood.logged_date?.slice(0, 10) }}</span>
          <button class="btn-sm btn-danger" @click="deleteMood(mood.id)">删</button>
        </BaseCard>
      </div>
    </div>

    <!-- ==================== 日记 ==================== -->
    <div v-if="activeTab === 'diary'" class="tab-content">
      <div class="content-toolbar">
        <span class="count-text">共 {{ diaries.length }} 篇日记</span>
        <button class="btn-primary" @click="openNewDiary">+ 写日记</button>
      </div>

      <!-- 编辑器 -->
      <BaseCard v-if="showDiaryEditor" class="editor-card">
        <h3 class="section-title">{{ editingDiary ? '编辑日记' : '新日记' }}</h3>
        <div class="dimension-selector">
          <button
            v-for="dim in dimensions" :key="dim.key"
            class="dim-btn" :class="{ active: diaryForm.dimension === dim.key }"
            @click="diaryForm.dimension = dim.key"
          >
            {{ dim.icon }} {{ dim.label }}
          </button>
        </div>
        <input v-model="diaryForm.title" class="form-input" placeholder="标题" />
        <textarea v-model="diaryForm.content" class="form-textarea diary-textarea" placeholder="今天发生了什么..." rows="8" />
        <div class="form-row">
          <input v-model="diaryForm.tags" class="form-input" placeholder="标签（逗号分隔）" />
          <select v-model="diaryForm.identity_id" class="form-input">
            <option value="">身份：未归类</option>
            <option v-for="i in activeIdentities" :key="i.id" :value="i.id">{{ i.name }}</option>
          </select>
        </div>
        <div class="form-row">
          <button class="btn-primary" @click="saveDiary">保存</button>
          <button class="btn-secondary" @click="showDiaryEditor = false">取消</button>
        </div>
      </BaseCard>

      <div v-if="diariesLoading" class="loading">加载中...</div>
      <div v-else-if="diaries.length === 0 && !showDiaryEditor" class="empty-state">
        <div class="empty-icon">📔</div>
        <p>还没有日记，开始记录生活吧</p>
      </div>

      <div v-else class="diary-list">
        <BaseCard v-for="diary in diaries" :key="diary.id" class="diary-item" @click="openEditDiary(diary)">
          <div class="diary-header">
            <span class="diary-dimension">
              {{ dimensions.find(d => d.key === diary.dimension)?.icon || '📝' }}
              {{ dimensions.find(d => d.key === diary.dimension)?.label || '日常' }}
            </span>
            <span class="diary-date">{{ diary.diary_date?.slice(0, 10) }}</span>
          </div>
          <h3 class="diary-title">{{ diary.title || '无标题' }}</h3>
          <p class="diary-preview">{{ diary.content?.slice(0, 100) }}{{ diary.content && diary.content.length > 100 ? '...' : '' }}</p>
          <div class="diary-tags">
            <span v-for="tag in diary.tags" :key="tag" class="tag">{{ tag }}</span>
          </div>
          <button class="btn-sm btn-danger" @click.stop="deleteDiary(diary.id)">删除</button>
        </BaseCard>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.life-page {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.page-title { font-size: var(--text-2xl); font-weight: 800; color: var(--text-hi); font-family: var(--font-cute); }
.page-sub { color: var(--text-mid); font-size: var(--text-sm); margin-top: 4px; }

.tab-nav { display: flex; gap: var(--space-2); background: var(--bg-panel); padding: 6px; border-radius: var(--radius-lg); border: 1px solid var(--line); width: fit-content; }
.tab-btn { display: flex; align-items: center; gap: 6px; padding: 8px 16px; border-radius: var(--radius-md); border: none; background: transparent; color: var(--text-mid); font-size: var(--text-sm); font-weight: 600; cursor: pointer; transition: all 0.2s; &:hover { background: var(--bg-hover); } &.active { background: var(--primary); color: white; box-shadow: 0 2px 8px var(--primary-shadow); } }
.tab-icon { font-size: 16px; }

.content-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-3); }
.count-text { color: var(--text-mid); font-size: var(--text-sm); }
.btn-primary { padding: 8px 18px; border-radius: var(--radius-md); border: none; background: var(--primary); color: white; font-size: var(--text-sm); font-weight: 600; cursor: pointer; &:hover { opacity: 0.9; } }
.btn-secondary { padding: 8px 18px; border-radius: var(--radius-md); border: 1px solid var(--line); background: var(--bg-panel); color: var(--text-mid); font-size: var(--text-sm); cursor: pointer; }
.btn-sm { padding: 4px 10px; border-radius: var(--radius-sm); border: none; font-size: var(--text-xs); cursor: pointer; }
.btn-danger { background: var(--danger, #ff4d4f); color: white; }

.form-card { margin-bottom: var(--space-3); }
.form-row { display: flex; gap: var(--space-3); margin-bottom: var(--space-3); align-items: center; }
.form-input { flex: 1; padding: 8px 12px; border-radius: var(--radius-md); border: 1px solid var(--line); background: var(--bg-input); color: var(--text-hi); font-size: var(--text-sm); }
.icon-input { flex: 0 0 60px; text-align: center; font-size: 18px; }
.form-color { width: 40px; height: 36px; border: 1px solid var(--line); border-radius: var(--radius-md); cursor: pointer; padding: 2px; }
.form-textarea { width: 100%; padding: 8px 12px; border-radius: var(--radius-md); border: 1px solid var(--line); background: var(--bg-input); color: var(--text-hi); font-size: var(--text-sm); resize: vertical; margin-bottom: var(--space-3); }
.diary-textarea { margin: var(--space-3) 0; }

.loading, .empty-state { text-align: center; padding: var(--space-8); color: var(--text-mid); }
.empty-icon { font-size: 48px; margin-bottom: 12px; }
.section-title { font-size: var(--text-base); font-weight: 600; color: var(--text-hi); margin-bottom: var(--space-3); }

/* ========== 习惯 ========== */
.habits-layout { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
@media (max-width: 900px) { .habits-layout { grid-template-columns: 1fr; } }
.habit-list { display: flex; flex-direction: column; gap: var(--space-2); }
.habit-item { display: flex; align-items: center; gap: 12px; padding: var(--space-3); cursor: pointer; transition: all 0.2s; &:hover { transform: translateX(4px); } &.active { border-color: var(--primary); box-shadow: 0 0 0 2px var(--primary-soft); } }
.habit-icon { width: 44px; height: 44px; border-radius: var(--radius-md); display: flex; align-items: center; justify-content: center; font-size: 22px; flex-shrink: 0; }
.habit-info { flex: 1; }
.habit-name { font-size: var(--text-base); font-weight: 600; color: var(--text-hi); }
.habit-meta { display: flex; gap: 12px; font-size: var(--text-xs); color: var(--text-mid); margin-top: 2px; }
.checkin-btn { padding: 8px 16px; border-radius: var(--radius-md); border: 2px solid var(--primary); background: transparent; color: var(--primary); font-size: var(--text-sm); font-weight: 600; cursor: pointer; transition: all 0.2s; &:hover { background: var(--primary-soft); } &.done { background: var(--primary); color: white; } }

/* 日历 */
.calendar-card { padding: var(--space-4); }
.calendar-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-3); }
.calendar-title { font-size: var(--text-base); font-weight: 600; color: var(--text-hi); }
.nav-btn { width: 32px; height: 32px; border-radius: var(--radius-sm); border: 1px solid var(--line); background: var(--bg-panel); color: var(--text-mid); font-size: 18px; cursor: pointer; display: flex; align-items: center; justify-content: center; &:hover { background: var(--bg-hover); } }
.calendar-stats { display: flex; gap: 16px; margin-bottom: var(--space-3); font-size: var(--text-sm); color: var(--text-mid); }
.calendar-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
.cal-weekday { text-align: center; font-size: var(--text-xs); color: var(--text-mid); padding: 4px 0; font-weight: 600; }
.cal-day { aspect-ratio: 1; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); font-size: var(--text-xs); color: var(--text-mid); background: var(--bg-hover); &.checked { background: var(--primary); color: white; font-weight: 600; } &.today { border: 2px solid var(--primary); } }

/* ========== 心情 ========== */
.mood-quick-card { padding: var(--space-4); margin-bottom: var(--space-4); }
.mood-selector { display: flex; gap: 8px; margin-bottom: var(--space-3); flex-wrap: wrap; }
.mood-btn { flex: 1; min-width: 70px; display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 12px 8px; border-radius: var(--radius-md); border: 2px solid transparent; background: var(--bg-hover); cursor: pointer; transition: all 0.2s; &:hover { transform: scale(1.05); } &.active { border-color: var(--primary); background: var(--primary-soft); } }
.mood-emoji { font-size: 28px; }
.mood-label { font-size: var(--text-xs); color: var(--text-mid); }

.stats-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-3); margin-bottom: var(--space-4); }
.stat-card { text-align: center; padding: var(--space-4); }
.stat-value { font-size: var(--text-3xl); font-weight: 800; color: var(--primary); margin-bottom: 4px; }
.stat-label { font-size: var(--text-sm); color: var(--text-mid); }
.trend-icon { font-size: 32px; }

.distribution-card { padding: var(--space-4); margin-bottom: var(--space-4); }
.distribution-bars { display: flex; flex-direction: column; gap: 8px; }
.dist-item { display: flex; align-items: center; gap: 10px; }
.dist-emoji { font-size: 20px; width: 28px; text-align: center; }
.dist-bar-bg { flex: 1; height: 16px; background: var(--bg-hover); border-radius: 8px; overflow: hidden; }
.dist-bar-fill { height: 100%; background: linear-gradient(90deg, var(--primary), var(--primary-light, var(--primary))); border-radius: 8px; transition: width 0.3s; }
.dist-count { font-size: var(--text-xs); color: var(--text-mid); width: 24px; text-align: right; }

.mood-list { display: flex; flex-direction: column; gap: var(--space-2); }
.mood-item { display: flex; align-items: center; gap: 12px; padding: var(--space-3); }
.mood-item-emoji { font-size: 24px; }
.mood-item-info { flex: 1; }
.mood-item-content { font-size: var(--text-sm); color: var(--text-hi); margin-bottom: 4px; }
.mood-item-date { font-size: var(--text-xs); color: var(--text-mid); white-space: nowrap; }
.tag { display: inline-block; padding: 2px 8px; border-radius: var(--radius-pill); background: var(--primary-soft); color: var(--primary); font-size: var(--text-xs); margin-right: 4px; }

/* ========== 日记 ========== */
.editor-card { padding: var(--space-4); margin-bottom: var(--space-4); }
.dimension-selector { display: flex; gap: 8px; margin-bottom: var(--space-3); flex-wrap: wrap; }
.dim-btn { padding: 6px 14px; border-radius: var(--radius-pill); border: 1px solid var(--line); background: var(--bg-panel); color: var(--text-mid); font-size: var(--text-sm); cursor: pointer; &.active { background: var(--primary-soft); color: var(--primary); border-color: var(--primary); } }

.diary-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: var(--space-3); }
.diary-item { padding: var(--space-4); cursor: pointer; transition: all 0.2s; &:hover { transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,0.1); } }
.diary-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.diary-dimension { font-size: var(--text-xs); color: var(--text-mid); }
.diary-date { font-size: var(--text-xs); color: var(--text-mid); }
.diary-title { font-size: var(--text-base); font-weight: 600; color: var(--text-hi); margin-bottom: 6px; }
.diary-preview { font-size: var(--text-sm); color: var(--text-mid); line-height: 1.5; margin-bottom: 10px; }
.diary-tags { margin-bottom: 8px; }
</style>
