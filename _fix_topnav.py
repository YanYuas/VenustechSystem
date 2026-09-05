path = r'C:\Users\21722\Desktop\夏令营集训\Venustech System\frontend\src\components\layout\TopNav.vue'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 修正项目导航路由
content = content.replace(
    "{ id: 'projects', label: '项目', icon: 'folder', route: '/tasks?view=project' }",
    "{ id: 'projects', label: '项目', icon: 'folder', route: '/projects' }"
)

# 修正activeId匹配
old_active = '''  if (path.startsWith('/tasks')) return 'today'
  if (path.startsWith('/documents')) return 'learning' '''
new_active = '''  if (path.startsWith('/projects')) return 'projects'
  if (path.startsWith('/tasks')) return 'today'
  if (path.startsWith('/documents')) return 'learning' '''
content = content.replace(old_active, new_active)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('OK: TopNav projects route fixed')
