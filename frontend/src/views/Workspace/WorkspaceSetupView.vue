<script setup lang="ts">
// ============================================================
// 工作区引导向导（三期 C · 可选功能的第一界面）
//
// 设计决策（三期规划 §5.0，勿改方向）：
//   工作区默认关闭、零预设 —— 别人的电脑文件夹结构不同，不存在
//   内置路径。本向导负责"引导部署"：
//     ① 欢迎与说明（这是什么、数据主权承诺）
//     ② 启用功能
//     ③ 选路径：登记现有文件夹 或 按身份生成目录骨架
//        —— 两条路可都走：先登记，再在骨架上补身份文件夹
//     ④ 首次扫描 → 完成
// ============================================================
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { workspaceApi } from '@/api'
import { useIdentity } from '@/composables/useIdentity'
import { useToast } from '@/composables/useToast'
import BaseCard from '@/components/common/BaseCard.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import BaseInput from '@/components/common/BaseInput.vue'
import BaseSelect from '@/components/common/BaseSelect.vue'
import AppIcon from '@/components/common/AppIcon.vue'
import type { WorkspaceRoot } from '@/types'

const router = useRouter()
const toast = useToast()
const { loadIdentities, activeIdentities } = useIdentity()

const step = ref(1)
const enabled = ref(false)
const roots = ref<WorkspaceRoot[]>([])
const enabling = ref(false)

// ---------- 步骤②：启用 ----------
async function enable() {
  enabling.value = true
  try {
    await workspaceApi.setEnabled(true)
    enabled.value = true
    toast.success('工作区已启用', '下一步：告诉启明星你的文件夹在哪')
    step.value = 3
  } catch { /* http 层已提示 */ } finally {
    enabling.value = false
  }
}

// ---------- 步骤③a：登记现有文件夹 ----------
const rootPath = ref('')
const rootLabel = ref('')
const registering = ref(false)

async function registerRoot() {
  const p = rootPath.value.trim()
  if (!p) return toast.warning('请输入文件夹的完整路径（绝对路径）')
  registering.value = true
  try {
    const root = await workspaceApi.registerRoot(p, rootLabel.value.trim() || undefined)
    toast.success('已登记', root.path)
    roots.value = await workspaceApi.roots()
    rootPath.value = ''
    rootLabel.value = ''
  } catch { /* http 层已提示（含安全拦截原因） */ } finally {
    registering.value = false
  }
}

// ---------- 步骤③b：按身份生成目录骨架 ----------
const skeletonTarget = ref('')
const skeletonOptions = computed(() =>
  roots.value.map((r) => ({
    label: r.label ? `${r.label}（${r.path}）` : r.path,
    value: r.id,
  })),
)
const skeletonRunning = ref(false)
const skeletonResult = ref<{ created: string[]; skipped: string[] } | null>(null)

async function buildSkeleton() {
  if (!skeletonTarget.value) return toast.warning('请选择一个已登记的根')
  if (activeIdentities.value.length === 0) {
    return toast.warning('还没有活跃身份', '先去「身份管理」建立身份，再生成骨架')
  }
  skeletonRunning.value = true
  skeletonResult.value = null
  try {
    const res = await workspaceApi.buildSkeleton(skeletonTarget.value)
    skeletonResult.value = { created: res.created, skipped: res.skipped }
    roots.value = await workspaceApi.roots()
    if (res.created.length) toast.success(`已创建 ${res.created.length} 个身份文件夹`)
    else toast.info('没有需要创建的文件夹', '同名文件夹已存在，均已跳过')
  } catch { /* http 层已提示 */ } finally {
    skeletonRunning.value = false
  }
}

// ---------- 步骤④：扫描 ----------
const scanningId = ref('')
async function scan(root: WorkspaceRoot) {
  scanningId.value = root.id
  try {
    const updated = await workspaceApi.scan(root.id)
    roots.value = roots.value.map((r) => (r.id === root.id ? updated : r))
    toast.success('扫描完成', `${updated.file_count} 个条目已索引（噪声已过滤）`)
  } catch { /* http 层已提示 */ } finally {
    scanningId.value = ''
  }
}

function finish() {
  router.push('/workspace')
}

const canFinish = computed(() => roots.value.length > 0)

onMounted(async () => {
  loadIdentities()
  try {
    const status = await workspaceApi.status()
    enabled.value = status.enabled
    if (status.enabled) step.value = 3
    roots.value = await workspaceApi.roots()
  } catch { /* http 层已提示 */ }
})

function formatSize(n: number) {
  if (n < 1024) return `${n} B`
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 ** 2).toFixed(1)} MB`
}
</script>

<template>
  <div class="wsetup">
    <div class="wsetup__head">
      <h1 class="wsetup__title">工作区 · 引导设置</h1>
      <div class="wsetup__steps">
        <span
          v-for="n in 4" :key="n"
          class="wsetup__step" :class="{ 'is-active': step === n, 'is-done': step > n }"
        >{{ n }}</span>
      </div>
    </div>

    <!-- ① 欢迎与说明 -->
    <BaseCard v-if="step === 1">
      <div class="wsetup__welcome">
        <AppIcon name="folder" :size="40" />
        <h2>把启明星连到你的文件夹</h2>
        <p>
          工作区让启明星<b>索引</b>你电脑上的真实文件夹（比如 AI 研究、音乐各自的目录），
          让档案、任务和磁盘上的产出对得上号，还能一键在文件夹里打开终端。
        </p>
        <p class="wsetup__promise">
          🤝 两条承诺：只记录路径和大小，<b>绝不读取或复制文件内容</b>；
          目录结构由你自己决定 —— 本向导会引导你建立，不会替你假设任何路径。
        </p>
        <BaseButton variant="primary" @click="step = 2">开始设置</BaseButton>
      </div>
    </BaseCard>

    <!-- ② 启用 -->
    <BaseCard v-else-if="step === 2">
      <h2 class="wsetup__h2">启用工作区功能</h2>
      <p class="wsetup__hint">随时可以在设置里停用；停用不会删除任何已索引数据。</p>
      <BaseButton variant="primary" :loading="enabling" @click="enable">启用</BaseButton>
    </BaseCard>

    <!-- ③ 选路径 -->
    <template v-else-if="step === 3">
      <BaseCard title="路径 A · 登记现有文件夹" icon="folder">
        <p class="wsetup__hint">
          输入你电脑上已有的文件夹完整路径（例如 D:\Projects 或 C:\Users\你\Documents）。
          必须是绝对路径；盘符根目录（如 D:\）不允许登记。
        </p>
        <div class="wsetup__row">
          <BaseInput v-model="rootPath" placeholder="文件夹完整路径，如 D:\Projects" />
          <BaseInput v-model="rootLabel" placeholder="备注名（可选，如：项目盘）" />
          <BaseButton variant="primary" :loading="registering" @click="registerRoot">登记</BaseButton>
        </div>

        <div v-if="roots.length" class="wsetup__roots">
          <div v-for="r in roots" :key="r.id" class="wsetup__root">
            <AppIcon name="folder" :size="15" />
            <span class="wsetup__root-path">{{ r.label ?? r.path }}</span>
            <span class="wsetup__root-meta">{{ r.path }}</span>
          </div>
        </div>
      </BaseCard>

      <BaseCard title="路径 B · 按身份生成目录骨架" icon="spark">
        <p class="wsetup__hint">
          在选定的根下，为你的每个<b>活跃身份</b>创建一个同名文件夹
          （比如身份是「AI 研究」就建「AI 研究」文件夹）——
          一重身份一个抽屉，和磁盘上的产出对应起来。已存在的同名文件夹会跳过，可放心执行。
        </p>
        <div v-if="roots.length === 0" class="wsetup__hint">请先用「路径 A」登记至少一个文件夹。</div>
        <div v-else class="wsetup__row">
          <BaseSelect
            v-model="skeletonTarget"
            :options="skeletonOptions"
            placeholder="选择一个已登记的根"
          />
          <BaseButton variant="secondary" :loading="skeletonRunning" @click="buildSkeleton">
            生成骨架
          </BaseButton>
        </div>
        <div v-if="skeletonResult" class="wsetup__skeleton-result">
          <p v-if="skeletonResult.created.length">✅ 已创建：{{ skeletonResult.created.join('、') }}</p>
          <p v-if="skeletonResult.skipped.length">↩️ 已存在跳过：{{ skeletonResult.skipped.join('、') }}</p>
        </div>
      </BaseCard>

      <div class="wsetup__nav">
        <BaseButton variant="primary" :disabled="!canFinish" @click="step = 4">
          下一步：扫描
        </BaseButton>
      </div>
    </template>

    <!-- ④ 扫描并完成 -->
    <template v-else>
      <BaseCard title="建立索引" icon="search">
        <p class="wsetup__hint">
          对每个根做一次扫描：过滤噪声（node_modules、venv、.git 等），只记录路径、大小、时间。
        </p>
        <div class="wsetup__roots">
          <div v-for="r in roots" :key="r.id" class="wsetup__root">
            <AppIcon name="folder" :size="15" />
            <span class="wsetup__root-path">{{ r.label ?? r.path }}</span>
            <span class="wsetup__root-meta">
              {{ r.scan_status === 'ok' ? `已索引 ${r.file_count} 项 · ${formatSize(r.total_size)}` : '未扫描' }}
            </span>
            <BaseButton
              size="sm" variant="secondary"
              :loading="scanningId === r.id"
              @click="scan(r)"
            >{{ r.scan_status === 'ok' ? '重新扫描' : '扫描' }}</BaseButton>
          </div>
        </div>
      </BaseCard>
      <div class="wsetup__nav">
        <BaseButton variant="primary" icon="check" :disabled="!canFinish" @click="finish">
          完成设置，进入工作区
        </BaseButton>
      </div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.wsetup {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-6);
  max-width: 760px;
  margin: 0 auto;
}
.wsetup__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.wsetup__title {
  margin: 0;
  font-size: var(--text-xl);
  color: var(--text-hi);
}
.wsetup__steps { display: flex; gap: var(--space-2); }
.wsetup__step {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: var(--radius-pill);
  background: var(--bg-inset);
  color: var(--text-low);
  font-size: var(--text-xs);
  &.is-active { background: var(--primary); color: var(--on-primary); }
  &.is-done { background: var(--primary-soft); color: var(--primary-ink); }
}
.wsetup__welcome {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-3);
  color: var(--text-mid);
  h2 { margin: 0; color: var(--text-hi); }
  p { margin: 0; line-height: 1.7; font-size: var(--text-sm); }
}
.wsetup__promise {
  padding: var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--mint-soft);
  color: var(--text-hi);
}
.wsetup__h2 { margin: 0 0 var(--space-2); font-size: var(--text-base); color: var(--text-hi); }
.wsetup__hint {
  margin: 0 0 var(--space-3);
  font-size: var(--text-sm);
  color: var(--text-mid);
  line-height: 1.7;
}
.wsetup__row {
  display: grid;
  grid-template-columns: 2fr 1fr auto;
  gap: var(--space-3);
  align-items: center;
}
.wsetup__roots {
  margin-top: var(--space-3);
  display: flex;
  flex-direction: column;
}
.wsetup__root {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--line);
  color: var(--text-mid);
  &:last-child { border-bottom: none; }
}
.wsetup__root-path {
  font-size: var(--text-sm);
  color: var(--text-hi);
}
.wsetup__root-meta {
  margin-left: auto;
  font-size: var(--text-xs);
  color: var(--text-low);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 45%;
}
.wsetup__skeleton-result {
  margin-top: var(--space-3);
  font-size: var(--text-sm);
  color: var(--text-hi);
  p { margin: var(--space-1) 0; }
}
.wsetup__nav {
  display: flex;
  justify-content: flex-end;
}
</style>
