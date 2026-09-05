path = r'C:\Users\21722\Desktop\夏令营集训\Venustech System\backend\app\services\dashboard_service.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 把4个模块的状态从planned改为beta
content = content.replace('status="planned", description="收集箱/领域库/模板库"', 'status="beta", description="收集箱/领域库/模板库"')
content = content.replace('status="planned", description="学习计划/知识卡片"', 'status="beta", description="学习计划/知识卡片"')
content = content.replace('status="planned", description="健康/精力/习惯追踪"', 'status="beta", description="健康/精力/习惯追踪"')
content = content.replace('status="planned", description="SOP/Prompt/Skill沉淀"', 'status="beta", description="SOP/Prompt/Skill沉淀"')

# 把模块实例的状态也改为beta
content = content.replace('ResourceCenter(categories=RESOURCE_CATEGORIES, status="planned")', 'ResourceCenter(categories=RESOURCE_CATEGORIES, status="beta")')
content = content.replace('LearningSection(status="planned")', 'LearningSection(status="beta")')
content = content.replace('LifeSection(categories=LIFE_CATEGORIES, status="planned")', 'LifeSection(categories=LIFE_CATEGORIES, status="beta")')
content = content.replace('AssetsSection(categories=ASSET_CATEGORIES, status="planned")', 'AssetsSection(categories=ASSET_CATEGORIES, status="beta")')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('OK: dashboard module status changed to beta')
