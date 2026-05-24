import pytest
from django.utils import timezone

from accounts.models import User
from core.constants import UserRole
from examination.models import AuditLog, Exam, ExamQuestion, Question
from examination.services import AntiCheatService, ExamService


@pytest.mark.django_db
class TestAntiCheatService:
    def test_log_action(self, teacher, student):
        exam = Exam.objects.create(title="测试", created_by=teacher, visibility="public")
        record = ExamService.start_exam(exam.id, student)

        log = AntiCheatService.log_action(
            record_id=record.id,
            action="screen_switch",
            detail="第1次切屏",
            ip_address="127.0.0.1",
        )

        assert log.record_id == record.id
        assert log.action == "screen_switch"
        assert log.detail == "第1次切屏"

    def test_get_audit_logs(self, teacher, student):
        exam = Exam.objects.create(title="测试", created_by=teacher, visibility="public")
        record = ExamService.start_exam(exam.id, student)

        AntiCheatService.log_action(record.id, "screen_switch", "切屏1")
        AntiCheatService.log_action(record.id, "copy", "复制")
        AntiCheatService.log_action(record.id, "screen_switch", "切屏2")

        logs = AntiCheatService.get_audit_logs(record.id)
        assert logs.count() == 3

    def test_get_suspicious_records(self, teacher, student):
        exam = Exam.objects.create(title="测试", created_by=teacher, visibility="public")
        record = ExamService.start_exam(exam.id, student)

        # 记录 6 次切屏
        for i in range(6):
            AntiCheatService.log_action(record.id, "screen_switch", f"切屏{i+1}")

        suspicious = AntiCheatService.get_suspicious_records(exam.id, threshold=5)
        assert suspicious.count() == 1
        assert suspicious.first().id == record.id

    def test_get_suspicious_records_below_threshold(self, teacher, student):
        exam = Exam.objects.create(title="测试", created_by=teacher, visibility="public")
        record = ExamService.start_exam(exam.id, student)

        # 记录 4 次切屏（低于阈值）
        for i in range(4):
            AntiCheatService.log_action(record.id, "screen_switch", f"切屏{i+1}")

        suspicious = AntiCheatService.get_suspicious_records(exam.id, threshold=5)
        assert suspicious.count() == 0
