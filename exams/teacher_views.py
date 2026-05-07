from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Avg, Max, Min, Count, Case, When, F, FloatField, ExpressionWrapper
from django.db.models.functions import TruncDate, TruncHour
from django.db import transaction
from django.contrib import messages
from datetime import timedelta
import json
from .models import Exam, Question, ExamRecord, ExamQuestion, ClassInfo
from accounts.models import User
from .grader import grade_exam


def teacher_required(f):
    """教师权限装饰器"""
    from functools import wraps
    @wraps(f)
    def decorated_function(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:teacher_login')
        if request.user.role != 'teacher' and not request.user.is_superuser:
            messages.error(request, '您没有教师权限')
            return redirect('accounts:permission_denied')
        return f(request, *args, **kwargs)
    return decorated_function


@teacher_required
def dashboard(request):
    """教师仪表盘"""
    now = timezone.now()
    
    # 统计考试数据
    exams = Exam.objects.filter(created_by=request.user)
    total_exams = exams.count()
    ongoing_exams = exams.filter(start_time__lte=now, end_time__gt=now).count()
    not_started_exams = exams.filter(start_time__gt=now).count()
    over_exams = exams.filter(end_time__lte=now).count()
    
    # 统计答卷数据
    exam_ids = list(exams.values_list('id', flat=True))
    all_records = ExamRecord.objects.filter(exam_id__in=exam_ids)
    graded_records = all_records.filter(is_submitted=True).count()
    pending_grading = all_records.filter(is_submitted=True, final_score=0).count()
    
    # 最近考试
    recent_exams = exams.order_by('-created_at')[:5]
    for exam in recent_exams:
        exam.questions_count = exam.exam_questions.count()
    
    # 即将到来的考试
    upcoming_exams = exams.filter(
        end_time__gt=now
    ).order_by('start_time')[:3]
    
    # 成绩统计
    if graded_records > 0:
        score_stats = all_records.filter(
            is_submitted=True
        ).aggregate(
            avg_score=Avg('final_score'),
            max_score=Max('final_score'),
            total_students=Count('student', distinct=True)
        )
        score_stats['has_data'] = True
        score_stats['max_possible_score'] = exams.aggregate(Max('max_score'))['max_score__max'] or 100
    else:
        score_stats = {'has_data': False}
    
    context = {
        'active_menu': 'dashboard',
        'now': now,
        'stats': {
            'total_exams': total_exams,
            'ongoing_exams': ongoing_exams,
            'pending_grading': pending_grading,
            'graded_records': graded_records
        },
        'recent_exams': recent_exams,
        'upcoming_exams': upcoming_exams,
        'score_stats': score_stats
    }
    
    return render(request, 'teacher/dashboard.html', context)


@teacher_required
def exam_list(request):
    """考试管理列表"""
    exams = Exam.objects.filter(created_by=request.user).annotate(
        questions_count=Count('exam_questions')
    ).order_by('-created_at')
    
    for exam in exams:
        exam.student_count = exam.records.count()
        exam.submitted_count = exam.records.filter(is_submitted=True).count()
    
    context = {
        'active_menu': 'exams',
        'exams': exams
    }
    
    return render(request, 'teacher/exam_list.html', context)


@teacher_required
def exam_create(request):
    """创建考试"""
    if request.method == 'POST':
        try:
            title = request.POST.get('title')
            description = request.POST.get('description', '')
            start_time = request.POST.get('start_time')
            end_time = request.POST.get('end_time')
            max_score = request.POST.get('max_score', 100)
            is_active = request.POST.get('is_active') == 'on'
            visibility = request.POST.get('visibility', 'class_specific')
            allowed_class_ids = request.POST.getlist('allowed_classes[]')

            if not title:
                messages.error(request, '考试名称不能为空')
                return redirect('teacher:exam_create')

            start_time = timezone.datetime.fromisoformat(start_time)
            end_time = timezone.datetime.fromisoformat(end_time)

            if end_time <= start_time:
                messages.error(request, '结束时间必须晚于开始时间')
                return redirect('teacher:exam_create')

            exam = Exam.objects.create(
                title=title,
                description=description,
                start_time=timezone.make_aware(start_time) if timezone.is_naive(start_time) else start_time,
                end_time=timezone.make_aware(end_time) if timezone.is_naive(end_time) else end_time,
                max_score=int(max_score),
                is_active=is_active,
                visibility=visibility,
                created_by=request.user
            )

            # 设置允许访问的班级
            if visibility == 'class_specific' and allowed_class_ids:
                exam.allowed_classes.set(allowed_class_ids)

            messages.success(request, f'考试"{title}"创建成功')
            return redirect('teacher:exam_edit', exam_id=exam.id)

        except Exception as e:
            messages.error(request, f'创建失败：{str(e)}')
            return redirect('teacher:exam_create')

    # 获取教师的班级列表（用于选择）
    classes = ClassInfo.objects.filter(teacher=request.user, is_active=True)

    context = {
        'active_menu': 'exams',
        'form_type': 'create',
        'classes': classes
    }

    return render(request, 'teacher/exam_form.html', context)


@teacher_required
def exam_edit(request, exam_id):
    """编辑考试"""
    exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)

    if request.method == 'POST':
        try:
            exam.title = request.POST.get('title')
            exam.description = request.POST.get('description', '')
            start_time = request.POST.get('start_time')
            end_time = request.POST.get('end_time')
            exam.max_score = int(request.POST.get('max_score', 100))
            exam.is_active = request.POST.get('is_active') == 'on'
            exam.visibility = request.POST.get('visibility', 'class_specific')
            allowed_class_ids = request.POST.getlist('allowed_classes[]')

            start_time = timezone.datetime.fromisoformat(start_time)
            end_time = timezone.datetime.fromisoformat(end_time)

            if end_time <= start_time:
                messages.error(request, '结束时间必须晚于开始时间')
                return redirect('teacher:exam_edit', exam_id=exam.id)

            exam.start_time = timezone.make_aware(start_time) if timezone.is_naive(start_time) else start_time
            exam.end_time = timezone.make_aware(end_time) if timezone.is_naive(end_time) else end_time

            exam.save()

            # 更新允许访问的班级
            if exam.visibility == 'class_specific':
                exam.allowed_classes.set(allowed_class_ids)
            else:
                exam.allowed_classes.clear()

            messages.success(request, '考试信息已更新')
            return redirect('teacher:exam_edit', exam_id=exam.id)

        except Exception as e:
            messages.error(request, f'更新失败：{str(e)}')

    exam.questions_count = exam.exam_questions.count()
    exam.student_count = exam.records.count()
    exam.submitted_count = exam.records.filter(is_submitted=True).count()

    # 获取教师的班级列表和当前已选班级
    classes = ClassInfo.objects.filter(teacher=request.user, is_active=True)
    selected_class_ids = list(exam.allowed_classes.values_list('id', flat=True))

    context = {
        'active_menu': 'exams',
        'form_type': 'edit',
        'exam': exam,
        'classes': classes,
        'selected_class_ids': selected_class_ids
    }

    return render(request, 'teacher/exam_form.html', context)


@teacher_required
def exam_stats(request, exam_id):
    """获取考试统计数据（AJAX）"""
    exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)
    
    stats = {
        'questions_count': exam.questions.count(),
        'student_count': exam.records.count(),
        'submitted_count': exam.records.filter(is_submitted=True).count(),
        'average_score': None,
        'max_score': None,
        'min_score': None
    }
    
    # 计算成绩统计
    submitted_records = exam.records.filter(is_submitted=True, final_score__gt=0)
    if submitted_records.exists():
        from django.db.models import Avg, Max, Min
        score_stats = submitted_records.aggregate(
            avg=Avg('final_score'),
            max=Max('final_score'),
            min=Min('final_score')
        )
        stats['average_score'] = round(float(score_stats['avg']), 2) if score_stats['avg'] else None
        stats['max_score'] = float(score_stats['max']) if score_stats['max'] else None
        stats['min_score'] = float(score_stats['min']) if score_stats['min'] else None
    
    return JsonResponse({'success': True, **stats})


@teacher_required
def exam_records(request, exam_id):
    """查看考试答卷记录"""
    exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)
    records = ExamRecord.objects.filter(
        exam=exam,
        is_submitted=True
    ).select_related('student').order_by('-final_score', '-submitted_at')
    
    context = {
        'active_menu': 'exams',
        'exam': exam,
        'records': records,
    }
    
    return render(request, 'teacher/exam_records.html', context)


@teacher_required
def exam_questions(request, exam_id):
    """题目管理（按考试）"""
    exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)
    exam_questions = ExamQuestion.objects.filter(exam=exam).select_related('question').order_by('order', 'id')
    
    total_score = sum(eq.score for eq in exam_questions)
    
    # 获取所有其他考试的题目用于复用
    exams = Exam.objects.filter(created_by=request.user).exclude(id=exam_id)
    
    context = {
        'active_menu': 'questions',
        'exam': exam,
        'questions': [eq.question for eq in exam_questions],  # 保持模板兼容
        'exam_questions': exam_questions,  # 新增：包含关联信息
        'total_score': total_score,
        'exams': exams
    }
    
    return render(request, 'teacher/exam_questions.html', context)


@teacher_required
def questions(request):
    """题目管理主页（所有考试）"""
    exams = Exam.objects.filter(created_by=request.user).annotate(
        questions_count=Count('exam_questions')
    ).order_by('-created_at')
    
    total_questions = sum(exam.questions_count for exam in exams)
    
    context = {
        'active_menu': 'questions',
        'exams': exams,
        'total_questions': total_questions
    }
    
    return render(request, 'teacher/questions.html', context)


@require_http_methods(["GET"])
@teacher_required
def get_existing_questions(request, exam_id):
    """获取指定考试的题目列表（用于复用）"""
    exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)
    source_exam_id = request.GET.get('source_exam_id')
    
    if not source_exam_id:
        return JsonResponse({
            'success': False,
            'error': '请指定源考试 ID'
        }, status=400)
    
    try:
        source_exam = get_object_or_404(Exam, id=source_exam_id, created_by=request.user)
        exam_questions = ExamQuestion.objects.filter(
            exam=source_exam
        ).select_related('question').order_by('order', 'id')
        
        questions_data = [{
            'id': eq.question.id,
            'question_type': eq.question.question_type,
            'question_text': eq.question.question_text,
            'score': eq.score,  # 使用当前考试的分值
            'answer': eq.question.answer,
            'option_a': eq.question.option_a,
            'option_b': eq.question.option_b,
            'option_c': eq.question.option_c,
            'option_d': eq.question.option_d,
        } for eq in exam_questions]
        
        return JsonResponse({
            'success': True,
            'questions': questions_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@require_http_methods(["POST"])
@teacher_required
def add_existing_questions(request, exam_id):
    """添加已有题目到当前考试"""
    exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)
    
    try:
        data = json.loads(request.body)
        question_ids = data.get('question_ids', [])
        
        if not question_ids:
            return JsonResponse({
                'success': False,
                'error': '请选择要添加的题目'
            }, status=400)
        
        # 获取源题目
        source_questions = Question.objects.filter(id__in=question_ids)
        
        # 通过 ExamQuestion 表关联到当前考试
        added_count = 0
        max_order = ExamQuestion.objects.filter(exam=exam).aggregate(Max('order'))['order__max'] or 0
        
        for source_q in source_questions:
            # 检查是否已存在
            exists = ExamQuestion.objects.filter(
                exam=exam,
                question=source_q
            ).exists()
            
            if not exists:
                ExamQuestion.objects.create(
                    exam=exam,
                    question=source_q,
                    score=source_q.score,
                    order=max_order + added_count + 1
                )
                added_count += 1
        
        return JsonResponse({
            'success': True,
            'added_count': added_count,
            'message': f'成功添加 {added_count} 道题目'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@require_http_methods(["GET"])
@teacher_required
def get_question_detail(request, exam_id, question_id):
    """获取题目详情（用于编辑）"""
    exam_question = get_object_or_404(ExamQuestion, id=question_id, exam_id=exam_id)
    question = exam_question.question
    
    question_data = {
        'id': question.id,
        'question_type': question.question_type,
        'question_text': question.question_text,
        'option_a': question.option_a,
        'option_b': question.option_b,
        'option_c': question.option_c,
        'option_d': question.option_d,
        'answer': question.answer,
        'score': exam_question.score,  # 返回当前考试的分值
    }
    
    return JsonResponse(question_data)


@require_http_methods(["POST"])
@teacher_required
def update_question_order(request, exam_id, question_id):
    """更新题目顺序"""
    exam_question = get_object_or_404(ExamQuestion, id=question_id, exam_id=exam_id)
    
    try:
        data = json.loads(request.body)
        order = data.get('order', 0)
        exam_question.order = order
        exam_question.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@require_http_methods(["POST"])
@teacher_required
def create_question(request, exam_id):
    """创建题目（先创建题目，再关联到考试）"""
    exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)
    
    try:
        data = json.loads(request.body)
        
        # 验证必填字段
        if not data.get('question_type'):
            return JsonResponse({
                'success': False,
                'error': '请选择题型'
            }, status=400)
        
        if not data.get('question_text'):
            return JsonResponse({
                'success': False,
                'error': '请输入题干内容'
            }, status=400)
        
        if not data.get('answer'):
            return JsonResponse({
                'success': False,
                'error': '请输入正确答案'
            }, status=400)
        
        # 第一步：创建题目
        question = Question.objects.create(
            created_by=request.user,
            question_type=data.get('question_type'),
            question_text=data.get('question_text'),
            option_a=data.get('option_a', ''),
            option_b=data.get('option_b', ''),
            option_c=data.get('option_c', ''),
            option_d=data.get('option_d', ''),
            answer=data.get('answer'),
            score=int(data.get('score', 5))
        )
        
        # 第二步：关联到考试
        max_order = ExamQuestion.objects.filter(exam=exam).aggregate(Max('order'))['order__max'] or 0
        ExamQuestion.objects.create(
            exam=exam,
            question=question,
            score=question.score,
            order=max_order + 1
        )
        
        return JsonResponse({
            'success': True,
            'question_id': question.id
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@require_http_methods(["POST"])
@teacher_required
def update_question(request, exam_id, question_id):
    """更新题目（只更新题目表，不修改关联）"""
    # 通过 ExamQuestion 表找到对应的题目
    exam_question = get_object_or_404(ExamQuestion, id=question_id, exam_id=exam_id)
    question = exam_question.question
    
    try:
        data = json.loads(request.body)
        
        # 验证必填字段
        if not data.get('question_type'):
            return JsonResponse({
                'success': False,
                'error': '请选择题型'
            }, status=400)
        
        if not data.get('question_text'):
            return JsonResponse({
                'success': False,
                'error': '请输入题干内容'
            }, status=400)
        
        if not data.get('answer'):
            return JsonResponse({
                'success': False,
                'error': '请输入正确答案'
            }, status=400)
        
        question.question_type = data.get('question_type', question.question_type)
        question.question_text = data.get('question_text', question.question_text)
        question.option_a = data.get('option_a', question.option_a)
        question.option_b = data.get('option_b', question.option_b)
        question.option_c = data.get('option_c', question.option_c)
        question.option_d = data.get('option_d', question.option_d)
        question.answer = data.get('answer', question.answer)
        question.score = int(data.get('score', question.score))
        question.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@require_http_methods(["POST"])
@teacher_required
def delete_question(request, exam_id, question_id):
    """删除题目（从考试中移除关联，不删除题目本身）"""
    exam_question = get_object_or_404(ExamQuestion, id=question_id, exam_id=exam_id)
    exam_question.delete()
    return JsonResponse({'success': True})


@require_http_methods(["POST"])
@teacher_required
def delete_exam(request, exam_id):
    """删除考试"""
    exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)
    exam_title = exam.title
    exam.delete()
    return JsonResponse({
        'success': True,
        'message': f'考试"{exam_title}"已删除'
    })


@teacher_required
def qrcode(request):
    """二维码管理"""
    exams = Exam.objects.filter(
        created_by=request.user,
        is_active=True
    ).order_by('-created_at')
    
    selected_exam = request.GET.get('exam_id')
    
    context = {
        'active_menu': 'qrcode',
        'exams': exams,
        'selected_exam': int(selected_exam) if selected_exam else None
    }
    
    return render(request, 'teacher/qrcode.html', context)


@teacher_required
def scores(request):
    """成绩管理"""
    exams = Exam.objects.filter(created_by=request.user).order_by('-created_at')
    
    context = {
        'active_menu': 'scores',
        'exams': exams
    }
    
    return render(request, 'teacher/scores.html', context)


@teacher_required
def students(request):
    """学生管理"""
    students = User.objects.filter(role='student').annotate(
        exam_count=Count('exam_records'),
        average_score=Avg('exam_records__final_score'),
        highest_score=Max('exam_records__final_score'),
        lowest_score=Min('exam_records__final_score')
    ).order_by('student_id')
    
    total_students = students.count()
    active_students = students.exclude(last_login__isnull=True).count()
    total_records = sum(s.exam_count for s in students)
    recent_logins = students.filter(
        last_login__gte=timezone.now() - timedelta(days=7)
    ).count()
    
    context = {
        'active_menu': 'students',
        'students': students,
        'total_students': total_students,
        'active_students': active_students,
        'total_records': total_records,
        'recent_logins': recent_logins
    }
    
    return render(request, 'teacher/students.html', context)


@teacher_required
def question_bank(request):
    """题库管理"""
    # 获取教师创建的所有题目
    questions = Question.objects.filter(created_by=request.user)
    
    # 统计
    total_questions = questions.count()
    choice_count = questions.filter(question_type='choice').count()
    blank_count = questions.filter(question_type='blank').count()
    
    # 统计关联的考试数量
    exam_count = Exam.objects.filter(
        created_by=request.user,
        exam_questions__isnull=False
    ).distinct().count()
    
    # 获取教师的考试列表（用于导入时选择）
    exams = Exam.objects.filter(created_by=request.user).order_by('-created_at')
    
    context = {
        'active_menu': 'questions',
        'questions': questions[:50],  # 默认显示前 50 道
        'total_questions': total_questions,
        'choice_count': choice_count,
        'blank_count': blank_count,
        'exam_count': exam_count,
        'exams': exams
    }
    
    return render(request, 'teacher/question_bank.html', context)


@login_required
@require_http_methods(["POST"])
def batch_add_questions(request, exam_id):
    """批量添加题目到考试"""
    try:
        exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)
        data = json.loads(request.body)
        question_ids = data.get('question_ids', [])
        
        # 验证题目属于该教师
        questions = Question.objects.filter(
            id__in=question_ids,
            created_by=request.user
        )
        
        added_count = 0
        for question in questions:
            # 检查是否已存在
            if not ExamQuestion.objects.filter(exam=exam, question=question).exists():
                ExamQuestion.objects.create(
                    exam=exam,
                    question=question,
                    order=exam.questions.count() + 1
                )
                added_count += 1
        
        return JsonResponse({
            'success': True,
            'added_count': added_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
