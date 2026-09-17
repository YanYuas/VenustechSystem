<script setup lang="ts">
// ============================================================
// 人生报告（S6-5 · 三轴合一）
// 预览三轴数据，一键导出单文件 HTML（内联样式零依赖，可存档带走）
// ============================================================
import { computed, onMounted, ref } from 'vue'
import { reportApi } from '@/api'
import { useIdentity } from '@/composables/useIdentity'
import BaseCard from '@/components/common/BaseCard.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import BaseSkeleton from '@/components/common/BaseSkeleton.vue'
import AppIcon from '@/components/common/AppIcon.vue'
import { downloadReport } from '@/utils/reportHtml'
import type { ReportData } from '@/types'

const { colorVar } = useIdentity()
const data = ref<ReportData | null>(null)
const loading = ref(true)
const exporting = ref(false)

async function load() {
  loading.value = true
  try {
    data.value = await reportApi.get()
  } catch { /* http 层已提示 */ } finally {
    loading.value = false
  }
}
onMounted(load)

function onExport() {
  if (!data.value) return
  exporting.value = true
  try {
    downloadReport(data.value)
  } finally {
    exporting.value = false
  }
}

const maxSkill = computed(() =>
  Math.max(1, ...(data.value?.growth_axis.skills ?? []).map((s) => s.count)),
)
</script>

<template>
  <div class="report">
    <div class="report__head">
      <h1 class="report__title">人生报告</h1>
      <BaseButton
        variant="primary" icon="doc" :loading="exporting" :disabled="!data"
        @click="onExport"
      >导出 HTML 存档</BaseButton>
    </div>

    <div v-if="loading"><BaseSkeleton variant="list" :rows="6" /></div>

    <template v-else-if="data">
      <p class="report__intro">
        身份 × 成长 × 档案 三轴合一。导出的 HTML 内联全部样式、零外部依赖 ——
        报告归你所有，可存档、可带走、可用任何浏览器打开。
      </p>

      <!-- 身份轴 -->
      <BaseCard title="身份轴 · 我在推进哪几条线" icon="star">
        <div v-if="data.identity_axis.identities.length" class="report__cards">
          <div v-for="r in data.identity_axis.identities" :key="r.id" class="report__card">
            <div class="report__card-head">
              <span class="report__dot" :style="{ background: colorVar(r.color_token) }" />
              <AppIcon :name="r.icon" :size="13" />
              <b>{{ r.name }}</b>
              <span v-if="r.is_archived" class="report__archived">已归档</span>
            </div>
            <div class="report__pills">
              <span>待办 {{ r.tasks_open }}</span>
              <span>完成 {{ r.tasks_completed }}</span>
              <span>文档 {{ r.documents }}</span>
              <span>日记 {{ r.diaries }}</span>
              <span>复盘 {{ r.reviews }}</span>
              <span>记忆 {{ r.memories }}</span>
            </div>
          </div>
        </div>
        <p v-else class="report__muted">还没有建立身份</p>
        <p class="report__muted report__unassigned">
          另有未归类：待办 {{ data.identity_axis.unassigned.tasks_open }} ·
          文档 {{ data.identity_axis.unassigned.documents }} ·
          日记 {{ data.identity_axis.unassigned.diaries }} ·
          复盘 {{ data.identity_axis.unassigned.reviews }} ·
          记忆 {{ data.identity_axis.unassigned.memories }}
        </p>
      </BaseCard>

      <!-- 成长轴 -->
      <BaseCard title="成长轴 · 我积累了多少" icon="flame">
        <div class="report__grid2">
          <div class="report__card">
            <div class="report__big">LV{{ data.growth_axis.level }}</div>
            <p class="report__muted">
              {{ data.growth_axis.exp }} EXP · 进度 {{ data.growth_axis.percent }}%<br>
              完成 {{ data.growth_axis.tasks_completed_total }} 任务 ·
              日记 {{ data.growth_axis.diaries_total }} 篇 ·
              复盘 {{ data.growth_axis.reviews_total }} 次
            </p>
          </div>
          <div class="report__card">
            <template v-if="data.growth_axis.skills.length">
              <div v-for="s in data.growth_axis.skills" :key="s.name" class="report__skill">
                <span class="report__skill-name">{{ s.name }}</span>
                <div class="report__track">
                  <div class="report__fill" :style="{ width: (s.count / maxSkill) * 100 + '%' }" />
                </div>
                <em>{{ s.count }}</em>
              </div>
            </template>
            <p v-else class="report__muted">还没有点亮技能</p>
          </div>
        </div>
      </BaseCard>

      <!-- 档案轴 -->
      <BaseCard title="档案轴 · 我沉淀了什么" icon="folder">
        <div class="report__grid2">
          <div class="report__card">
            <div class="report__big">{{ data.archive_axis.documents_total }}</div>
            <p class="report__muted">文档总数</p>
          </div>
          <div class="report__card">
            <p class="report__muted report__asset-line">
              SOP {{ data.archive_axis.sops_total }} ·
              提示词 {{ data.archive_axis.prompts_total }} ·
              技能 {{ data.archive_axis.skills_total }}<br>
              项目记忆 {{ data.archive_axis.project_memories_total }} ·
              分身记忆 {{ data.archive_axis.avatar_memories_total }}
            </p>
          </div>
        </div>
        <div v-if="data.archive_axis.workspace_enabled && data.archive_axis.roots.length" class="report__roots">
          <div v-for="r in data.archive_axis.roots" :key="r.path" class="report__root">
            <span class="report__mono">{{ r.label ?? r.path }}</span>
            <em>{{ r.file_count }} 项</em>
          </div>
        </div>
      </BaseCard>

      <!-- 近期经历 -->
      <BaseCard title="近期经历" icon="clock">
        <ul v-if="data.recent_experience.length" class="report__exp">
          <li v-for="(e, i) in data.recent_experience" :key="i">
            <span class="report__tag">{{ e.source_label }}</span>
            <b>{{ e.title }}</b>
            <span class="report__muted">
              {{ e.identity_name ? `· ${e.identity_name} ` : '' }}· {{ e.occurred_at.slice(0, 10) }}
            </span>
          </li>
        </ul>
        <p v-else class="report__muted">近期还没有经历记录</p>
      </BaseCard>
    </template>
  </div>
</template>

<style scoped lang="scss">
.report {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-6);
  max-width: 860px;
  margin: 0 auto;
}
.report__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.report__title {
  margin: 0;
  font-size: var(--text-xl);
  color: var(--text-hi);
}
.report__intro {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--text-mid);
  line-height: 1.7;
}
.report__cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: var(--space-3);
}
.report__card {
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--bg-inset);
}
.report__card-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-hi);
}
.report__dot {
  flex: none;
  width: 10px;
  height: 10px;
  border-radius: var(--radius-pill);
}
.report__archived {
  font-size: var(--text-xs);
  padding: 1px 8px;
  border-radius: var(--radius-pill);
  background: var(--bg-panel);
  color: var(--text-mid);
}
.report__pills {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  margin-top: var(--space-2);
  span {
    font-size: var(--text-xs);
    background: var(--bg-panel);
    border-radius: var(--radius-pill);
    padding: 2px 9px;
    color: var(--text-mid);
  }
}
.report__unassigned { margin-top: var(--space-3); }
.report__muted {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--text-mid);
  line-height: 1.7;
}
.report__grid2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}
.report__big {
  font-size: 30px;
  font-weight: 700;
  color: var(--primary-ink);
  margin-bottom: var(--space-1);
}
.report__asset-line { line-height: 2; }
.report__skill {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 4px 0;
  font-size: var(--text-sm);
  color: var(--text-hi);
}
.report__skill-name { width: 88px; flex: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.report__skill em {
  font-style: normal;
  font-size: var(--text-xs);
  color: var(--text-low);
  width: 28px;
  text-align: right;
}
.report__track {
  flex: 1;
  height: 8px;
  border-radius: var(--radius-pill);
  background: var(--bg-panel);
  overflow: hidden;
}
.report__fill {
  height: 100%;
  border-radius: var(--radius-pill);
  background: var(--primary);
  transition: width 0.4s var(--ease-soft);
}
.report__roots { margin-top: var(--space-3); }
.report__root {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  padding: 5px 0;
  font-size: var(--text-sm);
  color: var(--text-mid);
  em { font-style: normal; color: var(--text-low); }
}
.report__mono {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.report__exp {
  list-style: none;
  margin: 0;
  padding: 0;
  li {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
    flex-wrap: wrap;
    padding: 7px 0;
    border-bottom: 1px solid var(--line);
    font-size: var(--text-sm);
    color: var(--text-hi);
    &:last-child { border-bottom: none; }
  }
}
.report__tag {
  background: var(--lilac-soft);
  border-radius: var(--radius-pill);
  padding: 2px 8px;
  font-size: var(--text-xs);
  color: var(--lilac-ink);
}
</style>
