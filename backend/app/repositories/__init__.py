from app.repositories.base import BaseRepository
from app.repositories.user_repo import UserRepository
from app.repositories.task_repo import SubtaskRepository, TaskRepository
from app.repositories.folder_repo import FolderRepository
from app.repositories.document_repo import (
    BacklinkRepository,
    DocumentRepository,
    DocumentVersionRepository,
)
from app.repositories.conversation_repo import ConversationRepository, MessageRepository
from app.repositories.review_repo import ReviewRepository
from app.repositories.panel_repo import QuickTodoRepository, ReminderRepository
from app.repositories.notification_repo import NotificationRepository
from app.repositories.project_repo import MilestoneRepository, ProjectRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "TaskRepository",
    "SubtaskRepository",
    "FolderRepository",
    "DocumentRepository",
    "DocumentVersionRepository",
    "BacklinkRepository",
    "ConversationRepository",
    "MessageRepository",
    "ReviewRepository",
    "QuickTodoRepository",
    "ReminderRepository",
    "NotificationRepository",
    "ProjectRepository",
    "MilestoneRepository",
]

# 二期新模块 Repository
from app.repositories.resource_repo import InboxItemRepository
from app.repositories.template_repo import TemplateRepository
from app.repositories.domain_repo import DomainRepository
from app.repositories.study_plan_repo import StudyPlanRepository
from app.repositories.flashcard_repo import FlashcardRepository
from app.repositories.study_time_repo import StudyTimeRepository
from app.repositories.habit_repo import HabitRepository
from app.repositories.habit_checkin_repo import HabitCheckinRepository
from app.repositories.mood_repo import MoodRepository
from app.repositories.diary_repo import DiaryRepository
from app.repositories.sop_repo import SOPRepository
from app.repositories.prompt_repo import PromptRepository
from app.repositories.skill_repo import SkillRepository
from app.repositories.project_memory_repo import ProjectMemoryRepository
