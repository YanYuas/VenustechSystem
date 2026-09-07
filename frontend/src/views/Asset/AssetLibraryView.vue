<script setup lang="ts">
// ============================================================
// 长期资产库（二期 M10 P0）
// SOP流程 + Prompt模板 + Skill技能 + 项目记忆
// ============================================================
import { ref, onMounted } from 'vue'
import { assetApi } from '@/api'
import { useToast } from '@/composables'
import type { SOP, PromptTemplate, Skill, ProjectMemory } from '@/types'
import BaseCard from '@/components/common/BaseCard.vue'

const toast = useToast()

const activeTab = ref<'sop' | 'prompt' | 'skill' | 'memory'>('sop')
const tabs = [
  { key: 'sop', label: 'SOP流程', icon: '📋' },
  { key: 'prompt', label: 'Prompt模板', icon: '💬' },
  { key: 'skill', label: '技能库', icon: '🎯' },
  { key: 'memory', label: '项目记忆', icon: '🧠' },
] as const

// ==================== SOP 流程 ====================
const sops = ref<SOP[]>([])
const sopsLoading = ref(false)
const showSOPForm = ref(false)
const editingSOP = ref<SOP | null>(null)
const sopForm = ref({ name: '', category: '', description: '', steps: '', checklist: '', tags: '' })
const selectedSOP = ref<SOP | null>(null)
const sopVersions = ref<{ version: number; change_note: string | null; created_at: string }[]>([])

async function fetchSOPs() {
  sopsLoading.value = true
  try {
    const data = await assetApi.listSOPs({ page: 1, page_size: 50 })
    sops.value = data.list
  } catch (e) { toast.error('加载SOP失败') }
  finally { sopsLoading.value = false }
}

function openNewSOP() {
  editingSOP.value = null
  sopForm.value = { name: '', category: '', description: '', steps: '', checklist: '', tags: '' }
  showSOPForm.value = true
}

function openEditSOP(sop: SOP) {
  editingSOP.value = sop
  sopForm.value = {
    name: sop.name, category: sop.category || '', description: sop.description || '',
    steps: (sop.steps || []).join('\n'), checklist: (sop.checklist || []).join('\n'),
    tags: (sop.tags || []).join(','),
  }
  showSOPForm.value = true
}

async function saveSOP() {
  if (!sopForm.value.name) { toast.warning('请填写名称'); return }
  try {
    const payload = {
      name: sopForm.value.name,
      category: sopForm.value.category || undefined,
      description: sopForm.value.description || undefined,
      steps: sopForm.value.steps.split('\n').filter(Boolean),
      checklist: sopForm.value.checklist.split('\n').filter(Boolean),
      tags: sopForm.value.tags.split(/[,，]/).filter(Boolean),
    }
    if (editingSOP.value) {
      await assetApi.updateSOP(editingSOP.value.id, payload, '更新SOP')
      toast.success('SOP已更新（版本已保存）')
    } else {
      await assetApi.createSOP(payload)
      toast.success('SOP已创建')
    }
    showSOPForm.value = false
    fetchSOPs()
    if (selectedSOP.value) { await viewSOP(selectedSOP.value.id) }
  } catch (e) { toast.error('保存失败') }
}

async function viewSOP(id: string) {
  try {
    selectedSOP.value = await assetApi.getSOP(id)
    const ver = await assetApi.listSOPVersions(id)
    sopVersions.value = ver.versions
  } catch (e) { toast.error('加载详情失败') }
}

async function deleteSOP(id: string) {
  try { await assetApi.deleteSOP(id); toast.success('已删除'); fetchSOPs(); if (selectedSOP.value?.id === id) selectedSOP.value = null }
  catch (e) { toast.error('删除失败') }
}

async function useSOP(id: string) {
  try { await assetApi.useSOP(id); toast.success('已记录使用'); fetchSOPs() }
  catch (e) { toast.error('操作失败') }
}

// ==================== Prompt 模板 ====================
const prompts = ref<PromptTemplate[]>([])
const promptsLoading = ref(false)
const showPromptForm = ref(false)
const editingPrompt = ref<PromptTemplate | null>(null)
const promptForm = ref({ name: '', category: '', description: '', role_setting: '', task_description: '', constraints: '', output_format: '', variables: '' })
const applyingPrompt = ref<PromptTemplate | null>(null)
const applyVariables = ref('')
const applyResult = ref('')

async function fetchPrompts() {
  promptsLoading.value = true
  try {
    const data = await assetApi.listPrompts({ page: 1, page_size: 50 })
    prompts.value = data.list
  } catch (e) { toast.error('加载Prompt失败') }
  finally { promptsLoading.value = false }
}

function openNewPrompt() {
  editingPrompt.value = null
  promptForm.value = { name: '', category: '', description: '', role_setting: '', task_description: '', constraints: '', output_format: '', variables: '' }
  showPromptForm.value = true
}

function openEditPrompt(p: PromptTemplate) {
  editingPrompt.value = p
  promptForm.value = {
    name: p.name, category: p.category || '', description: p.description || '',
    role_setting: p.role_setting || '', task_description: p.task_description || '',
    constraints: p.constraints || '', output_format: p.output_format || '',
    variables: (p.variables || []).join(','),
  }
  showPromptForm.value = true
}

async function savePrompt() {
  if (!promptForm.value.name) { toast.warning('请填写名称'); return }
  try {
    const payload = {
      ...promptForm.value,
      variables: promptForm.value.variables.split(/[,，]/).filter(Boolean),
    }
    if (editingPrompt.value) {
      await assetApi.updatePrompt(editingPrompt.value.id, payload)
      toast.success('Prompt已更新')
    } else {
      await assetApi.createPrompt(payload)
      toast.success('Prompt已创建')
    }
    showPromptForm.value = false
    fetchPrompts()
  } catch (e) { toast.error('保存失败') }
}

function openApply(p: PromptTemplate) {
  applyingPrompt.value = p
  applyVariables.value = ''
  applyResult.value = ''
}

async function doApply() {
  if (!applyingPrompt.value) return
  try {
    const vars: Record<string, string> = {}
    applyVariables.value.split('\n').forEach(line => {
      const [k, ...v] = line.split('=')
      if (k && v.length) vars[k.trim()] = v.join('=').trim()
    })
    const result = await assetApi.applyPrompt(applyingPrompt.value.id, vars)
    applyResult.value = result.rendered
    toast.success(`变量替换完成: ${result.variables_used.length}个`)
    fetchPrompts()
  } catch (e) { toast.error('应用失败') }
}

function copyResult() {
  navigator.clipboard.writeText(applyResult.value)
  toast.success('已复制到剪贴板')
}

function formatVar(name: string) {
  return '{{' + name + '}}'
}

async function deletePrompt(id: string) {
  try { await assetApi.deletePrompt(id); toast.success('已删除'); fetchPrompts() }
  catch (e) { toast.error('删除失败') }
}

// ==================== Skill 技能库 ====================
const skills = ref<Skill[]>([])
const skillsLoading = ref(false)
const showSkillForm = ref(false)
const skillForm = ref({ name: '', category: '', description: '', methodology: '', proficiency: 'beginner', tags: '' })

const proficiencyMap: Record<string, { label: string; color: string }> = {
  beginner: { label: '入门', color: '#909399' },
  intermediate: { label: '熟练', color: '#409EFF' },
  expert: { label: '专家', color: '#67C23A' },
}

async function fetchSkills() {
  skillsLoading.value = true
  try {
    const data = await assetApi.listSkills({ page: 1, page_size: 50 })
    skills.value = data.list
  } catch (e) { toast.error('加载技能失败') }
  finally { skillsLoading.value = false }
}

async function saveSkill() {
  if (!skillForm.value.name) { toast.warning('请填写名称'); return }
  try {
    const payload = {
      ...skillForm.value,
      proficiency: skillForm.value.proficiency as 'beginner' | 'intermediate' | 'advanced' | 'expert',
      tags: skillForm.value.tags.split(/[,，]/).filter(Boolean),
    }
    await assetApi.createSkill(payload)
    toast.success('技能已创建')
    showSkillForm.value = false
    skillForm.value = { name: '', category: '', description: '', methodology: '', proficiency: 'beginner', tags: '' }
    fetchSkills()
  } catch (e) { toast.error('创建失败') }
}

async function deleteSkill(id: string) {
  try { await assetApi.deleteSkill(id); toast.success('已删除'); fetchSkills() }
  catch (e) { toast.error('删除失败') }
}

// ==================== 项目记忆 ====================
const memories = ref<ProjectMemory[]>([])
const memoriesLoading = ref(false)
const showMemoryForm = ref(false)
const editingMemory = ref<ProjectMemory | null>(null)
const memoryForm = ref({ name: '', summary: '', successes: '', failures: '', tags: '' })

async function fetchMemories() {
  memoriesLoading.value = true
  try {
    const data = await assetApi.listMemories({ page: 1, page_size: 50 })
    memories.value = data.list
  } catch (e) { toast.error('加载记忆失败') }
  finally { memoriesLoading.value = false }
}

function openNewMemory() {
  editingMemory.value = null
  memoryForm.value = { name: '', summary: '', successes: '', failures: '', tags: '' }
  showMemoryForm.value = true
}

function openEditMemory(m: ProjectMemory) {
  editingMemory.value = m
  memoryForm.value = {
    name: m.name, summary: m.summary || '', successes: m.successes || '',
    failures: m.failures || '', tags: (m.tags || []).join(','),
  }
  showMemoryForm.value = true
}

async function saveMemory() {
  if (!memoryForm.value.name) { toast.warning('请填写名称'); return }
  try {
    const payload = {
      ...memoryForm.value,
      tags: memoryForm.value.tags.split(/[,，]/).filter(Boolean),
    }
    if (editingMemory.value) {
      await assetApi.updateMemory(editingMemory.value.id, payload)
      toast.success('记忆已更新')
    } else {
      await assetApi.createMemory(payload)
      toast.success('记忆已创建')
    }
    showMemoryForm.value = false
    fetchMemories()
  } catch (e) { toast.error('保存失败') }
}

async function deleteMemory(id: string) {
  try { await assetApi.deleteMemory(id); toast.success('已删除'); fetchMemories() }
  catch (e) { toast.error('删除失败') }
}

function switchTab(tab: 'sop' | 'prompt' | 'skill' | 'memory') {
  activeTab.value = tab
  if (tab === 'sop') fetchSOPs()
  if (tab === 'prompt') fetchPrompts()
  if (tab === 'skill') fetchSkills()
  if (tab === 'memory') fetchMemories()
}

onMounted(() => fetchSOPs())
</script>

<template>
  <div class="asset-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">长期资产库</h1>
        <p class="page-sub">SOP流程 · Prompt模板 · 技能沉淀 · 项目记忆</p>
      </div>
    </div>

    <!-- Tab导航 -->
    <div class="tab-nav">
      <button v-for="tab in tabs" :key="tab.key" class="tab-btn" :class="{ active: activeTab === tab.key }" @click="switchTab(tab.key)">
        <span class="tab-icon">{{ tab.icon }}</span>
        <span>{{ tab.label }}</span>
      </button>
    </div>

    <!-- ==================== SOP 流程 ==================== -->
    <div v-if="activeTab === 'sop'" class="tab-content">
      <div class="content-toolbar">
        <span class="count-text">共 {{ sops.length }} 个SOP</span>
        <button class="btn-primary" @click="openNewSOP">+ 新建SOP</button>
      </div>

      <!-- 编辑器 -->
      <BaseCard v-if="showSOPForm" class="editor-card">
        <h3 class="section-title">{{ editingSOP ? '编辑SOP' : '新建SOP' }}</h3>
        <div class="form-row">
          <input v-model="sopForm.name" class="form-input" placeholder="SOP名称" />
          <input v-model="sopForm.category" class="form-input" placeholder="分类" />
        </div>
        <textarea v-model="sopForm.description" class="form-textarea" placeholder="描述" rows="2" />
        <label class="form-label">步骤（每行一步）</label>
        <textarea v-model="sopForm.steps" class="form-textarea" placeholder="第一步&#10;第二步&#10;..." rows="4" />
        <label class="form-label">检查清单（每行一项）</label>
        <textarea v-model="sopForm.checklist" class="form-textarea" placeholder="检查项1&#10;检查项2&#10;..." rows="3" />
        <input v-model="sopForm.tags" class="form-input" placeholder="标签（逗号分隔）" />
        <div class="form-actions">
          <button class="btn-primary" @click="saveSOP">保存</button>
          <button class="btn-secondary" @click="showSOPForm = false">取消</button>
        </div>
      </BaseCard>

      <div class="sop-layout">
        <!-- 列表 -->
        <div class="sop-list">
          <div v-if="sopsLoading" class="loading">加载中...</div>
          <div v-else-if="sops.length === 0 && !showSOPForm" class="empty-state">
            <div class="empty-icon">📋</div>
            <p>还没有SOP，创建第一个标准流程吧</p>
          </div>
          <BaseCard
            v-for="sop in sops" :key="sop.id"
            class="sop-item"
            :class="{ active: selectedSOP?.id === sop.id }"
            @click="viewSOP(sop.id)"
          >
            <div class="sop-item-header">
              <h3 class="sop-name">{{ sop.name }}</h3>
              <span class="sop-version">v{{ sop.version }}</span>
            </div>
            <p v-if="sop.description" class="sop-desc">{{ sop.description }}</p>
            <div class="sop-meta">
              <span v-if="sop.category" class="tag">{{ sop.category }}</span>
              <span>{{ (sop.steps || []).length }}步</span>
              <span>使用{{ sop.use_count }}次</span>
            </div>
            <div class="sop-actions">
              <button class="btn-sm btn-primary" @click.stop="useSOP(sop.id)">使用</button>
              <button class="btn-sm" @click.stop="openEditSOP(sop)">编辑</button>
              <button class="btn-sm btn-danger" @click.stop="deleteSOP(sop.id)">删除</button>
            </div>
          </BaseCard>
        </div>

        <!-- 详情 -->
        <BaseCard v-if="selectedSOP" class="sop-detail">
          <div class="detail-header">
            <h3 class="detail-title">{{ selectedSOP.name }}</h3>
            <span class="sop-version">v{{ selectedSOP.version }}</span>
          </div>
          <p v-if="selectedSOP.description" class="detail-desc">{{ selectedSOP.description }}</p>

          <h4 class="detail-section">执行步骤</h4>
          <ol class="step-list">
            <li v-for="(step, i) in selectedSOP.steps" :key="i" class="step-item">{{ step }}</li>
          </ol>

          <h4 class="detail-section">检查清单</h4>
          <div class="checklist">
            <label v-for="(item, i) in selectedSOP.checklist" :key="i" class="check-item">
              <input type="checkbox" />
              <span>{{ item }}</span>
            </label>
          </div>

          <h4 class="detail-section">版本历史</h4>
          <div v-if="sopVersions.length === 0" class="empty-mini">暂无历史版本</div>
          <div v-else class="version-list">
            <div v-for="ver in sopVersions" :key="ver.version + ver.created_at" class="version-item">
              <span class="version-tag">v{{ ver.version }}</span>
              <span class="version-note">{{ ver.change_note || '无说明' }}</span>
              <span class="version-date">{{ ver.created_at?.slice(0, 10) }}</span>
            </div>
          </div>
        </BaseCard>
      </div>
    </div>

    <!-- ==================== Prompt 模板 ==================== -->
    <div v-if="activeTab === 'prompt'" class="tab-content">
      <div class="content-toolbar">
        <span class="count-text">共 {{ prompts.length }} 个模板</span>
        <button class="btn-primary" @click="openNewPrompt">+ 新建模板</button>
      </div>

      <!-- 编辑器 -->
      <BaseCard v-if="showPromptForm" class="editor-card">
        <h3 class="section-title">{{ editingPrompt ? '编辑模板' : '新建模板' }}</h3>
        <div class="form-row">
          <input v-model="promptForm.name" class="form-input" placeholder="模板名称" />
          <input v-model="promptForm.category" class="form-input" placeholder="分类" />
        </div>
        <textarea v-model="promptForm.description" class="form-textarea" placeholder="描述" rows="2" />
        <label class="form-label">角色设定</label>
        <textarea v-model="promptForm.role_setting" class="form-textarea" rows="2" />
        <label class="form-label">任务描述（可用变量占位符）</label>
        <textarea v-model="promptForm.task_description" class="form-textarea" rows="3" />
        <label class="form-label">约束条件</label>
        <textarea v-model="promptForm.constraints" class="form-textarea" rows="2" />
        <label class="form-label">输出格式</label>
        <textarea v-model="promptForm.output_format" class="form-textarea" rows="2" />
        <input v-model="promptForm.variables" class="form-input" placeholder="变量名（逗号分隔）" />
        <div class="form-actions">
          <button class="btn-primary" @click="savePrompt">保存</button>
          <button class="btn-secondary" @click="showPromptForm = false">取消</button>
        </div>
      </BaseCard>

      <!-- 应用弹窗 -->
      <BaseCard v-if="applyingPrompt" class="apply-card">
        <h3 class="section-title">应用模板: {{ applyingPrompt.name }}</h3>
        <p class="apply-hint">输入变量（格式：变量名=值，每行一个）</p>
        <textarea v-model="applyVariables" class="form-textarea" placeholder="name=小明&#10;topic=数学" rows="3" />
        <div class="form-actions">
          <button class="btn-primary" @click="doApply">生成</button>
          <button class="btn-secondary" @click="applyingPrompt = null">关闭</button>
        </div>
        <div v-if="applyResult" class="apply-result">
          <div class="result-header">
            <span>生成结果</span>
            <button class="btn-sm" @click="copyResult">复制</button>
          </div>
          <pre class="result-content">{{ applyResult }}</pre>
        </div>
      </BaseCard>

      <div v-if="promptsLoading" class="loading">加载中...</div>
      <div v-else-if="prompts.length === 0 && !showPromptForm" class="empty-state">
        <div class="empty-icon">💬</div>
        <p>还没有Prompt模板</p>
      </div>
      <div v-else class="prompt-grid">
        <BaseCard v-for="p in prompts" :key="p.id" class="prompt-card">
          <div class="prompt-header">
            <h3 class="prompt-name">{{ p.name }}</h3>
            <span v-if="p.rating" class="prompt-rating">⭐ {{ p.rating }}</span>
          </div>
          <p v-if="p.description" class="prompt-desc">{{ p.description }}</p>
          <div v-if="p.variables?.length" class="prompt-vars">
            <span v-for="v in p.variables" :key="v" class="var-tag">{{ formatVar(v) }}</span>
          </div>
          <div class="prompt-meta">
            <span v-if="p.category" class="tag">{{ p.category }}</span>
            <span>使用{{ p.use_count }}次</span>
          </div>
          <div class="prompt-actions">
            <button class="btn-sm btn-primary" @click="openApply(p)">应用</button>
            <button class="btn-sm" @click="openEditPrompt(p)">编辑</button>
            <button class="btn-sm btn-danger" @click="deletePrompt(p.id)">删除</button>
          </div>
        </BaseCard>
      </div>
    </div>

    <!-- ==================== Skill 技能库 ==================== -->
    <div v-if="activeTab === 'skill'" class="tab-content">
      <div class="content-toolbar">
        <span class="count-text">共 {{ skills.length }} 项技能</span>
        <button class="btn-primary" @click="showSkillForm = !showSkillForm">{{ showSkillForm ? '取消' : '+ 新建技能' }}</button>
      </div>

      <BaseCard v-if="showSkillForm" class="editor-card">
        <div class="form-row">
          <input v-model="skillForm.name" class="form-input" placeholder="技能名称" />
          <input v-model="skillForm.category" class="form-input" placeholder="分类" />
          <select v-model="skillForm.proficiency" class="form-select">
            <option value="beginner">入门</option>
            <option value="intermediate">熟练</option>
            <option value="expert">专家</option>
          </select>
        </div>
        <textarea v-model="skillForm.description" class="form-textarea" placeholder="描述" rows="2" />
        <textarea v-model="skillForm.methodology" class="form-textarea" placeholder="方法论" rows="3" />
        <input v-model="skillForm.tags" class="form-input" placeholder="标签（逗号分隔）" />
        <button class="btn-primary" @click="saveSkill">创建</button>
      </BaseCard>

      <div v-if="skillsLoading" class="loading">加载中...</div>
      <div v-else-if="skills.length === 0 && !showSkillForm" class="empty-state">
        <div class="empty-icon">🎯</div>
        <p>还没有技能记录，开始沉淀你的能力吧</p>
      </div>
      <div v-else class="skill-grid">
        <BaseCard v-for="s in skills" :key="s.id" class="skill-card">
          <div class="skill-header">
            <h3 class="skill-name">{{ s.name }}</h3>
            <span class="skill-level" :style="{ background: proficiencyMap[s.proficiency]?.color + '20', color: proficiencyMap[s.proficiency]?.color }">
              {{ proficiencyMap[s.proficiency]?.label }}
            </span>
          </div>
          <p v-if="s.description" class="skill-desc">{{ s.description }}</p>
          <div v-if="s.methodology" class="skill-method">
            <span class="method-label">方法论:</span>
            <p>{{ s.methodology }}</p>
          </div>
          <div class="skill-tags">
            <span v-for="tag in s.tags" :key="tag" class="tag">{{ tag }}</span>
          </div>
          <div class="skill-footer">
            <span>使用{{ s.use_count }}次</span>
            <button class="btn-sm btn-danger" @click="deleteSkill(s.id)">删除</button>
          </div>
        </BaseCard>
      </div>
    </div>

    <!-- ==================== 项目记忆 ==================== -->
    <div v-if="activeTab === 'memory'" class="tab-content">
      <div class="content-toolbar">
        <span class="count-text">共 {{ memories.length }} 条记忆</span>
        <button class="btn-primary" @click="openNewMemory">+ 新建记忆</button>
      </div>

      <BaseCard v-if="showMemoryForm" class="editor-card">
        <h3 class="section-title">{{ editingMemory ? '编辑记忆' : '新建记忆' }}</h3>
        <input v-model="memoryForm.name" class="form-input" placeholder="项目/事件名称" />
        <label class="form-label">总结</label>
        <textarea v-model="memoryForm.summary" class="form-textarea" rows="3" />
        <label class="form-label">成功经验</label>
        <textarea v-model="memoryForm.successes" class="form-textarea" rows="2" />
        <label class="form-label">失败教训</label>
        <textarea v-model="memoryForm.failures" class="form-textarea" rows="2" />
        <input v-model="memoryForm.tags" class="form-input" placeholder="标签（逗号分隔）" />
        <div class="form-actions">
          <button class="btn-primary" @click="saveMemory">保存</button>
          <button class="btn-secondary" @click="showMemoryForm = false">取消</button>
        </div>
      </BaseCard>

      <div v-if="memoriesLoading" class="loading">加载中...</div>
      <div v-else-if="memories.length === 0 && !showMemoryForm" class="empty-state">
        <div class="empty-icon">🧠</div>
        <p>还没有项目记忆，记录你的经验教训吧</p>
      </div>
      <div v-else class="memory-list">
        <BaseCard v-for="m in memories" :key="m.id" class="memory-card" @click="openEditMemory(m)">
          <div class="memory-header">
            <h3 class="memory-name">{{ m.name }}</h3>
            <span class="memory-date">{{ m.created_at?.slice(0, 10) }}</span>
          </div>
          <p v-if="m.summary" class="memory-summary">{{ m.summary }}</p>
          <div v-if="m.successes" class="memory-section success">
            <span class="section-icon">✅</span>
            <p>{{ m.successes }}</p>
          </div>
          <div v-if="m.failures" class="memory-section failure">
            <span class="section-icon">⚠️</span>
            <p>{{ m.failures }}</p>
          </div>
          <div class="memory-tags">
            <span v-for="tag in m.tags" :key="tag" class="tag">{{ tag }}</span>
          </div>
          <button class="btn-sm btn-danger" @click.stop="deleteMemory(m.id)">删除</button>
        </BaseCard>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.asset-page { padding: var(--space-4); display: flex; flex-direction: column; gap: var(--space-4); }
.page-title { font-size: var(--text-2xl); font-weight: 800; color: var(--text-hi); font-family: var(--font-cute); }
.page-sub { color: var(--text-mid); font-size: var(--text-sm); margin-top: 4px; }

.tab-nav { display: flex; gap: var(--space-2); background: var(--bg-panel); padding: 6px; border-radius: var(--radius-lg); border: 1px solid var(--line); width: fit-content; flex-wrap: wrap; }
.tab-btn { display: flex; align-items: center; gap: 6px; padding: 8px 16px; border-radius: var(--radius-md); border: none; background: transparent; color: var(--text-mid); font-size: var(--text-sm); font-weight: 600; cursor: pointer; transition: all 0.2s; &:hover { background: var(--bg-hover); } &.active { background: var(--primary); color: white; box-shadow: 0 2px 8px var(--primary-shadow); } }
.tab-icon { font-size: 16px; }

.content-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-3); }
.count-text { color: var(--text-mid); font-size: var(--text-sm); }
.btn-primary { padding: 8px 18px; border-radius: var(--radius-md); border: none; background: var(--primary); color: white; font-size: var(--text-sm); font-weight: 600; cursor: pointer; &:hover { opacity: 0.9; } }
.btn-secondary { padding: 8px 18px; border-radius: var(--radius-md); border: 1px solid var(--line); background: var(--bg-panel); color: var(--text-mid); font-size: var(--text-sm); cursor: pointer; }
.btn-sm { padding: 4px 10px; border-radius: var(--radius-sm); border: 1px solid var(--line); background: var(--bg-panel); color: var(--text-mid); font-size: var(--text-xs); cursor: pointer; &.btn-primary { background: var(--primary); color: white; border-color: var(--primary); } &.btn-danger { background: var(--danger, #ff4d4f); color: white; border-color: var(--danger, #ff4d4f); } }

.editor-card, .apply-card { padding: var(--space-4); margin-bottom: var(--space-4); }
.section-title { font-size: var(--text-base); font-weight: 600; color: var(--text-hi); margin-bottom: var(--space-3); }
.form-row { display: flex; gap: var(--space-3); margin-bottom: var(--space-3); }
.form-input, .form-select { flex: 1; padding: 8px 12px; border-radius: var(--radius-md); border: 1px solid var(--line); background: var(--bg-input); color: var(--text-hi); font-size: var(--text-sm); }
.form-textarea { width: 100%; padding: 8px 12px; border-radius: var(--radius-md); border: 1px solid var(--line); background: var(--bg-input); color: var(--text-hi); font-size: var(--text-sm); resize: vertical; margin-bottom: var(--space-3); }
.form-label { font-size: var(--text-sm); color: var(--text-mid); margin-bottom: 4px; display: block; font-weight: 600; }
.form-actions { display: flex; gap: var(--space-3); margin-top: var(--space-3); }

.loading, .empty-state { text-align: center; padding: var(--space-8); color: var(--text-mid); }
.empty-icon { font-size: 48px; margin-bottom: 12px; }
.empty-mini { text-align: center; padding: var(--space-3); color: var(--text-mid); font-size: var(--text-sm); }
.tag { display: inline-block; padding: 2px 8px; border-radius: var(--radius-pill); background: var(--primary-soft); color: var(--primary); font-size: var(--text-xs); margin-right: 4px; }

/* ========== SOP ========== */
.sop-layout { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
@media (max-width: 900px) { .sop-layout { grid-template-columns: 1fr; } }
.sop-list { display: flex; flex-direction: column; gap: var(--space-2); }
.sop-item { padding: var(--space-3); cursor: pointer; transition: all 0.2s; &:hover { transform: translateX(4px); } &.active { border-color: var(--primary); box-shadow: 0 0 0 2px var(--primary-soft); } }
.sop-item-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.sop-name { font-size: var(--text-base); font-weight: 600; color: var(--text-hi); }
.sop-version { padding: 2px 8px; border-radius: var(--radius-pill); background: var(--bg-hover); color: var(--text-mid); font-size: var(--text-xs); font-weight: 600; }
.sop-desc { font-size: var(--text-sm); color: var(--text-mid); margin-bottom: 8px; }
.sop-meta { display: flex; gap: 10px; font-size: var(--text-xs); color: var(--text-mid); margin-bottom: 8px; align-items: center; }
.sop-actions { display: flex; gap: 6px; }

.sop-detail { padding: var(--space-4); }
.detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.detail-title { font-size: var(--text-lg); font-weight: 700; color: var(--text-hi); }
.detail-desc { font-size: var(--text-sm); color: var(--text-mid); margin-bottom: var(--space-3); }
.detail-section { font-size: var(--text-sm); font-weight: 600; color: var(--text-hi); margin: var(--space-3) 0 8px; }
.step-list { padding-left: 20px; }
.step-item { font-size: var(--text-sm); color: var(--text-hi); margin-bottom: 6px; line-height: 1.5; }
.checklist { display: flex; flex-direction: column; gap: 6px; }
.check-item { display: flex; align-items: center; gap: 8px; font-size: var(--text-sm); color: var(--text-hi); cursor: pointer; }
.version-list { display: flex; flex-direction: column; gap: 6px; }
.version-item { display: flex; align-items: center; gap: 10px; padding: 6px 10px; background: var(--bg-hover); border-radius: var(--radius-sm); font-size: var(--text-xs); }
.version-tag { font-weight: 700; color: var(--primary); }
.version-note { flex: 1; color: var(--text-mid); }
.version-date { color: var(--text-mid); }

/* ========== Prompt ========== */
.prompt-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: var(--space-3); }
.prompt-card { padding: var(--space-4); }
.prompt-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.prompt-name { font-size: var(--text-base); font-weight: 600; color: var(--text-hi); }
.prompt-rating { font-size: var(--text-sm); color: #faad14; }
.prompt-desc { font-size: var(--text-sm); color: var(--text-mid); margin-bottom: 8px; }
.prompt-vars { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
.var-tag { padding: 2px 6px; border-radius: var(--radius-sm); background: var(--bg-hover); color: var(--primary); font-size: var(--text-xs); font-family: monospace; }
.prompt-meta { display: flex; gap: 10px; font-size: var(--text-xs); color: var(--text-mid); margin-bottom: 10px; align-items: center; }
.prompt-actions { display: flex; gap: 6px; }
.apply-hint { font-size: var(--text-sm); color: var(--text-mid); margin-bottom: 8px; }
.apply-result { margin-top: var(--space-3); }
.result-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; font-size: var(--text-sm); font-weight: 600; color: var(--text-hi); }
.result-content { background: var(--bg-hover); padding: var(--space-3); border-radius: var(--radius-md); font-size: var(--text-sm); color: var(--text-hi); white-space: pre-wrap; max-height: 300px; overflow-y: auto; }

/* ========== Skill ========== */
.skill-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: var(--space-3); }
.skill-card { padding: var(--space-4); }
.skill-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.skill-name { font-size: var(--text-base); font-weight: 600; color: var(--text-hi); }
.skill-level { padding: 2px 10px; border-radius: var(--radius-pill); font-size: var(--text-xs); font-weight: 600; }
.skill-desc { font-size: var(--text-sm); color: var(--text-mid); margin-bottom: 8px; }
.skill-method { margin-bottom: 10px; }
.method-label { font-size: var(--text-xs); color: var(--text-mid); font-weight: 600; }
.skill-method p { font-size: var(--text-sm); color: var(--text-hi); margin-top: 2px; }
.skill-tags { margin-bottom: 10px; }
.skill-footer { display: flex; justify-content: space-between; align-items: center; font-size: var(--text-xs); color: var(--text-mid); }

/* ========== Memory ========== */
.memory-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: var(--space-3); }
.memory-card { padding: var(--space-4); cursor: pointer; transition: all 0.2s; &:hover { transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,0.1); } }
.memory-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.memory-name { font-size: var(--text-base); font-weight: 600; color: var(--text-hi); }
.memory-date { font-size: var(--text-xs); color: var(--text-mid); }
.memory-summary { font-size: var(--text-sm); color: var(--text-hi); margin-bottom: 10px; line-height: 1.5; }
.memory-section { display: flex; gap: 8px; margin-bottom: 8px; font-size: var(--text-sm); }
.memory-section p { color: var(--text-hi); line-height: 1.5; }
.memory-section.success .section-icon { color: #52c41a; }
.memory-section.failure .section-icon { color: #faad14; }
.memory-tags { margin-bottom: 10px; }
</style>
