import pytest

from accounts.models import User
from core.constants import UserRole


@pytest.mark.django_db
class TestUserProperties:
    def test_is_teacher_property(self):
        user = User(username="t", role=UserRole.TEACHER)
        assert user.is_teacher is True
        assert user.is_student is False

    def test_is_student_property(self):
        user = User(username="s", role=UserRole.STUDENT)
        assert user.is_student is True
        assert user.is_teacher is False

    def test_str_representation(self):
        user = User.objects.create_user(username="testuser", password="Test@1234")
        assert str(user) == "testuser"
