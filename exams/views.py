from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Case, When, Value
from django.db import transaction
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from .models import Exam, Question, ExamRecord, ExamQuestion, StudentClassRelation
from .grader import grade_exam
from .decorators import exam_authorization_required
from .excel_importer import ExcelQuestionImporter
import os
import json


@login_required
@exam_authorization_required
def exam_list(request):
    """
    考试列表页面（考试主页）
    需要 exam_authorized 权限标记
    展示时间范围合法的待考卡片列表
    根据学生所在班级过滤可见性
    """
    now = timezone.now()

    # 基础查询：时间范围合法的考试
    base_queryset = Exam.objects.filter(
        is_active=True,
        end_time__gt=now
    )

    # 如果是学生，根据班级可见性过滤
    if request.user.is_student():
        visible_exam_ids = []

        for exam in base_queryset:
            if exam.is_visible_to_student(request.user):
                visible_exam_ids.append(exam.id)

        exams = base_queryset.filter(id__in=visible_exam_ids)
    else:
        # 教师和管理员可以看到所有考试
        exams = base_queryset

    exams = exams.annotate(
        # 添加考试状态标记
        status=Case(
            When(start_time__lte=now, then=Value('ongoing')),
            When(start_time__gt=now, then=Value('not_started')),
            default=Value('over')
        )
    ).order_by('start_time')

    # 检查学生是否已有答卷记录
    for exam in exams:
        record = ExamRecord.objects.filter(
            student=request.user,
            exam=exam
        ).first()
        exam.has_record = record is not None
        exam.is_submitted = record.is_submitted if record else False

    return render(request, 'exams/exam_list.html', {
        'exams': exams,
        'now': now
    })


@login_required
@exam_authorization_required
def exam_detail(request, exam_id):
    """
    考试详情页面
    需要 exam_authorized 权限标记
    检查学生是否有权访问该考试（基于班级可见性）
    """
    exam = get_object_or_404(Exam, id=exam_id)

    # 如果是学生，检查班级可见性权限
    if request.user.is_student():
        if not exam.is_visible_to_student(request.user):
            from django.contrib import messages
            messages.error(request, '您没有权限访问此考试')
            return redirect('exams:exam_list')

    return render(request, 'exams/exam_detail.html', {
        'exam': exam
    })


@login_required
@exam_authorization_required
def exam_take(request, exam_id):
    """
    答题页面
    渲染当前考试的所有题目
    支持选择题和填空题
    检查学生是否有权参加该考试（基于班级可见性）
    """
    exam = get_object_or_404(Exam, id=exam_id)
    now = timezone.now()

    # 如果是学生，检查班级可见性权限
    if request.user.is_student():
        if not exam.is_visible_to_student(request.user):
            from django.contrib import messages
            messages.error(request, '您没有权限参加此考试')
            return redirect('exams:exam_list')

    # 检查考试时间
    if now < exam.start_time:
        return render(request, 'exams/exam_not_started.html', {
            'exam': exam,
            'start_time': exam.start_time
        })

    if now > exam.end_time:
        return render(request, 'exams/exam_over.html', {
            'exam': exam
        })
    
    # 查询所有题目（通过 ExamQuestion 表）
    exam_questions = ExamQuestion.objects.filter(exam=exam).select_related('question').order_by('order', 'id')
    questions = [eq.question for eq in exam_questions]
    
    # 构建题目 ID 到分值的映射
    question_scores = {eq.question.id: eq.score for eq in exam_questions}
    
    # 获取或创建答卷记录
    record, created = ExamRecord.objects.get_or_create(
        student=request.user,
        exam=exam
    )
    
    # 如果已交卷，显示提示
    if record.is_submitted:
        return render(request, 'exams/exam_submitted.html', {
            'exam': exam,
            'record': record
        })
    
    return render(request, 'exams/exam_take.html', {
        'exam': exam,
        'questions': questions,
        'record': record
    })


@login_required
@require_http_methods(["POST"])
@exam_authorization_required
def save_answer(request, exam_id):
    """
    保存答案 API 接口
    接收前端提交的答案草稿并保存到 ExamRecord
    """
    exam = get_object_or_404(Exam, id=exam_id)
    now = timezone.now()
    
    # 检查考试时间
    if now < exam.start_time or now > exam.end_time:
        return JsonResponse({'success': False, 'error': '不在考试时间内'}, status=400)
    
    # 获取或创建答卷记录
    record, created = ExamRecord.objects.get_or_create(
        student=request.user,
        exam=exam
    )
    
    if record.is_submitted:
        return JsonResponse({'success': False, 'error': '考试已交卷'}, status=400)
    
    try:
        # 解析提交的答案
        import json
        data = json.loads(request.body)
        answer_sheet = data.get('answers', {})
        
        # 保存答案草稿
        record.answer_sheet = answer_sheet
        record.save()
        
        return JsonResponse({
            'success': True,
            'message': '答案已保存',
            'saved_at': now.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': '无效的数据格式'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
@exam_authorization_required
def submit_exam(request, exam_id):
    """
    提交考试 API 接口
    接收最终答案并计算得分
    防重复提交机制
    """
    exam = get_object_or_404(Exam, id=exam_id)
    now = timezone.now()
    
    # 检查考试时间
    if now < exam.start_time or now > exam.end_time:
        return JsonResponse({'success': False, 'error': '不在考试时间内'}, status=400)
    
    # 使用事务和 select_for_update 防止重复提交
    try:
        with transaction.atomic():
            # 获取答卷记录（加锁）
            record = ExamRecord.objects.select_for_update().get(
                student=request.user, 
                exam=exam
            )
            
            # 检查是否已交卷
            if record.is_submitted:
                return JsonResponse({
                    'success': False,
                    'error': '考试已交卷'
                }, status=400)
            
            # 解析提交的答案
            import json
            data = json.loads(request.body)
            answer_sheet = data.get('answers', {})
            
            # 保存最终答案
            record.answer_sheet = answer_sheet
            record.is_submitted = True
            record.submitted_at = now
            record.submission_method = 'manual'
            
            # 调用判题算法计算得分
            grading_result = grade_exam(exam, answer_sheet)
            record.final_score = grading_result['total_score']
            record.grading_details = grading_result  # 保存判题详情
            record.save()
            
            return JsonResponse({
                'success': True,
                'message': '考试已提交',
                'score': grading_result['total_score'],
                'max_score': exam.max_score,
                'correct_count': grading_result['correct_count'],
                'question_count': grading_result['question_count'],
                'redirect_url': f'/exams/{exam_id}/result/'
            })
            
    except ExamRecord.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': '答卷记录不存在'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': '无效的数据格式'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@exam_authorization_required
def exam_result(request, exam_id):
    """
    考试结果页面
    根据考试状态显示不同的内容：
    - 考试进行期间：仅显示成绩（总分、各题型得分）
    - 考试结束后：显示完整结果（正确答案、详细解析、答题对比）
    """
    exam = get_object_or_404(Exam, id=exam_id)
    record = get_object_or_404(
        ExamRecord,
        student=request.user,
        exam=exam,
        is_submitted=True
    )

    # 判断考试是否已结束
    is_exam_ended = exam.is_over()

    # 计算题型得分统计
    question_type_scores = {}
    question_type_counts = {}

    # 获取所有题目信息（仅在考试结束后需要）
    questions_with_details = []
    if is_exam_ended:
        exam_questions = ExamQuestion.objects.filter(exam=exam).select_related('question').order_by('order', 'id')
        for eq in exam_questions:
            question = eq.question
            question_id = str(question.id)
            question_detail = {
                'id': question.id,
                'question_type': question.question_type,
                'question_type_display': question.get_question_type_display(),
                'question_text': question.question_text,
                'option_a': question.option_a,
                'option_b': question.option_b,
                'option_c': question.option_c,
                'option_d': question.option_d,
                'score': eq.score,
                'options': question.get_options()
            }

            # 从 grading_details 中获取答题信息
            if record.grading_details and 'question_scores' in record.grading_details:
                score_detail = record.grading_details['question_scores'].get(question_id)
                if score_detail:
                    question_detail.update({
                        'student_answer': score_detail.get('student_answer', ''),
                        'correct_answer': score_detail.get('correct_answer', ''),
                        'is_correct': score_detail.get('is_correct', False),
                        'got_score': score_detail.get('score', 0),
                        'max_score': score_detail.get('max_score', eq.score)
                    })

            questions_with_details.append(question_detail)

    # 计算题型得分（无论考试是否结束都显示）
    if record.grading_details and 'question_scores' in record.grading_details:
        exam_questions = ExamQuestion.objects.filter(exam=exam).select_related('question')
        question_score_map = record.grading_details['question_scores']

        for eq in exam_questions:
            question = eq.question
            q_type = question.question_type
            q_type_display = question.get_question_type_display()
            question_id = str(question.id)

            if q_type not in question_type_scores:
                question_type_scores[q_type] = {
                    'display': q_type_display,
                    'got_score': 0,
                    'max_score': 0,
                    'count': 0
                }

            if question_id in question_score_map:
                score_detail = question_score_map[question_id]
                question_type_scores[q_type]['got_score'] += score_detail.get('score', 0)
                question_type_scores[q_type]['max_score'] += score_detail.get('max_score', eq.score)
                question_type_scores[q_type]['count'] += 1

    context = {
        'exam': exam,
        'record': record,
        'is_exam_ended': is_exam_ended,
        'question_type_scores': question_type_scores.values(),
        'questions_with_details': questions_with_details
    }

    return render(request, 'exams/exam_result.html', context)


@login_required
def excel_upload(request):
    """
    Excel 题目上传页面
    """
    return render(request, 'exams/excel_upload.html')


@login_required
@require_http_methods(["POST"])
def excel_parse(request):
    """
    Excel 文件解析 API
    上传并解析 Excel 文件，返回解析结果供预览
    """
    if 'file' not in request.FILES:
        return JsonResponse({
            'success': False,
            'error': '未找到上传文件'
        })
    
    excel_file = request.FILES['file']
    
    # 验证文件扩展名
    allowed_extensions = ['.xlsx', '.xls']
    file_ext = os.path.splitext(excel_file.name)[1].lower()
    if file_ext not in allowed_extensions:
        return JsonResponse({
            'success': False,
            'error': f'不支持的文件格式，仅支持：{", ".join(allowed_extensions)}'
        })
    
    try:
        # 确保临时目录存在
        temp_dir = settings.MEDIA_ROOT / 'excel_temp'
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存临时文件
        fs = FileSystemStorage(location=temp_dir)
        filename = fs.save(f'{request.user.id}_{excel_file.name}', excel_file)
        file_path = fs.path(filename)
        
        # 解析 Excel
        importer = ExcelQuestionImporter(file_path, request.user)
        parse_result = importer.parse_excel()
        
        if parse_result['success']:
            # 将解析结果存入 session（用于后续导入）
            request.session['excel_import_data'] = {
                'file_path': file_path,
                'questions': parse_result['questions'],
                'errors': parse_result['errors']
            }
            
            return JsonResponse({
                'success': True,
                'message': '文件解析成功',
                'data': {
                    'total_count': parse_result['total_count'],
                    'parsed_count': parse_result['parsed_count'],
                    'error_count': parse_result['error_count'],
                    'questions': parse_result['questions'],
                    'errors': parse_result['errors']
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'error': parse_result.get('error', '文件解析失败')
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'解析失败：{str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def excel_import_confirm(request):
    """
    Excel 题目导入确认 API
    根据用户选择的题目执行导入操作
    """
    try:
        data = json.loads(request.body)
        selected_rows = data.get('selected_rows', [])
        
        if not selected_rows:
            return JsonResponse({
                'success': False,
                'error': '未选择要导入的题目'
            })
        
        # 从 session 获取解析数据
        import_data = request.session.get('excel_import_data')
        if not import_data:
            return JsonResponse({
                'success': False,
                'error': '会话已过期，请重新上传文件'
            })
        
        file_path = import_data['file_path']
        
        # 执行导入
        importer = ExcelQuestionImporter(file_path, request.user)
        importer.parsed_questions = import_data['questions']
        import_result = importer.import_questions(selected_rows)
        
        # 清理 session 和临时文件
        del request.session['excel_import_data']
        try:
            os.remove(file_path)
        except:
            pass
        
        if import_result['success']:
            return JsonResponse({
                'success': True,
                'message': f'成功导入 {import_result["imported_count"]} 道题目',
                'data': import_result
            })
        else:
            return JsonResponse({
                'success': False,
                'error': '导入过程中发生错误'
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': '无效的数据格式'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'导入失败：{str(e)}'
        }, status=500)


@login_required
def question_import_list(request):
    """
    题库导入页面（包含 Excel 导入功能入口）
    """
    return render(request, 'exams/question_import.html')
