<script setup lang="ts">
// ============================================================
// 身份管理（三期 B · 横切标签）
//
// 身份不是第五个模块，是所有记录共用的分类轴。本页负责：
// 建 / 改 / 归档 / 排序 / 删。任务、文档、日记等在使用侧挂身份。
// ============================================================
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { identityApi } from '@/api'
import { useIdentity } from '@/composables/useIdentity'
import { useToast } from '@/composables/useToast'
import { useModal } from '@/composables/useModal'
import BaseCard from '@/components/common/BaseCard.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import BaseInput from '@/components/common/BaseInput.vue'
import BaseSelect from '@/components/common/BaseSelect.vue'
import BaseSwitch from '@/components/common/BaseSwitch.vue'
import BaseModal from '@/components/common/BaseModal.vue'
import BaseEmpty from '@/components/common/BaseEmpty.vue'
import AppIcon from '@/components/common/AppIcon.vue'
import type { Identity } from '@/types'

const toast = useToast()
const modal = useModal()
const router = useRouter()
const { identities, loadIdentities, colorVar } = useIdentity()

const loading = ref(true)

async function load() {
  loading.value = true
  try {
    await loadIdentities(true) // force：管理页要求看到别处刚建的
  } finally {
    loading.value = false
  }
}
onMounted(load)

// ---------- 调色板 / 图标（与后端白名单一致） ----------
const COLOR_OPTIONS = [
  { label: '启明粉', value: 'primary' },
  { label: '薄荷绿', value: 'mint' },
  { label: '奶黄', value: 'butter' },
  { label: '云朵蓝', value: 'sky' },
  { label: '淡紫', value: 'lilac' },
  { label: '草莓红', value: 'strawberry' },
  { label: '星尘金', value: 'gold' },
]
const ICON_OPTIONS = ['spark', 'star', 'heart', 'book', 'target', 'chart', 'sun', 'moon', 'doc', 'folder', 'command', 'flame', 'user', 'calendar', 'cloud', 'owl']

// ---------- 新建 ----------
const createOpen = ref(false)
const form = ref({ name: '', slug: '', color_token: 'primary', icon: 'spark', description: '' })

/** 中文名 → 默认 slug（取 ASCII 字符；纯中文则留空要求手填） */
function autoSlug() {
  const ascii = form.value.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
  if (ascii) form.value.slug = ascii
}

async function onCreate() {
  const name = form.value.name.trim()
  const slug = form.value.slug.trim()
  if (!name) return toast.warning('请输入身份名称')
  if (!slug) return toast.warning('请输入标识（slug），用于稳定的筛选与跳转')
  try {
    await identityApi.create({
      name, slug,
      color_token: form.value.color_token,
      icon: form.value.icon,
      description: form.value.description || undefined,
      sort_order: identities.value.length,
    })
    toast.success('身份已创建', '新建任务/文档时即可选择它')
    createOpen.value = false
    form.value = { name: '', slug: '', color_token: 'primary', icon: 'spark', description: '' }
    await loadIdentities(true)
  } catch { /* http 层已提示 */ }
}

// ---------- 编辑 ----------
const editOpen = ref(false)
const editing = ref<Identity | null>(null)
const editForm = ref({ name: '', color_token: 'primary', icon: 'spark', description: '', sort_order: 0, is_active: true })

function openEdit(i: Identity) {
  editing.value = i
  editForm.value = {
    name: i.name,
    color_token: i.color_token,
    icon: i.icon,
    description: i.description ?? '',
    sort_order: i.sort_order,
    is_active: i.is_active,
  }
  editOpen.value = true
}

async function onSave() {
  if (!editing.value) return
  try {
    await identityApi.update(editing.value.id, {
      name: editForm.value.name.trim() || undefined,
      color_token: editForm.value.color_token,
      icon: editForm.value.icon,
      description: editForm.value.description || undefined,
      sort_order: editForm.value.sort_order,
      is_active: editForm.value.is_active,
    })
    toast.success('已保存')
    editOpen.value = false
    await loadIdentities(true)
  } catch { /* http 层已提示 */ }
}

async function onDelete(i: Identity) {
  const ok = await modal.confirm({
    title: '删除身份',
    message: `确定删除「${i.name}」吗？它名下的任务/文档不会被删除，只是变回「未归类」。`,
    confirmText: '删除',
  })
  if (!ok) return
  try {
    await identityApi.remove(i.id)
    toast.success('身份已删除')
    await loadIdentities(true)
  } catch { /* http 层已提示 */ }
}
</script>

<template>
  <div class="identity">
    <div class="identity__head">
      <h1 class="identity__title">身份</h1>
      <BaseButton variant="primary" icon="plus" @click="createOpen = true">新建身份</BaseButton>
    </div>

    <p class="identity__intro">
      身份是你人生的分类轴：AI 研究、音乐、交易……都各自是一条线。
      挂上身份的任务 / 文档 / 日记，在筛选器里可以按线查看 ——
      这样才能一眼看出「我在推进哪一条」，而不是面对一锅待办。
    </p>

    <BaseCard>
      <div v-if="loading" class="identity__loading">加载中…</div>
      <BaseEmpty
        v-else-if="identities.length === 0"
        description="还没有身份。建议先建 3~5 个当前真正在投入的，别一次建太多。"
      />
      <ul v-else class="identity__list">
        <li
          v-for="i in identities" :key="i.id"
          class="identity__item"
          :class="{ 'is-archived': !i.is_active }"
        >
          <span class="identity__dot" :style="{ background: colorVar(i.color_token) }" />
          <div class="identity__main">
            <div class="identity__name-row">
              <AppIcon :name="i.icon" :size="15" />
              <span class="identity__name">{{ i.name }}</span>
              <span class="identity__slug">{{ i.slug }}</span>
              <span v-if="!i.is_active" class="identity__archived-tag">已归档</span>
            </div>
            <p v-if="i.description" class="identity__desc">{{ i.description }}</p>
          </div>
          <div class="identity__ops">
            <button
              class="identity__op"
              :title="`查看「${i.name}」的经历时间线`"
              @click="router.push({ path: '/experience', query: { identity_id: i.id } })"
            >
              <AppIcon name="book" :size="16" />
            </button>
            <button class="identity__op" title="编辑" @click="openEdit(i)">
              <AppIcon name="edit" :size="16" />
            </button>
            <button class="identity__op" title="删除" @click="onDelete(i)">
              <AppIcon name="trash" :size="16" />
            </button>
          </div>
        </li>
      </ul>
    </BaseCard>

    <!-- 新建弹窗 -->
    <BaseModal v-model="createOpen" title="新建身份" @confirm="onCreate">
      <div class="identity__form">
        <BaseInput v-model="form.name" placeholder="名称（如：AI 研究）" @update:model-value="autoSlug" />
        <BaseInput v-model="form.slug" placeholder="标识 slug（小写字母/数字/连字符，创建后不可改）" />
        <div class="identity__form-row">
          <BaseSelect v-model="form.color_token" :options="COLOR_OPTIONS" placeholder="颜色" />
          <BaseSelect
            v-model="form.icon"
            :options="ICON_OPTIONS.map(n => ({ label: n, value: n }))"
            placeholder="图标"
          />
        </div>
        <BaseInput v-model="form.description" placeholder="一句话描述（可选）" />
      </div>
    </BaseModal>

    <!-- 编辑弹窗 -->
    <BaseModal v-model="editOpen" title="编辑身份" @confirm="onSave">
      <div v-if="editing" class="identity__form">
        <div class="identity__preview">
          <span class="identity__dot" :style="{ background: colorVar(editForm.color_token) }" />
          <AppIcon :name="editForm.icon" :size="16" />
          <span class="identity__name">{{ editForm.name || editing.name }}</span>
        </div>
        <BaseInput v-model="editForm.name" placeholder="名称" />
        <div class="identity__form-row">
          <BaseSelect v-model="editForm.color_token" :options="COLOR_OPTIONS" placeholder="颜色" />
          <BaseSelect
            v-model="editForm.icon"
            :options="ICON_OPTIONS.map(n => ({ label: n, value: n }))"
            placeholder="图标"
          />
        </div>
        <BaseInput v-model="editForm.description" placeholder="一句话描述（可选）" />
        <div class="identity__form-row">
          <label class="identity__field">排序
            <input
              v-model.number="editForm.sort_order"
              type="number"
              class="identity__sort"
            />
          </label>
          <label class="identity__field identity__field--switch">
            启用
            <BaseSwitch v-model="editForm.is_active" />
          </label>
        </div>
      </div>
    </BaseModal>
  </div>
</template>

<style scoped lang="scss">
.identity {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-6);
}
.identity__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.identity__title {
  margin: 0;
  font-size: var(--text-xl);
  color: var(--text-hi);
}
.identity__intro {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--text-mid);
  line-height: 1.7;
}
.identity__loading {
  color: var(--text-mid);
  font-size: var(--text-sm);
}

.identity__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.identity__item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--line);
  &:last-child { border-bottom: none; }
  &.is-archived { opacity: 0.55; }
}
.identity__dot {
  flex: none;
  width: 12px;
  height: 12px;
  border-radius: var(--radius-pill);
}
.identity__main {
  flex: 1;
  min-width: 0;
}
.identity__name-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-mid);
}
.identity__name {
  font-size: var(--text-base);
  color: var(--text-hi);
}
.identity__slug {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-low);
}
.identity__archived-tag {
  padding: 1px 8px;
  border-radius: var(--radius-pill);
  background: var(--bg-inset);
  font-size: var(--text-xs);
  color: var(--text-mid);
}
.identity__desc {
  margin: var(--space-1) 0 0;
  font-size: var(--text-xs);
  color: var(--text-mid);
}
.identity__ops {
  display: flex;
  gap: var(--space-1);
}
.identity__op {
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

.identity__form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.identity__form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
  align-items: center;
}
.identity__preview {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--bg-inset);
  color: var(--text-mid);
}
.identity__field {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-mid);
  &--switch { justify-content: flex-end; }
}
.identity__sort {
  width: 72px;
  height: var(--control-h);
  padding: 0 var(--space-2);
  border: none;
  border-radius: var(--radius-sm);
  background: var(--bg-inset);
  color: var(--text-hi);
  font-size: var(--text-sm);
  outline: none;
}
</style>
