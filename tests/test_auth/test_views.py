import pytest
from django.urls import reverse

from accounts.models import User
from core.constants import UserRole


@pytest.mark.django_db
class TestStudentLogin:
    def test_get_login_page(self, client):
        resp = client.get("/accounts/login/")
        assert resp.status_code == 200
        assert "学生登录" in resp.content.decode()

    def test_login_success(self, client):
        User.objects.create_user(username="stu01", password="Test@1234", role=UserRole.STUDENT)
        resp = client.post("/accounts/login/", {"username": "stu01", "password": "Test@1234"})
        assert resp.status_code == 302
        assert resp.url == "/exams/"

    def test_login_wrong_password(self, client):
        User.objects.create_user(username="stu01", password="Test@1234", role=UserRole.STUDENT)
        resp = client.post("/accounts/login/", {"username": "stu01", "password": "wrong"})
        assert resp.status_code == 200
        assert "错误" in resp.content.decode()

    def test_login_teacher_on_student_page(self, client):
        User.objects.create_user(username="teach01", password="Test@1234", role=UserRole.TEACHER)
        resp = client.post("/accounts/login/", {"username": "teach01", "password": "Test@1234"})
        assert resp.status_code == 200
        assert "不匹配" in resp.content.decode()

    def test_must_change_password_redirect(self, client):
        User.objects.create_user(
            username="stu01", password="Test@1234", role=UserRole.STUDENT, must_change_password=True
        )
        resp = client.post("/accounts/login/", {"username": "stu01", "password": "Test@1234"})
        assert resp.status_code == 302
        assert resp.url == "/accounts/change-password/"

    def test_already_logged_in_redirects(self, client, student):
        client.login(username="student01", password="Test@1234")
        resp = client.get("/accounts/login/")
        assert resp.status_code == 302
        assert resp.url == "/exams/"


@pytest.mark.django_db
class TestTeacherLogin:
    def test_get_login_page(self, client):
        resp = client.get("/accounts/teacher/login/")
        assert resp.status_code == 200
        assert "教师登录" in resp.content.decode()

    def test_login_success(self, client):
        User.objects.create_user(username="teach01", password="Test@1234", role=UserRole.TEACHER)
        resp = client.post("/accounts/teacher/login/", {"username": "teach01", "password": "Test@1234"})
        assert resp.status_code == 302
        assert resp.url == "/teacher/"

    def test_login_student_on_teacher_page(self, client):
        User.objects.create_user(username="stu01", password="Test@1234", role=UserRole.STUDENT)
        resp = client.post("/accounts/teacher/login/", {"username": "stu01", "password": "Test@1234"})
        assert resp.status_code == 200
        assert "不匹配" in resp.content.decode()


@pytest.mark.django_db
class TestLogout:
    def test_logout(self, client, student):
        client.login(username="student01", password="Test@1234")
        resp = client.get("/accounts/logout/")
        assert resp.status_code == 302
        assert resp.url == "/accounts/login/"


@pytest.mark.django_db
class TestChangePassword:
    def test_get_page(self, client, student):
        client.login(username="student01", password="Test@1234")
        resp = client.get("/accounts/change-password/")
        assert resp.status_code == 200
        assert "修改密码" in resp.content.decode()

    def test_change_success(self, client, student):
        client.login(username="student01", password="Test@1234")
        resp = client.post("/accounts/change-password/", {
            "old_password": "Test@1234",
            "new_password": "NewPass@123",
            "confirm_password": "NewPass@123",
        })
        assert resp.status_code == 302
        student.refresh_from_db()
        assert student.check_password("NewPass@123")

    def test_wrong_old_password(self, client, student):
        client.login(username="student01", password="Test@1234")
        resp = client.post("/accounts/change-password/", {
            "old_password": "wrong",
            "new_password": "NewPass@123",
            "confirm_password": "NewPass@123",
        })
        assert resp.status_code == 200
        assert "错误" in resp.content.decode()

    def test_password_mismatch(self, client, student):
        client.login(username="student01", password="Test@1234")
        resp = client.post("/accounts/change-password/", {
            "old_password": "Test@1234",
            "new_password": "NewPass@123",
            "confirm_password": "Different@123",
        })
        assert resp.status_code == 200
        assert "不一致" in resp.content.decode()

    def test_redirect_when_not_logged_in(self, client):
        resp = client.get("/accounts/change-password/")
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url


@pytest.mark.django_db
class TestUploadStudents:
    def test_requires_superuser(self, client, teacher):
        client.login(username="teacher01", password="Test@1234")
        resp = client.post("/accounts/upload-students/")
        assert resp.status_code == 403

    def test_requires_file(self, client, django_user_model):
        admin = django_user_model.objects.create_superuser(username="admin", password="Admin@1234")
        client.login(username="admin", password="Admin@1234")
        resp = client.post("/accounts/upload-students/")
        assert resp.status_code == 400
