<script setup lang="ts">
// ============================================================
// 工作流中心（二期 P1）
// 预设工作流浏览 + 一键应用 + 应用历史
// ============================================================
import { ref, onMounted } from 'vue'
import { workflowApi } from '@/api/workflow'
import { useToast } from '@/composables'
import type { Workflow, WorkflowApplication } from '@/api/workflow'
import BaseCard from '@/components/common/BaseCard.vue'

const toast = useToast()

const activeTab = ref<'presets' | 'history'>('presets')
const presets = ref<Workflow[]>([])
const applications = ref<WorkflowApplication[]>([])
const loading = ref(false)
const selectedWorkflow = ref<Workflow | null>(null)
const applying = ref(false)
const applyParams = ref('')

const categoryMap: Record<string, { label: string; color: string }> = {
  study: { label: '学习', color: '#409EFF' },
  dev: { label: '开发', color: '#67C23A' },
  writing: { label: '写作', color: '#E6A23C' },
  custom: { label: '自定义', color: '#909399' },
}

async function fetchPresets() {
  loading.value = true
  try {
    const data = await workflowApi.listPresets()
    presets.value = data.list
  } catch (e) {
    toast.error('加载工作流失败')
  } finally {
    loading.value = false
  }
}

async function fetchHistory() {
  loading.value = true
  try {
    const data = await workflowApi.listApplications({ page: 1, page_size: 20 })
    applications.value = data.list
  } catch (e) {
    toast.error('加载历史失败')
  } finally {
    loading.value = false
  }
}

function viewDetail(wf: Workflow) {
  selectedWorkflow.value = wf
  applyParams.value = ''
}

function closeDetail() {
  selectedWorkflow.value = null
}

async function doApply() {
  if (!selectedWorkflow.value) return
  applying.value = true
  try {
    let params: Record<string, unknown> = {}
    if (applyParams.value.trim()) {
      applyParams.value.split('\n').forEach(line => {
        const [k, ...v] = line.split('=')
        if (k && v.length) params[k.trim()] = v.join('=').trim()
      })
    }
    const result = await workflowApi.applyWorkflow(selectedWorkflow.value.id, params)
    toast.success(result.summary)
    closeDetail()
    fetchPresets()
    fetchHistory()
  } catch (e) {
    toast.error('应用失败')
  } finally {
    applying.value = false
  }
}

function getRules(wf: Workflow | null): { trigger: string; action: string }[] {
  if (!wf) return []
  return ((wf.config as Record<string, unknown>).automation_rules || []) as { trigger: string; action: string }[]
}

function getTaskTemplates(wf: Workflow | null): { name: string; steps: string[] }[] {
  if (!wf) return []
  return ((wf.config as Record<string, unknown>).task_templates || []) as { name: string; steps: string[] }[]
}

function getStringList(wf: Workflow | null, key: string): string[] {
  if (!wf) return []
  return ((wf.config as Record<string, unknown>)[key] || []) as string[]
}

function getTagSystem(wf: Workflow | null): Record<string, string[]> {
  if (!wf) return {}
  return ((wf.config as Record<string, unknown>).tag_system || {}) as Record<string, string[]>
}

function switchTab(tab: 'presets' | 'history') {
  activeTab.value = tab
  if (tab === 'presets') fetchPresets()
  if (tab === 'history') fetchHistory()
}

onMounted(() => fetchPresets())
</script>

<template>
  <div class="workflow-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">工作流中心</h1>
        <p class="page-sub">一键应用预设工作流，快速搭建个人工作体系</p>
      </div>
    </div>

    <!-- Tab导航 -->
    <div class="tab-nav">
      <button class="tab-btn" :class="{ active: activeTab === 'presets' }" @click="switchTab('presets')">
        <span class="tab-icon">📦</span>
        <span>预设工作流</span>
      </button>
      <button class="tab-btn" :class="{ active: activeTab === 'history' }" @click="switchTab('history')">
        <span class="tab-icon">📋</span>
        <span>应用历史</span>
      </button>
    </div>

    <!-- ==================== 预设工作流 ==================== -->
    <div v-if="activeTab === 'presets'" class="tab-content">
      <div v-if="loading" class="loading">加载中...</div>
      <div v-else class="workflow-grid">
        <BaseCard
          v-for="wf in presets" :key="wf.id"
          class="workflow-card"
          @click="viewDetail(wf)"
        >
          <div class="wf-header">
            <span class="wf-icon">{{ wf.icon }}</span>
            <span class="wf-category" :style="{ background: categoryMap[wf.category || 'custom']?.color + '20', color: categoryMap[wf.category || 'custom']?.color }">
              {{ categoryMap[wf.category || 'custom']?.label }}
            </span>
          </div>
          <h3 class="wf-name">{{ wf.name }}</h3>
          <p class="wf-desc">{{ wf.description }}</p>
          <div class="wf-meta">
            <span>🎯 {{ wf.scenario }}</span>
          </div>
          <div class="wf-stats">
            <div class="stat">
              <span class="stat-num">{{ getStringList(wf, 'modules').length }}</span>
              <span class="stat-label">模块</span>
            </div>
            <div class="stat">
              <span class="stat-num">{{ getTaskTemplates(wf).length }}</span>
              <span class="stat-label">任务模板</span>
            </div>
            <div class="stat">
              <span class="stat-num">{{ getStringList(wf, 'doc_templates').length }}</span>
              <span class="stat-label">文档模板</span>
            </div>
            <div class="stat">
              <span class="stat-num">{{ wf.use_count }}</span>
              <span class="stat-label">已应用</span>
            </div>
          </div>
          <button class="apply-btn" @click.stop="viewDetail(wf)">查看详情</button>
        </BaseCard>
      </div>
    </div>

    <!-- ==================== 应用历史 ==================== -->
    <div v-if="activeTab === 'history'" class="tab-content">
      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="applications.length === 0" class="empty-state">
        <div class="empty-icon">📋</div>
        <p>还没有应用记录，去预设工作流看看吧</p>
      </div>
      <div v-else class="history-list">
        <BaseCard v-for="app in applications" :key="app.id" class="history-item">
          <div class="history-header">
            <span class="history-workflow">{{ (app.params as Record<string, unknown>).name || '工作流应用' }}</span>
            <span class="history-date">{{ app.applied_at?.slice(0, 16) }}</span>
          </div>
          <p class="history-summary">{{ app.result_summary }}</p>
          <span class="history-status" :class="app.status">{{ app.status === 'completed' ? '已完成' : app.status }}</span>
        </BaseCard>
      </div>
    </div>

    <!-- ==================== 详情弹窗 ==================== -->
    <div v-if="selectedWorkflow" class="modal-overlay" @click="closeDetail">
      <BaseCard class="modal-card" @click.stop>
        <div class="modal-header">
          <div class="modal-title-row">
            <span class="modal-icon">{{ selectedWorkflow.icon }}</span>
            <h2 class="modal-title">{{ selectedWorkflow.name }}</h2>
          </div>
          <button class="modal-close" @click="closeDetail">✕</button>
        </div>

        <p class="modal-desc">{{ selectedWorkflow.description }}</p>
        <p class="modal-scenario">🎯 适用场景: {{ selectedWorkflow.scenario }}</p>

        <div class="modal-sections">
          <div class="modal-section">
            <h4 class="section-title">📦 模块组合</h4>
            <div class="tag-list">
              <span v-for="m in getStringList(selectedWorkflow, 'modules')" :key="m" class="module-tag">{{ m }}</span>
            </div>
          </div>

          <div class="modal-section">
            <h4 class="section-title">🏷️ 标签体系</h4>
            <div class="tag-system">
              <div v-for="(tags, category) in getTagSystem(selectedWorkflow)" :key="category" class="tag-group">
                <span class="tag-category">{{ category }}:</span>
                <span v-for="t in tags" :key="t" class="tag-item">{{ t }}</span>
              </div>
            </div>
          </div>

          <div class="modal-section">
            <h4 class="section-title">📝 任务模板</h4>
            <div v-for="(tpl, i) in getTaskTemplates(selectedWorkflow)" :key="i" class="task-tpl">
              <span class="tpl-name">{{ tpl.name }}</span>
              <span class="tpl-steps">{{ tpl.steps?.join(' → ') }}</span>
            </div>
          </div>

          <div class="modal-section">
            <h4 class="section-title">📄 文档模板</h4>
            <div class="tag-list">
              <span v-for="t in getStringList(selectedWorkflow, 'doc_templates')" :key="t" class="doc-tag">{{ t }}</span>
            </div>
          </div>

          <div class="modal-section">
            <h4 class="section-title">📋 SOP流程</h4>
            <div class="tag-list">
              <span v-for="s in getStringList(selectedWorkflow, 'sops')" :key="s" class="sop-tag">{{ s }}</span>
            </div>
          </div>

          <div class="modal-section">
            <h4 class="section-title">⚡ 自动化规则</h4>
            <div v-for="(rule, i) in getRules(selectedWorkflow)" :key="i" class="rule-item">
              <span class="rule-trigger">{{ rule.trigger }}</span>
              <span class="rule-arrow">→</span>
              <span class="rule-action">{{ rule.action }}</span>
            </div>
          </div>
        </div>

        <!-- 应用参数 -->
        <div class="apply-section">
          <h4 class="section-title">⚙️ 应用参数（可选）</h4>
          <textarea
            v-model="applyParams"
            class="params-textarea"
            placeholder="每行一个参数，格式: 参数名=值&#10;例如:&#10;name=我的项目&#10;category=数学"
            rows="3"
          />
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" @click="closeDetail">取消</button>
          <button class="btn-primary apply-action" :disabled="applying" @click="doApply">
            {{ applying ? '应用中...' : '🚀 一键应用' }}
          </button>
        </div>
      </BaseCard>
    </div>
  </div>
</template>

<style scoped lang="scss">
.workflow-page { padding: var(--space-4); display: flex; flex-direction: column; gap: var(--space-4); }
.page-title { font-size: var(--text-2xl); font-weight: 800; color: var(--text-hi); font-family: var(--font-cute); }
.page-sub { color: var(--text-mid); font-size: var(--text-sm); margin-top: 4px; }

.tab-nav { display: flex; gap: var(--space-2); background: var(--bg-panel); padding: 6px; border-radius: var(--radius-lg); border: 1px solid var(--line); width: fit-content; }
.tab-btn { display: flex; align-items: center; gap: 6px; padding: 8px 16px; border-radius: var(--radius-md); border: none; background: transparent; color: var(--text-mid); font-size: var(--text-sm); font-weight: 600; cursor: pointer; transition: all 0.2s; &:hover { background: var(--bg-hover); } &.active { background: var(--primary); color: white; box-shadow: 0 2px 8px var(--primary-shadow); } }
.tab-icon { font-size: 16px; }

.loading, .empty-state { text-align: center; padding: var(--space-8); color: var(--text-mid); }
.empty-icon { font-size: 48px; margin-bottom: 12px; }

/* 工作流卡片 */
.workflow-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: var(--space-4); }
.workflow-card { padding: var(--space-4); cursor: pointer; transition: all 0.2s; &:hover { transform: translateY(-4px); box-shadow: 0 8px 24px rgba(0,0,0,0.12); } }
.wf-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.wf-icon { font-size: 36px; }
.wf-category { padding: 4px 10px; border-radius: var(--radius-pill); font-size: var(--text-xs); font-weight: 600; }
.wf-name { font-size: var(--text-lg); font-weight: 700; color: var(--text-hi); margin-bottom: 6px; }
.wf-desc { font-size: var(--text-sm); color: var(--text-mid); margin-bottom: 10px; line-height: 1.5; min-height: 40px; }
.wf-meta { font-size: var(--text-xs); color: var(--text-mid); margin-bottom: 12px; }
.wf-stats { display: flex; gap: 12px; margin-bottom: 14px; padding: 10px 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.stat { flex: 1; text-align: center; }
.stat-num { display: block; font-size: var(--text-lg); font-weight: 700; color: var(--primary); }
.stat-label { font-size: var(--text-xs); color: var(--text-mid); }
.apply-btn { width: 100%; padding: 10px; border-radius: var(--radius-md); border: none; background: var(--primary); color: white; font-size: var(--text-sm); font-weight: 600; cursor: pointer; &:hover { opacity: 0.9; } }

/* 历史列表 */
.history-list { display: flex; flex-direction: column; gap: var(--space-2); }
.history-item { padding: var(--space-3); }
.history-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.history-workflow { font-size: var(--text-base); font-weight: 600; color: var(--text-hi); }
.history-date { font-size: var(--text-xs); color: var(--text-mid); }
.history-summary { font-size: var(--text-sm); color: var(--text-mid); margin-bottom: 8px; }
.history-status { padding: 2px 8px; border-radius: var(--radius-pill); font-size: var(--text-xs); background: var(--success, #52c41a); color: white; }

/* 弹窗 */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; padding: var(--space-4); }
.modal-card { width: 100%; max-width: 640px; max-height: 85vh; overflow-y: auto; padding: var(--space-5); }
.modal-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.modal-title-row { display: flex; align-items: center; gap: 12px; }
.modal-icon { font-size: 32px; }
.modal-title { font-size: var(--text-xl); font-weight: 700; color: var(--text-hi); }
.modal-close { width: 32px; height: 32px; border-radius: 50%; border: none; background: var(--bg-hover); color: var(--text-mid); font-size: 16px; cursor: pointer; &:hover { background: var(--danger, #ff4d4f); color: white; } }
.modal-desc { font-size: var(--text-sm); color: var(--text-mid); margin-bottom: 6px; }
.modal-scenario { font-size: var(--text-sm); color: var(--primary); margin-bottom: var(--space-4); }

.modal-sections { display: flex; flex-direction: column; gap: var(--space-3); margin-bottom: var(--space-4); }
.modal-section { padding: var(--space-3); background: var(--bg-hover); border-radius: var(--radius-md); }
.section-title { font-size: var(--text-sm); font-weight: 600; color: var(--text-hi); margin-bottom: 8px; }
.tag-list { display: flex; flex-wrap: wrap; gap: 6px; }
.module-tag, .doc-tag, .sop-tag { padding: 3px 10px; border-radius: var(--radius-pill); background: var(--primary-soft); color: var(--primary); font-size: var(--text-xs); }
.tag-system { display: flex; flex-direction: column; gap: 6px; }
.tag-group { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.tag-category { font-size: var(--text-xs); color: var(--text-mid); font-weight: 600; }
.tag-item { padding: 2px 8px; border-radius: var(--radius-sm); background: var(--bg-panel); color: var(--text-hi); font-size: var(--text-xs); }
.task-tpl { display: flex; gap: 10px; margin-bottom: 6px; font-size: var(--text-xs); }
.tpl-name { font-weight: 600; color: var(--text-hi); min-width: 80px; }
.tpl-steps { color: var(--text-mid); }
.rule-item { display: flex; align-items: center; gap: 8px; font-size: var(--text-xs); margin-bottom: 4px; }
.rule-trigger { color: var(--text-hi); }
.rule-arrow { color: var(--primary); font-weight: 700; }
.rule-action { color: var(--text-mid); }

.apply-section { margin-bottom: var(--space-4); }
.params-textarea { width: 100%; padding: 10px 12px; border-radius: var(--radius-md); border: 1px solid var(--line); background: var(--bg-input); color: var(--text-hi); font-size: var(--text-sm); resize: vertical; font-family: monospace; }

.modal-actions { display: flex; gap: var(--space-3); justify-content: flex-end; }
.btn-primary { padding: 10px 24px; border-radius: var(--radius-md); border: none; background: var(--primary); color: white; font-size: var(--text-sm); font-weight: 600; cursor: pointer; &:hover { opacity: 0.9; } &:disabled { opacity: 0.5; cursor: not-allowed; } }
.btn-secondary { padding: 10px 24px; border-radius: var(--radius-md); border: 1px solid var(--line); background: var(--bg-panel); color: var(--text-mid); font-size: var(--text-sm); cursor: pointer; }
.apply-action { min-width: 140px; }
</style>
