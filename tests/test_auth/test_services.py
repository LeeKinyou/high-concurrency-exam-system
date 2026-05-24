import io
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache

from accounts.models import LoginAttempt, User
from accounts.services import AuthService
from core.constants import UserRole
from core.exceptions import (
    AuthenticationError,
    RateLimitError,
    ValidationError,
)


@pytest.mark.django_db
class TestAuthenticateUser:
    def _make_request(self, ip="127.0.0.1"):
        request = MagicMock()
        request.META = {"REMOTE_ADDR": ip}
        return request

    def test_success(self):
        User.objects.create_user(username="test", password="Test@1234", role=UserRole.STUDENT)
        request = self._make_request()
        user = AuthService.authenticate_user(request, "test", "Test@1234")
        assert user.username == "test"

    def test_wrong_password(self):
        User.objects.create_user(username="test", password="Test@1234", role=UserRole.STUDENT)
        request = self._make_request()
        with pytest.raises(AuthenticationError, match="用户名或密码错误"):
            AuthService.authenticate_user(request, "test", "wrong")

    def test_nonexistent_user(self):
        request = self._make_request()
        with pytest.raises(AuthenticationError, match="用户名或密码错误"):
            AuthService.authenticate_user(request, "nobody", "Test@1234")

    def test_inactive_user(self):
        User.objects.create_user(username="test", password="Test@1234", role=UserRole.STUDENT, is_active=False)
        request = self._make_request()
        with pytest.raises(AuthenticationError, match="已被禁用"):
            AuthService.authenticate_user(request, "test", "Test@1234")

    def test_role_mismatch(self):
        User.objects.create_user(username="test", password="Test@1234", role=UserRole.STUDENT)
        request = self._make_request()
        with pytest.raises(AuthenticationError, match="角色不匹配"):
            AuthService.authenticate_user(request, "test", "Test@1234", role=UserRole.TEACHER)

    def test_login_by_student_id(self):
        User.objects.create_user(
            username="stu01", password="Test@1234", role=UserRole.STUDENT, student_id="2024001"
        )
        request = self._make_request()
        user = AuthService.authenticate_user(request, "2024001", "Test@1234")
        assert user.username == "stu01"

    def test_login_by_email(self):
        User.objects.create_user(
            username="stu01", password="Test@1234", role=UserRole.STUDENT, email="stu@test.com"
        )
        request = self._make_request()
        user = AuthService.authenticate_user(request, "stu@test.com", "Test@1234")
        assert user.username == "stu01"

    def test_ip_rate_limit(self):
        User.objects.create_user(username="test", password="Test@1234", role=UserRole.STUDENT)
        request = self._make_request(ip="10.0.0.1")

        # Fail 5 times
        for _ in range(5):
            with pytest.raises(AuthenticationError):
                AuthService.authenticate_user(request, "test", "wrong")

        # 6th attempt should be rate limited
        with pytest.raises(RateLimitError, match="登录尝试过多"):
            AuthService.authenticate_user(request, "test", "Test@1234")

        # Clean up cache
        cache.delete("login_attempts:10.0.0.1")

    def test_login_clears_attempts(self):
        User.objects.create_user(username="test", password="Test@1234", role=UserRole.STUDENT)
        request = self._make_request(ip="10.0.0.2")

        # Fail 3 times
        for _ in range(3):
            with pytest.raises(AuthenticationError):
                AuthService.authenticate_user(request, "test", "wrong")

        # Success should clear attempts
        user = AuthService.authenticate_user(request, "test", "Test@1234")
        assert user.username == "test"

        cache.delete("login_attempts:10.0.0.2")

    def test_records_login_attempt(self):
        User.objects.create_user(username="test", password="Test@1234", role=UserRole.STUDENT)
        request = self._make_request()
        AuthService.authenticate_user(request, "test", "Test@1234")
        assert LoginAttempt.objects.filter(username="test", success=True).exists()

    def test_updates_last_login_ip(self):
        User.objects.create_user(username="test", password="Test@1234", role=UserRole.STUDENT)
        request = self._make_request(ip="192.168.1.1")
        user = AuthService.authenticate_user(request, "test", "Test@1234")
        user.refresh_from_db()
        assert user.last_login_ip == "192.168.1.1"


@pytest.mark.django_db
class TestChangePassword:
    def test_success(self):
        user = User.objects.create_user(username="test", password="Old@1234")
        AuthService.change_password(user, "Old@1234", "New@1234")
        user.refresh_from_db()
        assert user.check_password("New@1234")
        assert user.must_change_password is False

    def test_wrong_old_password(self):
        user = User.objects.create_user(username="test", password="Old@1234")
        with pytest.raises(ValidationError, match="原密码错误"):
            AuthService.change_password(user, "wrong", "New@1234")

    def test_weak_new_password(self):
        user = User.objects.create_user(username="test", password="Old@1234")
        with pytest.raises(ValidationError):
            AuthService.change_password(user, "Old@1234", "123")


@pytest.mark.django_db
class TestImportStudentsFromExcel:
    def _make_file(self, rows):
        """Create a mock xlsx file."""
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["学号", "姓名", "邮箱"])
        for row in rows:
            ws.append(row)

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        buf.name = "students.xlsx"
        buf.size = buf.getbuffer().nbytes
        return buf

    def test_import_success(self):
        file = self._make_file([
            ["2024001", "张三", "zhang@test.com"],
            ["2024002", "李四", "li@test.com"],
        ])
        result = AuthService.import_students_from_excel(file)
        assert result["success_count"] == 2
        assert len(result["errors"]) == 0
        assert User.objects.filter(student_id="2024001").exists()
        assert User.objects.filter(student_id="2024002").exists()

    def test_duplicate_student_id(self):
        User.objects.create_user(
            username="2024001", password="Test@1234", role=UserRole.STUDENT, student_id="2024001"
        )
        file = self._make_file([
            ["2024001", "张三", ""],
            ["2024002", "李四", ""],
        ])
        result = AuthService.import_students_from_excel(file)
        assert result["success_count"] == 1
        assert len(result["errors"]) == 1
        assert "已存在" in result["errors"][0]

    def test_invalid_file_extension(self):
        file = MagicMock()
        file.name = "data.pdf"
        file.size = 1024
        with pytest.raises(ValidationError, match="不支持的文件格式"):
            AuthService.import_students_from_excel(file)
