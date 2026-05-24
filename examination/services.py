import json
import logging

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.constants import RecordStatus, Visibility
from core.exceptions import (
    DuplicateSubmissionError,
    ExamFinishedError,
    ExamNotStartedError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from core.utils import get_client_ip

from .grader import grade_exam
from .models import ClassInfo, Exam, ExamQuestion, ExamRecord, Question, StudentClassRelation

logger = logging.getLogger(__name__)


class ExamService:
    """考试业务服务"""

    @staticmethod
    def get_available_exams(student):
        """获取学生可见的考试列表（JOIN 查询过滤可见性）"""
        now = timezone.now()
        return (
            Exam.objects.filter(is_active=True)
            .filter(Q(start_time__isnull=True) | Q(start_time__lte=now))
            .filter(Q(end_time__isnull=True) | Q(end_time__gte=now))
            .filter(
                Q(visibility=Visibility.PUBLIC)
                | Q(
                    visibility=Visibility.CLASS_SPECIFIC,
                    allowed_classes__student_relations__student=student,
                )
            )
            .select_related("created_by")
            .prefetch_related("allowed_classes")
            .distinct()
            .order_by("-created_at")
        )

    @staticmethod
    def get_exam_detail(exam_id: int) -> Exam:
        """获取考试详情"""
        try:
            return Exam.objects.select_related("created_by").prefetch_related(
                "allowed_classes", "exam_questions__question"
            ).get(id=exam_id)
        except Exam.DoesNotExist:
            raise NotFoundError("考试不存在")

    @staticmethod
    @transaction.atomic
    def start_exam(exam_id: int, student) -> ExamRecord:
        """开始考试，创建或获取 ExamRecord"""
        exam = ExamService.get_exam_detail(exam_id)

        if not exam.is_visible_to_student(student):
            raise PermissionDeniedError("无权参加此考试")

        if not exam.is_started:
            raise ExamNotStartedError()

        if exam.is_ended:
            raise ExamFinishedError()

        # 已有记录则返回
        record = ExamRecord.objects.filter(exam=exam, student=student).first()
        if record:
            return record

        total = sum(
            eq.question.score for eq in exam.exam_questions.select_related("question")
        )

        record = ExamRecord.objects.create(
            exam=exam,
            student=student,
            total_score=total,
            status=RecordStatus.DRAFT,
        )
        return record

    @staticmethod
    def save_answers(record_id: int, answers: dict) -> ExamRecord:
        """保存草稿"""
        try:
            record = ExamRecord.objects.get(id=record_id)
        except ExamRecord.DoesNotExist:
            raise NotFoundError("考试记录不存在")

        if record.status != RecordStatus.DRAFT:
            raise ValidationError("答卷已提交，无法修改")

        record.answers = json.dumps(answers, ensure_ascii=False)
        record.save(update_fields=["answers"])
        return record

    @staticmethod
    @transaction.atomic
    def submit_exam(record_id: int, student, ip_address: str = "") -> ExamRecord:
        """提交答卷"""
        try:
            record = ExamRecord.objects.select_for_update().get(id=record_id, student=student)
        except ExamRecord.DoesNotExist:
            raise NotFoundError("考试记录不存在")

        if record.status != RecordStatus.DRAFT:
            raise DuplicateSubmissionError()

        if record.exam.is_ended:
            raise ExamFinishedError()

        record.submit_time = timezone.now()
        record.ip_address = ip_address
        record.submission_method = "manual"
        record.status = RecordStatus.SUBMITTED

        # 自动判分
        answers = record.get_answers_dict()
        score, details = grade_exam(record.exam_id, answers)
        record.score = score
        record.grading_details = json.dumps(details, ensure_ascii=False)
        record.is_graded = True
        record.status = RecordStatus.AUTO_GRADED

        record.save()
        return record

    @staticmethod
    def get_exam_result(record_id: int, student) -> ExamRecord:
        """获取考试结果"""
        try:
            record = ExamRecord.objects.select_related("exam").get(
                id=record_id, student=student
            )
        except ExamRecord.DoesNotExist:
            raise NotFoundError("考试记录不存在")

        if record.status == RecordStatus.DRAFT:
            raise ValidationError("尚未提交，无法查看成绩")

        return record

    @staticmethod
    def get_or_create_record(exam_id: int, student) -> ExamRecord | None:
        """获取学生某场考试的记录"""
        return ExamRecord.objects.filter(exam_id=exam_id, student=student).first()


class ScoreService:
    """成绩管理服务"""

    @staticmethod
    def get_exam_scores(exam_id: int, teacher) -> dict:
        """获取某场考试的所有学生成绩"""
        try:
            exam = Exam.objects.get(id=exam_id, created_by=teacher)
        except Exam.DoesNotExist:
            raise NotFoundError("考试不存在")

        records = (
            ExamRecord.objects.filter(exam=exam)
            .select_related("student")
            .order_by("-score")
        )

        total_students = records.count()
        graded_students = records.filter(is_graded=True).count()
        submitted_students = records.exclude(status=RecordStatus.DRAFT).count()

        scores = [r.score for r in records if r.is_graded]
        avg_score = sum(scores) / len(scores) if scores else 0
        max_score = max(scores) if scores else 0
        min_score = min(scores) if scores else 0

        return {
            "exam": exam,
            "records": records,
            "stats": {
                "total_students": total_students,
                "submitted_students": submitted_students,
                "graded_students": graded_students,
                "avg_score": round(avg_score, 1),
                "max_score": max_score,
                "min_score": min_score,
            },
        }

    @staticmethod
    def export_exam_scores(exam_id: int, teacher) -> bytes:
        """导出考试成绩为 Excel 文件"""
        from io import BytesIO

        from openpyxl import Workbook

        data = ScoreService.get_exam_scores(exam_id, teacher)
        exam = data["exam"]
        records = data["records"]

        wb = Workbook()
        ws = wb.active
        ws.title = f"{exam.title} - 成绩"

        headers = ["学号", "姓名", "状态", "得分", "总分", "提交时间"]
        ws.append(headers)

        for record in records:
            student = record.student
            status_display = dict(RecordStatus.choices).get(record.status, record.status)
            ws.append([
                student.student_id or "",
                student.first_name or student.username,
                status_display,
                record.score if record.is_graded else "",
                record.total_score,
                record.submit_time.strftime("%Y-%m-%d %H:%M") if record.submit_time else "",
            ])

        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf.getvalue()


class ClassService:
    """班级管理服务"""

    @staticmethod
    def get_classes_for_teacher(teacher):
        """获取教师的班级列表"""
        return ClassInfo.objects.filter(teacher=teacher, is_active=True).order_by(
            "-created_at"
        )

    @staticmethod
    def get_students_in_class(class_info_id: int):
        """获取班级学生列表"""
        from accounts.models import User

        student_ids = StudentClassRelation.objects.filter(
            class_info_id=class_info_id
        ).values_list("student_id", flat=True)
        return User.objects.filter(id__in=student_ids, is_active=True).order_by(
            "student_id"
        )

    @staticmethod
    @transaction.atomic
    def create_class(teacher, name: str, description: str = "") -> ClassInfo:
        """创建班级"""
        return ClassInfo.objects.create(
            name=name, description=description, teacher=teacher
        )

    @staticmethod
    @transaction.atomic
    def add_student_to_class(class_info_id: int, student_id: int) -> StudentClassRelation:
        """将学生加入班级"""
        relation, created = StudentClassRelation.objects.get_or_create(
            class_info_id=class_info_id, student_id=student_id
        )
        return relation


class AntiCheatService:
    """防作弊服务"""

    @staticmethod
    def log_action(record_id: int, action: str, detail: str = "", ip_address: str = ""):
        """记录操作审计日志"""
        from .models import AuditLog

        return AuditLog.objects.create(
            record_id=record_id,
            action=action,
            detail=detail,
            ip_address=ip_address,
        )

    @staticmethod
    def get_audit_logs(record_id: int):
        """获取考试记录的审计日志"""
        from .models import AuditLog

        return AuditLog.objects.filter(record_id=record_id).order_by("-created_at")

    @staticmethod
    def get_suspicious_records(exam_id: int, threshold: int = 5):
        """获取可疑的考试记录（切屏次数超过阈值）"""
        from django.db.models import Count

        from .models import AuditLog

        suspicious_record_ids = (
            AuditLog.objects.filter(
                record__exam_id=exam_id,
                action__in=["screen_switch", "tab_switch", "focus_loss"],
            )
            .values("record_id")
            .annotate(switch_count=Count("id"))
            .filter(switch_count__gte=threshold)
            .values_list("record_id", flat=True)
        )

        return ExamRecord.objects.filter(id__in=suspicious_record_ids).select_related("student")


class NotificationService:
    """消息通知服务"""

    @staticmethod
    def create_notification(user, title: str, content: str, notification_type: str = "system", related_exam=None):
        """创建通知"""
        from .models import Notification

        return Notification.objects.create(
            user=user,
            title=title,
            content=content,
            notification_type=notification_type,
            related_exam=related_exam,
        )

    @staticmethod
    def get_unread_notifications(user):
        """获取用户未读通知"""
        from .models import Notification

        return Notification.objects.filter(user=user, is_read=False).order_by("-created_at")

    @staticmethod
    def mark_as_read(notification_id: int, user):
        """标记通知为已读"""
        from .models import Notification

        try:
            notification = Notification.objects.get(id=notification_id, user=user)
            notification.is_read = True
            notification.save(update_fields=["is_read"])
            return True
        except Notification.DoesNotExist:
            return False

    @staticmethod
    def mark_all_as_read(user):
        """标记所有通知为已读"""
        from .models import Notification

        return Notification.objects.filter(user=user, is_read=False).update(is_read=True)

    @staticmethod
    def notify_exam_created(exam):
        """通知学生考试创建"""
        from accounts.models import User

        if exam.visibility == "public":
            students = User.objects.filter(role="student", is_active=True)
        else:
            student_ids = exam.allowed_classes.values_list("student_relations__student_id", flat=True)
            students = User.objects.filter(id__in=student_ids, is_active=True)

        for student in students:
            NotificationService.create_notification(
                user=student,
                title=f"新考试：{exam.title}",
                content=f"教师 {exam.created_by.first_name or exam.created_by.username} 创建了新考试「{exam.title}」",
                notification_type="exam_created",
                related_exam=exam,
            )
