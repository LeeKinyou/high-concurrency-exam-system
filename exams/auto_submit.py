"""
兜底交卷策略
自动检查并处理考试时间已结束但未交卷的答卷记录
"""
import logging
from django.utils import timezone
from django.db import transaction
from .models import Exam, ExamRecord
from .grader import grade_exam

logger = logging.getLogger(__name__)


def auto_submit_overdue_exams():
    """
    兜底交卷函数
    检查所有考试已结束但未交卷的记录，自动判阅并提交
    
    Returns:
        dict: 处理结果统计
            - total_count: 总处理数
            - success_count: 成功数
            - error_count: 错误数
            - details: 详细处理日志
    """
    now = timezone.now()
    
    # 查询所有已结束的考试
    overdue_exams = Exam.objects.filter(
        end_time__lt=now,
        is_active=True
    )
    
    total_count = 0
    success_count = 0
    error_count = 0
    details = []
    
    for exam in overdue_exams:
        # 查询该考试未交卷的记录
        unsubmitted_records = ExamRecord.objects.filter(
            exam=exam,
            is_submitted=False
        )
        
        for record in unsubmitted_records:
            total_count += 1
            
            try:
                with transaction.atomic():
                    # 重新查询并加锁
                    record = ExamRecord.objects.select_for_update().get(
                        id=record.id
                    )
                    
                    # 再次检查是否已交卷（避免并发问题）
                    if record.is_submitted:
                        logger.info(f"记录 {record.id} 已被其他进程提交，跳过")
                        continue
                    
                    # 使用最后一次同步的草稿答案
                    answer_sheet = record.answer_sheet or {}
                    
                    # 调用判题算法
                    grading_result = grade_exam(exam, answer_sheet)
                    
                    # 更新记录
                    record.is_submitted = True
                    record.submitted_at = now
                    record.final_score = grading_result['total_score']
                    record.grading_details = grading_result
                    record.submission_method = 'auto'
                    record.save()
                    
                    logger.info(
                        f"自动提交成功 - 考试：{exam.title}, "
                        f"学生：{record.student.username}, "
                        f"得分：{grading_result['total_score']}"
                    )
                    
                    details.append({
                        'exam_id': exam.id,
                        'exam_title': exam.title,
                        'student_id': record.student.id,
                        'student_username': record.student.username,
                        'record_id': record.id,
                        'score': grading_result['total_score'],
                        'status': 'success'
                    })
                    
                    success_count += 1
                    
            except Exception as e:
                error_count += 1
                error_msg = f"自动提交失败 - 记录 ID: {record.id}, 错误：{str(e)}"
                logger.error(error_msg)
                
                details.append({
                    'exam_id': exam.id,
                    'exam_title': exam.title,
                    'student_id': record.student.id,
                    'student_username': record.student.username,
                    'record_id': record.id,
                    'error': str(e),
                    'status': 'error'
                })
    
    result = {
        'total_count': total_count,
        'success_count': success_count,
        'error_count': error_count,
        'details': details
    }
    
    logger.info(f"兜底交卷完成 - 总计：{total_count}, 成功：{success_count}, 失败：{error_count}")
    
    return result


def check_and_submit_for_exam(exam_id):
    """
    针对特定考试的兜底交卷函数
    
    Args:
        exam_id: 考试 ID
    
    Returns:
        dict: 处理结果统计
    """
    try:
        exam = Exam.objects.get(id=exam_id)
        now = timezone.now()
        
        # 检查考试是否已结束
        if exam.end_time >= now:
            return {
                'success': False,
                'error': '考试尚未结束',
                'total_count': 0,
                'success_count': 0,
                'error_count': 0
            }
        
        # 调用通用兜底交卷函数
        result = auto_submit_overdue_exams()
        
        return {
            'success': True,
            **result
        }
        
    except Exam.DoesNotExist:
        return {
            'success': False,
            'error': '考试不存在',
            'total_count': 0,
            'success_count': 0,
            'error_count': 0
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'total_count': 0,
            'success_count': 0,
            'error_count': 0
        }
