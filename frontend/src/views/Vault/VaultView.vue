<script setup lang="ts">
// ============================================================
// 保险箱（三期 D · 主密码 + 凭据加密存储）
//
// 状态机：未初始化 → 设置主密码；已初始化未解锁 → 解锁；
// 已解锁 → 凭据 CRUD。明文只在「查看」时按需解密显示。
// 服务重启即自动上锁（后端解锁态只存进程内存）。
// ============================================================
import { onMounted, ref } from 'vue'
import { vaultApi } from '@/api'
import { useIdentity } from '@/composables/useIdentity'
import { useToast } from '@/composables/useToast'
import { useModal } from '@/composables/useModal'
import BaseCard from '@/components/common/BaseCard.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import BaseInput from '@/components/common/BaseInput.vue'
import BaseSelect from '@/components/common/BaseSelect.vue'
import BaseModal from '@/components/common/BaseModal.vue'
import BaseEmpty from '@/components/common/BaseEmpty.vue'
import BaseSkeleton from '@/components/common/BaseSkeleton.vue'
import AppIcon from '@/components/common/AppIcon.vue'
import type { VaultItem, VaultStatus } from '@/types'

const toast = useToast()
const modal = useModal()
const { loadIdentities, identityOptions, colorVar, byId } = useIdentity()

const status = ref<VaultStatus | null>(null)
const loading = ref(true)
const items = ref<VaultItem[]>([])
const itemsLoading = ref(false)

async function loadStatus() {
  loading.value = true
  try {
    status.value = await vaultApi.status()
    if (status.value.unlocked) await loadItems()
  } catch { /* http 层已提示 */ } finally {
    loading.value = false
  }
}
onMounted(() => {
  loadIdentities()
  loadStatus()
})

// ---------- 设置主密码 ----------
const setupPassword = ref('')
const setupPassword2 = ref('')
const settingUp = ref(false)
async function onSetup() {
  if (setupPassword.value.length < 8) return toast.warning('主密码至少 8 位')
  if (setupPassword.value !== setupPassword2.value) return toast.warning('两次输入不一致')
  settingUp.value = true
  try {
    status.value = await vaultApi.setup(setupPassword.value)
    setupPassword.value = ''
    setupPassword2.value = ''
    toast.success('保险箱已创建', '主密码不落盘，请牢记 —— 忘记无法找回')
  } catch { /* http 层已提示 */ } finally {
    settingUp.value = false
  }
}

// ---------- 解锁 ----------
const unlockPassword = ref('')
const unlocking = ref(false)
async function onUnlock() {
  if (!unlockPassword.value) return toast.warning('请输入主密码')
  unlocking.value = true
  try {
    status.value = await vaultApi.unlock(unlockPassword.value)
    unlockPassword.value = ''
    await loadItems()
  } catch { /* http 层已提示 */ } finally {
    unlocking.value = false
  }
}

async function onLock() {
  try {
    status.value = await vaultApi.lock()
    items.value = []
    toast.success('已上锁')
  } catch { /* http 层已提示 */ }
}

// ---------- 凭据 CRUD ----------
const itemOpen = ref(false)
const editing = ref<VaultItem | null>(null)
const form = ref({
  name: '', category: 'login' as 'login' | 'note', username: '', url: '', secret: '', notes: '', identity_id: '',
  action_type: 'none' as 'none' | 'ssh', action_host: '', action_user: '', action_port: '',
})

function openCreate() {
  editing.value = null
  form.value = {
    name: '', category: 'login', username: '', url: '', secret: '', notes: '', identity_id: '',
    action_type: 'none', action_host: '', action_user: '', action_port: '',
  }
  itemOpen.value = true
}

async function openEdit(item: VaultItem) {
  editing.value = item
  let secret = ''
  if (item.has_secret) {
    try {
      secret = (await vaultApi.revealSecret(item.id)).secret ?? ''
    } catch { /* http 层已提示 */ }
  }
  form.value = {
    name: item.name, category: item.category,
    username: item.username ?? '', url: item.url ?? '',
    secret, notes: item.notes ?? '', identity_id: item.identity_id ?? '',
    action_type: item.action_type, action_host: item.action_host ?? '',
    action_user: item.action_user ?? '', action_port: item.action_port ?? '',
  }
  itemOpen.value = true
}

async function onSave() {
  if (!form.value.name.trim()) return toast.warning('请输入名称')
  try {
    const payload = {
      name: form.value.name.trim(),
      category: form.value.category,
      username: form.value.username || undefined,
      url: form.value.url || undefined,
      secret: form.value.secret || undefined,
      notes: form.value.notes || undefined,
      identity_id: form.value.identity_id || undefined,
      action_type: form.value.action_type,
      action_host: form.value.action_host || undefined,
      action_user: form.value.action_user || undefined,
      action_port: form.value.action_port || undefined,
    }
    if (editing.value) await vaultApi.updateItem(editing.value.id, payload)
    else await vaultApi.createItem(payload)
    toast.success(editing.value ? '已保存' : '凭据已加密入库')
    itemOpen.value = false
    await loadItems()
  } catch { /* http 层已提示 */ }
}

async function onRunAction(item: VaultItem) {
  try {
    await vaultApi.runAction(item.id)
    toast.success('终端已打开', 'SSH 会话已按白名单模板建立')
  } catch { /* http 层已提示（含白名单拦截原因） */ }
}

async function onDelete(item: VaultItem) {
  const ok = await modal.confirm({
    title: '删除凭据', message: `确定删除「${item.name}」吗？删除后无法恢复。`, confirmText: '删除',
  })
  if (!ok) return
  try {
    await vaultApi.removeItem(item.id)
    await loadItems()
  } catch { /* http 层已提示 */ }
}

// ---------- 明文查看（唯一出口，看一次显示一次） ----------
const revealed = ref<Record<string, string>>({})

async function toggleReveal(item: VaultItem) {
  if (revealed.value[item.id]) {
    delete revealed.value[item.id]
    return
  }
  try {
    revealed.value[item.id] = (await vaultApi.revealSecret(item.id)).secret ?? '（无）'
  } catch { /* http 层已提示 */ }
}

async function loadItems() {
  itemsLoading.value = true
  try {
    items.value = await vaultApi.items()
  } catch { /* http 层已提示 */ } finally {
    itemsLoading.value = false
  }
}

const identityName = (id: string | null) => byId(id)?.name ?? null
const categoryLabel = (c: string) => (c === 'login' ? '账号' : '笔记')
const categoryOptions = [
  { label: '账号', value: 'login' },
  { label: '笔记', value: 'note' },
]
</script>

<template>
  <div class="vault">
    <div class="vault__head">
      <h1 class="vault__title">保险箱</h1>
      <div v-if="status?.unlocked" class="vault__head-actions">
        <BaseButton variant="primary" icon="plus" @click="openCreate">新增凭据</BaseButton>
        <BaseButton variant="secondary" icon="command" @click="onLock">上锁</BaseButton>
      </div>
    </div>

    <div v-if="loading"><BaseSkeleton variant="list" :rows="4" /></div>

    <!-- 未初始化：设置主密码 -->
    <BaseCard v-else-if="status && !status.configured" title="创建保险箱" icon="command">
      <p class="vault__hint">
        保险箱用<b>主密码</b>加密你的凭据（账号密码、令牌、密钥）。
        主密码不落盘 —— 忘记后<b>无法找回</b>，数据无法解密，请务必牢记。
        密文在磁盘上不可读；解锁状态只存内存，重启即上锁。
      </p>
      <div class="vault__form">
        <input
          v-model="setupPassword" type="password" placeholder="主密码（至少 8 位）"
          class="vault__pwd" @keyup.enter="onSetup"
        />
        <input
          v-model="setupPassword2" type="password" placeholder="再输一遍"
          class="vault__pwd" @keyup.enter="onSetup"
        />
        <BaseButton variant="primary" :loading="settingUp" @click="onSetup">创建保险箱</BaseButton>
      </div>
    </BaseCard>

    <!-- 已初始化未解锁：解锁 -->
    <BaseCard v-else-if="status && !status.unlocked" title="保险箱已上锁" icon="command">
      <p class="vault__hint">{{ status.hint ?? '输入主密码解锁' }}</p>
      <div class="vault__form">
        <input
          v-model="unlockPassword" type="password" placeholder="主密码"
          class="vault__pwd" @keyup.enter="onUnlock"
        />
        <BaseButton variant="primary" :loading="unlocking" @click="onUnlock">解锁</BaseButton>
      </div>
    </BaseCard>

    <!-- 已解锁：凭据列表 -->
    <template v-else>
      <BaseCard>
        <div v-if="itemsLoading"><BaseSkeleton variant="list" :rows="4" /></div>
        <BaseEmpty
          v-else-if="items.length === 0"
          title="还没有凭据"
          description="把账号密码、令牌、密钥放进来 —— 只存密文，明文永不落盘"
        >
          <template #action>
            <BaseButton variant="primary" @click="openCreate">新增凭据</BaseButton>
          </template>
        </BaseEmpty>
        <ul v-else class="vault__list">
          <li v-for="it in items" :key="it.id" class="vault__item">
            <span
              v-if="it.identity_id"
              class="vault__dot" :style="{ background: colorVar(byId(it.identity_id)?.color_token ?? null) }"
            />
            <div class="vault__main">
              <div class="vault__line">
                <b class="vault__name">{{ it.name }}</b>
                <span class="vault__cat">{{ categoryLabel(it.category) }}</span>
                <span v-if="identityName(it.identity_id)" class="vault__cat">
                  {{ identityName(it.identity_id) }}
                </span>
              </div>
              <p v-if="it.username || it.url" class="vault__meta">
                {{ it.username }}<template v-if="it.username && it.url"> · </template>{{ it.url }}
              </p>
              <p v-if="revealed[it.id]" class="vault__secret">{{ revealed[it.id] }}</p>
            </div>
            <div class="vault__ops">
              <button
                v-if="it.action_type === 'ssh'" class="vault__op" title="SSH 连接"
                @click="onRunAction(it)"
              >
                <AppIcon name="send" :size="16" />
              </button>
              <button
                v-if="it.has_secret" class="vault__op" title="查看/隐藏明文"
                @click="toggleReveal(it)"
              >
                <AppIcon :name="revealed[it.id] ? 'eye-off' : 'eye'" :size="16" />
              </button>
              <button class="vault__op" title="编辑" @click="openEdit(it)">
                <AppIcon name="edit" :size="16" />
              </button>
              <button class="vault__op" title="删除" @click="onDelete(it)">
                <AppIcon name="trash" :size="16" />
              </button>
            </div>
          </li>
        </ul>
      </BaseCard>
      <p class="vault__footnote">
        明文只在点击「查看」时按需解密显示；服务重启自动上锁。主密码不落盘，忘记无法找回。
      </p>
    </template>

    <!-- 新建/编辑弹窗 -->
    <BaseModal v-model="itemOpen" :title="editing ? '编辑凭据' : '新增凭据'" @confirm="onSave">
      <div class="vault__form">
        <BaseInput v-model="form.name" placeholder="名称（必填，如：GitHub）" />
        <div class="vault__form-row">
          <BaseSelect v-model="form.category" :options="categoryOptions" />
          <BaseInput v-model="form.username" placeholder="用户名（可选）" />
        </div>
        <BaseInput v-model="form.url" placeholder="网址（可选）" />
        <input v-model="form.secret" type="password" placeholder="密码 / 令牌（可选，只存密文）" class="vault__pwd" />
        <BaseInput v-model="form.notes" placeholder="备注（可选）" />
        <BaseSelect
          v-model="form.identity_id" :options="identityOptions(true)"
          placeholder="所属身份（可选）"
        />
        <!-- 终端动作（D 收尾）：白名单模板 -->
        <div class="vault__form-row">
          <BaseSelect
            v-model="form.action_type"
            :options="[
              { label: '无终端动作', value: 'none' },
              { label: 'SSH 连接', value: 'ssh' },
            ]"
          />
          <BaseInput v-model="form.action_host" placeholder="主机（ssh 动作时必填）" />
        </div>
        <div v-if="form.action_type === 'ssh'" class="vault__form-row">
          <BaseInput v-model="form.action_user" placeholder="用户名（可选）" />
          <BaseInput v-model="form.action_port" placeholder="端口（可选，默认 22）" />
        </div>
        <p v-if="form.action_type === 'ssh'" class="vault__action-hint">
          上方「密码/令牌」栏填<b>密钥文件路径</b>（如 C:\Users\你\.ssh\id_ed25519）。
          连接时会打开终端执行 ssh -i 密钥路径 登录 —— 只支持密钥认证，不支持密码。
        </p>
      </div>
    </BaseModal>
  </div>
</template>

<style scoped lang="scss">
.vault {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-6);
  max-width: 760px;
  margin: 0 auto;
}
.vault__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.vault__head-actions { display: flex; gap: var(--space-2); }
.vault__title {
  margin: 0;
  font-size: var(--text-xl);
  color: var(--text-hi);
}
.vault__hint {
  margin: 0 0 var(--space-3);
  font-size: var(--text-sm);
  color: var(--text-mid);
  line-height: 1.7;
}
.vault__form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.vault__form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}
.vault__action-hint {
  margin: 0;
  font-size: var(--text-xs);
  color: var(--text-mid);
  line-height: 1.7;
}
.vault__pwd {
  height: var(--control-h);
  padding: 0 var(--space-3);
  border: none;
  border-radius: var(--radius-sm);
  background: var(--bg-inset);
  color: var(--text-hi);
  font-size: var(--text-base);
  outline: none;
  &:focus { box-shadow: var(--focus-ring); }
}
.vault__footnote {
  margin: 0;
  font-size: var(--text-xs);
  color: var(--text-low);
  text-align: center;
}

.vault__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.vault__item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--line);
  &:last-child { border-bottom: none; }
}
.vault__dot {
  flex: none;
  width: 9px;
  height: 9px;
  border-radius: var(--radius-pill);
}
.vault__main { flex: 1; min-width: 0; }
.vault__line {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
}
.vault__name {
  font-size: var(--text-sm);
  color: var(--text-hi);
}
.vault__cat {
  font-size: var(--text-xs);
  padding: 1px 8px;
  border-radius: var(--radius-pill);
  background: var(--bg-inset);
  color: var(--text-mid);
}
.vault__meta {
  margin: 2px 0 0;
  font-size: var(--text-xs);
  color: var(--text-low);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.vault__secret {
  margin: var(--space-1) 0 0;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--straw-ink);
  word-break: break-all;
}
.vault__ops { display: flex; gap: var(--space-1); }
.vault__op {
  display: inline-flex;
  padding: 6px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-mid);
  cursor: pointer;
  transition: background-color 0.15s, color 0.15s;
  &:hover { background: var(--bg-inset); color: var(--text-hi); }
}
</style>
