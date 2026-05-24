from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from core.constants import UserRole


class User(AbstractUser):
    """Custom user model with role support."""

    role = models.CharField(max_length=10, choices=UserRole.choices, default=UserRole.STUDENT, verbose_name="角色")
    student_id = models.CharField(max_length=20, unique=True, null=True, blank=True, verbose_name="学号")
    first_name = models.CharField(max_length=150, blank=True, verbose_name="姓名")
    must_change_password = models.BooleanField(default=False, verbose_name="强制改密")
    last_login_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="最后登录IP")
    is_active = models.BooleanField(default=True, verbose_name="启用")

    class Meta:
        db_table = "accounts_user"
        verbose_name = "用户"
        verbose_name_plural = "用户"

    @property
    def is_teacher(self) -> bool:
        return self.role == UserRole.TEACHER

    @property
    def is_student(self) -> bool:
        return self.role == UserRole.STUDENT


class LoginAttempt(models.Model):
    """Records login attempts for rate limiting and audit."""

    ip_address = models.GenericIPAddressField(verbose_name="IP地址")
    username = models.CharField(max_length=150, blank=True, verbose_name="用户名")
    success = models.BooleanField(default=False, verbose_name="是否成功")
    attempted_at = models.DateTimeField(default=timezone.now, verbose_name="尝试时间")

    class Meta:
        db_table = "accounts_login_attempt"
        verbose_name = "登录尝试"
        verbose_name_plural = "登录尝试"
        ordering = ["-attempted_at"]

    def __str__(self):
        status = "成功" if self.success else "失败"
        return f"{self.username} @ {self.ip_address} ({status})"
