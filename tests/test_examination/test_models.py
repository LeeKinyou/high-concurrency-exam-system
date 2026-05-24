import pytest
from django.utils import timezone

from accounts.models import User
from core.constants import UserRole
from examination.models import ClassInfo, Exam, ExamRecord, Question, StudentClassRelation


@pytest.mark.django_db
class TestClassInfo:
    def test_create_class(self, teacher):
        cls = ClassInfo.objects.create(name="计科1班", teacher=teacher)
        assert str(cls) == "计科1班"
        assert cls.is_active is True

    def test_teacher_classes(self, teacher):
        ClassInfo.objects.create(name="A班", teacher=teacher)
        ClassInfo.objects.create(name="B班", teacher=teacher)
        assert ClassInfo.objects.filter(teacher=teacher).count() == 2


@pytest.mark.django_db
class TestStudentClassRelation:
    def test_add_student_to_class(self, teacher, student):
        cls = ClassInfo.objects.create(name="计科1班", teacher=teacher)
        relation = StudentClassRelation.objects.create(student=student, class_info=cls)
        assert str(relation) == f"{student} - {cls}"

    def test_unique_constraint(self, teacher, student):
        cls = ClassInfo.objects.create(name="计科1班", teacher=teacher)
        StudentClassRelation.objects.create(student=student, class_info=cls)
        with pytest.raises(Exception):
            StudentClassRelation.objects.create(student=student, class_info=cls)


@pytest.mark.django_db
class TestExam:
    def test_create_exam(self, teacher):
        exam = Exam.objects.create(title="期中考试", created_by=teacher)
        assert str(exam) == "期中考试"
        assert exam.is_started is True
        assert exam.is_ended is False

    def test_exam_with_time_range(self, teacher):
        now = timezone.now()
        exam = Exam.objects.create(
            title="限时考试",
            created_by=teacher,
            start_time=now - timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=1),
        )
        assert exam.is_started is True
        assert exam.is_ended is False

    def test_exam_visibility_public(self, teacher, student):
        exam = Exam.objects.create(title="公开考试", created_by=teacher, visibility="public")
        assert exam.is_visible_to_student(student) is True

    def test_exam_visibility_class_specific(self, teacher, student):
        cls = ClassInfo.objects.create(name="计科1班", teacher=teacher)
        StudentClassRelation.objects.create(student=student, class_info=cls)
        exam = Exam.objects.create(title="班级考试", created_by=teacher, visibility="class_specific")
        exam.allowed_classes.add(cls)
        assert exam.is_visible_to_student(student) is True

    def test_exam_visibility_class_specific_denied(self, teacher, student):
        exam = Exam.objects.create(title="班级考试", created_by=teacher, visibility="class_specific")
        assert exam.is_visible_to_student(student) is False


@pytest.mark.django_db
class TestQuestion:
    def test_create_choice_question(self, teacher):
        exam = Exam.objects.create(title="测试", created_by=teacher)
        q = Question.objects.create(
            exam=exam, question_type="choice", content="1+1=?",
            options='[{"label":"A","text":"1"},{"label":"B","text":"2"}]',
            answer="B", score=10,
        )
        assert q.get_options_list() == [{"label": "A", "text": "1"}, {"label": "B", "text": "2"}]

    def test_create_blank_question(self, teacher):
        exam = Exam.objects.create(title="测试", created_by=teacher)
        q = Question.objects.create(
            exam=exam, question_type="blank", content="首都是___",
            answer="北京", score=10,
        )
        assert q.get_options_list() == []


@pytest.mark.django_db
class TestExamRecord:
    def test_create_record(self, teacher, student):
        exam = Exam.objects.create(title="测试", created_by=teacher, total_score=100)
        record = ExamRecord.objects.create(exam=exam, student=student, total_score=100)
        assert record.status == "draft"
        assert record.is_graded is False
        assert record.get_answers_dict() == {}

    def test_unique_record_per_exam_student(self, teacher, student):
        exam = Exam.objects.create(title="测试", created_by=teacher)
        ExamRecord.objects.create(exam=exam, student=student)
        with pytest.raises(Exception):
            ExamRecord.objects.create(exam=exam, student=student)
