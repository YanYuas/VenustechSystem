<script setup lang="ts">
// ============================================================
// 桌宠设置（二期 P1）
// 显示设置 + 状态感知 + 语音TTS + 形象管理
// ============================================================
import { ref, onMounted } from 'vue'
import { petApi } from '@/api/pet'
import { useToast } from '@/composables'
import type { PetConfig, PetAvatar, PetState } from '@/api/pet'
import BaseCard from '@/components/common/BaseCard.vue'

const toast = useToast()

const activeTab = ref<'display' | 'state' | 'voice' | 'avatar'>('display')
const tabs = [
  { key: 'display', label: '显示设置', icon: '🖥️' },
  { key: 'state', label: '状态感知', icon: '🎭' },
  { key: 'voice', label: '语音TTS', icon: '🔊' },
  { key: 'avatar', label: '形象管理', icon: '🎨' },
] as const

// ==================== 配置 ====================
const config = ref<PetConfig | null>(null)
const configLoading = ref(false)
const currentState = ref<PetState | null>(null)

async function fetchConfig() {
  configLoading.value = true
  try {
    config.value = await petApi.getConfig()
  } catch (e) {
    toast.error('加载配置失败')
  } finally {
    configLoading.value = false
  }
}

async function fetchState() {
  try {
    currentState.value = await petApi.getState()
  } catch (e) {
    // 状态获取失败不报错
  }
}

async function saveConfig() {
  if (!config.value) return
  try {
    config.value = await petApi.updateConfig(config.value)
    toast.success('配置已保存')
  } catch (e) {
    toast.error('保存失败')
  }
}

function switchTab(tab: 'display' | 'state' | 'voice' | 'avatar') {
  activeTab.value = tab
  if (tab === 'state') fetchState()
  if (tab === 'avatar') fetchAvatars()
}

// ==================== 形象管理 ====================
const avatars = ref<PetAvatar[]>([])
const avatarLoading = ref(false)
const showAvatarForm = ref(false)
const avatarForm = ref({ name: '', description: '', image_url: '', mode: 'simple' as 'simple' | 'advanced' })

async function fetchAvatars() {
  avatarLoading.value = true
  try {
    avatars.value = await petApi.listAvatars()
  } catch (e) {
    toast.error('加载形象失败')
  } finally {
    avatarLoading.value = false
  }
}

async function createAvatar() {
  if (!avatarForm.value.name) { toast.warning('请填写形象名称'); return }
  try {
    await petApi.createAvatar(avatarForm.value)
    toast.success('形象已创建')
    avatarForm.value = { name: '', description: '', image_url: '', mode: 'simple' }
    showAvatarForm.value = false
    fetchAvatars()
  } catch (e) {
    toast.error('创建失败')
  }
}

async function activateAvatar(id: string) {
  try {
    config.value = await petApi.activateAvatar(id)
    toast.success('已切换形象')
    fetchAvatars()
  } catch (e) {
    toast.error('切换失败')
  }
}

async function deleteAvatar(id: string) {
  try {
    await petApi.deleteAvatar(id)
    toast.success('已删除')
    fetchAvatars()
  } catch (e) {
    toast.error('删除失败')
  }
}

// ==================== TTS ====================
const ttsTestText = ref('你好，我是启明星，你的桌面伙伴！')

function testTTS() {
  if (!config.value?.tts_enabled) { toast.warning('请先开启TTS'); return }
  if ('speechSynthesis' in window) {
    const utterance = new SpeechSynthesisUtterance(ttsTestText.value)
    utterance.rate = config.value.tts_rate
    utterance.pitch = config.value.tts_pitch
    utterance.volume = config.value.tts_volume
    speechSynthesis.speak(utterance)
    toast.success('正在播放测试语音')
  } else {
    toast.error('当前浏览器不支持语音合成')
  }
}

onMounted(() => fetchConfig())
</script>

<template>
  <div class="pet-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">桌宠设置</h1>
        <p class="page-sub">你的桌面伙伴 · 状态感知 · 语音互动</p>
      </div>
    </div>

    <!-- Tab导航 -->
    <div class="tab-nav">
      <button v-for="tab in tabs" :key="tab.key" class="tab-btn" :class="{ active: activeTab === tab.key }" @click="switchTab(tab.key)">
        <span class="tab-icon">{{ tab.icon }}</span>
        <span>{{ tab.label }}</span>
      </button>
    </div>

    <div v-if="configLoading" class="loading">加载中...</div>
    <template v-else-if="config">

      <!-- ==================== 显示设置 ==================== -->
      <div v-if="activeTab === 'display'" class="tab-content">
        <BaseCard class="config-section">
          <h3 class="section-title">🖥️ 显示设置</h3>
          <div class="form-row">
            <label class="form-label">
              <input type="checkbox" v-model="config.enabled" />
              启用桌宠
            </label>
          </div>
          <div class="form-row">
            <label class="form-label">桌宠大小</label>
            <select v-model="config.size" class="form-select">
              <option value="small">小 (80px)</option>
              <option value="medium">中 (120px)</option>
              <option value="large">大 (160px)</option>
            </select>
          </div>
          <div class="form-row">
            <label class="form-label">透明度: {{ Math.round(config.opacity * 100) }}%</label>
            <input type="range" v-model.number="config.opacity" min="0.3" max="1" step="0.1" class="form-range" />
          </div>
          <div class="form-row">
            <label class="form-label">
              <input type="checkbox" v-model="config.always_on_top" />
              始终置顶
            </label>
            <label class="form-label">
              <input type="checkbox" v-model="config.auto_start" />
              开机自启
            </label>
          </div>
          <div class="form-row">
            <label class="form-label">
              <input type="checkbox" v-model="config.draggable" />
              允许拖拽
            </label>
            <label class="form-label">
              <input type="checkbox" v-model="config.click_interaction" />
              点击互动
            </label>
            <label class="form-label">
              <input type="checkbox" v-model="config.right_click_menu" />
              右键菜单
            </label>
          </div>
        </BaseCard>

        <BaseCard class="config-section">
          <h3 class="section-title">💬 气泡设置</h3>
          <div class="form-row">
            <label class="form-label">
              <input type="checkbox" v-model="config.show_bubble" />
              显示对话气泡
            </label>
          </div>
          <div class="form-row">
            <label class="form-label">气泡时长: {{ config.bubble_duration }}秒</label>
            <input type="range" v-model.number="config.bubble_duration" min="2" max="15" step="1" class="form-range" />
          </div>
        </BaseCard>

        <button class="save-btn" @click="saveConfig">💾 保存设置</button>
      </div>

      <!-- ==================== 状态感知 ==================== -->
      <div v-if="activeTab === 'state'" class="tab-content">
        <BaseCard class="config-section">
          <h3 class="section-title">🎭 状态感知</h3>
          <p class="section-desc">桌宠会根据时间、任务、心情自动切换动作和表情</p>
          <div class="form-row">
            <label class="form-label">
              <input type="checkbox" v-model="config.state_awareness_enabled" />
              启用状态感知
            </label>
          </div>
          <div class="form-row">
            <label class="form-label">动作切换间隔: {{ config.action_switch_interval }}秒</label>
            <input type="range" v-model.number="config.action_switch_interval" min="10" max="120" step="5" class="form-range" />
          </div>
        </BaseCard>

        <!-- 当前状态预览 -->
        <BaseCard class="config-section" v-if="currentState">
          <h3 class="section-title">📊 当前状态</h3>
          <div class="state-preview">
            <div class="state-item">
              <span class="state-icon">🕐</span>
              <div>
                <div class="state-label">时间状态</div>
                <div class="state-value">{{ currentState.time_label }}</div>
              </div>
            </div>
            <div class="state-item">
              <span class="state-icon">🎬</span>
              <div>
                <div class="state-label">当前动作</div>
                <div class="state-value">{{ currentState.action_label }}</div>
              </div>
            </div>
            <div class="state-item">
              <span class="state-icon">😊</span>
              <div>
                <div class="state-label">心情状态</div>
                <div class="state-value">{{ currentState.mood_label }}</div>
              </div>
            </div>
            <div class="state-item">
              <span class="state-icon">📋</span>
              <div>
                <div class="state-label">待办任务</div>
                <div class="state-value">{{ currentState.todo_count }}个</div>
              </div>
            </div>
          </div>
          <div v-if="currentState.bubble_text" class="bubble-preview">
            <span class="bubble-icon">💬</span>
            <span>{{ currentState.bubble_text }}</span>
          </div>
          <button class="btn-secondary" @click="fetchState">🔄 刷新状态</button>
        </BaseCard>

        <!-- 时间段说明 -->
        <BaseCard class="config-section">
          <h3 class="section-title">⏰ 时间段动作</h3>
          <div class="time-grid">
            <div class="time-item"><span class="time-range">06:00-09:00</span><span class="time-action">伸懒腰</span></div>
            <div class="time-item"><span class="time-range">09:00-12:00</span><span class="time-action">认真工作</span></div>
            <div class="time-item"><span class="time-range">12:00-14:00</span><span class="time-action">吃饭休息</span></div>
            <div class="time-item"><span class="time-range">14:00-18:00</span><span class="time-action">思考中</span></div>
            <div class="time-item"><span class="time-range">18:00-19:00</span><span class="time-action">放松中</span></div>
            <div class="time-item"><span class="time-range">19:00-23:00</span><span class="time-action">休闲阅读</span></div>
            <div class="time-item"><span class="time-range">23:00-06:00</span><span class="time-action">睡觉/守夜</span></div>
          </div>
        </BaseCard>

        <button class="save-btn" @click="saveConfig">💾 保存设置</button>
      </div>

      <!-- ==================== 语音TTS ==================== -->
      <div v-if="activeTab === 'voice'" class="tab-content">
        <BaseCard class="config-section">
          <h3 class="section-title">🔊 语音TTS</h3>
          <p class="section-desc">桌宠说话时播放语音（使用浏览器内置语音合成）</p>
          <div class="form-row">
            <label class="form-label">
              <input type="checkbox" v-model="config.tts_enabled" />
              启用语音
            </label>
          </div>
          <div class="form-row" v-if="config.tts_enabled">
            <label class="form-label">说话场景</label>
            <select v-model="config.speak_scene" class="form-select">
              <option value="never">从不说话</option>
              <option value="remind">仅提醒时</option>
              <option value="interact">互动时</option>
              <option value="celebrate">庆祝时</option>
              <option value="always">始终说话</option>
            </select>
          </div>
          <div class="form-row" v-if="config.tts_enabled">
            <label class="form-label">语速: {{ config.tts_rate.toFixed(1) }}x</label>
            <input type="range" v-model.number="config.tts_rate" min="0.5" max="2" step="0.1" class="form-range" />
          </div>
          <div class="form-row" v-if="config.tts_enabled">
            <label class="form-label">音调: {{ config.tts_pitch.toFixed(1) }}</label>
            <input type="range" v-model.number="config.tts_pitch" min="0.5" max="2" step="0.1" class="form-range" />
          </div>
          <div class="form-row" v-if="config.tts_enabled">
            <label class="form-label">音量: {{ Math.round(config.tts_volume * 100) }}%</label>
            <input type="range" v-model.number="config.tts_volume" min="0" max="1" step="0.1" class="form-range" />
          </div>
        </BaseCard>

        <BaseCard class="config-section" v-if="config.tts_enabled">
          <h3 class="section-title">🧪 语音测试</h3>
          <input v-model="ttsTestText" class="form-input" placeholder="输入测试文本" />
          <button class="btn-primary" @click="testTTS">▶️ 播放测试</button>
        </BaseCard>

        <button class="save-btn" @click="saveConfig">💾 保存设置</button>
      </div>

      <!-- ==================== 形象管理 ==================== -->
      <div v-if="activeTab === 'avatar'" class="tab-content">
        <div class="content-toolbar">
          <h3 class="section-title" style="margin:0">🎨 形象列表</h3>
          <button class="btn-primary" @click="showAvatarForm = !showAvatarForm">{{ showAvatarForm ? '取消' : '+ 上传形象' }}</button>
        </div>

        <!-- 上传表单 -->
        <BaseCard v-if="showAvatarForm" class="form-card">
          <div class="form-row">
            <input v-model="avatarForm.name" class="form-input" placeholder="形象名称" />
            <select v-model="avatarForm.mode" class="form-select">
              <option value="simple">简单模式（静态+表情）</option>
              <option value="advanced">进阶模式（多帧动作）</option>
            </select>
          </div>
          <input v-model="avatarForm.description" class="form-input" placeholder="描述（可选）" />
          <input v-model="avatarForm.image_url" class="form-input" placeholder="图片URL（可选，后续支持本地上传）" />
          <button class="btn-primary" @click="createAvatar">创建形象</button>
        </BaseCard>

        <div v-if="avatarLoading" class="loading">加载中...</div>
        <div v-else class="avatar-grid">
          <BaseCard
            v-for="av in avatars" :key="av.id"
            class="avatar-card"
            :class="{ active: av.is_active }"
          >
            <div class="avatar-preview">
              <div v-if="av.image_url" class="avatar-image" :style="{ backgroundImage: `url(${av.image_url})` }"></div>
              <div v-else class="avatar-placeholder">
                <span class="placeholder-icon">🐱</span>
              </div>
              <span v-if="av.is_active" class="active-badge">当前使用</span>
            </div>
            <div class="avatar-info">
              <h4 class="avatar-name">{{ av.name }}</h4>
              <p v-if="av.description" class="avatar-desc">{{ av.description }}</p>
              <div class="avatar-meta">
                <span class="tag">{{ av.avatar_type === 'builtin' ? '内置' : '自定义' }}</span>
                <span class="tag">{{ av.mode === 'simple' ? '简单' : '进阶' }}</span>
              </div>
            </div>
            <div class="avatar-actions">
              <button v-if="!av.is_active" class="btn-sm btn-primary" @click="activateAvatar(av.id)">使用</button>
              <button v-if="av.avatar_type === 'custom'" class="btn-sm btn-danger" @click="deleteAvatar(av.id)">删除</button>
            </div>
          </BaseCard>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.pet-page { padding: var(--space-4); display: flex; flex-direction: column; gap: var(--space-4); }
.page-title { font-size: var(--text-2xl); font-weight: 800; color: var(--text-hi); font-family: var(--font-cute); }
.page-sub { color: var(--text-mid); font-size: var(--text-sm); margin-top: 4px; }

.tab-nav { display: flex; gap: var(--space-2); background: var(--bg-panel); padding: 6px; border-radius: var(--radius-lg); border: 1px solid var(--line); width: fit-content; flex-wrap: wrap; }
.tab-btn { display: flex; align-items: center; gap: 6px; padding: 8px 16px; border-radius: var(--radius-md); border: none; background: transparent; color: var(--text-mid); font-size: var(--text-sm); font-weight: 600; cursor: pointer; transition: all 0.2s; &:hover { background: var(--bg-hover); } &.active { background: var(--primary); color: white; box-shadow: 0 2px 8px var(--primary-shadow); } }
.tab-icon { font-size: 16px; }

.loading { text-align: center; padding: var(--space-8); color: var(--text-mid); }
.section-title { font-size: var(--text-base); font-weight: 600; color: var(--text-hi); margin-bottom: 6px; }
.section-desc { font-size: var(--text-sm); color: var(--text-mid); margin-bottom: var(--space-3); }

.btn-primary { padding: 8px 18px; border-radius: var(--radius-md); border: none; background: var(--primary); color: white; font-size: var(--text-sm); font-weight: 600; cursor: pointer; &:hover { opacity: 0.9; } }
.btn-secondary { padding: 8px 18px; border-radius: var(--radius-md); border: 1px solid var(--line); background: var(--bg-panel); color: var(--text-mid); font-size: var(--text-sm); cursor: pointer; margin-top: var(--space-3); }
.btn-sm { padding: 4px 10px; border-radius: var(--radius-sm); border: 1px solid var(--line); background: var(--bg-panel); color: var(--text-mid); font-size: var(--text-xs); cursor: pointer; &.btn-primary { background: var(--primary); color: white; border-color: var(--primary); } &.btn-danger { background: var(--danger, #ff4d4f); color: white; border-color: var(--danger, #ff4d4f); } }

.config-section { padding: var(--space-4); margin-bottom: var(--space-3); }
.form-row { display: flex; gap: var(--space-3); margin-bottom: var(--space-3); align-items: center; flex-wrap: wrap; }
.form-label { font-size: var(--text-sm); color: var(--text-hi); display: flex; align-items: center; gap: 6px; cursor: pointer; }
.form-input, .form-select { flex: 1; min-width: 120px; padding: 8px 12px; border-radius: var(--radius-md); border: 1px solid var(--line); background: var(--bg-input); color: var(--text-hi); font-size: var(--text-sm); }
.form-range { flex: 1; }

.save-btn { width: 100%; padding: 14px; border-radius: var(--radius-md); border: none; background: var(--primary); color: white; font-size: var(--text-base); font-weight: 600; cursor: pointer; &:hover { opacity: 0.9; } }

/* 状态感知 */
.state-preview { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: var(--space-3); margin-bottom: var(--space-3); }
.state-item { display: flex; align-items: center; gap: 10px; padding: var(--space-2); background: var(--bg-hover); border-radius: var(--radius-md); }
.state-icon { font-size: 24px; }
.state-label { font-size: var(--text-xs); color: var(--text-mid); }
.state-value { font-size: var(--text-sm); font-weight: 600; color: var(--text-hi); }
.bubble-preview { display: flex; align-items: center; gap: 8px; padding: var(--space-3); background: var(--primary-soft); border-radius: var(--radius-md); margin-bottom: var(--space-3); font-size: var(--text-sm); color: var(--primary); }
.bubble-icon { font-size: 18px; }

.time-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; }
.time-item { display: flex; justify-content: space-between; padding: 8px 12px; background: var(--bg-hover); border-radius: var(--radius-sm); font-size: var(--text-xs); }
.time-range { color: var(--text-mid); }
.time-action { color: var(--text-hi); font-weight: 600; }

/* 形象管理 */
.content-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-3); }
.form-card { padding: var(--space-4); margin-bottom: var(--space-3); }
.avatar-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: var(--space-3); }
.avatar-card { padding: var(--space-3); text-align: center; &.active { border: 2px solid var(--primary); } }
.avatar-preview { position: relative; width: 100%; height: 120px; margin-bottom: var(--space-2); border-radius: var(--radius-md); overflow: hidden; background: var(--bg-hover); }
.avatar-image { width: 100%; height: 100%; background-size: contain; background-position: center; background-repeat: no-repeat; }
.avatar-placeholder { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; }
.placeholder-icon { font-size: 48px; }
.active-badge { position: absolute; top: 6px; right: 6px; padding: 2px 8px; border-radius: var(--radius-pill); background: var(--primary); color: white; font-size: var(--text-xs); font-weight: 600; }
.avatar-name { font-size: var(--text-base); font-weight: 600; color: var(--text-hi); margin-bottom: 4px; }
.avatar-desc { font-size: var(--text-xs); color: var(--text-mid); margin-bottom: 8px; }
.avatar-meta { display: flex; gap: 6px; justify-content: center; margin-bottom: 10px; }
.tag { display: inline-block; padding: 2px 8px; border-radius: var(--radius-pill); background: var(--primary-soft); color: var(--primary); font-size: var(--text-xs); }
.avatar-actions { display: flex; gap: 6px; justify-content: center; }
</style>
