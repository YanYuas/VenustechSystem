path = r'C:\Users\21722\Desktop\夏令营集训\Venustech System\backend\app\services\dashboard_service.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = '''    def _build_projects(self, all_tasks: list) -> ProjectsSection:
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

new = '''    def _build_projects(self, all_tasks: list) -> ProjectsSection:
        """当前项目：优先使用真实 Project 实体，降级到 project_tag 聚合"""
        from app.services.project_service import ProjectService
        try:
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

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK: dashboard_service.py updated to use real projects')
else:
    print('SKIP: pattern not found')
