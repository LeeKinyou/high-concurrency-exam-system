import pytest

from accounts.models import LoginAttempt, User
from core.constants import UserRole


@pytest.mark.django_db
class TestUserModel:
    def test_create_student(self):
        user = User.objects.create_user(
            username="stu01", password="Test@1234", role=UserRole.STUDENT, student_id="2024001"
        )
        assert user.is_student is True
        assert user.is_teacher is False
        assert user.student_id == "2024001"
        assert user.check_password("Test@1234")

    def test_create_teacher(self):
        user = User.objects.create_user(username="teach01", password="Test@1234", role=UserRole.TEACHER)
        assert user.is_teacher is True
        assert user.is_student is False

    def test_student_id_unique(self):
        User.objects.create_user(username="s1", password="Test@1234", role=UserRole.STUDENT, student_id="2024001")
        with pytest.raises(Exception):
            User.objects.create_user(username="s2", password="Test@1234", role=UserRole.STUDENT, student_id="2024001")

    def test_default_role_is_student(self):
        user = User.objects.create_user(username="default", password="Test@1234")
        assert user.role == UserRole.STUDENT

    def test_must_change_password_default(self):
        user = User.objects.create_user(username="test", password="Test@1234")
        assert user.must_change_password is False

    def test_last_login_ip_nullable(self):
        user = User.objects.create_user(username="test", password="Test@1234")
        assert user.last_login_ip is None


@pytest.mark.django_db
class TestLoginAttempt:
    def test_create_attempt(self):
        attempt = LoginAttempt.objects.create(
            ip_address="127.0.0.1", username="test", success=False
        )
        assert str(attempt) == "test @ 127.0.0.1 (失败)"

    def test_success_attempt(self):
        attempt = LoginAttempt.objects.create(
            ip_address="127.0.0.1", username="test", success=True
        )
        assert str(attempt) == "test @ 127.0.0.1 (成功)"
