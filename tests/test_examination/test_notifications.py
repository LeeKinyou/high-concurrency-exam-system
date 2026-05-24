import pytest

from accounts.models import User
from core.constants import UserRole
from examination.models import Exam, Notification
from examination.services import NotificationService


@pytest.mark.django_db
class TestNotificationService:
    def test_create_notification(self, teacher, student):
        notification = NotificationService.create_notification(
            user=student,
            title="测试通知",
            content="这是一条测试通知",
            notification_type="system",
        )

        assert notification.user_id == student.id
        assert notification.title == "测试通知"
        assert notification.is_read is False

    def test_get_unread_notifications(self, teacher, student):
        NotificationService.create_notification(student, "通知1", "内容1")
        NotificationService.create_notification(student, "通知2", "内容2")
        NotificationService.create_notification(teacher, "教师通知", "内容")

        unread = NotificationService.get_unread_notifications(student)
        assert unread.count() == 2

    def test_mark_as_read(self, teacher, student):
        notification = NotificationService.create_notification(student, "通知", "内容")

        result = NotificationService.mark_as_read(notification.id, student)
        assert result is True

        notification.refresh_from_db()
        assert notification.is_read is True

    def test_mark_as_read_wrong_user(self, teacher, student):
        notification = NotificationService.create_notification(student, "通知", "内容")

        result = NotificationService.mark_as_read(notification.id, teacher)
        assert result is False

    def test_mark_all_as_read(self, teacher, student):
        NotificationService.create_notification(student, "通知1", "内容1")
        NotificationService.create_notification(student, "通知2", "内容2")
        NotificationService.create_notification(teacher, "教师通知", "内容")

        NotificationService.mark_all_as_read(student)

        unread_student = NotificationService.get_unread_notifications(student)
        assert unread_student.count() == 0

        unread_teacher = NotificationService.get_unread_notifications(teacher)
        assert unread_teacher.count() == 1

    def test_notify_exam_created(self, teacher, student):
        exam = Exam.objects.create(title="新考试", created_by=teacher, visibility="public")
        NotificationService.notify_exam_created(exam)

        notifications = Notification.objects.filter(user=student)
        assert notifications.count() == 1
        assert "新考试" in notifications.first().title
