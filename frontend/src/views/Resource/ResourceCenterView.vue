<script setup lang="ts">
// ============================================================
// 资源中心（二期 M7 P0）
// 收集箱 + 模板库 + 领域库
// ============================================================
import { ref, onMounted } from 'vue'
import { resourceApi } from '@/api'
import { useToast } from '@/composables'
import type { InboxItem, Template, Domain } from '@/types'
import BaseCard from '@/components/common/BaseCard.vue'

const toast = useToast()

// Tab切换
const activeTab = ref<'inbox' | 'templates' | 'domains'>('inbox')
const tabs = [
  { key: 'inbox', label: '收集箱', icon: '📥' },
  { key: 'templates', label: '模板库', icon: '📋' },
  { key: 'domains', label: '领域库', icon: '📚' },
] as const

// ==================== 收集箱 ====================
const inboxItems = ref<InboxItem[]>([])
const inboxLoading = ref(false)
const inboxFilter = ref<'all' | 'pending' | 'archived'>('all')
const showInboxForm = ref(false)
const inboxForm = ref<{ content_type: 'text'|'link'|'image'|'file'; content: string; title: string; tags: string }>({ content_type: 'text', content: '', title: '', tags: '' })

async function fetchInbox() {
  inboxLoading.value = true
  try {
    const status = inboxFilter.value === 'all' ? undefined : inboxFilter.value
    const data = await resourceApi.listInbox({ status, page: 1, page_size: 50 })
    inboxItems.value = data.list
  } catch (e) {
    toast.show('加载收集箱失败', 'error')
  } finally {
    inboxLoading.value = false
  }
}

async function createInboxItem() {
  if (!inboxForm.value.content && !inboxForm.value.title) {
    toast.show('请输入内容或标题', 'warning')
    return
  }
  try {
    const tags = inboxForm.value.tags.split(',').map(t => t.trim()).filter(Boolean)
    await resourceApi.createInboxItem({
      content_type: inboxForm.value.content_type,
      content: inboxForm.value.content,
      title: inboxForm.value.title,
      tags,
    })
    toast.show('已添加到收集箱', 'success')
    inboxForm.value = { content_type: 'text', content: '', title: '', tags: '' }
    showInboxForm.value = false
    fetchInbox()
  } catch (e) {
    toast.show('添加失败', 'error')
  }
}

async function processItem(item: InboxItem, action: 'archive' | 'delete' | 'convert_task' | 'convert_doc') {
  try {
    await resourceApi.processInboxItem(item.id, action)
    const labels = { archive: '已归档', delete: '已删除', convert_task: '已转为任务', convert_doc: '已转为文档' }
    toast.show(labels[action], 'success')
    fetchInbox()
  } catch (e) {
    toast.show('操作失败', 'error')
  }
}

const contentTypes = [
  { value: 'text', label: '文字' },
  { value: 'link', label: '链接' },
  { value: 'image', label: '图片' },
  { value: 'file', label: '文件' },
]

// ==================== 模板库 ====================
const templates = ref<Template[]>([])
const templatesLoading = ref(false)
const showTemplateForm = ref(false)
const templateForm = ref({ name: '', category: '', content: '', variables: '' })

async function fetchTemplates() {
  templatesLoading.value = true
  try {
    const data = await resourceApi.listTemplates({ page: 1, page_size: 50 })
    templates.value = data.list
  } catch (e) {
    toast.show('加载模板失败', 'error')
  } finally {
    templatesLoading.value = false
  }
}

async function createTemplate() {
  if (!templateForm.value.name || !templateForm.value.content) {
    toast.show('请填写模板名称和内容', 'warning')
    return
  }
  try {
    const variables = templateForm.value.variables.split(',').map(v => v.trim()).filter(Boolean)
    await resourceApi.createTemplate({
      name: templateForm.value.name,
      category: templateForm.value.category || '通用',
      content: templateForm.value.content,
      variables,
    })
    toast.show('模板已创建', 'success')
    templateForm.value = { name: '', category: '', content: '', variables: '' }
    showTemplateForm.value = false
    fetchTemplates()
  } catch (e) {
    toast.show('创建失败', 'error')
  }
}

async function deleteTemplate(id: string) {
  try {
    await resourceApi.deleteTemplate(id)
    toast.show('模板已删除', 'success')
    fetchTemplates()
  } catch (e) {
    toast.show('删除失败', 'error')
  }
}

// ==================== 领域库 ====================
const domains = ref<Domain[]>([])
const domainsLoading = ref(false)
const showDomainForm = ref(false)
const domainForm = ref({ name: '', description: '', icon: '📁', color: '#FFB6C1' })

async function fetchDomains() {
  domainsLoading.value = true
  try {
    domains.value = await resourceApi.listDomains()
  } catch (e) {
    toast.show('加载领域失败', 'error')
  } finally {
    domainsLoading.value = false
  }
}

async function createDomain() {
  if (!domainForm.value.name) {
    toast.show('请填写领域名称', 'warning')
    return
  }
  try {
    await resourceApi.createDomain(domainForm.value)
    toast.show('领域已创建', 'success')
    domainForm.value = { name: '', description: '', icon: '📁', color: '#FFB6C1' }
    showDomainForm.value = false
    fetchDomains()
  } catch (e) {
    toast.show('创建失败', 'error')
  }
}

async function deleteDomain(id: string) {
  try {
    await resourceApi.deleteDomain(id)
    toast.show('领域已删除', 'success')
    fetchDomains()
  } catch (e) {
    toast.show('删除失败', 'error')
  }
}

const domainIcons = ['📁', '📚', '💼', '🎨', '🎵', '🏃', '🍳', '✈️', '💡', '🔧']
const domainColors = ['#FFB6C1', '#87CEEB', '#98FB98', '#FFDAB9', '#DDA0DD', '#F0E68C']

// 初始化
onMounted(() => {
  fetchInbox()
})

function switchTab(tab: 'inbox' | 'templates' | 'domains') {
  activeTab.value = tab
  if (tab === 'inbox') fetchInbox()
  if (tab === 'templates') fetchTemplates()
  if (tab === 'domains') fetchDomains()
}
</script>

<template>
  <div class="resource-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <div>
        <h1 class="page-title">资源中心</h1>
        <p class="page-sub">收集灵感、管理模板、组织领域知识</p>
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
      </button>
    </div>

    <!-- ==================== 收集箱 ==================== -->
    <div v-if="activeTab === 'inbox'" class="tab-content">
      <div class="content-toolbar">
        <div class="filter-group">
          <button
            v-for="f in [{k:'all',l:'全部'},{k:'pending',l:'待处理'},{k:'archived',l:'已归档'}]"
            :key="f.k"
            class="filter-btn"
            :class="{ active: inboxFilter === f.k }"
            @click="inboxFilter = f.k as any; fetchInbox()"
          >{{ f.l }}</button>
        </div>
        <button class="btn-primary" @click="showInboxForm = !showInboxForm">
          {{ showInboxForm ? '取消' : '+ 添加' }}
        </button>
      </div>

      <!-- 新建表单 -->
      <BaseCard v-if="showInboxForm" class="form-card">
        <div class="form-row">
          <select v-model="inboxForm.content_type" class="form-select">
            <option v-for="ct in contentTypes" :key="ct.value" :value="ct.value">{{ ct.label }}</option>
          </select>
          <input v-model="inboxForm.title" class="form-input" placeholder="标题（可选）" />
        </div>
        <textarea v-model="inboxForm.content" class="form-textarea" placeholder="内容..." rows="3" />
        <div class="form-row">
          <input v-model="inboxForm.tags" class="form-input" placeholder="标签（逗号分隔）" />
          <button class="btn-primary" @click="createInboxItem">保存</button>
        </div>
      </BaseCard>

      <!-- 收集箱列表 -->
      <div v-if="inboxLoading" class="loading">加载中...</div>
      <div v-else-if="inboxItems.length === 0" class="empty-state">
        <div class="empty-icon">📥</div>
        <p>收集箱是空的，点击"添加"捕获灵感</p>
      </div>
      <div v-else class="inbox-list">
        <BaseCard v-for="item in inboxItems" :key="item.id" class="inbox-item">
          <div class="inbox-item-header">
            <span class="inbox-type">{{ item.content_type }}</span>
            <span class="inbox-status" :class="item.status">{{ item.status === 'pending' ? '待处理' : item.status === 'archived' ? '已归档' : '已处理' }}</span>
          </div>
          <h3 class="inbox-title">{{ item.title || item.content?.slice(0, 50) }}</h3>
          <p v-if="item.title && item.content" class="inbox-content">{{ item.content }}</p>
          <div class="inbox-tags">
            <span v-for="tag in item.tags" :key="tag" class="tag">{{ tag }}</span>
          </div>
          <div class="inbox-actions">
            <button v-if="item.status === 'pending'" class="btn-sm btn-success" @click="processItem(item, 'archive')">归档</button>
            <button v-if="item.status === 'pending'" class="btn-sm btn-info" @click="processItem(item, 'convert_task')">转任务</button>
            <button class="btn-sm btn-danger" @click="processItem(item, 'delete')">删除</button>
          </div>
        </BaseCard>
      </div>
    </div>

    <!-- ==================== 模板库 ==================== -->
    <div v-if="activeTab === 'templates'" class="tab-content">
      <div class="content-toolbar">
        <span class="count-text">共 {{ templates.length }} 个模板</span>
        <button class="btn-primary" @click="showTemplateForm = !showTemplateForm">
          {{ showTemplateForm ? '取消' : '+ 新建模板' }}
        </button>
      </div>

      <BaseCard v-if="showTemplateForm" class="form-card">
        <div class="form-row">
          <input v-model="templateForm.name" class="form-input" placeholder="模板名称" />
          <input v-model="templateForm.category" class="form-input" placeholder="分类" />
        </div>
        <textarea v-model="templateForm.content" class="form-textarea" placeholder="模板内容，使用 {{变量名}} 定义变量" rows="4" />
        <div class="form-row">
          <input v-model="templateForm.variables" class="form-input" placeholder="变量名（逗号分隔）" />
          <button class="btn-primary" @click="createTemplate">创建</button>
        </div>
      </BaseCard>

      <div v-if="templatesLoading" class="loading">加载中...</div>
      <div v-else-if="templates.length === 0" class="empty-state">
        <div class="empty-icon">📋</div>
        <p>还没有模板，创建一个吧</p>
      </div>
      <div v-else class="template-grid">
        <BaseCard v-for="tpl in templates" :key="tpl.id" class="template-card">
          <div class="template-header">
            <h3 class="template-name">{{ tpl.name }}</h3>
            <span class="template-category">{{ tpl.category }}</span>
          </div>
          <p class="template-content">{{ tpl.content?.slice(0, 80) }}{{ tpl.content && tpl.content.length > 80 ? '...' : '' }}</p>
          <div class="template-meta">
            <span>使用 {{ tpl.use_count }} 次</span>
            <span v-for="v in tpl.variables" :key="v" class="tag">{{ v }}</span>
          </div>
          <div class="template-actions">
            <button class="btn-sm btn-danger" @click="deleteTemplate(tpl.id)">删除</button>
          </div>
        </BaseCard>
      </div>
    </div>

    <!-- ==================== 领域库 ==================== -->
    <div v-if="activeTab === 'domains'" class="tab-content">
      <div class="content-toolbar">
        <span class="count-text">共 {{ domains.length }} 个领域</span>
        <button class="btn-primary" @click="showDomainForm = !showDomainForm">
          {{ showDomainForm ? '取消' : '+ 新建领域' }}
        </button>
      </div>

      <BaseCard v-if="showDomainForm" class="form-card">
        <div class="form-row">
          <input v-model="domainForm.name" class="form-input" placeholder="领域名称" />
          <input v-model="domainForm.description" class="form-input" placeholder="描述（可选）" />
        </div>
        <div class="form-row">
          <div class="icon-picker">
            <button
              v-for="icon in domainIcons"
              :key="icon"
              class="icon-btn"
              :class="{ active: domainForm.icon === icon }"
              @click="domainForm.icon = icon"
            >{{ icon }}</button>
          </div>
        </div>
        <div class="form-row">
          <div class="color-picker">
            <button
              v-for="color in domainColors"
              :key="color"
              class="color-btn"
              :style="{ background: color }"
              :class="{ active: domainForm.color === color }"
              @click="domainForm.color = color"
            />
          </div>
          <button class="btn-primary" @click="createDomain">创建</button>
        </div>
      </BaseCard>

      <div v-if="domainsLoading" class="loading">加载中...</div>
      <div v-else-if="domains.length === 0" class="empty-state">
        <div class="empty-icon">📚</div>
        <p>还没有领域，创建你的第一个知识领域</p>
      </div>
      <div v-else class="domain-grid">
        <BaseCard v-for="domain in domains" :key="domain.id" class="domain-card" :style="{ borderLeftColor: domain.color }">
          <div class="domain-icon">{{ domain.icon }}</div>
          <h3 class="domain-name">{{ domain.name }}</h3>
          <p v-if="domain.description" class="domain-desc">{{ domain.description }}</p>
          <button class="btn-sm btn-danger" @click="deleteDomain(domain.id)">删除</button>
        </BaseCard>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.resource-page {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
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

/* 工具栏 */
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
  transition: all 0.2s;
  &.active {
    background: var(--primary-soft);
    color: var(--primary);
    border-color: var(--primary);
  }
}
.count-text { color: var(--text-mid); font-size: var(--text-sm); }

/* 按钮 */
.btn-primary {
  padding: 8px 18px;
  border-radius: var(--radius-md);
  border: none;
  background: var(--primary);
  color: white;
  font-size: var(--text-sm);
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  &:hover { opacity: 0.9; transform: translateY(-1px); }
}
.btn-sm {
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  border: none;
  font-size: var(--text-xs);
  cursor: pointer;
  transition: opacity 0.2s;
  &:hover { opacity: 0.8; }
}
.btn-success { background: var(--success, #52c41a); color: white; }
.btn-info { background: var(--info, #1890ff); color: white; }
.btn-danger { background: var(--danger, #ff4d4f); color: white; }

/* 表单 */
.form-card { margin-bottom: var(--space-3); }
.form-row {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
  &:last-child { margin-bottom: 0; }
}
.form-input, .form-select {
  flex: 1;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--line);
  background: var(--bg-input);
  color: var(--text-hi);
  font-size: var(--text-sm);
  &:focus { outline: none; border-color: var(--primary); }
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
  &:focus { outline: none; border-color: var(--primary); }
}

/* 收集箱列表 */
.inbox-list { display: flex; flex-direction: column; gap: var(--space-3); }
.inbox-item { padding: var(--space-4); }
.inbox-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.inbox-type {
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  background: var(--primary-soft);
  color: var(--primary);
  font-size: var(--text-xs);
  font-weight: 600;
}
.inbox-status {
  font-size: var(--text-xs);
  font-weight: 600;
  &.pending { color: var(--warning, #faad14); }
  &.archived { color: var(--text-mid); }
  &.processed { color: var(--success, #52c41a); }
}
.inbox-title {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-hi);
  margin-bottom: 4px;
}
.inbox-content {
  color: var(--text-mid);
  font-size: var(--text-sm);
  margin-bottom: 8px;
  line-height: 1.5;
}
.inbox-tags { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; }
.tag {
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  background: var(--bg-hover);
  color: var(--text-mid);
  font-size: var(--text-xs);
}
.inbox-actions { display: flex; gap: 8px; }

/* 模板网格 */
.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-3);
}
.template-card { padding: var(--space-4); }
.template-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.template-name {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-hi);
}
.template-category {
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  background: var(--primary-soft);
  color: var(--primary);
  font-size: var(--text-xs);
}
.template-content {
  color: var(--text-mid);
  font-size: var(--text-sm);
  margin-bottom: 10px;
  line-height: 1.5;
}
.template-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
  font-size: var(--text-xs);
  color: var(--text-mid);
}
.template-actions { display: flex; justify-content: flex-end; }

/* 领域网格 */
.domain-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--space-3);
}
.domain-card {
  padding: var(--space-4);
  text-align: center;
  border-left: 4px solid var(--primary);
}
.domain-icon { font-size: 36px; margin-bottom: 8px; }
.domain-name {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-hi);
  margin-bottom: 4px;
}
.domain-desc {
  color: var(--text-mid);
  font-size: var(--text-xs);
  margin-bottom: 12px;
}

/* 图标/颜色选择器 */
.icon-picker { display: flex; gap: 6px; flex-wrap: wrap; }
.icon-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  border: 2px solid transparent;
  background: var(--bg-panel);
  font-size: 18px;
  cursor: pointer;
  &.active { border-color: var(--primary); background: var(--primary-soft); }
}
.color-picker { display: flex; gap: 8px; align-items: center; }
.color-btn {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 3px solid transparent;
  cursor: pointer;
  &.active { border-color: var(--text-hi); }
}

/* 状态 */
.loading, .empty-state {
  text-align: center;
  padding: var(--space-8);
  color: var(--text-mid);
}
.empty-icon { font-size: 48px; margin-bottom: 12px; }
</style>
