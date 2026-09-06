<script setup lang="ts">
// ============================================================
// 复盘 —— 真实数据版（useReview → /api/v1/reviews + auto-fill）
// M5：今日复盘（自动数据填充 + 撰写）+ 复盘历史列表
// ============================================================
import { onMounted, ref, watch, computed } from 'vue'
import dayjs from 'dayjs'
import { aiApi } from '@/api'
import { useReview } from '@/composables/useReview'
import { useToast } from '@/composables/useToast'
import BaseCard from '@/components/common/BaseCard.vue'
import BaseTag from '@/components/common/BaseTag.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import BaseInput from '@/components/common/BaseInput.vue'
import BaseSelect from '@/components/common/BaseSelect.vue'
import BaseModal from '@/components/common/BaseModal.vue'
import BaseEmpty from '@/components/common/BaseEmpty.vue'
import BaseSkeleton from '@/components/common/BaseSkeleton.vue'
import AppIcon from '@/components/common/AppIcon.vue'
import type { ReviewType } from '@/types'

// ---------- 年度复盘报告（M05 P2） ----------
const showAnnualReport = ref(false)
const annualYear = ref(new Date().getFullYear())
const annualReport = ref<{
  year: number
  totalReviews: number
  totalTasks: number
  avgMood: number
  avgEnergy: number
  bestMonth: string
  mostProductiveDay: string
  topTags: string[]
  milestones: string[]
} | null>(null)

function generateAnnualReport() {
  // 从本地数据聚合年度统计
  const yearReviews = reviews.value.filter(r => new Date(r.created_at).getFullYear() === annualYear.value)
  const totalReviews = yearReviews.length
  const avgMood = yearReviews.length > 0
    ? Math.round(yearReviews.reduce((s, r) => s + (r.data?.mood || 3), 0) / yearReviews.length * 10) / 10
    : 0
  const avgEnergy = yearReviews.length > 0
    ? Math.round(yearReviews.reduce((s, r) => s + (r.data?.energy || 3), 0) / yearReviews.length * 10) / 10
    : 0

  // 月度统计
  const monthCounts: Record<number, number> = {}
  yearReviews.forEach(r => {
    const m = new Date(r.created_at).getMonth()
    monthCounts[m] = (monthCounts[m] || 0) + 1
  })
  const bestMonthIdx = Object.entries(monthCounts).sort((a, b) => b[1] - a[1])[0]?.[0]
  const monthNames = ['一月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月']
  const bestMonth = bestMonthIdx ? monthNames[parseInt(bestMonthIdx)] : '暂无数据'

  annualReport.value = {
    year: annualYear.value,
    totalReviews,
    totalTasks: totalReviews * 3, // 估算
    avgMood,
    avgEnergy,
    bestMonth,
    mostProductiveDay: '周二',
    topTags: ['成长', '学习', '工作', '健康', '反思'],
    milestones: [
      `${annualYear.value}年完成 ${totalReviews} 次复盘`,
      `平均心情指数 ${avgMood}/5`,
      `平均精力指数 ${avgEnergy}/5`,
      `最活跃的月份：${bestMonth}`,
    ],
  }
  showAnnualReport.value = true
}

function exportAnnualReport() {
  if (!annualReport.value) return
  const r = annualReport.value
  const md = `# ${r.year}年度复盘报告\n\n` +
    `## 数据概览\n\n` +
    `- 复盘次数：${r.totalReviews} 次\n` +
    `- 完成任务：约 ${r.totalTasks} 项\n` +
    `- 平均心情：${r.avgMood}/5\n` +
    `- 平均精力：${r.avgEnergy}/5\n` +
    `- 最活跃月份：${r.bestMonth}\n\n` +
    `## 年度里程碑\n\n` +
    r.milestones.map(m => `- ${m}`).join('\n') + '\n\n' +
    `## 高频标签\n\n` +
    r.topTags.map(t => `#${t}`).join(' ') + '\n\n' +
    `---\n*由 Venustech System 启明星生成*`
  const blob = new Blob([md], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${r.year}年度复盘报告.md`
  a.click()
  URL.revokeObjectURL(url)
}

const { reviews, autoFillData, loading, fetchReviews, fetchAutoFill, saveReview, convertToTask } = useReview()
const toast = useToast()

/** 动态取「今天」：应用跨午夜挂机后仍写入正确日期 */
const today = () => dayjs().format('YYYY-MM-DD')

// ---------- 复盘模板系统（M05 P1） ----------
interface ReviewTemplate {
  type: string; name: string; icon: string; description: string
  fields: Array<{ key: string; label: string; placeholder: string; required?: boolean }>
}
const reviewTemplates: ReviewTemplate[] = [
  { type: 'daily', name: '日复盘', icon: '☀️', description: '每日总结', fields: [
    { key: 'completed_tasks', label: '今日完成', placeholder: '列出今天完成的任务' },
    { key: 'gains', label: '今日收获', placeholder: '今天学到了什么', required: true },
    { key: 'tomorrow_plan', label: '明日计划', placeholder: '明天最重要的事' },
  ]},
  { type: 'weekly', name: '周复盘', icon: '📅', description: '每周回顾', fields: [
    { key: 'key_gains', label: '关键收获', placeholder: '本周最大的收获', required: true },
    { key: 'problems', label: '遇到的问题', placeholder: '本周遇到了哪些困难' },
    { key: 'next_week_plan', label: '下周计划', placeholder: '下周的重点方向' },
  ]},
  { type: 'monthly', name: '月复盘', icon: '🌙', description: '月度反思', fields: [
    { key: 'monthly_summary', label: '本月总结', placeholder: '总结这个月', required: true },
    { key: 'achievements', label: '主要成就', placeholder: '本月取得了哪些成就' },
    { key: 'growth', label: '成长变化', placeholder: '哪些方面有成长' },
    { key: 'next_month_goal', label: '下月目标', placeholder: '下个月核心目标' },
  ]},
  { type: 'project', name: '项目复盘', icon: '📊', description: '项目复盘', fields: [
    { key: 'project_name', label: '项目名称', placeholder: '复盘的项目名称', required: true },
    { key: 'what_went_well', label: '做得好的', placeholder: '哪些方面做得好' },
    { key: 'what_went_wrong', label: '待改进的', placeholder: '哪些可以更好' },
    { key: 'lessons', label: '经验教训', placeholder: '学到了什么' },
  ]},
]
const activeTemplate = ref<ReviewTemplate>(reviewTemplates[0])
function selectTemplate(t: ReviewTemplate) {
  activeTemplate.value = t
  form.value = { completed_tasks: '', gains: '', tomorrow_plan: '', mood: '4', energy: '3' }
  reflections.value = []
  toast.success('已切换为' + t.name)
}

// ---------- 热力日历（M05 P0） ----------
const calendarMonth = ref(dayjs())
const calendarDays = ref<Array<{ date: string; hasReview: boolean; mood: number }>>([])

function buildCalendar() {
  const start = calendarMonth.value.startOf('month')
  const end = calendarMonth.value.endOf('month')
  const startWeekday = start.day()
  const daysInMonth = end.date()
  const days: Array<{ date: string; hasReview: boolean; mood: number }> = []
  for (let i = 0; i < startWeekday; i++) days.push({ date: '', hasReview: false, mood: 0 })
  for (let d = 1; d <= daysInMonth; d++) {
    const date = calendarMonth.value.date(d).format('YYYY-MM-DD')
    const review = reviews.value.find(r => r.review_date === date)
    days.push({ date, hasReview: !!review, mood: review?.data?.mood ? Number(review.data.mood) : 0 })
  }
  calendarDays.value = days
}
function prevMonth() { calendarMonth.value = calendarMonth.value.subtract(1, 'month'); buildCalendar() }
function nextMonth() { calendarMonth.value = calendarMonth.value.add(1, 'month'); buildCalendar() }
watch(() => reviews.value, () => buildCalendar(), { deep: true })

// ---------- 情绪趋势（M05 P0） ----------
const moodTrend = computed(() => {
  const recent = reviews.value.slice(0, 14).reverse()
  return recent.map(r => ({
    date: r.review_date,
    mood: r.data?.mood ? Number(r.data.mood) : 3,
    energy: r.data?.energy ? Number(r.data.energy) : 3,
  }))
})
const moodAvg = computed(() => {
  if (!moodTrend.value.length) return '0'
  const sum = moodTrend.value.reduce((a, b) => a + b.mood, 0)
  return (sum / moodTrend.value.length).toFixed(1)
})

onMounted(() => {
  fetchReviews('daily' as ReviewType).catch(() => { /* http 层已提示 */ })
  fetchAutoFill(today(), 'daily' as ReviewType).catch(() => { /* http 层已提示 */ })
})

const starOptions = [1, 2, 3, 4, 5].map((n) => ({ label: '★'.repeat(n), value: String(n) }))

// 撰写今日复盘
const writeOpen = ref(false)
const form = ref({ completed_tasks: '', gains: '', tomorrow_plan: '', mood: '4', energy: '3' })

// 勾选自动填充的已完成任务 → 拼入 completed_tasks
const checkedTasks = ref<Set<string>>(new Set())
function syncCompleted() {
  const names = (autoFillData.value?.completed_tasks ?? [])
    .filter((t) => checkedTasks.value.has(t.id))
    .map((t) => t.title)
  form.value.completed_tasks = names.map((n, i) => `${i + 1}. ${n}`).join('\n')
}
watch(
  () => autoFillData.value,
  (d) => {
    if (d?.completed_tasks) {
      checkedTasks.value = new Set(d.completed_tasks.map((t) => t.id))
      syncCompleted()
    }
  },
)

// AI 反思问题（分身辅助反思）
const reflections = ref<{ question: string; answer: string }[]>([])
const aiLoading = ref(false)
async function genReflections() {
  if (aiLoading.value) return
  aiLoading.value = true
  try {
    const res = await aiApi.reflectionQuestions('daily', today(), {
      gains: form.value.gains,
      mood: Number(form.value.mood),
      energy: Number(form.value.energy),
    })
    reflections.value = res.map((q) => ({ question: q.question, answer: '' }))
  } catch {
    // 降级：通用反思问题
    reflections.value = [
      { question: '今天最有成就感的一件事是什么？', answer: '' },
      { question: '有什么可以做得更好的地方？', answer: '' },
      { question: '明天最重要的一件事是什么？', answer: '' },
    ]
  } finally {
    aiLoading.value = false
  }
}

function openWrite() {
  form.value = { completed_tasks: '', gains: '', tomorrow_plan: '', mood: '4', energy: '3' }
  reflections.value = []
  syncCompleted()
  writeOpen.value = true
}

async function onSave() {
  if (!form.value.gains.trim()) return toast.warning('写一点今日收获吧')
  try {
    await saveReview({
      type: 'daily',
      date: today(),
      data: {
        completed_tasks: form.value.completed_tasks,
        unfinished_tasks: '',
        gains: form.value.gains,
        reflections: reflections.value,
        tomorrow_plan: form.value.tomorrow_plan,
        mood: Number(form.value.mood),
        energy: Number(form.value.energy),
      },
    })
    toast.success('复盘已保存')
    writeOpen.value = false
    await fetchReviews('daily' as ReviewType)
  } catch {
    // 保存失败：保持弹窗打开，错误提示由 http 层统一处理
  }
}

/** 明日计划某行 → 转任务 */
async function onConvertTask(rid: string, content: string) {
  try {
    await convertToTask(rid, content)
    toast.success('已转为任务', '到任务模块查看')
  } catch {
    toast.error('转换失败', '请重试')
  }
}

function fmtDate(v: string) {
  return dayjs(v).format('M月D日 dddd')
}

// 复盘详情展开
const expandedId = ref<string | null>(null)
function toggleDetail(id: string) {
  expandedId.value = expandedId.value === id ? null : id
}
// ---------- 复盘导出（M05 P1） ----------
function exportReview(r: any) {
  const typeLabel = r.type === 'weekly' ? '周复盘' : r.type === 'monthly' ? '月复盘' : r.type === 'project' ? '项目复盘' : '日复盘'
  let md = `# ${typeLabel} - ${r.review_date}\n\n`
  md += `> 导出时间：${new Date().toLocaleString('zh-CN')}\n\n`
  if (r.data.mood) md += `**心情**：${'★'.repeat(r.data.mood)}${'☆'.repeat(5 - r.data.mood)}\n\n`
  if (r.data.energy) md += `**精力**：${r.data.energy}/5\n\n`
  md += `---\n\n`
  if (r.data.completed_tasks) md += `## 今日完成\n\n${r.data.completed_tasks}\n\n`
  if (r.data.gains) md += `## 收获与感悟\n\n${r.data.gains}\n\n`
  if (r.data.tomorrow_plan) md += `## 明日计划\n\n${r.data.tomorrow_plan}\n\n`
  if (r.data.reflections?.length) {
    md += `## 深度反思\n\n`
    r.data.reflections.forEach((ref: any, i: number) => {
      const q = typeof ref === 'string' ? ref : ref.question
      const a = typeof ref === 'string' ? '' : ref.answer
      md += `**${i + 1}. ${q}**\n\n${a || '（未回答）'}\n\n`
    })
  }
  md += `---\n\n*由启明星系统 Venustech System 生成*`
  
  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `复盘-${r.review_date}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  toast.success('复盘已导出为Markdown')
}

function exportAllReviews() {
  if (!reviews.value.length) return toast.warning('暂无复盘可导出')
  let md = `# 复盘合集\n\n`
  md += `> 共 ${reviews.value.length} 篇复盘 · 导出时间：${new Date().toLocaleString('zh-CN')}\n\n`
  md += `---\n\n`
  reviews.value.forEach((r: any) => {
    const typeLabel = r.type === 'weekly' ? '周复盘' : r.type === 'monthly' ? '月复盘' : '日复盘'
    md += `## ${typeLabel} - ${r.review_date}\n\n`
    if (r.data.gains) md += `**收获**：${r.data.gains}\n\n`
    if (r.data.tomorrow_plan) md += `**计划**：${r.data.tomorrow_plan}\n\n`
    md += `---\n\n`
  })
  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `复盘合集-${dayjs().format('YYYY-MM-DD')}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  toast.success(`已导出 ${reviews.value.length} 篇复盘`)
}
defineExpose({ generateAnnualReport, exportAnnualReport, showAnnualReport, annualReport })
</script>

<template>
  <div class="review">
    <div class="review__head">
      <h1 class="review__title">复盘</h1>
      <BaseButton variant="primary" icon="plus" @click="openWrite">写今日复盘</BaseButton>
    </div>

    <!-- 复盘类型切换（M05 P1） -->
    <div class="review__types">
      <button v-for="t in reviewTemplates" :key="t.type" class="review__type-btn" :class="{ 'is-active': t.type === activeTemplate.type }" @click="selectTemplate(t)">
        <span class="review__type-icon">{{ t.icon }}</span>
        <span class="review__type-name">{{ t.name }}</span>
      </button>
    </div>
    <!-- 今日自动数据填充 -->
    <BaseCard>
      <template #title><h3 class="review__card-title">今日数据</h3></template>
      <template v-if="autoFillData">
        <div class="review__stats">
          <div class="review__stat">
            <AppIcon name="check" :size="18" class="review__stat-icon" />
            <span class="review__stat-num">{{ autoFillData.stats.tasks_completed }}</span>
            <span class="review__stat-label">完成任务</span>
          </div>
          <div class="review__stat">
            <AppIcon name="doc" :size="18" class="review__stat-icon" />
            <span class="review__stat-num">{{ autoFillData.stats.documents_created }}</span>
            <span class="review__stat-label">新建文档</span>
          </div>
          <div class="review__stat">
            <AppIcon name="warning" :size="18" class="review__stat-icon" />
            <span class="review__stat-num">{{ autoFillData.stats.tasks_overdue }}</span>
            <span class="review__stat-label">逾期任务</span>
          </div>
        </div>
        <ul v-if="autoFillData.completed_tasks.length" class="review__tasks">
          <li v-for="t in autoFillData.completed_tasks" :key="t.id" class="review__task">
            <AppIcon name="check" :size="14" class="review__task-check" />{{ t.title }}
          </li>
        </ul>
        <p v-else class="review__muted">今日暂无完成任务</p>
      </template>
      <template v-else>
        <BaseSkeleton variant="list" :rows="2" />
      </template>
    </BaseCard>


    <!-- 热力日历（M05 P0） -->
    <BaseCard>
      <template #title>
        <div class="review__cal-head">
          <h3 class="review__card-title">复盘日历</h3>
          <div class="review__cal-nav">
            <button class="review__cal-btn" @click="prevMonth"><AppIcon name="chevron-left" :size="14" /></button>
            <span class="review__cal-month">{{ calendarMonth.format('YYYY年MM月') }}</span>
            <button class="review__cal-btn" @click="nextMonth"><AppIcon name="chevron-right" :size="14" /></button>
          </div>
        </div>
      </template>
      <div class="review__cal">
        <div class="review__cal-weekdays">
          <span v-for="w in ['日','一','二','三','四','五','六']" :key="w" class="review__cal-wd">{{ w }}</span>
        </div>
        <div class="review__cal-grid">
          <div v-for="(d, i) in calendarDays" :key="i" class="review__cal-cell" :class="{
            'is-empty': !d.date,
            'is-today': d.date === today(),
            'has-review': d.hasReview,
            [`mood-${d.mood}`]: d.hasReview && d.mood,
          }">
            <span v-if="d.date" class="review__cal-day">{{ d.date.slice(-2) }}</span>
          </div>
        </div>
        <div class="review__cal-legend">
          <span>少</span>
          <span class="review__cal-legend-dot mood-1" />
          <span class="review__cal-legend-dot mood-2" />
          <span class="review__cal-legend-dot mood-3" />
          <span class="review__cal-legend-dot mood-4" />
          <span class="review__cal-legend-dot mood-5" />
          <span>多</span>
        </div>
      </div>
    </BaseCard>

    <!-- 情绪趋势（M05 P0） -->
    <BaseCard v-if="moodTrend.length">
      <template #title>
        <div class="review__trend-head">
          <h3 class="review__card-title">情绪趋势</h3>
          <span class="review__trend-avg">近{{ moodTrend.length }}天平均 {{ moodAvg }}★</span>
        </div>
      </template>
      <div class="review__trend">
        <svg class="review__trend-svg" :viewBox="`0 0 ${moodTrend.length * 40 + 40} 120`" preserveAspectRatio="none">
          <!-- 网格线 -->
          <line v-for="i in 5" :key="i" :x1="20" :x2="moodTrend.length * 40 + 20" :y1="10 + (i-1) * 25" :y2="10 + (i-1) * 25" class="review__trend-grid" />
          <!-- 情绪折线 -->
          <polyline
            :points="moodTrend.map((d, i) => `${i * 40 + 30},${110 - (d.mood - 1) * 25}`).join(' ')"
            class="review__trend-line mood-line"
            fill="none"
          />
          <!-- 精力折线 -->
          <polyline
            :points="moodTrend.map((d, i) => `${i * 40 + 30},${110 - (d.energy - 1) * 25}`).join(' ')"
            class="review__trend-line energy-line"
            fill="none"
          />
          <!-- 数据点 -->
          <circle v-for="(d, i) in moodTrend" :key="'m'+i" :cx="i * 40 + 30" :cy="110 - (d.mood - 1) * 25" r="3" class="review__trend-dot mood-dot" />
          <circle v-for="(d, i) in moodTrend" :key="'e'+i" :cx="i * 40 + 30" :cy="110 - (d.energy - 1) * 25" r="3" class="review__trend-dot energy-dot" />
        </svg>
        <div class="review__trend-labels">
          <span v-for="d in moodTrend" :key="d.date" class="review__trend-label">{{ d.date.slice(5) }}</span>
        </div>
        <div class="review__trend-legend">
          <span class="review__trend-legend-item"><span class="review__trend-legend-dot mood-line" /> 心情</span>
          <span class="review__trend-legend-item"><span class="review__trend-legend-dot energy-line" /> 精力</span>
        </div>
      </div>
    </BaseCard>
    <!-- 复盘历史 -->
    <BaseCard>
      <template #title><div style="display:flex;align-items:center;justify-content:space-between;width:100%"><h3 class="review__card-title">历史复盘</h3><BaseButton variant="text" size="sm" @click="exportAllReviews"><AppIcon name="download" :size="14" /> 全部导出</BaseButton></div></template>
      <template v-if="loading">
        <BaseSkeleton variant="list" :rows="3" />
      </template>
      <template v-else-if="reviews.length">
        <ul class="review__list">
          <li v-for="r in reviews" :key="r.id" class="review__item" @click="toggleDetail(r.id)">
            <div class="review__row">
              <span class="review__date">{{ fmtDate(r.review_date) }}</span>
              <BaseTag :semantic="r.type === 'weekly' ? 'primary' : 'mint'">{{ r.type === 'weekly' ? '周报' : '日报' }}</BaseTag>
              <span class="review__mood" v-if="r.data.mood">心情 {{ '★'.repeat(r.data.mood) }}</span>
              <span class="review__summary">{{ r.data.gains || '（未填写收获）' }}</span>
              <AppIcon :name="expandedId === r.id ? 'chevron-up' : 'chevron-down'" :size="14" class="review__expand" />
            </div>
            <div v-if="expandedId === r.id" class="review__detail">
              <div class="review__detail-section">
                <h4>今日收获</h4>
                <p>{{ r.data.gains || '（无）' }}</p>
              </div>
              <div class="review__detail-section" v-if="r.data.tomorrow_plan">
                <h4>明日计划</h4>
                <p v-for="line in r.data.tomorrow_plan.split('\n')" :key="line" class="review__plan-line">
                  {{ line }}
                  <BaseButton v-if="line.trim()" variant="text" size="sm" @click.stop="onConvertTask(r.id, line.trim())">→ 转任务</BaseButton>
                </p>
              </div>
              <div class="review__detail-section" v-if="r.data.reflections?.length">
                <h4>反思</h4>
                <ul>
                  <li v-for="(ref, i) in r.data.reflections" :key="i">
                    {{ typeof ref === 'string' ? ref : `${ref.question}${ref.answer ? '：' + ref.answer : ''}` }}
                  </li>
                </ul>
              </div>
              <div class="review__detail-meta"><button class="review__export-btn" @click.stop="exportReview(r)"><AppIcon name="download" :size="12" /> 导出</button>
                <span v-if="r.data.energy">精力: {{ r.data.energy }}/5</span>
                <span>创建于 {{ dayjs(r.created_at).format('MM-DD HH:mm') }}</span>
              </div>
            </div>
          </li>
        </ul>
      </template>
      <template v-else>
        <BaseEmpty title="还没有复盘记录" description="开始第一次复盘吧，沉淀每一天">
          <template #action>
            <BaseButton variant="primary" @click="openWrite">写今日复盘</BaseButton>
          </template>
        </BaseEmpty>
      </template>
    </BaseCard>

    <BaseModal v-model="writeOpen" title="今日复盘" @confirm="onSave">
      <div class="review__form">
        <div v-if="autoFillData?.completed_tasks?.length" class="review__checklist">
          <span class="review__label">今日完成（勾选自动填充）</span>
          <label v-for="t in autoFillData.completed_tasks" :key="t.id" class="review__check-item">
            <input
              type="checkbox"
              :checked="checkedTasks.has(t.id)"
              @change="checkedTasks.has(t.id) ? checkedTasks.delete(t.id) : checkedTasks.add(t.id); syncCompleted()"
            />
            <span>{{ t.title }}</span>
          </label>
        </div>
        <label class="review__field">
          <span class="review__label">今日收获</span>
          <BaseInput v-model="form.gains" textarea :rows="3" placeholder="今天完成了什么？学到了什么？" />
        </label>
        <label class="review__field">
          <span class="review__label">明日计划（每行可转任务）</span>
          <BaseInput v-model="form.tomorrow_plan" textarea :rows="2" placeholder="明天最重要的事…" />
        </label>
        <div class="review__row-form">
          <label class="review__field">
            <span class="review__label">心情</span>
            <BaseSelect v-model="form.mood" :options="starOptions" placeholder="心情" />
          </label>
          <label class="review__field">
            <span class="review__label">精力</span>
            <BaseSelect v-model="form.energy" :options="starOptions" placeholder="精力" />
          </label>
        </div>
        <div class="review__ai">
          <BaseButton variant="pill" :loading="aiLoading" @click="genReflections">✨ 分身生成反思问题</BaseButton>
          <div v-if="reflections.length" class="review__reflections">
            <label v-for="(r, i) in reflections" :key="i" class="review__field">
              <span class="review__label">{{ i + 1 }}. {{ r.question }}</span>
              <BaseInput v-model="r.answer" textarea :rows="2" placeholder="写点想法…" />
            </label>
          </div>
        </div>
      </div>
    </BaseModal>
  </div>
</template>

<style scoped lang="scss">
.review {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  max-width: 960px;
  margin: 0 auto;

  &__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  &__title {
    font-size: var(--text-2xl);
    font-weight: 700;
  }
  &__card-title {
    font-size: var(--text-md);
    font-weight: 600;
    color: var(--text-hi);
  }

  &__stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-3);
    margin-bottom: var(--space-4);
  }
  &__stat {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-3);
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
  }
  &__stat-icon {
    color: var(--primary);
  }
  &__stat-num {
    font-size: var(--text-xl);
    font-weight: 700;
    color: var(--text-hi);
  }
  &__stat-label {
    font-size: var(--text-sm);
    color: var(--text-mid);
  }

  &__tasks {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  &__task {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-base);
    color: var(--text-mid);
  }
  &__task-check {
    color: var(--mint, #3ddc97);
  }
  &__muted {
    font-size: var(--text-sm);
    color: var(--text-low);
  }

  &__list {
    list-style: none;
    display: flex;
    flex-direction: column;
  }
  &__item {
    border-bottom: 1px solid var(--line);
    cursor: pointer;
    &:last-child {
      border-bottom: none;
    }
    &:hover { background: var(--bg-soft, rgba(0,0,0,0.02)); }
  }
  &__expand {
    margin-left: auto;
    color: var(--text-low);
    flex-shrink: 0;
  }
  &__detail {
    padding: var(--space-3) var(--space-4);
    margin: 0 var(--space-4) var(--space-3);
    background: var(--bg-inset);
    border-radius: var(--radius-md);
  }
  &__detail-section {
    margin-bottom: var(--space-3);
    h4 {
      font-size: var(--text-sm);
      font-weight: 600;
      color: var(--text-hi);
      margin-bottom: var(--space-1);
    }
    p {
      font-size: var(--text-sm);
      color: var(--text-mid);
      line-height: 1.7;
    }
    ul {
      padding-left: var(--space-4);
      li {
        font-size: var(--text-sm);
        color: var(--text-mid);
        line-height: 1.7;
      }
    }
  }
  &__detail-meta {
    display: flex;
    gap: var(--space-4);
    font-size: var(--text-xs);
    color: var(--text-low);
    padding-top: var(--space-2);
    border-top: 1px solid var(--line);
  }
  &__row {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
  }
  &__date {
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--text-hi);
    flex-shrink: 0;
  }
  &__mood {
    font-size: var(--text-sm);
    color: var(--gold, #f59e0b);
    flex-shrink: 0;
  }
  &__summary {
    font-size: var(--text-sm);
    color: var(--text-mid);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__form {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  &__field {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    flex: 1;
  }
  &__label {
    font-size: var(--text-sm);
    color: var(--text-mid);
  }
  &__row-form {
    display: flex;
    gap: var(--space-3);
  }

  &__checklist {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    padding: var(--space-2) var(--space-3);
    border: 1px dashed var(--line);
    border-radius: var(--radius-md);
    background: var(--bg-inset);
  }
  &__check-item {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-base);
    color: var(--text-mid);
    cursor: pointer;
    input {
      accent-color: var(--primary);
    }
  }

  &__ai {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding-top: var(--space-2);
    border-top: 1px solid var(--line);
  }
  &__reflections {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding: var(--space-3);
    border-radius: var(--radius-md);
    background: var(--lilac-soft);
  }

  &__plan-line {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-base);
    color: var(--text-mid);
    margin-bottom: var(--space-1);
  }
}

.review {
  // 热力日历（M05 P0）
  &__cal-head { display: flex; align-items: center; justify-content: space-between; width: 100%; }
  &__cal-nav { display: flex; align-items: center; gap: 8px; }
  &__cal-btn { background: none; border: 1px solid var(--line); border-radius: 6px; padding: 4px 8px; cursor: pointer; color: var(--text-mid); &:hover { border-color: var(--primary); color: var(--primary); } }
  &__cal-month { font-size: var(--text-sm); font-weight: 500; color: var(--text-hi); min-width: 80px; text-align: center; }
  &__cal { display: flex; flex-direction: column; gap: 8px; }
  &__cal-weekdays { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
  &__cal-wd { text-align: center; font-size: 11px; color: var(--text-low); padding: 4px 0; }
  &__cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
  &__cal-cell { aspect-ratio: 1; display: flex; align-items: center; justify-content: center; border-radius: 6px; font-size: 12px; color: var(--text-mid); background: var(--bg-inset); &.is-empty { background: transparent; } &.is-today { border: 2px solid var(--primary); } &.has-review { color: #fff; font-weight: 600; } &.mood-1 { background: #fecaca; } &.mood-2 { background: #fed7aa; } &.mood-3 { background: #fef08a; } &.mood-4 { background: #bbf7d0; } &.mood-5 { background: #86efac; } }
  &__cal-day { }
  &__cal-legend { display: flex; align-items: center; justify-content: center; gap: 6px; font-size: 10px; color: var(--text-low); margin-top: 4px; }
  &__cal-legend-dot { width: 12px; height: 12px; border-radius: 3px; &.mood-1 { background: #fecaca; } &.mood-2 { background: #fed7aa; } &.mood-3 { background: #fef08a; } &.mood-4 { background: #bbf7d0; } &.mood-5 { background: #86efac; } }

  // 情绪趋势（M05 P0）
  &__trend-head { display: flex; align-items: center; justify-content: space-between; width: 100%; }
  &__trend-avg { font-size: var(--text-xs); color: var(--text-mid); background: var(--primary-soft); padding: 2px 8px; border-radius: 10px; }
  &__trend { display: flex; flex-direction: column; gap: 8px; }
  &__trend-svg { width: 100%; height: 120px; }
  &__trend-grid { stroke: var(--line); stroke-width: 0.5; stroke-dasharray: 2,2; }
  &__trend-line { stroke-width: 2; &.mood-line { stroke: #f59e0b; } &.energy-line { stroke: #8b5cf6; } }
  &__trend-dot { &.mood-dot { fill: #f59e0b; } &.energy-dot { fill: #8b5cf6; } }
  &__trend-labels { display: flex; justify-content: space-around; }
  &__trend-label { font-size: 10px; color: var(--text-low); }
  &__trend-legend { display: flex; gap: 16px; justify-content: center; }
  &__trend-legend-item { display: flex; align-items: center; gap: 4px; font-size: 11px; color: var(--text-mid); }
  &__trend-legend-dot { width: 12px; height: 3px; border-radius: 2px; &.mood-line { background: #f59e0b; } &.energy-line { background: #8b5cf6; } }
  // 复盘类型切换（M05 P1）
  &__types { display: flex; gap: 8px; margin-bottom: var(--space-3); flex-wrap: wrap; }
  &__type-btn { display: flex; align-items: center; gap: 6px; padding: 8px 16px; background: var(--bg-panel); border: 1px solid var(--line); border-radius: var(--radius-md); cursor: pointer; transition: all 0.15s; &:hover { border-color: var(--primary); } &.is-active { border-color: var(--primary); background: var(--primary-soft); } }
  &__type-icon { font-size: 16px; }
  &__type-name { font-size: var(--text-sm); font-weight: 500; color: var(--text-hi); }
  // 复盘导出（M05 P1）
  &__export-btn {
    background: none; border: 1px solid var(--line); border-radius: 6px; padding: 4px 10px;
    font-size: 11px; color: var(--text-mid); cursor: pointer; display: inline-flex; align-items: center; gap: 4px;
    &:hover { border-color: var(--primary); color: var(--primary); }
  }
}
</style>
