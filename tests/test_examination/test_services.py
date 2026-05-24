import pytest
from django.utils import timezone

from accounts.models import User
from core.constants import UserRole
from core.exceptions import (
    DuplicateSubmissionError,
    ExamFinishedError,
    ExamNotStartedError,
    NotFoundError,
    PermissionDeniedError,
)
from examination.models import ClassInfo, Exam, ExamQuestion, ExamRecord, Question, StudentClassRelation
from examination.services import ClassService, ExamService, ScoreService


@pytest.mark.django_db
class TestGetAvailableExams:
    def test_public_exams_visible(self, teacher, student):
        Exam.objects.create(title="公开考试", created_by=teacher, is_active=True, visibility="public")
        exams = ExamService.get_available_exams(student)
        assert exams.count() == 1

    def test_inactive_exams_hidden(self, teacher, student):
        Exam.objects.create(title="已停用", created_by=teacher, is_active=False, visibility="public")
        exams = ExamService.get_available_exams(student)
        assert exams.count() == 0

    def test_class_specific_exams_filtered(self, teacher, student):
        cls = ClassInfo.objects.create(name="计科1班", teacher=teacher)
        StudentClassRelation.objects.create(student=student, class_info=cls)
        exam = Exam.objects.create(title="班级考试", created_by=teacher, visibility="class_specific")
        exam.allowed_classes.add(cls)

        exams = ExamService.get_available_exams(student)
        assert exams.count() == 1

    def test_class_specific_exams_not_in_class(self, teacher, student):
        Exam.objects.create(title="其他班级考试", created_by=teacher, visibility="class_specific")
        exams = ExamService.get_available_exams(student)
        assert exams.count() == 0

    def test_ended_exams_hidden(self, teacher, student):
        Exam.objects.create(
            title="已结束", created_by=teacher, visibility="public",
            end_time=timezone.now() - timezone.timedelta(hours=1),
        )
        exams = ExamService.get_available_exams(student)
        assert exams.count() == 0


@pytest.mark.django_db
class TestStartExam:
    def test_start_creates_record(self, teacher, student):
        exam = Exam.objects.create(title="测试", created_by=teacher, visibility="public")
        q = Question.objects.create(exam=exam, question_type="choice", content="Q1", answer="A", score=10)
        ExamQuestion.objects.create(exam=exam, question=q, order=1)

        record = ExamService.start_exam(exam.id, student)
        assert record.status == "draft"
        assert record.total_score == 10

    def test_start_returns_existing_record(self, teacher, student):
        exam = Exam.objects.create(title="测试", created_by=teacher, visibility="public")
        record1 = ExamService.start_exam(exam.id, student)
        record2 = ExamService.start_exam(exam.id, student)
        assert record1.id == record2.id

    def test_start_not_started_exam(self, teacher, student):
        exam = Exam.objects.create(
            title="未开始", created_by=teacher, visibility="public",
            start_time=timezone.now() + timezone.timedelta(hours=1),
        )
        with pytest.raises(ExamNotStartedError):
            ExamService.start_exam(exam.id, student)

    def test_start_ended_exam(self, teacher, student):
        exam = Exam.objects.create(
            title="已结束", created_by=teacher, visibility="public",
            end_time=timezone.now() - timezone.timedelta(hours=1),
        )
        with pytest.raises(ExamFinishedError):
            ExamService.start_exam(exam.id, student)

    def test_start_no_permission(self, teacher, student):
        exam = Exam.objects.create(title="无权限", created_by=teacher, visibility="class_specific")
        with pytest.raises(PermissionDeniedError):
            ExamService.start_exam(exam.id, student)


@pytest.mark.django_db
class TestSubmitExam:
    def test_submit_success(self, teacher, student):
        exam = Exam.objects.create(title="测试", created_by=teacher, visibility="public", total_score=10)
        q = Question.objects.create(
            exam=exam, question_type="choice", content="1+1=?", answer="B", score=10,
        )
        ExamQuestion.objects.create(exam=exam, question=q, order=1)
        record = ExamService.start_exam(exam.id, student)
        ExamService.save_answers(record.id, {str(q.id): "B"})

        record = ExamService.submit_exam(record.id, student, "127.0.0.1")
        assert record.status == "auto_graded"
        assert record.is_graded is True
        assert record.score == 10

    def test_submit_duplicate(self, teacher, student):
        exam = Exam.objects.create(title="测试", created_by=teacher, visibility="public")
        record = ExamService.start_exam(exam.id, student)
        ExamService.submit_exam(record.id, student, "127.0.0.1")

        with pytest.raises(DuplicateSubmissionError):
            ExamService.submit_exam(record.id, student, "127.0.0.1")


@pytest.mark.django_db
class TestClassService:
    def test_get_classes_for_teacher(self, teacher):
        ClassService.create_class(teacher, "A班")
        ClassService.create_class(teacher, "B班")
        classes = ClassService.get_classes_for_teacher(teacher)
        assert classes.count() == 2

    def test_get_students_in_class(self, teacher, student):
        cls = ClassService.create_class(teacher, "A班")
        ClassService.add_student_to_class(cls.id, student.id)
        students = ClassService.get_students_in_class(cls.id)
        assert students.count() == 1


@pytest.mark.django_db
class TestScoreService:
    def test_get_exam_scores(self, teacher, student):
        exam = Exam.objects.create(title="测试", created_by=teacher, visibility="public", total_score=10)
        q = Question.objects.create(exam=exam, question_type="choice", content="Q1", answer="B", score=10)
        ExamQuestion.objects.create(exam=exam, question=q, order=1)
        record = ExamService.start_exam(exam.id, student)
        ExamService.save_answers(record.id, {str(q.id): "B"})
        ExamService.submit_exam(record.id, student, "127.0.0.1")

        data = ScoreService.get_exam_scores(exam.id, teacher)
        assert data["exam"].id == exam.id
        assert data["stats"]["total_students"] == 1
        assert data["stats"]["graded_students"] == 1
        assert data["stats"]["avg_score"] == 10

    def test_get_exam_scores_wrong_teacher(self, teacher, student):
        exam = Exam.objects.create(title="测试", created_by=teacher, visibility="public")
        other_teacher = User.objects.create_user(
            username="other", password="Test@1234", role=UserRole.TEACHER
        )
        with pytest.raises(NotFoundError):
            ScoreService.get_exam_scores(exam.id, other_teacher)

    def test_export_exam_scores(self, teacher, student):
        exam = Exam.objects.create(title="测试", created_by=teacher, visibility="public", total_score=10)
        q = Question.objects.create(exam=exam, question_type="choice", content="Q1", answer="B", score=10)
        ExamQuestion.objects.create(exam=exam, question=q, order=1)
        record = ExamService.start_exam(exam.id, student)
        ExamService.save_answers(record.id, {str(q.id): "B"})
        ExamService.submit_exam(record.id, student, "127.0.0.1")

        file_data = ScoreService.export_exam_scores(exam.id, teacher)
        assert isinstance(file_data, bytes)
        assert len(file_data) > 0
