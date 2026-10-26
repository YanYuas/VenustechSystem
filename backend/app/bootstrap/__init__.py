# ============================================================
# 组合根（Composition Root）
#
# 这是全应用**唯一**允许"知道所有层"的地方：它把 api / services /
# repositories / models / core 装配成一个可运行的应用。
#
# 为什么需要它（历史问题）：
#   事件订阅者（文档保存→AI 摘要、任务完成→通知、成长 EXP 结算）原本住在
#   app/core/ 下，导致「基础设施层 → 业务层」的反向依赖：
#       core/event_handlers.py    -> app.services.ai, app.repositories
#       core/growth_handlers.py   -> app.services.growth_service
#   于是 core/ 不再是可复用的最底层 —— 任何只想用 core（加密/事件/缓存）
#   的代码都会被被动拉起大半个业务层。
#
# 现在 core/ 只依赖 models（纯数据定义），订阅者注册上移到本包：
#   app/bootstrap/event_handlers.py   业务事件订阅（AI 摘要/标签、通知）
#   app/bootstrap/growth_handlers.py  成长体系订阅（EXP/技能归类）
#
# 依赖规则（由 scripts/audit_architecture.py 强制）：
#   core       → core, models        （不得向上）
#   bootstrap  → 任意（组合根特权）
#
# ⚠️ 本包刻意不在 __init__ 里 import 子模块：包导入不应产生副作用。
#    需要哪个装配模块就显式 import 哪个（见 app/main.py）。
#
# 新增启动期逻辑（定时任务、订阅者、迁移钩子）请放这里，不要放 core/。
# ============================================================
