<script setup lang="ts">
// ============================================================
// 学习成长（二期 M8 P0）
// 学习计划 + 知识卡片(SM-2) + 复习 + 学习统计
// ============================================================
import { ref, computed, onMounted } from 'vue'
import { learningApi } from '@/api'
import { useToast } from '@/composables'
import type { Flashcard, GeneratedPlan, StudyPlan } from '@/types'
import BaseCard from '@/components/common/BaseCard.vue'

const toast = useToast()

// Tab切换
const activeTab = ref<'plans' | 'cards' | 'review' | 'stats'>('review')
const tabs = [
  { key: 'review', label: '今日复习', icon: '🎯' },
  { key: 'cards', label: '知识卡片', icon: '🃏' },
  { key: 'plans', label: '学习计划', icon: '📋' },
  { key: 'stats', label: '学习统计', icon: '📊' },
] as const

// ==================== 今日复习（SM-2） ====================
const reviewCards = ref<Flashcard[]>([])
const reviewIndex = ref(0)
const showAnswer = ref(false)
const reviewLoading = ref(false)

const currentCard = computed(() => reviewCards.value[reviewIndex.value])
const reviewProgress = computed(() => ({
  current: reviewIndex.value + 1,
  total: reviewCards.value.length,
  percent: reviewCards.value.length > 0 ? Math.round((reviewIndex.value / reviewCards.value.length) * 100) : 0,
}))

async function fetchTodayReview() {
  reviewLoading.value = true
  try {
    const data = await learningApi.todayReview()
    reviewCards.value = data.list
    reviewIndex.value = 0
    showAnswer.value = false
  } catch (e) {
    toast.error('加载复习队列失败')
  } finally {
    reviewLoading.value = false
  }
}

function flipCard() {
  showAnswer.value = !showAnswer.value
}

async function rateCard(quality: number) {
  if (!currentCard.value) return
  try {
    await learningApi.submitReview(currentCard.value.id, quality)
    const labels = ['忘记', '模糊', '困难', '一般', '良好', '容易']
    toast.success(`评分: ${labels[quality]}`)
    // 下一张
    if (reviewIndex.value < reviewCards.value.length - 1) {
      reviewIndex.value++
      showAnswer.value = false
    } else {
      toast.success('今日复习完成！')
      fetchTodayReview()
    }
  } catch (e) {
    toast.error('提交失败')
  }
}

// ==================== 知识卡片 ====================
const cards = ref<Flashcard[]>([])
const cardsLoading = ref(false)
const showCardForm = ref(false)
const cardForm = ref({ front: '', back: '', card_type: 'qa' as 'qa' | 'cloze' | 'image', difficulty: 3 })

async function fetchCards() {
  cardsLoading.value = true
  try {
    const data = await learningApi.listCards({ page: 1, page_size: 50 })
    cards.value = data.list
  } catch (e) {
    toast.error('加载卡片失败')
  } finally {
    cardsLoading.value = false
  }
}

async function createCard() {
  if (!cardForm.value.front || !cardForm.value.back) {
    toast.warning('请填写正反面内容')
    return
  }
  try {
    await learningApi.createCard(cardForm.value)
    toast.success('卡片已创建')
    cardForm.value = { front: '', back: '', card_type: 'qa', difficulty: 3 }
    showCardForm.value = false
    fetchCards()
  } catch (e) {
    toast.error('创建失败')
  }
}

async function deleteCard(id: string) {
  try {
    await learningApi.deleteCard(id)
    toast.success('卡片已删除')
    fetchCards()
  } catch (e) {
    toast.error('删除失败')
  }
}

// ==================== 学习计划 ====================
const plans = ref<StudyPlan[]>([])
const plansLoading = ref(false)
const showPlanForm = ref(false)
const planForm = ref({ name: '', description: '', estimated_hours: undefined as number | undefined })

async function fetchPlans() {
  plansLoading.value = true
  try {
    const data = await learningApi.listPlans({ page: 1, page_size: 50 })
    plans.value = data.list
  } catch (e) {
    toast.error('加载计划失败')
  } finally {
    plansLoading.value = false
  }
}

async function createPlan() {
  if (!planForm.value.name) {
    toast.warning('请填写计划名称')
    return
  }
  try {
    await learningApi.createPlan(planForm.value)
    toast.success('计划已创建')
    planForm.value = { name: '', description: '', estimated_hours: undefined }
    showPlanForm.value = false
    fetchPlans()
  } catch (e) {
    toast.error('创建失败')
  }
}

async function deletePlan(id: string) {
  try {
    await learningApi.deletePlan(id)
    toast.success('计划已删除')
    fetchPlans()
  } catch (e) {
    toast.error('删除失败')
  }
}

// ==================== 从目标生成计划（S6-1 领域规则引擎）====================
// 这条路径**不需要 API Key**：后端走内置领域知识库（13 领域 / 90 条带
// 达标标准的任务），未命中时退化为四阶段通用拆解。
// 改造前「学习计划」是个空壳 —— 用户想学雅思，得自己从零写计划。
const showGenPanel = ref(false)
const genLoading = ref(false)
const applying = ref(false)
const genForm = ref({ goal: '', total_days: 30, minutes_per_day: 45 })
const genResult = ref<GeneratedPlan | null>(null)

/** 只预览前 8 项 —— 完整计划有 30~40 项，全铺开会淹没页面 */
const genItemsPreview = computed(() =>
  (genResult.value?.items ?? []).slice(0, 8).map((item) => ({
    ...item,
    // 后端标题形如「Day 3｜听力 · 精听与定位」/「Week 2｜摄影 · 构图」
    dayLabel: item.title.split('｜')[0] || `#${item.day}`,
  })),
)

function toggleGenPanel() {
  showGenPanel.value = !showGenPanel.value
  if (!showGenPanel.value) genResult.value = null
}

async function generatePlan() {
  const goal = genForm.value.goal.trim()
  if (!goal) {
    toast.warning('请先描述你的学习目标')
    return
  }
  genLoading.value = true
  try {
    genResult.value = await learningApi.generatePlan({
      goal,
      total_days: genForm.value.total_days,
      minutes_per_day: genForm.value.minutes_per_day,
    })
  } catch (e) {
    toast.error('生成计划失败')
  } finally {
    genLoading.value = false
  }
}

async function applyPlan() {
  const current = genResult.value
  if (!current) return
  applying.value = true
  try {
    const res = await learningApi.applyPlan({
      goal: genForm.value.goal.trim(),
      total_days: genForm.value.total_days,
      minutes_per_day: genForm.value.minutes_per_day,
      plan_name: `${current.skill_name} · ${current.total_days}天计划`,
    })
    toast.success(`已创建学习计划与 ${res.task_count} 条任务`, '可前往「任务」查看')
    genResult.value = null
    showGenPanel.value = false
    fetchPlans()
  } catch (e) {
    toast.error('应用计划失败')
  } finally {
    applying.value = false
  }
}

// ==================== 学习统计 ====================
const stats = ref<{ total_minutes: number; avg_minutes: number; daily: { date: string; minutes: number }[]; trend: string } | null>(null)
const statsLoading = ref(false)
const statsDays = ref(7)

async function fetchStats() {
  statsLoading.value = true
  try {
    stats.value = await learningApi.timeStats(statsDays.value)
  } catch (e) {
    toast.error('加载统计失败')
  } finally {
    statsLoading.value = false
  }
}

const maxMinutes = computed(() => {
  if (!stats.value) return 0
  return Math.max(...stats.value.daily.map(d => d.minutes), 30)
})

// 快速记录学习时长
const quickLog = ref({ duration: 25, subject: '' })
async function logStudyTime() {
  try {
    await learningApi.logStudyTime({ duration: quickLog.value.duration, subject: quickLog.value.subject || '通用', source: 'manual' })
    toast.success(`已记录 ${quickLog.value.duration} 分钟`)
    quickLog.value = { duration: 25, subject: '' }
    if (activeTab.value === 'stats') fetchStats()
  } catch (e) {
    toast.error('记录失败')
  }
}

// 初始化
onMounted(() => {
  fetchTodayReview()
})

function switchTab(tab: 'plans' | 'cards' | 'review' | 'stats') {
  activeTab.value = tab
  if (tab === 'review') fetchTodayReview()
  if (tab === 'cards') fetchCards()
  if (tab === 'plans') fetchPlans()
  if (tab === 'stats') fetchStats()
}
</script>

<template>
  <div class="learning-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <div>
        <h1 class="page-title">学习成长</h1>
        <p class="page-sub">SM-2间隔重复 · 知识卡片 · 学习追踪</p>
      </div>
      <!-- 快速记录 -->
      <div class="quick-log">
        <input v-model.number="quickLog.duration" type="number" min="1" class="quick-input" placeholder="分钟" />
        <input v-model="quickLog.subject" class="quick-input" placeholder="科目" />
        <button class="btn-primary" @click="logStudyTime">记录</button>
      </div>
    </div>

    <!-- Tab导航 -->
    <div class="tab-nav">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-btn"
        :class="{ active: activeTab === tab.key }"
        @click="switchTab(tab.key)"
      >
        <span class="tab-icon">{{ tab.icon }}</span>
        <span>{{ tab.label }}</span>
        <span v-if="tab.key === 'review' && reviewCards.length > 0" class="tab-badge">{{ reviewCards.length }}</span>
      </button>
    </div>

    <!-- ==================== 今日复习 ==================== -->
    <div v-if="activeTab === 'review'" class="tab-content">
      <div v-if="reviewLoading" class="loading">加载中...</div>
      <div v-else-if="reviewCards.length === 0" class="empty-state">
        <div class="empty-icon">🎉</div>
        <h3>今日复习已完成</h3>
        <p>没有待复习的卡片，去创建新知识卡片吧</p>
        <button class="btn-primary" @click="switchTab('cards')">创建卡片</button>
      </div>
      <div v-else class="review-area">
        <!-- 进度条 -->
        <div class="review-progress">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: reviewProgress.percent + '%' }" />
          </div>
          <span class="progress-text">{{ reviewProgress.current }} / {{ reviewProgress.total }}</span>
        </div>

        <!-- 翻卡区域 -->
        <div class="flashcard-container" @click="flipCard">
          <div class="flashcard" :class="{ flipped: showAnswer }">
            <div class="flashcard-face flashcard-front">
              <span class="face-label">问题</span>
              <p class="face-content">{{ currentCard?.front }}</p>
              <span class="flip-hint">点击查看答案</span>
            </div>
            <div class="flashcard-face flashcard-back">
              <span class="face-label">答案</span>
              <p class="face-content">{{ currentCard?.back }}</p>
              <span class="flip-hint">点击返回问题</span>
            </div>
          </div>
        </div>

        <!-- 评分按钮 -->
        <div v-if="showAnswer" class="rating-buttons">
          <button class="rate-btn rate-0" @click.stop="rateCard(0)">忘记</button>
          <button class="rate-btn rate-2" @click.stop="rateCard(2)">困难</button>
          <button class="rate-btn rate-3" @click.stop="rateCard(3)">一般</button>
          <button class="rate-btn rate-4" @click.stop="rateCard(4)">良好</button>
          <button class="rate-btn rate-5" @click.stop="rateCard(5)">容易</button>
        </div>
        <div v-else class="rating-hint">
          <p>先回忆答案，再点击卡片查看</p>
        </div>

        <!-- 卡片信息 -->
        <div v-if="currentCard" class="card-meta">
          <span>难度: {{ currentCard.difficulty }}/5</span>
          <span>EF: {{ currentCard.ef }}</span>
          <span>间隔: {{ currentCard.interval }}天</span>
          <span>已复习: {{ currentCard.review_count }}次</span>
        </div>
      </div>
    </div>

    <!-- ==================== 知识卡片 ==================== -->
    <div v-if="activeTab === 'cards'" class="tab-content">
      <div class="content-toolbar">
        <span class="count-text">共 {{ cards.length }} 张卡片</span>
        <button class="btn-primary" @click="showCardForm = !showCardForm">
          {{ showCardForm ? '取消' : '+ 新建卡片' }}
        </button>
      </div>

      <BaseCard v-if="showCardForm" class="form-card">
        <input v-model="cardForm.front" class="form-input" placeholder="正面（问题）" />
        <textarea v-model="cardForm.back" class="form-textarea" placeholder="背面（答案）" rows="3" />
        <div class="form-row">
          <select v-model="cardForm.card_type" class="form-select">
            <option value="qa">问答</option>
            <option value="cloze">填空</option>
          </select>
          <select v-model.number="cardForm.difficulty" class="form-select">
            <option :value="1">1-很简单</option>
            <option :value="2">2-简单</option>
            <option :value="3">3-中等</option>
            <option :value="4">4-困难</option>
            <option :value="5">5-很难</option>
          </select>
          <button class="btn-primary" @click="createCard">创建</button>
        </div>
      </BaseCard>

      <div v-if="cardsLoading" class="loading">加载中...</div>
      <div v-else-if="cards.length === 0" class="empty-state">
        <div class="empty-icon">🃏</div>
        <p>还没有卡片，创建第一张知识卡片</p>
      </div>
      <div v-else class="card-grid">
        <BaseCard v-for="card in cards" :key="card.id" class="card-item">
          <div class="card-item-header">
            <span class="card-type">{{ card.card_type === 'qa' ? '问答' : '填空' }}</span>
            <button class="btn-sm btn-danger" @click="deleteCard(card.id)">删除</button>
          </div>
          <p class="card-front">{{ card.front }}</p>
          <p class="card-back">{{ card.back }}</p>
          <div class="card-item-meta">
            <span>下次: {{ card.next_review?.slice(0, 10) || '今天' }}</span>
            <span>EF: {{ card.ef }}</span>
          </div>
        </BaseCard>
      </div>
    </div>

    <!-- ==================== 学习计划 ==================== -->
    <div v-if="activeTab === 'plans'" class="tab-content">
      <div class="content-toolbar">
        <span class="count-text">共 {{ plans.length }} 个计划</span>
        <div class="toolbar-actions">
          <button class="btn-ghost" @click="toggleGenPanel">
            {{ showGenPanel ? '取消' : '🎯 从目标生成' }}
          </button>
          <button class="btn-primary" @click="showPlanForm = !showPlanForm">
            {{ showPlanForm ? '取消' : '+ 新建计划' }}
          </button>
        </div>
      </div>

      <!-- S6-1 领域规则引擎：从一句目标生成计划（离线可用，不消耗 AI 额度） -->
      <BaseCard v-if="showGenPanel" class="form-card gen-card">
        <div class="gen-head">
          <h3 class="gen-title">从一句目标生成学习计划</h3>
          <p class="gen-hint">
            基于内置领域知识库（13 个领域 · 90 条任务，每条都带达标标准），
            <strong>无需配置 API Key</strong>
          </p>
        </div>

        <div class="form-row">
          <input
            v-model="genForm.goal"
            class="form-input"
            placeholder="例如：我想学雅思 / 学会吉他弹唱 / 我想学手冲咖啡"
            @keyup.enter="generatePlan"
          />
        </div>
        <div class="form-row gen-config">
          <label class="gen-label">
            周期
            <input v-model.number="genForm.total_days" type="number" min="1" max="730" class="form-input gen-num" />
            天
          </label>
          <label class="gen-label">
            每天
            <input v-model.number="genForm.minutes_per_day" type="number" min="10" max="600" class="form-input gen-num" />
            分钟
          </label>
          <button class="btn-primary" :disabled="genLoading || !genForm.goal.trim()" @click="generatePlan">
            {{ genLoading ? '生成中…' : '生成预览' }}
          </button>
        </div>

        <div v-if="genResult" class="gen-result">
          <div class="gen-summary">
            <span class="gen-badge" :class="{ fallback: !genResult.matched }">
              {{ genResult.matched ? `命中领域：${genResult.domain_name}` : '未匹配领域库 · 已用通用四阶段拆解' }}
            </span>
            <span class="gen-meta">
              共 {{ genResult.item_count }} 项 · {{ genResult.weekly_mode ? '按周排期' : '按天排期' }}
            </span>
          </div>

          <div class="gen-units">
            <span
              v-for="u in genResult.units"
              :key="u.name"
              class="gen-unit-chip"
              :class="'phase-' + u.phase"
            >
              {{ u.name }}
            </span>
          </div>

          <div class="gen-items">
            <div v-for="(p, i) in genItemsPreview" :key="i" class="gen-item">
              <span class="gen-day">{{ p.dayLabel }}</span>
              <div class="gen-item-body">
                <p class="gen-item-task">{{ p.task }}</p>
                <p class="gen-item-accept">达标标准：{{ p.acceptance }}</p>
              </div>
              <span class="gen-item-time">{{ p.duration }}</span>
            </div>
            <p v-if="genResult.items.length > genItemsPreview.length" class="gen-more">
              仅预览前 {{ genItemsPreview.length }} 项，实际共 {{ genResult.items.length }} 项
            </p>
          </div>

          <div class="gen-actions">
            <button class="btn-primary" :disabled="applying" @click="applyPlan">
              {{ applying ? '应用中…' : `应用到任务（${genResult.item_count} 条）` }}
            </button>
            <span class="gen-actions-hint">
              将创建 1 个学习计划 + {{ genResult.item_count }} 条任务，均带预估时长与达标标准
            </span>
          </div>
        </div>
      </BaseCard>

      <BaseCard v-if="showPlanForm" class="form-card">
        <div class="form-row">
          <input v-model="planForm.name" class="form-input" placeholder="计划名称" />
          <input v-model.number="planForm.estimated_hours" type="number" class="form-input" placeholder="预计小时数" />
        </div>
        <textarea v-model="planForm.description" class="form-textarea" placeholder="计划描述" rows="2" />
        <button class="btn-primary" @click="createPlan">创建</button>
      </BaseCard>

      <div v-if="plansLoading" class="loading">加载中...</div>
      <div v-else-if="plans.length === 0" class="empty-state">
        <div class="empty-icon">📋</div>
        <p>还没有学习计划</p>
      </div>
      <div v-else class="plan-list">
        <BaseCard v-for="plan in plans" :key="plan.id" class="plan-item">
          <div class="plan-header">
            <h3 class="plan-name">{{ plan.name }}</h3>
            <span class="plan-status" :class="plan.status">{{ plan.status === 'active' ? '进行中' : plan.status }}</span>
          </div>
          <p v-if="plan.description" class="plan-desc">{{ plan.description }}</p>
          <div class="plan-meta">
            <span v-if="plan.estimated_hours">预计 {{ plan.estimated_hours }} 小时</span>
            <span v-if="plan.target_date">目标: {{ plan.target_date?.slice(0, 10) }}</span>
            <span>进度: {{ plan.progress }}%</span>
          </div>
          <div class="plan-progress">
            <div class="progress-fill" :style="{ width: plan.progress + '%' }" />
          </div>
          <button class="btn-sm btn-danger" @click="deletePlan(plan.id)">删除</button>
        </BaseCard>
      </div>
    </div>

    <!-- ==================== 学习统计 ==================== -->
    <div v-if="activeTab === 'stats'" class="tab-content">
      <div class="content-toolbar">
        <div class="filter-group">
          <button v-for="d in [7, 14, 30]" :key="d" class="filter-btn" :class="{ active: statsDays === d }" @click="statsDays = d; fetchStats()">
            {{ d }}天
          </button>
        </div>
      </div>

      <div v-if="statsLoading" class="loading">加载中...</div>
      <div v-else-if="stats" class="stats-area">
        <!-- 统计卡片 -->
        <div class="stats-cards">
          <BaseCard class="stat-card">
            <div class="stat-value">{{ stats.total_minutes }}</div>
            <div class="stat-label">总学习分钟</div>
          </BaseCard>
          <BaseCard class="stat-card">
            <div class="stat-value">{{ stats.avg_minutes }}</div>
            <div class="stat-label">日均分钟</div>
          </BaseCard>
          <BaseCard class="stat-card">
            <div class="stat-value trend-icon">{{ stats.trend === 'up' ? '📈' : stats.trend === 'down' ? '📉' : '➡️' }}</div>
            <div class="stat-label">{{ stats.trend === 'up' ? '上升' : stats.trend === 'down' ? '下降' : '稳定' }}</div>
          </BaseCard>
        </div>

        <!-- 柱状图 -->
        <BaseCard class="chart-card">
          <h3 class="chart-title">每日学习时长</h3>
          <div class="bar-chart">
            <div v-for="day in stats.daily" :key="day.date" class="bar-item">
              <div class="bar-fill" :style="{ height: (day.minutes / maxMinutes * 100) + '%' }" :title="day.date + ': ' + day.minutes + '分钟'" />
              <span class="bar-label">{{ day.date.slice(5) }}</span>
            </div>
          </div>
        </BaseCard>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.learning-page {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: var(--space-3);
}
.page-title {
  font-size: var(--text-2xl);
  font-weight: 800;
  color: var(--text-hi);
  font-family: var(--font-cute);
}
.page-sub {
  color: var(--text-mid);
  font-size: var(--text-sm);
  margin-top: 4px;
}

.quick-log {
  display: flex;
  gap: 8px;
}
.quick-input {
  width: 80px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--line);
  background: var(--bg-input);
  color: var(--text-hi);
  font-size: var(--text-sm);
  &:nth-child(2) { width: 100px; }
}

/* Tab导航 */
.tab-nav {
  display: flex;
  gap: var(--space-2);
  background: var(--bg-panel);
  padding: 6px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--line);
  width: fit-content;
}
.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: var(--radius-md);
  border: none;
  background: transparent;
  color: var(--text-mid);
  font-size: var(--text-sm);
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  &:hover { background: var(--bg-hover); }
  &.active {
    background: var(--primary);
    color: white;
    box-shadow: 0 2px 8px var(--primary-shadow);
  }
}
.tab-icon { font-size: 16px; }
.tab-badge {
  background: rgba(255,255,255,0.3);
  padding: 1px 6px;
  border-radius: 10px;
  font-size: var(--text-xs);
}

/* 通用 */
.content-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3);
}
.filter-group { display: flex; gap: 8px; }
.filter-btn {
  padding: 6px 14px;
  border-radius: var(--radius-pill);
  border: 1px solid var(--line);
  background: var(--bg-panel);
  color: var(--text-mid);
  font-size: var(--text-xs);
  cursor: pointer;
  &.active { background: var(--primary-soft); color: var(--primary); border-color: var(--primary); }
}
.count-text { color: var(--text-mid); font-size: var(--text-sm); }

.btn-primary {
  padding: 8px 18px;
  border-radius: var(--radius-md);
  border: none;
  background: var(--primary);
  color: white;
  font-size: var(--text-sm);
  font-weight: 600;
  cursor: pointer;
  &:hover { opacity: 0.9; }
}
.btn-sm {
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  border: none;
  font-size: var(--text-xs);
  cursor: pointer;
}
.btn-danger { background: var(--danger, #ff4d4f); color: white; }

.form-card { margin-bottom: var(--space-3); }
.form-row { display: flex; gap: var(--space-3); margin-bottom: var(--space-3); }
.form-input, .form-select {
  flex: 1;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--line);
  background: var(--bg-input);
  color: var(--text-hi);
  font-size: var(--text-sm);
}
.form-textarea {
  width: 100%;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--line);
  background: var(--bg-input);
  color: var(--text-hi);
  font-size: var(--text-sm);
  resize: vertical;
  margin-bottom: var(--space-3);
}

.loading, .empty-state {
  text-align: center;
  padding: var(--space-8);
  color: var(--text-mid);
}
.empty-icon { font-size: 48px; margin-bottom: 12px; }

/* ========== 复习区域 ========== */
.review-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-4);
}
.review-progress {
  width: 100%;
  max-width: 500px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.progress-bar {
  flex: 1;
  height: 8px;
  background: var(--bg-hover);
  border-radius: 4px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: var(--primary);
  border-radius: 4px;
  transition: width 0.3s;
}
.progress-text { font-size: var(--text-sm); color: var(--text-mid); white-space: nowrap; }

/* 翻卡 */
.flashcard-container {
  width: 100%;
  max-width: 500px;
  height: 280px;
  perspective: 1000px;
  cursor: pointer;
}
.flashcard {
  position: relative;
  width: 100%;
  height: 100%;
  transition: transform 0.6s;
  transform-style: preserve-3d;
  &.flipped { transform: rotateY(180deg); }
}
.flashcard-face {
  position: absolute;
  width: 100%;
  height: 100%;
  backface-visibility: hidden;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: var(--space-6);
  border-radius: var(--radius-xl);
  border: 2px solid var(--line);
  background: var(--bg-panel);
  box-shadow: 0 8px 32px rgba(0,0,0,0.1);
}
.flashcard-back { transform: rotateY(180deg); background: var(--primary-soft); }
.face-label {
  position: absolute;
  top: 16px;
  left: 20px;
  font-size: var(--text-xs);
  color: var(--text-mid);
  font-weight: 600;
}
.face-content {
  font-size: var(--text-xl);
  color: var(--text-hi);
  text-align: center;
  line-height: 1.6;
  max-width: 90%;
}
.flip-hint {
  position: absolute;
  bottom: 16px;
  font-size: var(--text-xs);
  color: var(--text-mid);
}

/* 评分按钮 */
.rating-buttons {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: center;
}
.rate-btn {
  padding: 10px 20px;
  border-radius: var(--radius-md);
  border: none;
  font-size: var(--text-sm);
  font-weight: 600;
  cursor: pointer;
  color: white;
  transition: transform 0.1s;
  &:hover { transform: scale(1.05); }
  &:active { transform: scale(0.95); }
}
.rate-0 { background: #ff4d4f; }
.rate-2 { background: #fa8c16; }
.rate-3 { background: #faad14; }
.rate-4 { background: #52c41a; }
.rate-5 { background: #1890ff; }
.rating-hint { color: var(--text-mid); font-size: var(--text-sm); }

.card-meta {
  display: flex;
  gap: 16px;
  font-size: var(--text-xs);
  color: var(--text-mid);
  flex-wrap: wrap;
  justify-content: center;
}

/* ========== 卡片列表 ========== */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-3);
}
.card-item { padding: var(--space-4); }
.card-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.card-type {
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  background: var(--primary-soft);
  color: var(--primary);
  font-size: var(--text-xs);
}
.card-front {
  font-weight: 600;
  color: var(--text-hi);
  margin-bottom: 6px;
  font-size: var(--text-sm);
}
.card-back {
  color: var(--text-mid);
  font-size: var(--text-sm);
  margin-bottom: 10px;
}
.card-item-meta {
  display: flex;
  gap: 12px;
  font-size: var(--text-xs);
  color: var(--text-mid);
}

/* ========== 计划列表 ========== */
.plan-list { display: flex; flex-direction: column; gap: var(--space-3); }
.plan-item { padding: var(--space-4); }
.plan-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.plan-name { font-size: var(--text-base); font-weight: 600; color: var(--text-hi); }
.plan-status {
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  background: var(--success, #52c41a);
  color: white;
  font-size: var(--text-xs);
}
.plan-desc { color: var(--text-mid); font-size: var(--text-sm); margin-bottom: 10px; }
.plan-meta {
  display: flex;
  gap: 16px;
  font-size: var(--text-xs);
  color: var(--text-mid);
  margin-bottom: 8px;
}
.plan-progress {
  height: 6px;
  background: var(--bg-hover);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 10px;
}

/* ========== 统计 ========== */
.stats-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.stat-card {
  text-align: center;
  padding: var(--space-4);
}
.stat-value {
  font-size: var(--text-3xl);
  font-weight: 800;
  color: var(--primary);
  margin-bottom: 4px;
}
.stat-label { font-size: var(--text-sm); color: var(--text-mid); }
.trend-icon { font-size: 32px; }

.chart-card { padding: var(--space-4); }
.chart-title {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-hi);
  margin-bottom: var(--space-4);
}
.bar-chart {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  height: 150px;
  padding: 0 8px;
}
.bar-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
  justify-content: flex-end;
}
.bar-fill {
  width: 100%;
  max-width: 24px;
  background: linear-gradient(180deg, var(--primary), var(--primary-light, var(--primary)));
  border-radius: 4px 4px 0 0;
  min-height: 2px;
  transition: height 0.3s;
}
.bar-label {
  font-size: 10px;
  color: var(--text-mid);
  margin-top: 4px;
  transform: rotate(-45deg);
  white-space: nowrap;
}

/* ============================================================
   S6-1 从目标生成计划
   （颜色一律走 token，不写死色值）
   ============================================================ */
.toolbar-actions { display: flex; gap: var(--space-2); }
.btn-ghost {
  padding: 8px 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--line);
  background: var(--bg-panel);
  color: var(--text-mid);
  font-size: var(--text-sm);
  cursor: pointer;
  &:hover { color: var(--primary); border-color: var(--primary); }
}
.gen-card { padding: var(--space-4); }
.gen-head { margin-bottom: var(--space-3); }
.gen-title { margin: 0 0 4px; font-size: var(--text-md); color: var(--text-hi); }
.gen-hint { margin: 0; font-size: var(--text-xs); color: var(--text-mid); }
.gen-config { align-items: center; }
.gen-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--text-sm);
  color: var(--text-mid);
  white-space: nowrap;
}
.gen-num { width: 80px; flex: none; text-align: center; }

.gen-result { margin-top: var(--space-3); }
.gen-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.gen-badge {
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  background: var(--primary-soft);
  color: var(--primary-ink);
  font-size: var(--text-xs);
  font-weight: 600;
  &.fallback { background: var(--bg-inset); color: var(--text-mid); }
}
.gen-meta { font-size: var(--text-xs); color: var(--text-mid); }

.gen-units { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: var(--space-3); }
.gen-unit-chip {
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  border: 1px solid var(--line);
  background: var(--bg-inset);
  color: var(--text-mid);
  font-size: var(--text-xs);
}

.gen-items {
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  max-height: 320px;
  overflow-y: auto;
}
.gen-item {
  display: flex;
  gap: var(--space-3);
  padding: 10px var(--space-3);
  border-bottom: 1px solid var(--line);
  &:last-child { border-bottom: none; }
}
.gen-day {
  flex: none;
  width: 54px;
  padding-top: 2px;
  color: var(--primary-ink);
  font-size: var(--text-xs);
  font-weight: 600;
}
.gen-item-body { flex: 1; min-width: 0; }
.gen-item-task { margin: 0 0 2px; font-size: var(--text-sm); color: var(--text-hi); line-height: 1.5; }
.gen-item-accept { margin: 0; font-size: var(--text-xs); color: var(--text-mid); }
.gen-item-time { flex: none; font-size: var(--text-xs); color: var(--text-low); white-space: nowrap; }
.gen-more { margin: 0; padding: 8px var(--space-3); font-size: var(--text-xs); color: var(--text-mid); text-align: center; }

.gen-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-top: var(--space-3);
}
.gen-actions-hint { font-size: var(--text-xs); color: var(--text-mid); }

.gen-card .btn-primary:disabled,
.gen-config .btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
