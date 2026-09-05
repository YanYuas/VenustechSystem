import os

base = r'C:\Users\21722\Desktop\夏令营集训\Venustech System\frontend\src'

# 1. 添加路由
path = os.path.join(base, 'app', 'router', 'index.ts')
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

if "'projects'" not in content:
    old = '''        {
          path: 'tasks',
          name: 'tasks',
          component: () => import('@/views/Task/TaskListView.vue'),
          meta: { icon: 'check', title: '任务', crumbs: ['任务'] },
        },'''
    new = '''        {
          path: 'projects',
          name: 'projects',
          component: () => import('@/views/Project/ProjectListView.vue'),
          meta: { icon: 'folder', title: '项目', crumbs: ['项目'] },
        },
        {
          path: 'tasks',
          name: 'tasks',
          component: () => import('@/views/Task/TaskListView.vue'),
          meta: { icon: 'check', title: '任务', crumbs: ['任务'] },
        },'''
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK: router updated with projects route')

# 2. 更新 TopNav 导航
path = os.path.join(base, 'components', 'layout', 'TopNav.vue')
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 检查导航项定义
if 'projects' not in content:
    # 查找导航项数组
    import re
    # 在任务前面添加项目
    old_nav = "{ label: '任务', route: '/tasks', icon: 'check' }"
    new_nav = "{ label: '项目', route: '/projects', icon: 'folder' },\n        { label: '任务', route: '/tasks', icon: 'check' }"
    if old_nav in content:
        content = content.replace(old_nav, new_nav)
        print('OK: TopNav updated with projects nav')
    else:
        print('WARN: TopNav nav pattern not found, checking...')
        # 打印导航相关代码
        for i, line in enumerate(content.split('\\n')):
            if 'label' in line and '任务' in line:
                print(f'  Line {i}: {line.strip()}')

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

print('\\n=== 路由和导航更新完成 ===')
