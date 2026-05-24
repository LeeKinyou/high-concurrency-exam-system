import json
import logging

from celery import shared_task
from django.utils import timezone

from core.constants import RecordStatus

logger = logging.getLogger(__name__)


@shared_task
def auto_submit_expired_exams():
    """自动提交已过期考试的答卷。

    扫描所有状态为 draft 且考试已结束的记录，自动提交并判分。
    """
    from .grader import grade_exam
    from .models import ExamRecord

    now = timezone.now()
    expired_records = (
        ExamRecord.objects.filter(
            status=RecordStatus.DRAFT,
            exam__end_time__isnull=False,
            exam__end_time__lte=now,
        )
        .select_related("exam", "student")
    )

    submitted_count = 0
    for record in expired_records:
        try:
            # 直接判分并更新记录，不调用 submit_exam（避免时间检查）
            answers = record.get_answers_dict()
            score, details = grade_exam(record.exam_id, answers)

            record.submit_time = now
            record.submission_method = "auto"
            record.score = score
            record.grading_details = json.dumps(details, ensure_ascii=False)
            record.is_graded = True
            record.status = RecordStatus.AUTO_GRADED
            record.save()

            submitted_count += 1
            logger.info(f"自动提交考试记录: record_id={record.id}, exam={record.exam.title}, student={record.student.username}")
        except Exception as e:
            logger.error(f"自动提交失败: record_id={record.id}, error={e}")

    if submitted_count > 0:
        logger.info(f"自动交卷完成，共提交 {submitted_count} 份答卷")

    return submitted_count
