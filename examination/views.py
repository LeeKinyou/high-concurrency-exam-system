import json

from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from core.constants import UserRole
from core.responses import error_response, success_response
from core.utils import get_client_ip

from .decorators import exam_access_required
from .models import Exam, ExamRecord
from .services import ExamService


@require_POST
def exam_enter(request, exam_id):
    """进入考试验证（扫码或输入考试码）"""
    if not request.user.is_authenticated or request.user.role != UserRole.STUDENT:
        return error_response(401, "请先登录")

    code = request.POST.get("code", "").strip()
    if not code:
        return error_response(400, "请输入考试码")

    try:
        exam = Exam.objects.get(id=exam_id, is_active=True)
    except Exam.DoesNotExist:
        return error_response(404, "考试不存在")

    if exam.exam_code != code:
        return error_response(400, "考试码错误")

    return success_response(data={"exam_id": exam.id, "redirect": f"/exams/{exam.id}/take/"})


def exam_list(request):
    if not request.user.is_authenticated or request.user.role != UserRole.STUDENT:
        return redirect("/accounts/login/")

    exams = ExamService.get_available_exams(request.user)

    # 标记学生已参加的考试
    student_records = {
        r.exam_id: r
        for r in ExamRecord.objects.filter(student=request.user).select_related("exam")
    }
    exam_data = []
    for exam in exams:
        record = student_records.get(exam.id)
        exam_data.append({
            "exam": exam,
            "record": record,
        })

    return render(request, "exams/exam_list.html", {"exam_data": exam_data})


def exam_detail(request, exam_id):
    if not request.user.is_authenticated or request.user.role != UserRole.STUDENT:
        return redirect("/accounts/login/")

    try:
        exam = ExamService.get_exam_detail(exam_id)
    except Exception:
        return redirect("/exams/")

    record = ExamService.get_or_create_record(exam_id, request.user)
    question_count = exam.exam_questions.count()

    return render(request, "exams/exam_detail.html", {
        "exam": exam,
        "record": record,
        "question_count": question_count,
    })


@exam_access_required
def exam_take(request, exam_id):
    try:
        record = ExamService.start_exam(exam_id, request.user)
    except Exception as e:
        return redirect(f"/exams/{exam_id}/")

    exam = record.exam
    exam_questions = exam.exam_questions.select_related("question").order_by("order")

    questions = []
    for eq in exam_questions:
        q = eq.question
        questions.append({
            "id": q.id,
            "type": q.question_type,
            "content": q.content,
            "options": q.get_options_list(),
            "score": q.score,
            "order": eq.order,
        })

    saved_answers = record.get_answers_dict()

    return render(request, "exams/exam_take.html", {
        "exam": exam,
        "record": record,
        "questions": questions,
        "saved_answers": json.dumps(saved_answers, ensure_ascii=False),
    })


@require_POST
@exam_access_required
def exam_submit(request, exam_id):
    try:
        data = json.loads(request.body)
        answers = data.get("answers", {})
    except (json.JSONDecodeError, TypeError):
        return error_response(400, "答案格式错误")

    record = ExamService.get_or_create_record(exam_id, request.user)
    if not record:
        return error_response(404, "考试记录不存在")

    # 先保存答案
    ExamService.save_answers(record.id, answers)

    # 再提交
    try:
        record = ExamService.submit_exam(
            record.id, request.user, get_client_ip(request)
        )
    except Exception as e:
        return error_response(400, str(e))

    return success_response(
        data={
            "score": record.score,
            "total_score": record.total_score,
            "record_id": record.id,
        },
        message="提交成功",
    )


@require_POST
@exam_access_required
def exam_save_answer(request, exam_id):
    try:
        data = json.loads(request.body)
        answers = data.get("answers", {})
    except (json.JSONDecodeError, TypeError):
        return error_response(400, "答案格式错误")

    record = ExamService.get_or_create_record(exam_id, request.user)
    if not record:
        return error_response(404, "考试记录不存在")

    try:
        ExamService.save_answers(record.id, answers)
    except Exception as e:
        return error_response(400, str(e))

    return success_response(message="草稿已保存")


@exam_access_required
def exam_result(request, exam_id):
    record = ExamService.get_or_create_record(exam_id, request.user)
    if not record:
        return redirect(f"/exams/{exam_id}/")

    try:
        record = ExamService.get_exam_result(record.id, request.user)
    except Exception:
        return redirect(f"/exams/{exam_id}/")

    details = record.get_grading_details_dict()
    exam_questions = record.exam.exam_questions.select_related("question").order_by("order")

    result_items = []
    for eq in exam_questions:
        q = eq.question
        detail = details.get(str(q.id), {})
        result_items.append({
            "question": q,
            "detail": detail,
        })

    return render(request, "exams/exam_result.html", {
        "exam": record.exam,
        "record": record,
        "result_items": result_items,
    })


@require_POST
@exam_access_required
def exam_log_action(request, exam_id):
    """记录考试中的操作（切屏、复制等）"""
    from .services import AntiCheatService

    try:
        data = json.loads(request.body)
        action = data.get("action", "")
        detail = data.get("detail", "")
    except (json.JSONDecodeError, TypeError):
        return error_response(400, "请求格式错误")

    if action not in ["screen_switch", "copy", "paste", "focus_loss", "tab_switch"]:
        return error_response(400, "无效的操作类型")

    record = ExamService.get_or_create_record(exam_id, request.user)
    if not record or record.status != "draft":
        return error_response(400, "考试记录无效")

    AntiCheatService.log_action(
        record_id=record.id,
        action=action,
        detail=detail,
        ip_address=get_client_ip(request),
    )

    return success_response(message="已记录")


@require_POST
def notification_mark_read(request, notification_id):
    """标记通知为已读"""
    from .services import NotificationService

    if not request.user.is_authenticated:
        return error_response(401, "请先登录")

    success = NotificationService.mark_as_read(notification_id, request.user)
    if not success:
        return error_response(404, "通知不存在")

    return success_response(message="已标记为已读")


@require_POST
def notification_mark_all_read(request):
    """标记所有通知为已读"""
    from .services import NotificationService

    if not request.user.is_authenticated:
        return error_response(401, "请先登录")

    NotificationService.mark_all_as_read(request.user)
    return success_response(message="已全部标记为已读")
