# ============================================================
# 统一异常体系（对齐架构 v2.0 §9.1 / PRD §13.1 错误码）
# ============================================================
from __future__ import annotations


class AppException(Exception):
    """业务异常基类。"""

    code: int = 5000
    http_status: int = 500

    def __init__(self, message: str = "服务器内部错误"):
        self.message = message
        super().__init__(message)


# ---- 客户端错误（HTTP 4xx）----
class ValidationException(AppException):
    code = 1001
    http_status = 400


class NotFoundException(AppException):
    code = 1002
    http_status = 404


class UnauthorizedException(AppException):
    code = 2001
    http_status = 401


# ---- 业务规则冲突（HTTP 409）----
class BusinessException(AppException):
    code = 3001
    http_status = 409


class TaskStateException(BusinessException):
    """任务非法状态流转。"""


class FocusTaskExistsException(BusinessException):
    """今日最重要任务已存在。"""


class DuplicateFolderNameException(BusinessException):
    """同级文件夹重名。"""


class InboxImmutableException(BusinessException):
    """收集箱不可删除/重命名。"""


class ReviewExistsException(BusinessException):
    """复盘重复创建。"""


# ---- AI 服务错误（HTTP 502）----
class AIServiceException(AppException):
    code = 4001
    http_status = 502


class AIKeyMissingException(AIServiceException):
    """API Key 未配置。"""


class AIRequestFailedException(AIServiceException):
    """AI 请求失败。"""


# ---- 服务器内部错误（HTTP 500）----
class ServerException(AppException):
    code = 5000
    http_status = 500
