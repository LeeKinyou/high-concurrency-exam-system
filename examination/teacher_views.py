import io
import json

from django.db import models
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import teacher_required
from core.constants import Visibility
from core.responses import error_response, success_response

from .excel_importer import import_questions_from_excel
from .models import ClassInfo, Exam, ExamQuestion, Question, StudentClassRelation
from .services import AntiCheatService, ClassService, ExamService, ScoreService
from .utils import generate_exam_qrcode


@teacher_required
def dashboard(request):
    from accounts.models import User

    exams = Exam.objects.filter(created_by=request.user, is_active=True).order_by("-created_at")[:5]
    classes = ClassService.get_classes_for_teacher(request.user)
    exam_count = Exam.objects.filter(created_by=request.user, is_active=True).count()
    question_count = Question.objects.filter(exam__created_by=request.user).count()
    student_count = User.objects.filter(role="student", is_active=True).count()

    # 为新版仪表盘准备考试列表 JSON
    exams_json = json.dumps([{"id": e.id, "title": e.title} for e in exams], ensure_ascii=False)

    return render(request, "teacher/dashboard_new.html", {
        "exams": exams,
        "classes": classes,
        "exam_count": exam_count,
        "question_count": question_count,
        "student_count": student_count,
        "exams_json": exams_json,
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
        Question.objects.filter(
            models.Q(exam__created_by=request.user) | models.Q(exam__isnull=True)
        )
        .select_related("exam")
        .order_by("-id")[:100]
    )
    exams = Exam.objects.filter(created_by=request.user, is_active=True)
    return render(request, "teacher/question_list.html", {"questions": questions, "exams": exams})


@teacher_required
def question_create(request):
    """手动创建题目"""
    if request.method == "POST":
        try:
            exam_id = request.POST.get("exam_id", "").strip()
            q_type = request.POST.get("question_type", "choice")
            content = request.POST.get("content", "").strip()
            answer = request.POST.get("answer", "").strip()
            score_str = request.POST.get("score", "10").strip()
            score = int(score_str) if score_str else 10
            difficulty = request.POST.get("difficulty", "medium")
            explanation = request.POST.get("explanation", "").strip()

            if not content or not answer:
                exams = Exam.objects.filter(created_by=request.user, is_active=True)
                return render(request, "teacher/question_create.html", {"error": "题干和答案不能为空", "exams": exams})

            options = []
            if q_type == "choice":
                for label in ["A", "B", "C", "D"]:
                    opt_text = request.POST.get(f"option_{label}", "").strip()
                    if opt_text:
                        options.append({"label": label, "text": opt_text})

            exam = None
            if exam_id:
                exam = Exam.objects.get(id=int(exam_id))

            question = Question.objects.create(
                exam=exam,
                question_type=q_type,
                content=content,
                options=json.dumps(options, ensure_ascii=False) if options else "[]",
                answer=answer,
                score=score,
                difficulty=difficulty,
                explanation=explanation,
            )

            if exam:
                order = exam.exam_questions.count() + 1
                ExamQuestion.objects.create(exam=exam, question=question, order=order)

            return redirect("/teacher/questions/")
        except Exam.DoesNotExist:
            exams = Exam.objects.filter(created_by=request.user, is_active=True)
            return render(request, "teacher/question_create.html", {"error": "所选考试不存在", "exams": exams})
        except (ValueError, TypeError) as e:
            exams = Exam.objects.filter(created_by=request.user, is_active=True)
            return render(request, "teacher/question_create.html", {"error": f"输入数据有误: {e}", "exams": exams})

    exams = Exam.objects.filter(created_by=request.user, is_active=True)
    return render(request, "teacher/question_create.html", {"exams": exams})


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
@require_POST
def question_delete(request, question_id):
    """删除题目"""
    try:
        question = Question.objects.get(id=question_id)
        # 只能删除自己创建的考试的题目，或无关联的题目
        if question.exam and question.exam.created_by != request.user:
            return error_response(403, "无权删除此题目")
        question.delete()
        return success_response(message="题目已删除")
    except Question.DoesNotExist:
        return error_response(404, "题目不存在")


@teacher_required
@require_POST
def question_link_exam(request, question_id):
    """关联/取消关联题目到考试"""
    try:
        question = Question.objects.get(id=question_id)
        if question.exam and question.exam.created_by != request.user:
            return error_response(403, "无权操作此题目")
    except Question.DoesNotExist:
        return error_response(404, "题目不存在")

    exam_id = request.POST.get("exam_id", "").strip()

    if not exam_id:
        # 取消关联
        ExamQuestion.objects.filter(question=question).delete()
        question.exam = None
        question.save(update_fields=["exam"])
        return success_response(message="已取消关联")

    try:
        exam = Exam.objects.get(id=int(exam_id), created_by=request.user)
    except Exam.DoesNotExist:
        return error_response(404, "考试不存在")

    # 更新关联
    ExamQuestion.objects.filter(question=question).delete()
    question.exam = exam
    question.save(update_fields=["exam"])
    order = exam.exam_questions.count() + 1
    ExamQuestion.objects.create(exam=exam, question=question, order=order)
    return success_response(message=f"已关联到「{exam.title}」")


@teacher_required
def question_sample_excel(request):
    """下载题目导入模板"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "题目导入模板"

    headers = ["题型", "题干", "选项A", "选项B", "选项C", "选项D", "正确答案", "分值", "难度", "解析"]
    ws.append(headers)

    # 示例数据
    ws.append(["choice", "1+1=?", "1", "2", "3", "4", "B", 10, "easy", ""])
    ws.append(["choice", "Python是哪种类型的语言？", "编译型", "解释型", "汇编型", "机器语言", "B", 10, "easy", ""])
    ws.append(["blank", "中国的首都是___", "", "", "", "", "北京", 10, "easy", ""])
    ws.append(["blank", "2+3=___", "", "", "", "", "5", 10, "easy", ""])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    response = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="题目导入模板.xlsx"'
    return response


@teacher_required
def class_list(request):
    classes = ClassService.get_classes_for_teacher(request.user)
    class_data = []
    for cls in classes:
        students = ClassService.get_students_in_class(cls.id)
        class_data.append({"class_info": cls, "students": students, "student_count": students.count()})

    return render(request, "teacher/class_list.html", {"class_data": class_data})


@teacher_required
@require_POST
def class_create(request):
    """创建班级"""
    name = request.POST.get("name", "").strip()
    description = request.POST.get("description", "").strip()

    if not name:
        return redirect("/teacher/classes/")

    ClassService.create_class(request.user, name, description)
    return redirect("/teacher/classes/")


@teacher_required
@require_POST
def class_edit(request, class_id):
    """编辑班级"""
    try:
        cls = ClassInfo.objects.get(id=class_id, teacher=request.user)
    except ClassInfo.DoesNotExist:
        return redirect("/teacher/classes/")

    cls.name = request.POST.get("name", cls.name).strip()
    cls.description = request.POST.get("description", "").strip()
    cls.save()

    return redirect("/teacher/classes/")


@teacher_required
@require_POST
def class_delete(request, class_id):
    """删除班级（软删除）"""
    try:
        cls = ClassInfo.objects.get(id=class_id, teacher=request.user)
        cls.is_active = False
        cls.save(update_fields=["is_active"])
    except ClassInfo.DoesNotExist:
        pass
    return redirect("/teacher/classes/")


@teacher_required
@require_POST
def class_add_student(request, class_id):
    """向班级添加学生"""
    from accounts.models import User

    try:
        cls = ClassInfo.objects.get(id=class_id, teacher=request.user)
    except ClassInfo.DoesNotExist:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return error_response(404, "班级不存在")
        return redirect("/teacher/classes/")

    # 支持通过用户ID或学号添加
    user_id = request.POST.get("user_id", "").strip()
    student_id = request.POST.get("student_id", "").strip()

    try:
        if user_id:
            student = User.objects.get(id=int(user_id), role="student", is_active=True)
        elif student_id:
            student = User.objects.get(student_id=student_id, role="student", is_active=True)
        else:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return error_response(400, "请提供学生ID或学号")
            return redirect("/teacher/classes/")
        ClassService.add_student_to_class(cls.id, student.id)
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return success_response(message="学生已添加")
    except User.DoesNotExist:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return error_response(404, "未找到该学生")
    except Exception:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return error_response(400, "添加失败")

    return redirect("/teacher/classes/")


@teacher_required
@require_POST
def class_remove_student(request, class_id, student_id):
    """从班级移除学生"""
    try:
        cls = ClassInfo.objects.get(id=class_id, teacher=request.user)
        from examination.models import StudentClassRelation
        StudentClassRelation.objects.filter(class_info=cls, student_id=student_id).delete()
    except Exception:
        pass
    return redirect("/teacher/classes/")


@teacher_required
def student_search_api(request):
    """搜索学生（JSON API）"""
    from accounts.models import User

    keyword = request.GET.get("q", "").strip()
    class_id = request.GET.get("class_id")

    if not keyword or len(keyword) < 1:
        return success_response(data=[])

    students = User.objects.filter(
        role="student", is_active=True
    ).filter(
        models.Q(username__icontains=keyword) |
        models.Q(first_name__icontains=keyword) |
        models.Q(student_id__icontains=keyword)
    )

    # 排除已在该班级中的学生
    if class_id:
        existing_ids = StudentClassRelation.objects.filter(
            class_info_id=int(class_id)
        ).values_list("student_id", flat=True)
        students = students.exclude(id__in=existing_ids)

    results = [
        {
            "id": s.id,
            "username": s.username,
            "name": s.first_name or "",
            "student_id": s.student_id or "",
        }
        for s in students[:20]
    ]
    return success_response(data=results)


@teacher_required
@require_POST
def class_import_students(request, class_id):
    """Excel 导入学生并添加到班级"""
    try:
        cls = ClassInfo.objects.get(id=class_id, teacher=request.user)
    except ClassInfo.DoesNotExist:
        return error_response(404, "班级不存在")

    file = request.FILES.get("file")
    if not file:
        return error_response(400, "请上传文件")

    try:
        from accounts.services import AuthService

        result = AuthService.import_students_from_excel(file)

        # 将导入的学生添加到当前班级
        added_count = 0
        for err_msg in result["errors"]:
            pass  # 跳过错误

        # 重新获取所有导入成功的学生（通过查找最近创建的学生）
        from accounts.models import User

        # 从 Excel 重新读取学号，逐个添加到班级
        try:
            from openpyxl import load_workbook

            file.seek(0)
            wb = load_workbook(file, read_only=True)
            ws = wb.active
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row or not row[0]:
                    continue
                sid = str(row[0]).strip()
                try:
                    student = User.objects.get(student_id=sid, role="student")
                    _, created = StudentClassRelation.objects.get_or_create(
                        class_info=cls, student=student
                    )
                    if created:
                        added_count += 1
                except User.DoesNotExist:
                    pass
            wb.close()
        except Exception:
            pass

        return success_response(
            data={
                "success_count": result["success_count"],
                "added_count": added_count,
                "errors": result["errors"],
            },
            message=f"成功导入{result['success_count']}名学生，其中{added_count}人添加到班级",
        )
    except Exception as e:
        return error_response(400, str(e))


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


@teacher_required
def student_list(request):
    """学生管理页面"""
    from accounts.models import User

    students = User.objects.filter(role="student", is_active=True).order_by("-date_joined")

    # 搜索
    keyword = request.GET.get("q", "").strip()
    if keyword:
        students = students.filter(
            models.Q(username__icontains=keyword) |
            models.Q(first_name__icontains=keyword) |
            models.Q(student_id__icontains=keyword)
        )

    return render(request, "teacher/student_list.html", {
        "students": students,
        "keyword": keyword,
    })


@teacher_required
def student_upload(request):
    """批量导入学生"""
    if request.method == "POST":
        file = request.FILES.get("file")
        if not file:
            return render(request, "teacher/student_upload.html", {"error": "请上传文件"})

        try:
            from accounts.services import AuthService

            result = AuthService.import_students_from_excel(file)
            return render(request, "teacher/student_upload.html", {
                "success": f"成功导入{result['success_count']}名学生",
                "errors": result["errors"],
            })
        except Exception as e:
            return render(request, "teacher/student_upload.html", {"error": str(e)})

    return render(request, "teacher/student_upload.html")
