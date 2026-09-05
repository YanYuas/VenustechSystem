import os

path = r'C:\Users\21722\Desktop\夏令营集训\Venustech System\frontend\src\views\Task\TaskListView.vue'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 添加 projectApi 和 useRoute 导入
if 'projectApi' not in content:
    content = content.replace(
        "import { taskApi } from '@/api'",
        "import { taskApi, projectApi } from '@/api'\nimport { useRoute } from 'vue-router'"
    )
    print('OK: imports updated')

# 2. 添加项目列表和路由（在 const toast = useToast() 后面）
if 'projects = ref' not in content:
    content = content.replace(
        "const modal = useModal()",
        """const modal = useModal()
const route = useRoute()

// 项目列表
const projects = ref<Array<{ id: string; name: string; color: string }>>([])
const projectOptions = computed(() => [
  { label: '不归属项目', value: '' },
  ...projects.value.map(p => ({ label: p.name, value: p.id })),
])
async function loadProjects() {
  try {
    const list = await projectApi.list()
    projects.value = list.map(p => ({ id: p.id, name: p.name, color: p.color }))
  } catch { /* ignore */ }
}"""
    )
    print('OK: projects state added')

# 3. 在 onMounted 中加载项目和读取 URL 参数
# 查找 onMounted
if 'loadProjects()' not in content:
    # 查找 fetchTasks 调用位置，在前面添加 loadProjects
    content = content.replace(
        "fetchTasks()",
        "loadProjects()\n  // 从URL读取项目筛选\n  const urlProject = route.query.project_id as string\n  if (urlProject) query.value.project_id = urlProject\n  fetchTasks()",
        1  # 只替换第一个
    )
    print('OK: onMounted updated')

# 4. 修改新建任务表单，添加 project_id
if 'project_id' not in content.split('editForm')[0] if 'editForm' in content else True:
    # 修改新建表单默认值
    content = content.replace(
        "priority: 'medium' as TaskPriority, project_tag: '', due_date: '',",
        "priority: 'medium' as TaskPriority, project_tag: '', project_id: '', due_date: '',"
    )
    # 修改编辑表单赋值
    content = content.replace(
        "project_tag: t.project_tag ?? '', due_date: t.due_date ?? '',",
        "project_tag: t.project_tag ?? '', project_id: t.project_id ?? '', due_date: t.due_date ?? '',"
    )
    # 修改提交时传递 project_id
    content = content.replace(
        "project_tag: editForm.value.project_tag || undefined,\n    due_date",
        "project_tag: editForm.value.project_tag || undefined,\n    project_id: editForm.value.project_id || undefined,\n    due_date"
    )
    print('OK: form project_id added')

# 5. 在模板中替换"项目标签"文本输入为项目下拉选择
if '项目标签' in content:
    content = content.replace(
        '''            <label class="tasks__detail-label">项目标签</label>
            <BaseInput v-model="editForm.project_tag" placeholder="如：工作/学习" />''',
        '''            <label class="tasks__detail-label">归属项目</label>
            <BaseSelect v-model="editForm.project_id" :options="projectOptions" />
            <label class="tasks__detail-label" style="margin-top:8px">项目标签（可选）</label>
            <BaseInput v-model="editForm.project_tag" placeholder="如：工作/学习" />'''
    )
    print('OK: template project select added')

# 6. 在任务卡片中显示项目名称（如果有 project_name）
# 查找 project_tag 显示位置，在后面添加 project_name
if 'project_name' not in content:
    # 在任务卡片的标签区域添加项目名称显示
    # 查找 BaseTag 显示 project_tag 的地方
    old_tag = '''<BaseTag v-if="t.project_tag" :semantic="'default'">{{ t.project_tag }}</BaseTag>'''
    new_tag = '''<BaseTag v-if="t.project_name" :semantic="'lilac'" :style="{ borderColor: projects.find(p=>p.id===t.project_id)?.color }">{{ t.project_name }}</BaseTag>
              <BaseTag v-if="t.project_tag" :semantic="'default'">{{ t.project_tag }}</BaseTag>'''
    if old_tag in content:
        content = content.replace(old_tag, new_tag)
        print('OK: task card project name display added')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('\\n=== 任务页面项目支持改造完成 ===')
