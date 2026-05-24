import json

from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import teacher_required
from core.constants import Visibility
from core.responses import error_response, success_response

from .excel_importer import import_questions_from_excel
from .models import ClassInfo, Exam, ExamQuestion, Question
from .services import AntiCheatService, ClassService, ExamService, ScoreService
from .utils import generate_exam_qrcode


@teacher_required
def dashboard(request):
    exams = Exam.objects.filter(created_by=request.user, is_active=True).order_by("-created_at")[:5]
    classes = ClassService.get_classes_for_teacher(request.user)
    exam_count = Exam.objects.filter(created_by=request.user, is_active=True).count()
    question_count = Question.objects.filter(exam__created_by=request.user).count()

    return render(request, "teacher/dashboard.html", {
        "exams": exams,
        "classes": classes,
        "exam_count": exam_count,
        "question_count": question_count,
    })


@teacher_required
def exam_list(request):
    exams = (
        Exam.objects.filter(created_by=request.user)
        .select_related("created_by")
        .prefetch_related("allowed_classes")
        .order_by("-created_at")
    )
    return render(request, "teacher/exam_list.html", {"exams": exams})


@teacher_required
def exam_create(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        duration = int(request.POST.get("duration", 60))
        total_score = int(request.POST.get("total_score", 100))
        visibility = request.POST.get("visibility", Visibility.PUBLIC)
        start_time = request.POST.get("start_time") or None
        end_time = request.POST.get("end_time") or None

        if not title:
            return render(request, "teacher/exam_form.html", {"error": "考试名称不能为空"})

        exam = Exam.objects.create(
            title=title,
            description=description,
            created_by=request.user,
            duration=duration,
            total_score=total_score,
            visibility=visibility,
            start_time=start_time,
            end_time=end_time,
        )

        # 处理指定班级
        class_ids = request.POST.getlist("allowed_classes")
        if class_ids:
            exam.allowed_classes.set(class_ids)

        return redirect(f"/teacher/exams/{exam.id}/edit/")

    classes = ClassService.get_classes_for_teacher(request.user)
    return render(request, "teacher/exam_form.html", {"classes": classes, "exam": None})


@teacher_required
def exam_edit(request, exam_id):
    try:
        exam = Exam.objects.prefetch_related("allowed_classes", "exam_questions__question").get(
            id=exam_id, created_by=request.user
        )
    except Exam.DoesNotExist:
        return redirect("/teacher/exams/")

    if request.method == "POST":
        exam.title = request.POST.get("title", exam.title).strip()
        exam.description = request.POST.get("description", "").strip()
        exam.duration = int(request.POST.get("duration", exam.duration))
        exam.total_score = int(request.POST.get("total_score", exam.total_score))
        exam.visibility = request.POST.get("visibility", exam.visibility)
        exam.start_time = request.POST.get("start_time") or None
        exam.end_time = request.POST.get("end_time") or None
        exam.is_active = request.POST.get("is_active") == "on"
        exam.save()

        class_ids = request.POST.getlist("allowed_classes")
        exam.allowed_classes.set(class_ids)

        return redirect(f"/teacher/exams/{exam.id}/edit/")

    classes = ClassService.get_classes_for_teacher(request.user)
    exam_questions = exam.exam_questions.select_related("question").order_by("order")

    return render(request, "teacher/exam_form.html", {
        "exam": exam,
        "classes": classes,
        "exam_questions": exam_questions,
    })


@teacher_required
@require_POST
def exam_delete(request, exam_id):
    try:
        exam = Exam.objects.get(id=exam_id, created_by=request.user)
        exam.is_active = False
        exam.save(update_fields=["is_active"])
    except Exam.DoesNotExist:
        pass
    return redirect("/teacher/exams/")


@teacher_required
def question_list(request):
    questions = (
        Question.objects.filter(exam__created_by=request.user)
        .select_related("exam")
        .order_by("-id")[:100]
    )
    return render(request, "teacher/question_list.html", {"questions": questions})


@teacher_required
@require_POST
def question_import(request):
    file = request.FILES.get("file")
    if not file:
        return error_response(400, "请上传文件")

    exam_id = request.POST.get("exam_id")
    exam_id = int(exam_id) if exam_id else None

    try:
        result = import_questions_from_excel(file, exam_id)
        return success_response(
            data={"success_count": result["success_count"], "errors": result["errors"]},
            message=f"成功导入{result['success_count']}道题目",
        )
    except Exception as e:
        return error_response(400, str(e))


@teacher_required
def class_list(request):
    classes = ClassService.get_classes_for_teacher(request.user)
    class_data = []
    for cls in classes:
        students = ClassService.get_students_in_class(cls.id)
        class_data.append({"class_info": cls, "students": students, "student_count": students.count()})

    return render(request, "teacher/class_list.html", {"class_data": class_data})


@teacher_required
def score_list(request):
    """成绩管理页面"""
    exams = Exam.objects.filter(created_by=request.user, is_active=True).order_by("-created_at")
    exam_id = request.GET.get("exam_id")

    context = {"exams": exams, "selected_exam_id": int(exam_id) if exam_id else None}

    if exam_id:
        try:
            data = ScoreService.get_exam_scores(int(exam_id), request.user)
            context.update(data)
        except Exception:
            pass

    return render(request, "teacher/score_list.html", context)


@teacher_required
def score_export(request, exam_id):
    """导出考试成绩为 Excel"""
    try:
        file_data = ScoreService.export_exam_scores(exam_id, request.user)
    except Exception:
        return redirect("/teacher/scores/")

    exam = Exam.objects.get(id=exam_id)
    response = HttpResponse(
        file_data,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{exam.title}_scores.xlsx"'
    return response


@teacher_required
def exam_qrcode(request, exam_id):
    """生成考试二维码"""
    try:
        exam = Exam.objects.get(id=exam_id, created_by=request.user)
    except Exam.DoesNotExist:
        return redirect("/teacher/exams/")

    qr_image = generate_exam_qrcode(exam.id, exam.exam_code)

    return render(request, "teacher/exam_qrcode.html", {
        "exam": exam,
        "qr_image": qr_image,
    })


@teacher_required
def audit_logs(request, exam_id):
    """查看考试审计日志"""
    try:
        exam = Exam.objects.get(id=exam_id, created_by=request.user)
    except Exam.DoesNotExist:
        return redirect("/teacher/exams/")

    suspicious_records = AntiCheatService.get_suspicious_records(exam_id)

    return render(request, "teacher/audit_logs.html", {
        "exam": exam,
        "suspicious_records": suspicious_records,
    })
