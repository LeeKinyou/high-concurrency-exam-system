from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    自定义用户管理后台
    """
    list_display = [
        'username',
        'student_id',
        'role',
        'email',
        'is_staff',
        'is_active',
        'date_joined'
    ]
    list_filter = ['role', 'is_staff', 'is_active']
    search_fields = ['username', 'email', 'student_id']
    ordering = ['username']
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('个人信息', {'fields': ('email', 'role', 'student_id')}),
        ('权限', {'fields': ('is_staff', 'is_active', 'is_superuser', 'groups', 'user_permissions')}),
        ('重要日期', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username',
                'email',
                'role',
                'student_id',
                'password1',
                'password2',
                'is_staff',
                'is_active'
            ),
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """保存用户时自动设置学号"""
        super().save_model(request, obj, form, change)
        if obj.role == 'student' and not obj.student_id:
            obj.student_id = f"S{obj.id:08d}"
            obj.save()
