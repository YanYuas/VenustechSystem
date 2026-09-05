path = r'C:\Users\21722\Desktop\夏令营集训\Venustech System\backend\app\services\dashboard_service.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# 1. 修复 _build_projects 方法，使用真实Project数据
old_build = '''    def _build_projects(self, all_tasks: list) -> ProjectsSection:
        """当前项目：基于 project_tag 聚合（取前3个，复用已查询的任务列表）"""
        project_map: dict[str, list] = {}
        for t in all_tasks:
            if t.project_tag:
                project_map.setdefault(t.project_tag, []).append(t)

        items = []
        for tag, tasks in sorted(project_map.items(), key=lambda x: -len(x[1]))[:3]:
            total = len(tasks)
            done = sum(1 for t in tasks if t.status == "completed")
            progress = round(done / total * 100) if total else 0
            items.append(ProjectItem(
                id=tag,
                name=tag,
                progress=progress,
                task_count=total,
                completed_count=done,
                status="beta",
            ))

        return ProjectsSection(items=items, status="beta")'''

new_build = '''    def _build_projects(self, all_tasks: list) -> ProjectsSection:
        """当前项目：优先使用真实 Project 实体，降级到 project_tag 聚合"""
        try:
            from app.services.project_service import ProjectService
            projects = ProjectService(self.db).list(self.user.id)
            items = []
            for p in projects[:5]:
                items.append(ProjectItem(
                    id=p["id"],
                    name=p["name"],
                    progress=p["progress"],
                    task_count=p["task_count"],
                    completed_count=p["completed_count"],
                    color=p.get("color", "#7c5cff"),
                    status="ready",
                ))
            if items:
                return ProjectsSection(items=items, status="ready")
        except Exception:
            pass

        # 降级：基于 project_tag 聚合
        project_map: dict[str, list] = {}
        for t in all_tasks:
            if t.project_tag:
                project_map.setdefault(t.project_tag, []).append(t)

        items = []
        for tag, tasks in sorted(project_map.items(), key=lambda x: -len(x[1]))[:3]:
            total = len(tasks)
            done = sum(1 for t in tasks if t.status == "completed")
            progress = round(done / total * 100) if total else 0
            items.append(ProjectItem(
                id=tag,
                name=tag,
                progress=progress,
                task_count=total,
                completed_count=done,
                status="beta",
            ))

        return ProjectsSection(items=items, status="beta" if items else "empty")'''

if old_build in content:
    content = content.replace(old_build, new_build)
    changes += 1
    print('OK: _build_projects updated')
else:
    print('SKIP: _build_projects pattern not found')

# 2. 把4个模块的status从planned改为beta
content = content.replace('ResourceCenter(categories=RESOURCE_CATEGORIES, status="planned")',
                          'ResourceCenter(categories=RESOURCE_CATEGORIES, status="beta")')
content = content.replace('LearningSection(status="planned")',
                          'LearningSection(status="beta")')
content = content.replace('LifeSection(categories=LIFE_CATEGORIES, status="planned")',
                          'LifeSection(categories=LIFE_CATEGORIES, status="beta")')
content = content.replace('AssetsSection(categories=ASSET_CATEGORIES, status="planned")',
                          'AssetsSection(categories=ASSET_CATEGORIES, status="beta")')
changes += 4
print('OK: 4 module status changed to beta')

# 3. 修复 new_project 的 action
content = content.replace('action="/tasks?filter=project", status="beta"',
                          'action="/projects", status="ready"')
changes += 1
print('OK: new_project action fixed')

# 4. 修复 modules_status 中的4个模块状态
content = content.replace('ModuleStatusItem(id="resource_center", name="资源中心", status="planned"',
                          'ModuleStatusItem(id="resource_center", name="资源中心", status="beta"')
content = content.replace('ModuleStatusItem(id="learning", name="学习与成长", status="planned"',
                          'ModuleStatusItem(id="learning", name="学习与成长", status="beta"')
content = content.replace('ModuleStatusItem(id="life", name="生活与自我", status="planned"',
                          'ModuleStatusItem(id="life", name="生活与自我", status="beta"')
content = content.replace('ModuleStatusItem(id="assets", name="长期资产库", status="planned"',
                          'ModuleStatusItem(id="assets", name="长期资产库", status="beta"')
changes += 4
print('OK: modules_status updated')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'\\nTotal: {changes} changes applied')
