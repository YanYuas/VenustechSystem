path = r'C:\Users\21722\Desktop\夏令营集训\Venustech System\frontend\src\views\Task\TaskListView.vue'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = '''async function loadProjects() {
  try {
    const list = await projectApi.list()
    projects.value = list.map(p => ({ id: p.id, name: p.name, color: p.color }))
  } catch { /* ignore */ }
}'''

new = '''async function loadProjects() {
  try {
    const list = await projectApi.list()
    projects.value = list.map(p => ({ id: p.id, name: p.name, color: p.color }))
  } catch { /* ignore */ }
}

onMounted(() => {
  loadProjects()
  const urlProject = route.query.project_id as string
  if (urlProject) {
    query.value.project_id = urlProject
    fetchTasks()
  }
})'''

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK: onMounted added')
else:
    print('SKIP: pattern not found')
