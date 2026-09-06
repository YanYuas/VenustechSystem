# ============================================================
# 模型聚合：导入即注册到 Base.metadata（迁移/建表依赖）
# ============================================================
from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin, utcnow
from app.models.conversation import Conversation, Message
from app.models.document import Backlink, Document, DocumentVersion
from app.models.folder import Folder
from app.models.notification import Notification
from app.models.panel import QuickTodo, Reminder
from app.models.project import Project
from app.models.review import Review
from app.models.settings import Setting
from app.models.task import Subtask, Task
from app.models.user import User

from app.models.asset import SOP, SOPVersion, PromptTemplate, Skill, ProjectMemory
from app.models.learning import StudyPlan, Flashcard, StudyTimeLog
from app.models.life import Habit, HabitCheckin, MoodLog, Diary
from app.models.resource import InboxItem, Template, Domain
