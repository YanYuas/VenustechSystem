# ============================================================
# 第二分身 Service（二期 P1）
# 长期记忆 + 灵感工作流 + 五档配置
# ============================================================
from __future__ import annotations

import logging
import uuid
from sqlalchemy.orm import Session

from app.core.event_bus import event_bus
from app.core.exceptions import ValidationException
from app.repositories.avatar_repo import AvatarMemoryRepository, AvatarInspirationRepository, AvatarConfigRepository
from app.repositories.identity_repo import IdentityRepository
from app.schemas.avatar import CreateMemoryRequest, GenerateInspirationRequest, UpdateConfigRequest

logger = logging.getLogger("app.avatar")

EVENT_INSPIRATION_GENERATED = "inspiration.generated"
EVENT_INSPIRATION_EXECUTED = "inspiration.executed"
EVENT_MEMORY_UPDATED = "avatar.memory.updated"

# 灵感模板库（无AI时的模板化生成）
INSPIRATION_TEMPLATES = {
    "学习": [
        {"title": "构建知识图谱", "description": "将当前学习领域的知识点整理为可视化知识图谱，发现薄弱环节", "value": "高"},
        {"title": "费曼学习法实践", "description": "用自己的话讲解最近学的概念，录制音频回听找漏洞", "value": "中"},
        {"title": "间隔重复优化", "description": "分析复习数据，调整SM-2参数，提升记忆效率", "value": "中"},
        {"title": "跨领域联想", "description": "寻找当前领域与其他学科的共通原理，深化理解", "value": "高"},
    ],
    "开发": [
        {"title": "代码质量审计", "description": "对近期代码进行静态分析+人工审查，沉淀编码规范", "value": "高"},
        {"title": "架构重构机会", "description": "识别模块间耦合点，设计解耦方案，提升可维护性", "value": "高"},
        {"title": "性能瓶颈排查", "description": "用性能分析工具定位慢查询/大组件，制定优化计划", "value": "中"},
        {"title": "文档补全计划", "description": "扫描缺失文档的模块，制定文档补全优先级", "value": "低"},
    ],
    "写作": [
        {"title": "人物深度挖掘", "description": "为核心人物撰写2000字小传，包含童年阴影和核心欲望", "value": "高"},
        {"title": "伏笔回收检查", "description": "列出所有已埋伏笔，制定回收时间表，避免烂尾", "value": "高"},
        {"title": "节奏分析调整", "description": "统计每章字数和冲突密度，调整快慢节奏", "value": "中"},
        {"title": "世界观补全", "description": "为故事世界补充经济体系/社会结构/历史事件", "value": "中"},
    ],
    "通用": [
        {"title": "周复盘深化", "description": "回顾本周数据，提炼3条可执行改进项，写入下周计划", "value": "中"},
        {"title": "习惯联动设计", "description": "将两个已有习惯绑定（如跑步后听英语），提升坚持率", "value": "中"},
        {"title": "工具链优化", "description": "评估当前使用的工具，寻找替代或整合方案，提升效率", "value": "低"},
        {"title": "知识资产盘点", "description": "整理所有文档/笔记/模板，分类归档，建立索引", "value": "中"},
    ],
}


class AvatarService:
    """第二分身 业务逻辑层"""

    def __init__(self, db: Session):
        self.db = db
        self.logger = logger
        self.memory_repo = AvatarMemoryRepository(db)
        self.inspiration_repo = AvatarInspirationRepository(db)
        self.config_repo = AvatarConfigRepository(db)

    # ==================== 长期记忆 ====================

    def list_memories(self, user_id: str, memory_type: str | None = None,
                      page: int = 1, page_size: int = 20) -> dict:
        filters = {"user_id": user_id}
        if memory_type:
            filters["memory_type"] = memory_type
        items, total = self.memory_repo.paginate(page=page, page_size=page_size, **filters)
        return {"list": [self._memory_to_dict(m) for m in items], "total": total, "page": page, "page_size": page_size}

    def create_memory(self, user_id: str, data: CreateMemoryRequest) -> dict:
        if data.identity_id is not None:
            # 身份轴写入前校验（三期 B）：identity_id 无外键约束，归属在此把关
            identity = IdentityRepository(self.db).get(data.identity_id)
            if identity is None or identity.user_id != user_id or identity.deleted_at is not None:
                raise ValidationException("身份不存在")
        memory = self.memory_repo.create(user_id=user_id, **data.model_dump(exclude_none=True))
        event_bus.publish(EVENT_MEMORY_UPDATED, memory_id=memory.id, action="create")
        self.logger.info(f"记忆创建: {memory.id} ({memory.memory_type})")
        return self._memory_to_dict(memory)

    def update_memory(self, memory_id: str, data: dict) -> dict:
        memory = self.memory_repo.get_or_404(memory_id)
        update_data = {k: v for k, v in data.items() if v is not None}
        updated = self.memory_repo.update(memory, **update_data)
        return self._memory_to_dict(updated)

    def delete_memory(self, memory_id: str) -> None:
        memory = self.memory_repo.get_or_404(memory_id)
        self.memory_repo.delete(memory)

    def verify_memory(self, memory_id: str, verified: bool = True) -> dict:
        memory = self.memory_repo.get_or_404(memory_id)
        updated = self.memory_repo.update(memory, is_verified=verified)
        return self._memory_to_dict(updated)

    def get_memory_stats(self, user_id: str) -> dict:
        """记忆统计：按类型分组计数"""
        all_memories = self.memory_repo.list(user_id=user_id, limit=1000)
        stats = {"profile": 0, "knowledge": 0, "event": 0, "relation": 0, "total": 0, "verified": 0}
        for m in all_memories:
            stats[m.memory_type] = stats.get(m.memory_type, 0) + 1
            stats["total"] += 1
            if m.is_verified:
                stats["verified"] += 1
        return stats

    # ==================== 灵感工作流 ====================

    def generate_inspirations(self, user_id: str, data: GenerateInspirationRequest) -> dict:
        """
        生成灵感（模板化，后续可接入AI）
        一次生成count个灵感方向
        """
        domain = data.domain or "通用"
        templates = INSPIRATION_TEMPLATES.get(domain, INSPIRATION_TEMPLATES["通用"])
        batch_id = str(uuid.uuid4())

        # 取前count个（或循环取）
        selected = []
        for i in range(data.count):
            tpl = templates[i % len(templates)]
            inspiration = self.inspiration_repo.create(
                user_id=user_id,
                title=tpl["title"],
                description=tpl["description"],
                domain=domain,
                estimated_value=tpl["value"],
                status="generated",
                batch_id=batch_id,
                source_type=data.source_type,
            )
            selected.append(self._inspiration_to_dict(inspiration))

        event_bus.publish(EVENT_INSPIRATION_GENERATED, batch_id=batch_id, count=len(selected))
        self.logger.info(f"灵感生成: batch={batch_id}, {len(selected)}个")
        return {"batch_id": batch_id, "inspirations": selected, "count": len(selected)}

    def list_inspirations(self, user_id: str, status: str | None = None,
                          page: int = 1, page_size: int = 20) -> dict:
        filters = {"user_id": user_id}
        if status:
            filters["status"] = status
        items, total = self.inspiration_repo.paginate(page=page, page_size=page_size, **filters)
        return {"list": [self._inspiration_to_dict(i) for i in items], "total": total, "page": page, "page_size": page_size}

    def select_inspiration(self, inspiration_id: str) -> dict:
        """选择灵感方向，生成详细提示词"""
        insp = self.inspiration_repo.get_or_404(inspiration_id)
        # 生成详细提示词（模板化）
        prompt = self._build_prompt(insp)
        updated = self.inspiration_repo.update(insp, status="selected", prompt=prompt)
        return self._inspiration_to_dict(updated)

    def execute_inspiration(self, inspiration_id: str, result: str | None = None) -> dict:
        """执行灵感（标记完成，保存结果）"""
        insp = self.inspiration_repo.get_or_404(inspiration_id)
        updated = self.inspiration_repo.update(
            insp, status="completed", result=result or "已执行"
        )
        event_bus.publish(EVENT_INSPIRATION_EXECUTED, inspiration_id=inspiration_id)
        return self._inspiration_to_dict(updated)

    def feedback_inspiration(self, inspiration_id: str, feedback: str) -> dict:
        """灵感反馈：useful/useless/normal"""
        insp = self.inspiration_repo.get_or_404(inspiration_id)
        updated = self.inspiration_repo.update(insp, feedback=feedback)
        return self._inspiration_to_dict(updated)

    def discard_inspiration(self, inspiration_id: str) -> dict:
        insp = self.inspiration_repo.get_or_404(inspiration_id)
        updated = self.inspiration_repo.update(insp, status="discarded")
        return self._inspiration_to_dict(updated)

    def _build_prompt(self, insp) -> str:
        """根据灵感生成详细提示词"""
        return (
            f"# 角色设定\n你是一位资深的{insp.domain or '通用'}领域专家，有10年以上实践经验。\n\n"
            f"# 任务描述\n请围绕「{insp.title}」这个方向，提供详细的执行方案。\n\n"
            f"# 背景\n{insp.description}\n\n"
            f"# 约束条件\n- 方案必须具体可执行，不泛泛而谈\n- 分阶段说明，每阶段有明确产出\n- 考虑时间和资源限制\n\n"
            f"# 输出格式\n1. 目标拆解（3-5个阶段性目标）\n2. 执行步骤（每步含具体动作和时间预估）\n3. 所需资源/工具\n4. 风险与应对\n5. 验收标准"
        )

    # ==================== 配置管理 ====================

    def get_config(self, user_id: str) -> dict:
        config = self.config_repo.get_by_user(user_id)
        if not config:
            # 自动创建默认配置
            config = self.config_repo.create(user_id=user_id)
        return self._config_to_dict(config)

    def update_config(self, user_id: str, data: UpdateConfigRequest) -> dict:
        config = self.config_repo.get_by_user(user_id)
        if not config:
            config = self.config_repo.create(user_id=user_id)
        update_data = {k: v for k, v in data.model_dump(exclude_none=True).items()}
        updated = self.config_repo.update(config, **update_data)
        self.logger.info(f"分身配置更新: {user_id}")
        return self._config_to_dict(updated)

    # ==================== 序列化辅助 ====================

    @staticmethod
    def _memory_to_dict(memory) -> dict:
        return {
            "id": memory.id, "user_id": memory.user_id,
            "memory_type": memory.memory_type, "category": memory.category,
            "title": memory.title, "content": memory.content,
            "tags": memory.tags or [], "source": memory.source,
            "source_id": memory.source_id, "confidence": memory.confidence,
            "is_verified": memory.is_verified, "importance": memory.importance,
            "identity_id": memory.identity_id,
            "created_at": memory.created_at.isoformat(),
            "updated_at": memory.updated_at.isoformat(),
        }

    @staticmethod
    def _inspiration_to_dict(insp) -> dict:
        return {
            "id": insp.id, "user_id": insp.user_id,
            "title": insp.title, "description": insp.description,
            "domain": insp.domain, "estimated_value": insp.estimated_value,
            "prompt": insp.prompt, "result": insp.result,
            "status": insp.status, "feedback": insp.feedback,
            "batch_id": insp.batch_id, "source_type": insp.source_type,
            "created_at": insp.created_at.isoformat(),
            "updated_at": insp.updated_at.isoformat(),
        }

    @staticmethod
    def _config_to_dict(config) -> dict:
        return {
            "id": config.id, "user_id": config.user_id,
            "automation_level": config.automation_level,
            "local_model_enabled": config.local_model_enabled,
            "local_model_provider": config.local_model_provider,
            "local_model_name": config.local_model_name,
            "local_model_url": config.local_model_url,
            "cloud_model_enabled": config.cloud_model_enabled,
            "cloud_model_provider": config.cloud_model_provider,
            "cloud_model_name": config.cloud_model_name,
            "persona_name": config.persona_name,
            "persona_setting": config.persona_setting,
            "inspiration_enabled": config.inspiration_enabled,
            "inspiration_frequency": config.inspiration_frequency,
            "inspiration_domains": config.inspiration_domains or [],
            "reply_length": config.reply_length,
            "language_style": config.language_style,
            "creativity": config.creativity,
            "operation_overrides": config.operation_overrides or {},
            "updated_at": config.updated_at.isoformat(),
        }
