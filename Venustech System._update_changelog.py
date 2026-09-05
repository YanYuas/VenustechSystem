path = r'C:\Users\21722\Desktop\夏令营集训\Venustech System\CHANGELOG.md'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = '''## [Unreleased]

### Added
- **后端骨架 v0.1**'''

new = '''## [Unreleased]

### Added
- **一期完善（v0.1.70+）**：2026-09-04
  - **项目管理模块**：真正的项目实体（Project模型+迁移+Repository+Service+API 5端点），任务通过project_id外键归属项目，项目管理页面（列表/创建/编辑/删除+8色选择+进度条+状态标签），任务创建/编辑下拉选择项目，首页项目卡片点击跳转项目筛选视图
  - **第二分身无Key降级**：未配置API Key时自动切换到本地规则模式，基于关键词匹配给出有用回复并引导配置API Key，支持打字机效果
  - **提醒到期通知**：useReminderWatcher每30秒轮询检查到期提醒，触发桌面通知（Notification API）+应用内toast+系统通知栏消息，自动标记为已触发
  - **首页灰度模块可用化**：资源中心/学习与成长/生活与自我/长期资产库4个模块点击跳转对应已有模块，不再死链
- **后端骨架 v0.1**'''

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK: CHANGELOG updated')
else:
    print('SKIP: pattern not found')
