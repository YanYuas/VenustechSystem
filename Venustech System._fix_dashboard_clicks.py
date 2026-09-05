path = r'C:\Users\21722\Desktop\夏令营集训\Venustech System\frontend\src\views\Dashboard\DashboardView.vue'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# 1. 资源中心：点击跳转到知识模块
if "toast.info('资源中心', '该功能开发中')" in content:
    content = content.replace(
        "@click=\"toast.info('资源中心', '该功能开发中')\"",
        "@click=\"router.push('/documents')\""
    )
    changes += 1

# 2. 学习与成长：进入学习中心跳转到知识模块
if "toast.info('学习中心', '该功能开发中')" in content:
    content = content.replace(
        "@click=\"toast.info('学习中心', '该功能开发中')\"",
        "@click=\"router.push('/documents')\""
    )
    changes += 1

# 3. 生活与自我：点击跳转到任务模块
if "toast.info('生活追踪', '该功能开发中')" in content:
    content = content.replace(
        "@click=\"toast.info('生活追踪', '该功能开发中')\"",
        "@click=\"router.push('/tasks')\""
    )
    changes += 1

# 4. 生活与自我：记录生活跳转到任务模块
if "toast.info('生活记录', '该功能开发中')" in content:
    content = content.replace(
        "@click=\"toast.info('生活记录', '该功能开发中')\"",
        "@click=\"router.push('/tasks')\""
    )
    changes += 1

# 5. 长期资产库：点击跳转到复盘模块
if "toast.info('资产库', '该功能开发中')" in content:
    content = content.replace(
        "@click=\"toast.info('资产库', '该功能开发中')\"",
        "@click=\"router.push('/review')\""
    )
    changes += 1

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'OK: {changes} click handlers updated')
