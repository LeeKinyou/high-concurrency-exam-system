from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    自定义用户模型
    支持教师和学生两种角色
    """
    ROLE_CHOICES = (
        ('teacher', '教师'),
        ('student', '学生'),
    )
    
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default='student',
        verbose_name='角色'
    )
    student_id = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True,
        verbose_name='学号'
    )
    
    class Meta:
        verbose_name = '用户'
        verbose_name_plural = '用户'
        ordering = ['username']
    
    def __str__(self):
        return f"{self.username}({self.get_role_display()})"
    
    def is_teacher(self):
        return self.role == 'teacher'
    
    def is_student(self):
        return self.role == 'student'
