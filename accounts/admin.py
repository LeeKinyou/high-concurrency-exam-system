from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import LoginAttempt, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "first_name", "role", "student_id", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("username", "first_name", "student_id", "email")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("扩展信息", {"fields": ("role", "student_id", "must_change_password", "last_login_ip")}),
    )


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ("username", "ip_address", "success", "attempted_at")
    list_filter = ("success",)
    search_fields = ("username", "ip_address")
    readonly_fields = ("ip_address", "username", "success", "attempted_at")
