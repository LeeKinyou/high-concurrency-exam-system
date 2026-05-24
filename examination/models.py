import json
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.constants import (
    Difficulty,
    QuestionType,
    RecordStatus,
    SubmissionMethod,
    Visibility,
)


class ClassInfo(models.Model):
    """班级模型"""

    name = models.CharField(max_length=100, verbose_name="班级名称")
    description = models.TextField(blank=True, default="", verbose_name="描述")
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teaching_classes",
        verbose_name="班主任",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    is_active = models.BooleanField(default=True, verbose_name="启用")

    class Meta:
        db_table = "examination_classinfo"
        verbose_name = "班级"
        verbose_name_plural = "班级"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class StudentClassRelation(models.Model):
    """学生-班级关系"""

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="class_relations",
        verbose_name="学生",
    )
    class_info = models.ForeignKey(
        ClassInfo,
        on_delete=models.CASCADE,
        related_name="student_relations",
        verbose_name="班级",
    )
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name="加入时间")

    class Meta:
        db_table = "examination_student_class_relation"
        verbose_name = "学生班级关系"
        verbose_name_plural = "学生班级关系"
        unique_together = ("student", "class_info")

    def __str__(self):
        return f"{self.student} - {self.class_info}"


class Exam(models.Model):
    """考试主模型"""

    title = models.CharField(max_length=200, verbose_name="考试名称")
    description = models.TextField(blank=True, default="", verbose_name="考试描述")
    exam_code = models.CharField(
        max_length=50, unique=True, default=uuid.uuid4, verbose_name="考试码"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_exams",
        verbose_name="创建者",
    )
    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.PUBLIC,
        verbose_name="可见性",
    )
    start_time = models.DateTimeField(null=True, blank=True, verbose_name="开始时间")
    end_time = models.DateTimeField(null=True, blank=True, verbose_name="结束时间")
    duration = models.IntegerField(default=60, verbose_name="时长(分钟)")
    total_score = models.IntegerField(default=100, verbose_name="满分")
    require_qr = models.BooleanField(default=False, verbose_name="需扫码")
    submission_method = models.CharField(
        max_length=10,
        choices=SubmissionMethod.choices,
        default=SubmissionMethod.MANUAL,
        verbose_name="提交方式",
    )
    shuffle_questions = models.BooleanField(default=False, verbose_name="题目乱序")
    shuffle_options = models.BooleanField(default=False, verbose_name="选项乱序")
    is_active = models.BooleanField(default=True, verbose_name="启用")
    allowed_classes = models.ManyToManyField(
        ClassInfo,
        blank=True,
        related_name="exams",
        verbose_name="可见班级",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "examination_exam"
        verbose_name = "考试"
        verbose_name_plural = "考试"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def is_started(self) -> bool:
        if self.start_time is None:
            return True
        return timezone.now() >= self.start_time

    @property
    def is_ended(self) -> bool:
        if self.end_time is None:
            return False
        return timezone.now() >= self.end_time

    def is_visible_to_student(self, user) -> bool:
        if not self.is_active:
            return False
        if self.visibility == Visibility.PUBLIC:
            return True
        student_class_ids = user.class_relations.values_list("class_info_id", flat=True)
        return self.allowed_classes.filter(id__in=student_class_ids).exists()


class Question(models.Model):
    """题目模型"""

    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="questions",
        verbose_name="所属考试",
    )
    question_type = models.CharField(
        max_length=10,
        choices=QuestionType.choices,
        verbose_name="题型",
    )
    content = models.TextField(verbose_name="题干")
    options = models.TextField(blank=True, default="[]", verbose_name="选项(JSON)")
    answer = models.TextField(verbose_name="正确答案")
    score = models.IntegerField(default=10, verbose_name="分值")
    explanation = models.TextField(blank=True, default="", verbose_name="解析")
    difficulty = models.CharField(
        max_length=10,
        choices=Difficulty.choices,
        default=Difficulty.MEDIUM,
        verbose_name="难度",
    )
    order = models.IntegerField(default=0, verbose_name="排序")

    class Meta:
        db_table = "examination_question"
        verbose_name = "题目"
        verbose_name_plural = "题目"
        ordering = ["order", "id"]

    def __str__(self):
        return f"[{self.get_question_type_display()}] {self.content[:50]}"

    def get_options_list(self) -> list:
        try:
            return json.loads(self.options)
        except (json.JSONDecodeError, TypeError):
            return []


class ExamQuestion(models.Model):
    """考试-题目关联"""

    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name="exam_questions",
        verbose_name="考试",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="exam_questions",
        verbose_name="题目",
    )
    order = models.IntegerField(default=0, verbose_name="排序")

    class Meta:
        db_table = "examination_exam_question"
        verbose_name = "考试题目"
        verbose_name_plural = "考试题目"
        unique_together = ("exam", "question")
        ordering = ["order"]


class ExamRecord(models.Model):
    """考试记录——学生答题与判分"""

    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name="records",
        verbose_name="考试",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="exam_records",
        verbose_name="学生",
    )
    answers = models.TextField(blank=True, default="{}", verbose_name="答案(JSON)")
    score = models.IntegerField(default=0, verbose_name="得分")
    total_score = models.IntegerField(default=0, verbose_name="总分")
    grading_details = models.TextField(
        blank=True, default="{}", verbose_name="判题详情(JSON)"
    )
    is_graded = models.BooleanField(default=False, verbose_name="已判题")
    start_time = models.DateTimeField(auto_now_add=True, verbose_name="开始时间")
    submit_time = models.DateTimeField(null=True, blank=True, verbose_name="提交时间")
    submission_method = models.CharField(
        max_length=10,
        choices=SubmissionMethod.choices,
        default=SubmissionMethod.MANUAL,
        verbose_name="提交方式",
    )
    ip_address = models.CharField(max_length=45, blank=True, default="", verbose_name="答题IP")
    status = models.CharField(
        max_length=20,
        choices=RecordStatus.choices,
        default=RecordStatus.DRAFT,
        verbose_name="状态",
    )

    class Meta:
        db_table = "examination_exam_record"
        verbose_name = "考试记录"
        verbose_name_plural = "考试记录"
        unique_together = ("exam", "student")
        ordering = ["-start_time"]

    def __str__(self):
        return f"{self.student} - {self.exam} ({self.get_status_display()})"

    def get_answers_dict(self) -> dict:
        try:
            return json.loads(self.answers)
        except (json.JSONDecodeError, TypeError):
            return {}

    def get_grading_details_dict(self) -> dict:
        try:
            return json.loads(self.grading_details)
        except (json.JSONDecodeError, TypeError):
            return {}
