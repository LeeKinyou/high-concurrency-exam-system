import pytest
from django.utils import timezone

from accounts.models import User
from core.constants import RecordStatus, UserRole
from examination.models import Exam, ExamRecord, Question, ExamQuestion
from examination.services import ExamService
from examination.tasks import auto_submit_expired_exams


@pytest.mark.django_db
class TestAutoSubmitTask:
    def test_auto_submit_expired_exams(self, teacher, student):
        # 创建已结束的考试
        exam = Exam.objects.create(
            title="已结束考试",
            created_by=teacher,
            visibility="public",
            end_time=timezone.now() - timezone.timedelta(minutes=5),
        )
        q = Question.objects.create(exam=exam, question_type="choice", content="Q1", answer="A", score=10)
        ExamQuestion.objects.create(exam=exam, question=q, order=1)

        # 直接创建草稿记录（不使用 start_exam，因为考试已结束）
        record = ExamRecord.objects.create(
            exam=exam,
            student=student,
            total_score=10,
            status=RecordStatus.DRAFT,
        )

        # 执行自动交卷
        count = auto_submit_expired_exams()
        assert count == 1

        record.refresh_from_db()
        assert record.status == "auto_graded"

    def test_auto_submit_skips_active_exams(self, teacher, student):
        # 创建未结束的考试
        exam = Exam.objects.create(
            title="进行中考试",
            created_by=teacher,
            visibility="public",
            end_time=timezone.now() + timezone.timedelta(hours=1),
        )
        record = ExamService.start_exam(exam.id, student)

        count = auto_submit_expired_exams()
        assert count == 0

        record.refresh_from_db()
        assert record.status == "draft"

    def test_auto_submit_skips_submitted_records(self, teacher, student):
        exam = Exam.objects.create(
            title="已结束考试",
            created_by=teacher,
            visibility="public",
            end_time=timezone.now() - timezone.timedelta(minutes=5),
        )
        # 直接创建已提交的记录
        record = ExamRecord.objects.create(
            exam=exam,
            student=student,
            total_score=10,
            status=RecordStatus.AUTO_GRADED,
            is_graded=True,
            score=10,
        )

        count = auto_submit_expired_exams()
        assert count == 0
