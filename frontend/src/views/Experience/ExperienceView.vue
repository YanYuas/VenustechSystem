<script setup lang="ts">
// ============================================================
// 经历时间线（S6-4 · 视图不建表）
//
// 「我的人生历程、兴趣爱好与个人成果」的展示面：日记 / 复盘 /
// 分身记忆 / 项目记忆 四源按身份归并成一条时间线。
// 存储仍是四张源表 —— 本页只是聚合视图，不能也不需要在编辑。
// ============================================================
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { experienceApi } from '@/api'
import { useIdentity } from '@/composables/useIdentity'
import BaseCard from '@/components/common/BaseCard.vue'
import BaseSelect from '@/components/common/BaseSelect.vue'
import BaseEmpty from '@/components/common/BaseEmpty.vue'
import BaseSkeleton from '@/components/common/BaseSkeleton.vue'
import AppIcon from '@/components/common/AppIcon.vue'
import type { ExperienceItem, ExperienceSource } from '@/types'

const route = useRoute()
const { loadIdentities, identityOptions, colorVar, byId } = useIdentity()

const items = ref<ExperienceItem[]>([])
const total = ref(0)
const sourceCounts = ref<Partial<Record<ExperienceSource, number>>>({})
const loading = ref(true)
const page = ref(1)
const PAGE_SIZE = 50

// BaseSelect 空串 = 未选 → 用哨兵值三态（与任务页一致）
const FILTER_ALL = '__all__'
const FILTER_NONE = '__none__'
const filterIdentityId = ref(FILTER_ALL)

const filterOptions = computed(() => [
  { label: '全部身份', value: FILTER_ALL },
  { label: '未归类', value: FILTER_NONE },
  ...identityOptions().slice(1),
])

const SOURCE_META: Record<ExperienceSource, { icon: string; semantic: string }> = {
  diary: { icon: 'book', semantic: 'sky' },
  review: { icon: 'edit-doc', semantic: 'mint' },
  avatar_memory: { icon: 'user', semantic: 'lilac' },
  project_memory: { icon: 'star', semantic: 'gold' },
}

async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: PAGE_SIZE }
    if (filterIdentityId.value === FILTER_NONE) params.identity_unassigned = true
    else if (filterIdentityId.value !== FILTER_ALL) params.identity_id = filterIdentityId.value
    const res = await experienceApi.list(params)
    items.value = res.items
    total.value = res.total
    sourceCounts.value = res.source_counts
  } catch { /* http 层已提示 */ } finally {
    loading.value = false
  }
}

function onFilter(v: string) {
  filterIdentityId.value = v
  page.value = 1
  load()
}

// 支持从身份管理页 / Dashboard 带 ?identity_id= 跳入
watch(
  () => route.query.identity_id,
  (v) => {
    if (typeof v === 'string' && v) {
      filterIdentityId.value = v
      page.value = 1
      load()
    }
  },
)

onMounted(() => {
  loadIdentities()
  const urlIdentity = route.query.identity_id as string
  if (urlIdentity) filterIdentityId.value = urlIdentity
  load()
})

function dayLabel(iso: string) {
  return iso.slice(0, 10)
}
function timeLabel(iso: string) {
  return iso.length >= 16 ? iso.slice(11, 16) : ''
}

/** 按日期分组的时间线（occurred_at 已降序，分组保持顺序） */
const groups = computed(() => {
  const out: Array<{ day: string; items: ExperienceItem[] }> = []
  for (const it of items.value) {
    const day = dayLabel(it.occurred_at)
    const last = out[out.length - 1]
    if (last && last.day === day) last.items.push(it)
    else out.push({ day, items: [it] })
  }
  return out
})

const identityName = (id: string | null) => byId(id)?.name ?? '未归类'
</script>

<template>
  <div class="exp">
    <div class="exp__head">
      <h1 class="exp__title">经历</h1>
      <BaseSelect
        class="exp__filter"
        :model-value="filterIdentityId"
        :options="filterOptions"
        placeholder="身份"
        @change="onFilter"
      />
    </div>

    <p class="exp__intro">
      日记、复盘、分身记忆、项目记忆在这里汇成一条线 —— 按身份看，
      就是「这条线上发生过什么」。记录仍在各自的模块里完成，本页只负责归并展示。
    </p>

    <BaseCard>
      <div v-if="loading"><BaseSkeleton variant="list" :rows="6" /></div>
      <BaseEmpty
        v-else-if="items.length === 0"
        title="这条线上还没有经历"
        description="去写日记、复盘，或沉淀分身/项目记忆，并给它们挂上身份"
      />
      <template v-else>
        <div class="exp__counts">
          <span v-for="(c, s) in sourceCounts" :key="s" class="exp__count">
            {{ SOURCE_META[s as ExperienceSource]?.icon && '·' }} {{ s === 'diary' ? '日记' : s === 'review' ? '复盘' : s === 'avatar_memory' ? '分身记忆' : '项目记忆' }} {{ c }}
          </span>
          <span class="exp__total">共 {{ total }} 条</span>
        </div>

        <div v-for="g in groups" :key="g.day" class="exp__group">
          <div class="exp__day">
            <span class="exp__day-text">{{ g.day }}</span>
            <span class="exp__day-line" />
          </div>
          <ul class="exp__list">
            <li v-for="it in g.items" :key="it.source + it.id" class="exp__item">
              <span
                class="exp__dot"
                :style="{ background: colorVar(byId(it.identity_id)?.color_token ?? null) }"
              />
              <div class="exp__main">
                <div class="exp__line">
                  <AppIcon :name="SOURCE_META[it.source].icon" :size="13" />
                  <span class="exp__item-title">{{ it.title }}</span>
                  <span class="exp__srctag">{{ it.source_label }}</span>
                </div>
                <p v-if="it.snippet" class="exp__snippet">{{ it.snippet }}</p>
                <p class="exp__meta">
                  {{ identityName(it.identity_id) }}
                  <span v-if="timeLabel(it.occurred_at)"> · {{ timeLabel(it.occurred_at) }}</span>
                </p>
              </div>
            </li>
          </ul>
        </div>
      </template>
    </BaseCard>
  </div>
</template>

<style scoped lang="scss">
.exp {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-6);
}
.exp__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}
.exp__title {
  margin: 0;
  font-size: var(--text-xl);
  color: var(--text-hi);
}
.exp__filter { width: 160px; flex: none; }
.exp__intro {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--text-mid);
  line-height: 1.7;
}
.exp__counts {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
  font-size: var(--text-xs);
  color: var(--text-mid);
}
.exp__total { margin-left: auto; color: var(--text-low); }

.exp__group { margin-bottom: var(--space-3); }
.exp__day {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}
.exp__day-text {
  font-size: var(--text-xs);
  color: var(--text-low);
  font-family: var(--font-mono);
}
.exp__day-line { flex: 1; height: 1px; background: var(--line); }

.exp__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.exp__item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-2) 0;
}
.exp__dot {
  flex: none;
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: var(--radius-pill);
}
.exp__main { flex: 1; min-width: 0; }
.exp__line {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-mid);
}
.exp__item-title {
  font-size: var(--text-sm);
  color: var(--text-hi);
  font-weight: 600;
}
.exp__srctag {
  padding: 1px 8px;
  border-radius: var(--radius-pill);
  background: var(--bg-inset);
  font-size: var(--text-xs);
  color: var(--text-mid);
}
.exp__snippet {
  margin: var(--space-1) 0 0;
  font-size: var(--text-xs);
  color: var(--text-mid);
  line-height: 1.6;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.exp__meta {
  margin: 2px 0 0;
  font-size: var(--text-xs);
  color: var(--text-low);
}
</style>
