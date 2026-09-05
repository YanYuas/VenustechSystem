<script setup lang="ts">
// ============================================================
// 复盘 —— 真实数据版（useReview → /api/v1/reviews + auto-fill）
// M5：今日复盘（自动数据填充 + 撰写）+ 复盘历史列表
// ============================================================
import { onMounted, ref, watch } from 'vue'
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

const { reviews, autoFillData, loading, fetchReviews, fetchAutoFill, saveReview, convertToTask } = useReview()
const toast = useToast()

/** 动态取「今天」：应用跨午夜挂机后仍写入正确日期 */
const today = () => dayjs().format('YYYY-MM-DD')

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
</script>

<template>
  <div class="review">
    <div class="review__head">
      <h1 class="review__title">复盘</h1>
      <BaseButton variant="primary" icon="plus" @click="openWrite">写今日复盘</BaseButton>
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

    <!-- 复盘历史 -->
    <BaseCard>
      <template #title><h3 class="review__card-title">历史复盘</h3></template>
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
              <div class="review__detail-meta">
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
</style>
