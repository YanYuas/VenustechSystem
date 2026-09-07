<script setup lang="ts">
// ============================================================
// 第二分身设置（二期 P1）
// 五档配置 + 长期记忆 + 灵感工作流
// ============================================================
import { ref, onMounted } from 'vue'
import { avatarApi } from '@/api/avatar'
import { useToast } from '@/composables'
import type { AvatarConfig, AvatarMemory, AvatarInspiration } from '@/api/avatar'
import BaseCard from '@/components/common/BaseCard.vue'

const toast = useToast()

const activeTab = ref<'config' | 'memory' | 'inspiration'>('config')
const tabs = [
  { key: 'config', label: '分身配置', icon: '⚙️' },
  { key: 'memory', label: '长期记忆', icon: '🧠' },
  { key: 'inspiration', label: '灵感工作流', icon: '💡' },
] as const

// ==================== 配置 ====================
const config = ref<AvatarConfig | null>(null)
const configLoading = ref(false)

const automationLevels = [
  { level: 'L1', name: '完全手动', desc: '只在被问时回答，不主动操作' },
  { level: 'L2', name: '建议不执行', desc: '主动提建议，需用户确认后执行' },
  { level: 'L3', name: '低风险自动', desc: '自动打标签/摘要/整理，高风险需确认' },
  { level: 'L4', name: '大部分自动', desc: '大部分操作自动，删除/覆盖/发送确认' },
  { level: 'L5', name: '完全自主', desc: '全自动，用户只看结果' },
]

async function fetchConfig() {
  configLoading.value = true
  try {
    config.value = await avatarApi.getConfig()
  } catch (e) {
    toast.error('加载配置失败')
  } finally {
    configLoading.value = false
  }
}

async function saveConfig() {
  if (!config.value) return
  try {
    config.value = await avatarApi.updateConfig(config.value)
    toast.success('配置已保存')
  } catch (e) {
    toast.error('保存失败')
  }
}

// ==================== 记忆 ====================
const memories = ref<AvatarMemory[]>([])
const memoryStats = ref<{ total: number; profile: number; knowledge: number; event: number; relation: number; verified: number } | null>(null)
const memoryFilter = ref<string>('')
const memoryLoading = ref(false)
const showMemoryForm = ref(false)
const memoryForm = ref({ memory_type: 'profile' as 'profile' | 'knowledge' | 'event' | 'relation', category: '', title: '', content: '', importance: 3 })

const memoryTypeMap: Record<string, { label: string; icon: string; color: string }> = {
  profile: { label: '用户画像', icon: '👤', color: '#409EFF' },
  knowledge: { label: '知识记忆', icon: '📚', color: '#67C23A' },
  event: { label: '事件记忆', icon: '📅', color: '#E6A23C' },
  relation: { label: '关系记忆', icon: '🔗', color: '#909399' },
}

async function fetchMemories() {
  memoryLoading.value = true
  try {
    const params = memoryFilter.value ? { memory_type: memoryFilter.value } : {}
    const data = await avatarApi.listMemories({ ...params, page: 1, page_size: 50 })
    memories.value = data.list
    memoryStats.value = await avatarApi.memoryStats()
  } catch (e) {
    toast.error('加载记忆失败')
  } finally {
    memoryLoading.value = false
  }
}

async function createMemory() {
  if (!memoryForm.value.title) { toast.warning('请填写标题'); return }
  try {
    await avatarApi.createMemory(memoryForm.value)
    toast.success('记忆已创建')
    memoryForm.value = { memory_type: 'profile', category: '', title: '', content: '', importance: 3 }
    showMemoryForm.value = false
    fetchMemories()
  } catch (e) {
    toast.error('创建失败')
  }
}

async function toggleVerify(m: AvatarMemory) {
  try {
    await avatarApi.verifyMemory(m.id, !m.is_verified)
    toast.success(m.is_verified ? '已取消确认' : '已确认')
    fetchMemories()
  } catch (e) {
    toast.error('操作失败')
  }
}

async function deleteMemory(id: string) {
  try {
    await avatarApi.deleteMemory(id)
    toast.success('已删除')
    fetchMemories()
  } catch (e) {
    toast.error('删除失败')
  }
}

// ==================== 灵感工作流 ====================
const inspirations = ref<AvatarInspiration[]>([])
const inspirationLoading = ref(false)
const generating = ref(false)
const inspireDomain = ref('')
const inspireCount = ref(3)
const selectedInspiration = ref<AvatarInspiration | null>(null)

const domains = ['学习', '开发', '写作', '通用']

async function fetchInspirations() {
  inspirationLoading.value = true
  try {
    const data = await avatarApi.listInspirations({ page: 1, page_size: 20 })
    inspirations.value = data.list
  } catch (e) {
    toast.error('加载灵感失败')
  } finally {
    inspirationLoading.value = false
  }
}

async function generateInspirations() {
  generating.value = true
  try {
    const result = await avatarApi.generateInspirations({
      domain: inspireDomain.value || undefined,
      count: inspireCount.value,
    })
    inspirations.value = [...result.inspirations, ...inspirations.value]
    toast.success(`生成${result.count}个灵感`)
    fetchInspirations()
  } catch (e) {
    toast.error('生成失败')
  } finally {
    generating.value = false
  }
}

async function selectInspiration(insp: AvatarInspiration) {
  try {
    const updated = await avatarApi.selectInspiration(insp.id)
    selectedInspiration.value = updated
    toast.success('提示词已生成')
    fetchInspirations()
  } catch (e) {
    toast.error('操作失败')
  }
}

async function executeInspiration(insp: AvatarInspiration) {
  try {
    await avatarApi.executeInspiration(insp.id, '已执行')
    toast.success('灵感已执行')
    selectedInspiration.value = null
    fetchInspirations()
  } catch (e) {
    toast.error('执行失败')
  }
}

async function feedbackInspiration(insp: AvatarInspiration, feedback: string) {
  try {
    await avatarApi.feedbackInspiration(insp.id, feedback)
    toast.success(feedback === 'useful' ? '已标记有用' : '已反馈')
    fetchInspirations()
  } catch (e) {
    toast.error('操作失败')
  }
}

async function discardInspiration(id: string) {
  try {
    await avatarApi.discardInspiration(id)
    toast.success('已丢弃')
    fetchInspirations()
  } catch (e) {
    toast.error('操作失败')
  }
}

function copyPrompt() {
  if (selectedInspiration.value?.prompt) {
    navigator.clipboard.writeText(selectedInspiration.value.prompt)
    toast.success('提示词已复制')
  }
}

function switchTab(tab: 'config' | 'memory' | 'inspiration') {
  activeTab.value = tab
  if (tab === 'config') fetchConfig()
  if (tab === 'memory') fetchMemories()
  if (tab === 'inspiration') fetchInspirations()
}

onMounted(() => fetchConfig())
</script>

<template>
  <div class="avatar-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">第二分身</h1>
        <p class="page-sub">你的数字分身 · 长期记忆 · 灵感引擎</p>
      </div>
    </div>

    <!-- Tab导航 -->
    <div class="tab-nav">
      <button v-for="tab in tabs" :key="tab.key" class="tab-btn" :class="{ active: activeTab === tab.key }" @click="switchTab(tab.key)">
        <span class="tab-icon">{{ tab.icon }}</span>
        <span>{{ tab.label }}</span>
      </button>
    </div>

    <!-- ==================== 分身配置 ==================== -->
    <div v-if="activeTab === 'config'" class="tab-content">
      <div v-if="configLoading" class="loading">加载中...</div>
      <template v-else-if="config">
        <!-- 五档自动化 -->
        <BaseCard class="config-section">
          <h3 class="section-title">🤖 自动化档位</h3>
          <p class="section-desc">控制第二分身的自主程度，档位越高操作越自动</p>
          <div class="level-grid">
            <div
              v-for="lv in automationLevels" :key="lv.level"
              class="level-card"
              :class="{ active: config.automation_level === lv.level }"
              @click="config.automation_level = lv.level"
            >
              <div class="level-badge">{{ lv.level }}</div>
              <div class="level-name">{{ lv.name }}</div>
              <div class="level-desc">{{ lv.desc }}</div>
            </div>
          </div>
        </BaseCard>

        <!-- 模型配置 -->
        <BaseCard class="config-section">
          <h3 class="section-title">🔧 模型配置</h3>
          <div class="form-row">
            <label class="form-label">
              <input type="checkbox" v-model="config.cloud_model_enabled" />
              云端模型（强AI功能）
            </label>
          </div>
          <div class="form-row" v-if="config.cloud_model_enabled">
            <select v-model="config.cloud_model_provider" class="form-select">
              <option value="deepseek">DeepSeek</option>
              <option value="openai">OpenAI</option>
              <option value="custom">自定义</option>
            </select>
            <input v-model="config.cloud_model_name" class="form-input" placeholder="模型名称" />
          </div>
          <div class="form-row">
            <label class="form-label">
              <input type="checkbox" v-model="config.local_model_enabled" />
              本地模型（弱AI功能，需Ollama/LM Studio）
            </label>
          </div>
          <div class="form-row" v-if="config.local_model_enabled">
            <select v-model="config.local_model_provider" class="form-select">
              <option value="ollama">Ollama</option>
              <option value="lmstudio">LM Studio</option>
            </select>
            <input v-model="config.local_model_url" class="form-input" placeholder="服务地址" />
            <input v-model="config.local_model_name" class="form-input" placeholder="模型名称" />
          </div>
        </BaseCard>

        <!-- 人格设定 -->
        <BaseCard class="config-section">
          <h3 class="section-title">🎭 人格设定</h3>
          <div class="form-row">
            <input v-model="config.persona_name" class="form-input" placeholder="分身名称" />
          </div>
          <textarea v-model="config.persona_setting" class="form-textarea" placeholder="角色设定词（描述分身的性格、说话风格、能力等）" rows="4" />
          <div class="form-row">
            <label class="form-label">回复长度</label>
            <select v-model="config.reply_length" class="form-select">
              <option value="short">简短</option>
              <option value="medium">中等</option>
              <option value="long">详细</option>
            </select>
            <label class="form-label">语言风格</label>
            <select v-model="config.language_style" class="form-select">
              <option value="casual">随意</option>
              <option value="professional">专业</option>
              <option value="cute">可爱</option>
            </select>
          </div>
          <div class="form-row">
            <label class="form-label">创造力: {{ config.creativity }}</label>
            <input type="range" v-model.number="config.creativity" min="0" max="1" step="0.1" class="form-range" />
          </div>
        </BaseCard>

        <!-- 灵感设置 -->
        <BaseCard class="config-section">
          <h3 class="section-title">💡 灵感设置</h3>
          <div class="form-row">
            <label class="form-label">
              <input type="checkbox" v-model="config.inspiration_enabled" />
              启用灵感功能
            </label>
          </div>
          <div class="form-row">
            <label class="form-label">触发频率</label>
            <select v-model="config.inspiration_frequency" class="form-select">
              <option value="manual">仅手动</option>
              <option value="daily">每日推荐</option>
              <option value="weekly">每周推荐</option>
            </select>
          </div>
        </BaseCard>

        <button class="save-btn" @click="saveConfig">💾 保存配置</button>
      </template>
    </div>

    <!-- ==================== 长期记忆 ==================== -->
    <div v-if="activeTab === 'memory'" class="tab-content">
      <!-- 统计卡片 -->
      <div v-if="memoryStats" class="stats-row">
        <BaseCard v-for="(info, type) in memoryTypeMap" :key="type" class="stat-card">
          <div class="stat-icon">{{ info.icon }}</div>
          <div class="stat-value">{{ (memoryStats as Record<string, number>)[type] || 0 }}</div>
          <div class="stat-label">{{ info.label }}</div>
        </BaseCard>
        <BaseCard class="stat-card">
          <div class="stat-icon">✅</div>
          <div class="stat-value">{{ memoryStats.verified }}</div>
          <div class="stat-label">已确认</div>
        </BaseCard>
      </div>

      <div class="content-toolbar">
        <div class="filter-group">
          <button class="filter-btn" :class="{ active: !memoryFilter }" @click="memoryFilter = ''; fetchMemories()">全部</button>
          <button v-for="(info, type) in memoryTypeMap" :key="type" class="filter-btn" :class="{ active: memoryFilter === type }" @click="memoryFilter = type; fetchMemories()">
            {{ info.icon }} {{ info.label }}
          </button>
        </div>
        <button class="btn-primary" @click="showMemoryForm = !showMemoryForm">{{ showMemoryForm ? '取消' : '+ 添加记忆' }}</button>
      </div>

      <!-- 添加表单 -->
      <BaseCard v-if="showMemoryForm" class="form-card">
        <div class="form-row">
          <select v-model="memoryForm.memory_type" class="form-select">
            <option v-for="(info, type) in memoryTypeMap" :key="type" :value="type">{{ info.icon }} {{ info.label }}</option>
          </select>
          <input v-model="memoryForm.category" class="form-input" placeholder="分类" />
          <select v-model.number="memoryForm.importance" class="form-select">
            <option :value="1">重要度1</option>
            <option :value="2">重要度2</option>
            <option :value="3">重要度3</option>
            <option :value="4">重要度4</option>
            <option :value="5">重要度5</option>
          </select>
        </div>
        <input v-model="memoryForm.title" class="form-input" placeholder="记忆标题" />
        <textarea v-model="memoryForm.content" class="form-textarea" placeholder="记忆内容" rows="3" />
        <button class="btn-primary" @click="createMemory">创建</button>
      </BaseCard>

      <div v-if="memoryLoading" class="loading">加载中...</div>
      <div v-else-if="memories.length === 0" class="empty-state">
        <div class="empty-icon">🧠</div>
        <p>还没有记忆，添加第一条记忆吧</p>
      </div>
      <div v-else class="memory-list">
        <BaseCard v-for="m in memories" :key="m.id" class="memory-item">
          <div class="memory-header">
            <span class="memory-type" :style="{ background: memoryTypeMap[m.memory_type]?.color + '20', color: memoryTypeMap[m.memory_type]?.color }">
              {{ memoryTypeMap[m.memory_type]?.icon }} {{ memoryTypeMap[m.memory_type]?.label }}
            </span>
            <span class="memory-importance">⭐{{ m.importance }}</span>
            <button class="btn-sm" :class="{ verified: m.is_verified }" @click="toggleVerify(m)">
              {{ m.is_verified ? '✓ 已确认' : '确认' }}
            </button>
            <button class="btn-sm btn-danger" @click="deleteMemory(m.id)">删除</button>
          </div>
          <h3 class="memory-title">{{ m.title }}</h3>
          <p v-if="m.content" class="memory-content">{{ m.content }}</p>
          <div class="memory-meta">
            <span v-if="m.category" class="tag">{{ m.category }}</span>
            <span v-if="m.source">来源: {{ m.source }}</span>
            <span>可信度: {{ Math.round(m.confidence * 100) }}%</span>
          </div>
        </BaseCard>
      </div>
    </div>

    <!-- ==================== 灵感工作流 ==================== -->
    <div v-if="activeTab === 'inspiration'" class="tab-content">
      <!-- 生成区 -->
      <BaseCard class="generate-section">
        <h3 class="section-title">💡 生成灵感</h3>
        <div class="form-row">
          <select v-model="inspireDomain" class="form-select">
            <option value="">全部领域</option>
            <option v-for="d in domains" :key="d" :value="d">{{ d }}</option>
          </select>
          <select v-model.number="inspireCount" class="form-select">
            <option :value="3">3个</option>
            <option :value="5">5个</option>
            <option :value="10">10个</option>
          </select>
          <button class="btn-primary generate-btn" :disabled="generating" @click="generateInspirations">
            {{ generating ? '生成中...' : '🚀 生成灵感' }}
          </button>
        </div>
        <p class="generate-hint">灵感基于你的长期记忆和最近活动生成，选择一个方向深入，或要求再来一批</p>
      </BaseCard>

      <!-- 选中的灵感详情 -->
      <BaseCard v-if="selectedInspiration" class="selected-card">
        <div class="selected-header">
          <h3 class="selected-title">{{ selectedInspiration.title }}</h3>
          <button class="modal-close" @click="selectedInspiration = null">✕</button>
        </div>
        <p class="selected-desc">{{ selectedInspiration.description }}</p>
        <div class="selected-meta">
          <span class="tag">{{ selectedInspiration.domain }}</span>
          <span>预估价值: {{ selectedInspiration.estimated_value }}</span>
        </div>
        <div v-if="selectedInspiration.prompt" class="prompt-box">
          <div class="prompt-header">
            <span>📝 生成的提示词</span>
            <button class="btn-sm" @click="copyPrompt">复制</button>
          </div>
          <pre class="prompt-content">{{ selectedInspiration.prompt }}</pre>
        </div>
        <div class="selected-actions">
          <button class="btn-primary" @click="executeInspiration(selectedInspiration)">✅ 执行灵感</button>
          <button class="btn-secondary" @click="feedbackInspiration(selectedInspiration, 'useful')">👍 有用</button>
          <button class="btn-secondary" @click="feedbackInspiration(selectedInspiration, 'useless')">👎 无用</button>
        </div>
      </BaseCard>

      <!-- 灵感列表 -->
      <div v-if="inspirationLoading" class="loading">加载中...</div>
      <div v-else-if="inspirations.length === 0" class="empty-state">
        <div class="empty-icon">💡</div>
        <p>点击上方按钮生成第一批灵感</p>
      </div>
      <div v-else class="inspiration-grid">
        <BaseCard
          v-for="insp in inspirations" :key="insp.id"
          class="inspiration-card"
          :class="{ discarded: insp.status === 'discarded', completed: insp.status === 'completed' }"
        >
          <div class="insp-header">
            <span class="insp-status" :class="insp.status">
              {{ insp.status === 'generated' ? '新生成' : insp.status === 'selected' ? '已选择' : insp.status === 'completed' ? '已完成' : '已丢弃' }}
            </span>
            <span v-if="insp.estimated_value" class="insp-value">{{ insp.estimated_value }}</span>
          </div>
          <h3 class="insp-title">{{ insp.title }}</h3>
          <p class="insp-desc">{{ insp.description }}</p>
          <div class="insp-meta">
            <span v-if="insp.domain" class="tag">{{ insp.domain }}</span>
            <span>{{ insp.created_at?.slice(0, 10) }}</span>
          </div>
          <div class="insp-actions" v-if="insp.status === 'generated'">
            <button class="btn-sm btn-primary" @click="selectInspiration(insp)">选择方向</button>
            <button class="btn-sm" @click="discardInspiration(insp.id)">丢弃</button>
          </div>
          <div class="insp-actions" v-else-if="insp.status === 'selected'">
            <button class="btn-sm btn-primary" @click="selectedInspiration = insp">查看提示词</button>
            <button class="btn-sm" @click="executeInspiration(insp)">执行</button>
          </div>
          <div v-if="insp.feedback" class="insp-feedback">
            反馈: {{ insp.feedback === 'useful' ? '👍 有用' : insp.feedback === 'useless' ? '👎 无用' : '😐 一般' }}
          </div>
        </BaseCard>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.avatar-page { padding: var(--space-4); display: flex; flex-direction: column; gap: var(--space-4); }
.page-title { font-size: var(--text-2xl); font-weight: 800; color: var(--text-hi); font-family: var(--font-cute); }
.page-sub { color: var(--text-mid); font-size: var(--text-sm); margin-top: 4px; }

.tab-nav { display: flex; gap: var(--space-2); background: var(--bg-panel); padding: 6px; border-radius: var(--radius-lg); border: 1px solid var(--line); width: fit-content; }
.tab-btn { display: flex; align-items: center; gap: 6px; padding: 8px 16px; border-radius: var(--radius-md); border: none; background: transparent; color: var(--text-mid); font-size: var(--text-sm); font-weight: 600; cursor: pointer; transition: all 0.2s; &:hover { background: var(--bg-hover); } &.active { background: var(--primary); color: white; box-shadow: 0 2px 8px var(--primary-shadow); } }
.tab-icon { font-size: 16px; }

.loading, .empty-state { text-align: center; padding: var(--space-8); color: var(--text-mid); }
.empty-icon { font-size: 48px; margin-bottom: 12px; }
.section-title { font-size: var(--text-base); font-weight: 600; color: var(--text-hi); margin-bottom: 6px; }
.section-desc { font-size: var(--text-sm); color: var(--text-mid); margin-bottom: var(--space-3); }

.btn-primary { padding: 8px 18px; border-radius: var(--radius-md); border: none; background: var(--primary); color: white; font-size: var(--text-sm); font-weight: 600; cursor: pointer; &:hover { opacity: 0.9; } &:disabled { opacity: 0.5; cursor: not-allowed; } }
.btn-secondary { padding: 8px 18px; border-radius: var(--radius-md); border: 1px solid var(--line); background: var(--bg-panel); color: var(--text-mid); font-size: var(--text-sm); cursor: pointer; }
.btn-sm { padding: 4px 10px; border-radius: var(--radius-sm); border: 1px solid var(--line); background: var(--bg-panel); color: var(--text-mid); font-size: var(--text-xs); cursor: pointer; &.btn-primary { background: var(--primary); color: white; border-color: var(--primary); } &.btn-danger { background: var(--danger, #ff4d4f); color: white; border-color: var(--danger, #ff4d4f); } &.verified { background: var(--success, #52c41a); color: white; border-color: var(--success, #52c41a); } }

/* 配置 */
.config-section { padding: var(--space-4); margin-bottom: var(--space-3); }
.form-row { display: flex; gap: var(--space-3); margin-bottom: var(--space-3); align-items: center; flex-wrap: wrap; }
.form-label { font-size: var(--text-sm); color: var(--text-hi); display: flex; align-items: center; gap: 6px; cursor: pointer; }
.form-input, .form-select { flex: 1; min-width: 120px; padding: 8px 12px; border-radius: var(--radius-md); border: 1px solid var(--line); background: var(--bg-input); color: var(--text-hi); font-size: var(--text-sm); }
.form-textarea { width: 100%; padding: 8px 12px; border-radius: var(--radius-md); border: 1px solid var(--line); background: var(--bg-input); color: var(--text-hi); font-size: var(--text-sm); resize: vertical; margin-bottom: var(--space-3); }
.form-range { flex: 1; }

.level-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: var(--space-2); }
.level-card { padding: var(--space-3); border-radius: var(--radius-md); border: 2px solid var(--line); cursor: pointer; transition: all 0.2s; text-align: center; &:hover { border-color: var(--primary); } &.active { border-color: var(--primary); background: var(--primary-soft); } }
.level-badge { display: inline-block; padding: 2px 10px; border-radius: var(--radius-pill); background: var(--primary); color: white; font-size: var(--text-sm); font-weight: 700; margin-bottom: 6px; }
.level-name { font-size: var(--text-sm); font-weight: 600; color: var(--text-hi); margin-bottom: 4px; }
.level-desc { font-size: var(--text-xs); color: var(--text-mid); line-height: 1.4; }

.save-btn { width: 100%; padding: 14px; border-radius: var(--radius-md); border: none; background: var(--primary); color: white; font-size: var(--text-base); font-weight: 600; cursor: pointer; &:hover { opacity: 0.9; } }

/* 记忆 */
.stats-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: var(--space-2); margin-bottom: var(--space-3); }
.stat-card { text-align: center; padding: var(--space-3); }
.stat-icon { font-size: 24px; margin-bottom: 4px; }
.stat-value { font-size: var(--text-xl); font-weight: 700; color: var(--primary); }
.stat-label { font-size: var(--text-xs); color: var(--text-mid); }

.content-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-3); flex-wrap: wrap; gap: 8px; }
.filter-group { display: flex; gap: 6px; flex-wrap: wrap; }
.filter-btn { padding: 6px 12px; border-radius: var(--radius-pill); border: 1px solid var(--line); background: var(--bg-panel); color: var(--text-mid); font-size: var(--text-xs); cursor: pointer; &.active { background: var(--primary-soft); color: var(--primary); border-color: var(--primary); } }

.form-card { padding: var(--space-4); margin-bottom: var(--space-3); }
.memory-list { display: flex; flex-direction: column; gap: var(--space-2); }
.memory-item { padding: var(--space-3); }
.memory-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.memory-type { padding: 2px 8px; border-radius: var(--radius-pill); font-size: var(--text-xs); font-weight: 600; }
.memory-importance { font-size: var(--text-xs); color: var(--text-mid); }
.memory-title { font-size: var(--text-base); font-weight: 600; color: var(--text-hi); margin-bottom: 4px; }
.memory-content { font-size: var(--text-sm); color: var(--text-mid); margin-bottom: 8px; line-height: 1.5; }
.memory-meta { display: flex; gap: 10px; font-size: var(--text-xs); color: var(--text-mid); flex-wrap: wrap; align-items: center; }
.tag { display: inline-block; padding: 2px 8px; border-radius: var(--radius-pill); background: var(--primary-soft); color: var(--primary); font-size: var(--text-xs); }

/* 灵感 */
.generate-section { padding: var(--space-4); margin-bottom: var(--space-3); }
.generate-btn { min-width: 140px; }
.generate-hint { font-size: var(--text-xs); color: var(--text-mid); margin-top: 8px; }

.selected-card { padding: var(--space-4); margin-bottom: var(--space-3); border: 2px solid var(--primary); }
.selected-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.selected-title { font-size: var(--text-lg); font-weight: 700; color: var(--text-hi); }
.modal-close { width: 28px; height: 28px; border-radius: 50%; border: none; background: var(--bg-hover); color: var(--text-mid); cursor: pointer; &:hover { background: var(--danger, #ff4d4f); color: white; } }
.selected-desc { font-size: var(--text-sm); color: var(--text-mid); margin-bottom: 10px; }
.selected-meta { display: flex; gap: 10px; margin-bottom: 12px; font-size: var(--text-xs); color: var(--text-mid); align-items: center; }
.prompt-box { background: var(--bg-hover); border-radius: var(--radius-md); padding: var(--space-3); margin-bottom: 12px; }
.prompt-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; font-size: var(--text-sm); font-weight: 600; color: var(--text-hi); }
.prompt-content { font-size: var(--text-xs); color: var(--text-hi); white-space: pre-wrap; max-height: 200px; overflow-y: auto; line-height: 1.6; }
.selected-actions { display: flex; gap: 8px; flex-wrap: wrap; }

.inspiration-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: var(--space-3); }
.inspiration-card { padding: var(--space-3); &.discarded { opacity: 0.5; } &.completed { border-left: 3px solid var(--success, #52c41a); } }
.insp-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.insp-status { padding: 2px 8px; border-radius: var(--radius-pill); font-size: var(--text-xs); font-weight: 600; background: var(--bg-hover); color: var(--text-mid); &.generated { background: #409EFF20; color: #409EFF; } &.selected { background: #E6A23C20; color: #E6A23C; } &.completed { background: #67C23A20; color: #67C23A; } &.discarded { background: #90939920; color: #909399; } }
.insp-value { font-size: var(--text-xs); color: var(--text-mid); }
.insp-title { font-size: var(--text-base); font-weight: 600; color: var(--text-hi); margin-bottom: 4px; }
.insp-desc { font-size: var(--text-sm); color: var(--text-mid); margin-bottom: 8px; line-height: 1.5; min-height: 40px; }
.insp-meta { display: flex; gap: 8px; font-size: var(--text-xs); color: var(--text-mid); margin-bottom: 10px; align-items: center; }
.insp-actions { display: flex; gap: 6px; }
.insp-feedback { margin-top: 8px; font-size: var(--text-xs); color: var(--text-mid); }
</style>
