from django.contrib import admin

from .models import AuditLog, ClassInfo, Exam, ExamQuestion, ExamRecord, Notification, Question, StudentClassRelation


@admin.register(ClassInfo)
class ClassInfoAdmin(admin.ModelAdmin):
    list_display = ("name", "teacher", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "teacher__username")


@admin.register(StudentClassRelation)
class StudentClassRelationAdmin(admin.ModelAdmin):
    list_display = ("student", "class_info", "joined_at")
    list_filter = ("class_info",)


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ("title", "created_by", "visibility", "is_active", "created_at")
    list_filter = ("visibility", "is_active")
    search_fields = ("title", "created_by__username")
    readonly_fields = ("exam_code",)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("content", "exam", "question_type", "score", "difficulty")
    list_filter = ("question_type", "difficulty")
    search_fields = ("content",)


@admin.register(ExamQuestion)
class ExamQuestionAdmin(admin.ModelAdmin):
    list_display = ("exam", "question", "order")


@admin.register(ExamRecord)
class ExamRecordAdmin(admin.ModelAdmin):
    list_display = ("exam", "student", "score", "status", "is_graded", "submit_time")
    list_filter = ("status", "is_graded")
    search_fields = ("exam__title", "student__username")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("record", "action", "ip_address", "created_at")
    list_filter = ("action",)
    readonly_fields = ("record", "action", "detail", "ip_address", "created_at")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "notification_type", "is_read", "created_at")
    list_filter = ("notification_type", "is_read")
    search_fields = ("title", "user__username")
