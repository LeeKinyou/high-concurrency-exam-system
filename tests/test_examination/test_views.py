import json

import pytest
from django.utils import timezone

from accounts.models import User
from core.constants import UserRole
from examination.models import ClassInfo, Exam, ExamQuestion, ExamRecord, Question, StudentClassRelation
from examination.services import ExamService


@pytest.mark.django_db
class TestExamListView:
    def test_redirect_when_not_logged_in(self, client):
        resp = client.get("/exams/")
        assert resp.status_code == 302

    def test_student_sees_exams(self, client, student, teacher):
        Exam.objects.create(title="公开考试", created_by=teacher, is_active=True, visibility="public")
        client.login(username="student01", password="Test@1234")
        resp = client.get("/exams/")
        assert resp.status_code == 200
        assert "公开考试" in resp.content.decode()


@pytest.mark.django_db
class TestExamDetailView:
    def test_exam_detail(self, client, student, teacher):
        exam = Exam.objects.create(title="测试考试", created_by=teacher, visibility="public")
        client.login(username="student01", password="Test@1234")
        resp = client.get(f"/exams/{exam.id}/")
        assert resp.status_code == 200
        assert "测试考试" in resp.content.decode()


@pytest.mark.django_db
class TestExamSubmitView:
    def test_submit_exam(self, client, student, teacher):
        exam = Exam.objects.create(title="测试", created_by=teacher, visibility="public", total_score=10)
        q = Question.objects.create(exam=exam, question_type="choice", content="Q1", answer="B", score=10)
        ExamQuestion.objects.create(exam=exam, question=q, order=1)

        client.login(username="student01", password="Test@1234")
        # Start exam
        ExamService = __import__("examination.services", fromlist=["ExamService"]).ExamService
        record = ExamService.start_exam(exam.id, student)

        # Submit
        resp = client.post(
            f"/exams/{exam.id}/submit/",
            data=json.dumps({"answers": {str(q.id): "B"}}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data["data"]["score"] == 10

    def test_save_draft(self, client, student, teacher):
        exam = Exam.objects.create(title="测试", created_by=teacher, visibility="public")
        q = Question.objects.create(exam=exam, question_type="choice", content="Q1", answer="B", score=10)
        ExamQuestion.objects.create(exam=exam, question=q, order=1)

        client.login(username="student01", password="Test@1234")
        ExamService = __import__("examination.services", fromlist=["ExamService"]).ExamService
        record = ExamService.start_exam(exam.id, student)

        resp = client.post(
            f"/exams/{exam.id}/save-answer/",
            data=json.dumps({"answers": {str(q.id): "A"}}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        record.refresh_from_db()
        assert str(q.id) in record.answers


@pytest.mark.django_db
class TestTeacherViews:
    def test_dashboard(self, client, teacher):
        client.login(username="teacher01", password="Test@1234")
        resp = client.get("/teacher/")
        assert resp.status_code == 200

    def test_exam_list(self, client, teacher):
        Exam.objects.create(title="考试1", created_by=teacher)
        client.login(username="teacher01", password="Test@1234")
        resp = client.get("/teacher/exams/")
        assert resp.status_code == 200
        assert "考试1" in resp.content.decode()

    def test_create_exam(self, client, teacher):
        client.login(username="teacher01", password="Test@1234")
        resp = client.post("/teacher/exams/create/", {
            "title": "新建考试",
            "description": "描述",
            "duration": 90,
            "total_score": 100,
            "visibility": "public",
        })
        assert resp.status_code == 302
        assert Exam.objects.filter(title="新建考试").exists()

    def test_exam_edit(self, client, teacher):
        exam = Exam.objects.create(title="原始标题", created_by=teacher)
        client.login(username="teacher01", password="Test@1234")
        resp = client.post(f"/teacher/exams/{exam.id}/edit/", {
            "title": "修改后标题",
            "duration": 60,
            "total_score": 100,
            "visibility": "public",
            "is_active": "on",
        })
        assert resp.status_code == 302
        exam.refresh_from_db()
        assert exam.title == "修改后标题"

    def test_exam_delete(self, client, teacher):
        exam = Exam.objects.create(title="待删除", created_by=teacher)
        client.login(username="teacher01", password="Test@1234")
        resp = client.post(f"/teacher/exams/{exam.id}/delete/")
        assert resp.status_code == 302
        exam.refresh_from_db()
        assert exam.is_active is False

    def test_question_list(self, client, teacher):
        exam = Exam.objects.create(title="测试", created_by=teacher)
        Question.objects.create(exam=exam, question_type="choice", content="Q1", answer="A", score=10)
        client.login(username="teacher01", password="Test@1234")
        resp = client.get("/teacher/questions/")
        assert resp.status_code == 200
        assert "Q1" in resp.content.decode()

    def test_class_list(self, client, teacher):
        ClassInfo.objects.create(name="计科1班", teacher=teacher)
        client.login(username="teacher01", password="Test@1234")
        resp = client.get("/teacher/classes/")
        assert resp.status_code == 200
        assert "计科1班" in resp.content.decode()

    def test_score_list(self, client, teacher):
        client.login(username="teacher01", password="Test@1234")
        resp = client.get("/teacher/scores/")
        assert resp.status_code == 200

    def test_score_list_with_exam(self, client, teacher, student):
        exam = Exam.objects.create(title="测试", created_by=teacher, visibility="public", total_score=10)
        q = Question.objects.create(exam=exam, question_type="choice", content="Q1", answer="B", score=10)
        ExamQuestion.objects.create(exam=exam, question=q, order=1)
        record = ExamService.start_exam(exam.id, student)
        ExamService.save_answers(record.id, {str(q.id): "B"})
        ExamService.submit_exam(record.id, student, "127.0.0.1")

        client.login(username="teacher01", password="Test@1234")
        resp = client.get(f"/teacher/scores/?exam_id={exam.id}")
        assert resp.status_code == 200
        assert "测试" in resp.content.decode()

    def test_score_export(self, client, teacher, student):
        exam = Exam.objects.create(title="测试", created_by=teacher, visibility="public", total_score=10)
        q = Question.objects.create(exam=exam, question_type="choice", content="Q1", answer="B", score=10)
        ExamQuestion.objects.create(exam=exam, question=q, order=1)
        record = ExamService.start_exam(exam.id, student)
        ExamService.save_answers(record.id, {str(q.id): "B"})
        ExamService.submit_exam(record.id, student, "127.0.0.1")

        client.login(username="teacher01", password="Test@1234")
        resp = client.get(f"/teacher/scores/{exam.id}/export/")
        assert resp.status_code == 200
        assert resp["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def test_exam_qrcode(self, client, teacher):
        exam = Exam.objects.create(title="测试", created_by=teacher, visibility="public")
        client.login(username="teacher01", password="Test@1234")
        resp = client.get(f"/teacher/exams/{exam.id}/qrcode/")
        assert resp.status_code == 200
        assert "考试二维码" in resp.content.decode()


@pytest.mark.django_db
class TestExamEnterView:
    def test_enter_with_valid_code(self, client, student, teacher):
        exam = Exam.objects.create(title="测试", created_by=teacher, visibility="public", exam_code="TEST123")
        client.login(username="student01", password="Test@1234")
        resp = client.post(f"/exams/{exam.id}/enter/", {"code": "TEST123"})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data["data"]["exam_id"] == exam.id

    def test_enter_with_invalid_code(self, client, student, teacher):
        exam = Exam.objects.create(title="测试", created_by=teacher, visibility="public", exam_code="TEST123")
        client.login(username="student01", password="Test@1234")
        resp = client.post(f"/exams/{exam.id}/enter/", {"code": "WRONG"})
        assert resp.status_code == 400

    def test_enter_without_login(self, client, teacher):
        exam = Exam.objects.create(title="测试", created_by=teacher, visibility="public", exam_code="TEST123")
        resp = client.post(f"/exams/{exam.id}/enter/", {"code": "TEST123"})
        assert resp.status_code == 401
