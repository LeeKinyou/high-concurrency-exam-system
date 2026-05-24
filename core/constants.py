from django.db import models


class UserRole(models.TextChoices):
    TEACHER = "teacher", "教师"
    STUDENT = "student", "学生"


class ExamStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    PUBLISHED = "published", "已发布"
    ONGOING = "ongoing", "进行中"
    ENDED = "ended", "已结束"


class RecordStatus(models.TextChoices):
    DRAFT = "draft", "答题中"
    SUBMITTED = "submitted", "已提交"
    AUTO_GRADED = "auto_graded", "自动判分完成"
    MANUAL_GRADING = "manual_grading", "人工阅卷中"
    MANUAL_GRADED = "manual_graded", "人工判分完成"
    REVIEWED = "reviewed", "已复核"


class QuestionType(models.TextChoices):
    CHOICE = "choice", "选择题"
    BLANK = "blank", "填空题"


class Difficulty(models.TextChoices):
    EASY = "easy", "简单"
    MEDIUM = "medium", "中等"
    HARD = "hard", "困难"


class Visibility(models.TextChoices):
    PUBLIC = "public", "公开"
    CLASS_SPECIFIC = "class_specific", "指定班级"


class SubmissionMethod(models.TextChoices):
    MANUAL = "manual", "手动提交"
    AUTO = "auto", "自动提交"


# Login rate limiting
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 30

# Session
SESSION_ID_EXPIRE_SECONDS = 300  # QR login session expires in 5 minutes

# File upload
MAX_UPLOAD_FILE_SIZE_MB = 10
ALLOWED_EXCEL_EXTENSIONS = [".xlsx", ".xls"]

# Pagination
DEFAULT_PAGE_SIZE = 20
