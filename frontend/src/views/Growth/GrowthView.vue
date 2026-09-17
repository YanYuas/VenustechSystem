<script setup lang="ts">
// ============================================================
// 成长体系（S6-2）
// 等级 / 经验进度 / 技能树 / EXP 流水 / 如何获得经验
//
// 后端在 W2 已全部就绪，此前却只有顶栏一个小徽章 —— 数据在涨但看不见。
// 本页把这些已有能力暴露出来，不做任何新功能。
// ============================================================
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { growthApi } from '@/api'
import type { GrowthEventItem, GrowthMeta, GrowthState, SkillNode } from '@/types'
import BaseCard from '@/components/common/BaseCard.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import { useToast } from '@/composables'

const toast = useToast()
const router = useRouter()

const state = ref<GrowthState | null>(null)
const skills = ref<SkillNode[]>([])
const events = ref<GrowthEventItem[]>([])
const meta = ref<GrowthMeta | null>(null)
const loading = ref(true)

/** 技能条按最大值归一，让最高的那根占满 */
const maxSkillCount = computed(() => Math.max(1, ...skills.value.map((s) => s.count)))

async function load() {
  loading.value = true
  try {
    const [s, sk, ev, m] = await Promise.all([
      growthApi.state(),
      growthApi.skills(),
      growthApi.events(20),
      growthApi.meta(),
    ])
    state.value = s
    skills.value = sk.list
    events.value = ev.list
    meta.value = m
  } catch {
    toast.error('加载成长数据失败')
  } finally {
    loading.value = false
  }
}

onMounted(load)

function formatTime(iso: string | null) {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const min = Math.floor(diff / 60000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min} 分钟前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr} 小时前`
  return `${Math.floor(hr / 24)} 天前`
}

// 事件类型 → 中文标签（后端只给 key，展示层负责可读化）
const RULE_LABELS: Record<string, string> = {
  'project.memory.created': '沉淀项目记忆',
  'diary.created': '写日记',
  'review.created': '写复盘',
  'review.generated': '生成复盘',
  'project.created': '立项',
  'document.created': '新建文档',
  'sop.used': '复用 SOP',
  'inbox.item.processed': '整理收集箱',
  'task.completed': '完成任务',
  'prompt.used': '使用提示词',
  'habit.checkin': '习惯打卡',
  'flashcard.reviewed': '复习卡片',
  'mood.logged': '记录心情',
  'project.updated': '更新项目',
  'document.saved': '保存文档',
  'inbox.item.created': '收集想法',
  'task.created': '创建任务',
  'conversation.message': '与分身对话',
}

const rules = computed(() => {
  if (!meta.value) return []
  return Object.entries(meta.value.exp_rules)
    .map(([k, v]) => ({ key: k, label: RULE_LABELS[k] ?? k, exp: v }))
    .sort((a, b) => b.exp - a.exp)
})
</script>

<template>
  <div class="growth">
    <div class="growth__head">
      <BaseButton variant="secondary" icon="doc" @click="router.push('/report')">
        人生报告
      </BaseButton>
    </div>
    <div v-if="loading" class="growth__loading">加载中…</div>

    <template v-else>
      <BaseCard title="等级" icon="spark">
        <div v-if="state" class="growth__level">
          <div class="growth__level-badge">
            <span class="growth__level-num">LV{{ state.level }}</span>
          </div>
          <div class="growth__level-body">
            <div class="growth__level-track">
              <span class="growth__level-fill" :style="{ width: state.percent + '%' }" />
            </div>
            <p class="growth__level-text">
              <template v-if="state.is_max">
                已满级 · 累计 {{ state.exp }} EXP
              </template>
              <template v-else>
                {{ state.current }} / {{ state.need }} EXP · 累计 {{ state.exp }}
                <span v-if="state.next_level_exp">（下一级需 {{ state.next_level_exp }}）</span>
              </template>
            </p>
          </div>
        </div>
      </BaseCard>

      <BaseCard title="技能树" icon="star">
        <p v-if="skills.length === 0" class="growth__empty">
          还没有点亮任何技能 —— 去写复盘、沉淀项目记忆或完成学习任务吧
        </p>
        <div v-else class="growth__skills">
          <div v-for="s in skills" :key="s.id" class="growth__skill">
            <div class="growth__skill-head">
              <span class="growth__skill-name">{{ s.name }}</span>
              <span class="growth__skill-level">Lv.{{ s.level }}</span>
            </div>
            <div class="growth__skill-track">
              <span
                class="growth__skill-fill"
                :style="{ width: (s.count / maxSkillCount) * 100 + '%' }"
              />
            </div>
            <span class="growth__skill-count">{{ s.count }} 次</span>
          </div>
        </div>
      </BaseCard>

      <BaseCard title="经验流水" icon="clock">
        <p v-if="events.length === 0" class="growth__empty">还没有经验记录</p>
        <ul v-else class="growth__events">
          <li v-for="e in events" :key="e.id" class="growth__event">
            <span class="growth__event-exp">+{{ e.exp }}</span>
            <span class="growth__event-label">{{ e.label || e.event_type }}</span>
            <span class="growth__event-time">{{ formatTime(e.created_at) }}</span>
          </li>
        </ul>
      </BaseCard>

      <BaseCard title="如何获得经验" icon="chart">
        <p class="growth__hint">
          沉淀类行为（写、反思、沉淀资产）的收益远高于处理类（勾选、保存）。
          这是刻意的设计 —— 否则「勾任务」会和「写经历」赚得一样多，
          经验值就从"衡量成长"退化成"衡量点击量"。
        </p>
        <ul class="growth__rules">
          <li v-for="r in rules" :key="r.key" class="growth__rule">
            <span class="growth__rule-label">{{ r.label }}</span>
            <span class="growth__rule-exp">{{ r.exp }}</span>
          </li>
        </ul>
      </BaseCard>
    </template>
  </div>
</template>

<style scoped lang="scss">
.growth {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-6);
}
.growth__head {
  display: flex;
  justify-content: flex-end;
}
.growth__loading,
.growth__empty {
  margin: 0;
  color: var(--text-mid);
  font-size: var(--text-sm);
}
.growth__hint {
  margin: 0 0 var(--space-3);
  font-size: var(--text-xs);
  color: var(--text-mid);
  line-height: 1.6;
}

.growth__level {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}
.growth__level-badge {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  border-radius: var(--radius-lg);
  background: var(--primary-soft);
}
.growth__level-num {
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--primary-ink);
}
.growth__level-body {
  flex: 1;
  min-width: 0;
}
.growth__level-track,
.growth__skill-track {
  display: block;
  height: 8px;
  border-radius: var(--radius-pill);
  background: var(--bg-inset);
  overflow: hidden;
}
.growth__level-fill,
.growth__skill-fill {
  display: block;
  height: 100%;
  border-radius: var(--radius-pill);
  background: var(--primary);
  transition: width 0.5s var(--ease-soft);
}
.growth__level-text {
  margin: var(--space-2) 0 0;
  font-size: var(--text-sm);
  color: var(--text-mid);
}

.growth__skills {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--space-3);
}
.growth__skill {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.growth__skill-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
.growth__skill-name {
  font-size: var(--text-sm);
  color: var(--text-hi);
}
.growth__skill-level {
  font-size: var(--text-xs);
  color: var(--primary-ink);
}
.growth__skill-count {
  font-size: var(--text-xs);
  color: var(--text-low);
}

.growth__events {
  list-style: none;
  margin: 0;
  padding: 0;
}
.growth__event {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 8px 0;
  border-bottom: 1px solid var(--line);
  &:last-child {
    border-bottom: none;
  }
}
.growth__event-exp {
  flex: none;
  width: 44px;
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--primary-ink);
}
.growth__event-label {
  flex: 1;
  font-size: var(--text-sm);
  color: var(--text-hi);
}
.growth__event-time {
  font-size: var(--text-xs);
  color: var(--text-low);
}

.growth__rules {
  list-style: none;
  margin: 0;
  padding: 0;
}
.growth__rule {
  display: flex;
  justify-content: space-between;
  padding: 5px 0;
  font-size: var(--text-sm);
}
.growth__rule-label {
  color: var(--text-mid);
}
.growth__rule-exp {
  color: var(--text-hi);
  font-weight: 600;
}
</style>
