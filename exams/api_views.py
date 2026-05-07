from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Avg, Max, Min, Count, F
from django.db import transaction
from accounts.models import User
from exams.models import Exam, Question, ExamRecord
from accounts.utils import generate_session_id
import json
from datetime import datetime, timedelta
from django.core.files.uploadedfile import UploadedFile


@login_required
@require_http_methods(["POST"])
def api_generate_qr(request):
    """生成考试二维码"""
    try:
        data = json.loads(request.body)
        exam_id = data.get('exam_id')
        
        if not exam_id:
            return JsonResponse({
                'success': False,
                'error': '缺少考试 ID'
            })
        
        exam = get_object_or_404(Exam, id=exam_id)
        
        # 生成 session_id
        session_id = generate_session_id()
        
        # 将 exam_id 与 session_id 关联存储
        from django.core.cache import cache
        cache.set(f'qr_exam:{session_id}', exam_id, 3600)
        
        # 生成二维码 URL（使用原有系统的 URL 格式）
        qr_code_url = f'/accounts/generate-qr/?session_id={session_id}'
        
        return JsonResponse({
            'success': True,
            'session_id': session_id,
            'qr_code_url': qr_code_url,
            'exam_title': exam.title
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def api_qr_stats(request, exam_id):
    """获取二维码扫码统计"""
    try:
        # 这里需要从 Redis 或其他存储中获取扫码记录
        # 由于原系统已有扫码逻辑，这里模拟返回数据
        from django.core.cache import cache
        
        # 获取最近扫码的学生
        scan_records = []
        scan_count = 0
        
        # 实际应用中应该从 Redis 中读取
        # 这里返回空数据，实际功能依赖原有扫码系统
        
        return JsonResponse({
            'success': True,
            'scan_count': scan_count,
            'records': scan_records
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def api_scores(request):
    """获取成绩列表"""
    try:
        exam_id = request.GET.get('exam_id')
        
        # 获取教师创建的所有考试
        teacher_exams = Exam.objects.filter(created_by=request.user)
        
        if exam_id:
            teacher_exams = teacher_exams.filter(id=exam_id)
        
        exam_ids = list(teacher_exams.values_list('id', flat=True))
        
        # 检查是否有考试
        if not exam_ids:
            return JsonResponse({
                'success': True,
                'total': 0,
                'average': 0,
                'highest': 0,
                'pass_rate': 0,
                'score_distribution': {
                    'labels': ['0-59', '60-69', '70-79', '80-89', '90-100'],
                    'counts': [0, 0, 0, 0, 0]
                },
                'segments': {
                    'excellent': 0,
                    'good': 0,
                    'medium': 0,
                    'pass': 0,
                    'fail': 0
                },
                'records': []
            })
        
        # 获取成绩记录
        records = ExamRecord.objects.filter(
            exam_id__in=exam_ids,
            is_submitted=True
        ).select_related('student', 'exam').order_by('-submitted_at')
        
        # 计算统计数据
        total = records.count()
        
        if total > 0:
            average = records.aggregate(Avg('final_score'))['final_score__avg'] or 0
            highest = records.aggregate(Max('final_score'))['final_score__max'] or 0
            passed = records.filter(final_score__gte=0.6 * F('exam__max_score')).count()
            pass_rate = (passed / total * 100) if total > 0 else 0
        else:
            average = 0
            highest = 0
            pass_rate = 0
        
        # 分数段统计
        score_distribution = {
            'labels': ['0-59', '60-69', '70-79', '80-89', '90-100'],
            'counts': [0, 0, 0, 0, 0]
        }
        
        segments = {
            'excellent': 0,  # 90-100
            'good': 0,       # 80-89
            'medium': 0,     # 70-79
            'pass': 0,       # 60-69
            'fail': 0        # 0-59
        }
        
        for record in records:
            score = float(record.final_score or 0)
            max_score = float(record.exam.max_score or 100)
            percentage = (score / max_score * 100) if max_score > 0 else 0
            
            if percentage >= 90:
                score_distribution['counts'][4] += 1
                segments['excellent'] += 1
            elif percentage >= 80:
                score_distribution['counts'][3] += 1
                segments['good'] += 1
            elif percentage >= 70:
                score_distribution['counts'][2] += 1
                segments['medium'] += 1
            elif percentage >= 60:
                score_distribution['counts'][1] += 1
                segments['pass'] += 1
            else:
                score_distribution['counts'][0] += 1
                segments['fail'] += 1
        
        # 构建记录列表
        records_data = []
        for record in records:
            duration = ''
            if record.submitted_at and record.exam.start_time:
                delta = record.submitted_at - record.exam.start_time
                hours = int(delta.total_seconds() // 3600)
                minutes = int((delta.total_seconds() % 3600) // 60)
                duration = f"{hours}小时{minutes}分钟" if hours > 0 else f"{minutes}分钟"
            
            records_data.append({
                'id': record.id,
                'exam_title': record.exam.title,
                'student_name': record.student.username,
                'student_id': record.student.student_id,
                'score': float(record.final_score or 0),
                'max_score': record.exam.max_score or 100,
                'submitted_at': record.submitted_at.strftime('%Y-%m-%d %H:%M') if record.submitted_at else '',
                'duration': duration
            })
        
        return JsonResponse({
            'success': True,
            'total': total,
            'average': round(average, 2),
            'highest': highest,
            'pass_rate': round(pass_rate, 2),
            'score_distribution': score_distribution,
            'segments': segments,
            'records': records_data
        })
        
    except Exception as e:
        import traceback
        print(f"Error in api_scores: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def api_score_detail(request, record_id):
    """获取单个成绩详情"""
    try:
        record = get_object_or_404(ExamRecord, id=record_id)
        
        # 验证权限
        if record.exam.created_by != request.user:
            return JsonResponse({
                'success': False,
                'error': '无权限访问'
            }, status=403)
        
        # 获取题目详情（使用 ExamQuestion）
        exam_questions = record.exam.exam_questions.select_related('question').order_by('order', 'id')
        questions_data = []
        
        for eq in exam_questions:
            q = eq.question
            # 从 answer_sheet 中获取学生答案
            student_answer = record.answer_sheet.get(str(q.id), '') if record.answer_sheet else ''
            is_correct = student_answer == q.answer
            
            questions_data.append({
                'id': q.id,
                'question_type': q.question_type,
                'question_text': q.question_text,
                'correct_answer': q.answer,
                'student_answer': student_answer or '未作答',
                'max_score': q.score,
                'score': q.score if is_correct else 0,
                'is_correct': is_correct
            })
        
        return JsonResponse({
            'success': True,
            'student_name': record.student.username,
            'student_id': record.student.student_id,
            'exam_title': record.exam.title,
            'score': float(record.final_score or 0),
            'max_score': record.exam.max_score or 100,
            'submitted_at': record.submitted_at.strftime('%Y-%m-%d %H:%M') if record.submitted_at else '',
            'questions': questions_data
        })
        
    except Exception as e:
        import traceback
        print(f"Error in api_score_detail: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def api_students(request, student_id=None):
    """获取学生信息"""
    try:
        if student_id:
            student = get_object_or_404(User, id=student_id, role='student')
            
            records = ExamRecord.objects.filter(
                student=student,
                is_submitted=True
            ).select_related('exam')
            
            records_data = []
            for record in records:
                # 验证权限
                if record.exam.created_by != request.user:
                    continue
                    
                records_data.append({
                    'exam_title': record.exam.title,
                    'score': float(record.final_score or 0),
                    'max_score': record.exam.max_score or 100,
                    'submitted_at': record.submitted_at.strftime('%Y-%m-%d %H:%M') if record.submitted_at else ''
                })
            
            # 生成邮箱：学号@stu.cqupt.edu.cn
            expected_email = f"{student.student_id}@stu.cqupt.edu.cn"
            
            return JsonResponse({
                'success': True,
                'id': student.id,
                'username': student.username,
                'student_id': student.student_id,
                'email': student.email or expected_email,
                'date_joined': student.date_joined.strftime('%Y-%m-%d'),
                'last_login': student.last_login.strftime('%Y-%m-%d %H:%M') if student.last_login else None,
                'exam_count': records.count(),
                'average_score': round(records.aggregate(Avg('final_score'))['final_score__avg'] or 0, 2),
                'highest_score': records.aggregate(Max('final_score'))['final_score__max'] or 0,
                'lowest_score': records.aggregate(Min('final_score'))['final_score__min'] or 0,
                'records': records_data
            })
        else:
            # 返回所有学生列表
            students = User.objects.filter(role='student').annotate(
                exam_count=Count('exam_records'),
                average_score=Avg('exam_records__final_score')
            ).order_by('student_id')
            
            students_data = []
            for student in students:
                # 生成邮箱：学号@stu.cqupt.edu.cn
                expected_email = f"{student.student_id}@stu.cqupt.edu.cn"
                students_data.append({
                    'id': student.id,
                    'username': student.username,
                    'student_id': student.student_id,
                    'email': student.email or expected_email,
                    'exam_count': student.exam_count or 0,
                    'average_score': round(student.average_score or 0, 2)
                })
            
            return JsonResponse({
                'success': True,
                'students': students_data
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def api_reset_password(request, student_id):
    """重置学生密码"""
    try:
        student = get_object_or_404(User, id=student_id, role='student')
        
        # 重置密码为学号（不含年份前缀）
        new_password = student.student_id[1:]  # 去掉第一个字符（通常是 S）
        student.set_password(new_password)
        student.save()
        
        return JsonResponse({
            'success': True,
            'new_password': new_password
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def export_scores(request):
    """导出成绩 Excel"""
    try:
        from django.http import HttpResponse
        import openpyxl
        from openpyxl.styles import Font, Alignment, Border, Side
        
        exam_id = request.GET.get('exam_id')
        
        # 获取教师创建的所有考试
        teacher_exams = Exam.objects.filter(created_by=request.user)
        
        if exam_id:
            teacher_exams = teacher_exams.filter(id=exam_id)
        
        exam_ids = list(teacher_exams.values_list('id', flat=True))
        
        # 获取成绩记录
        records = ExamRecord.objects.filter(
            exam_id__in=exam_ids,
            is_submitted=True
        ).select_related('student', 'exam').order_by('exam__title', '-submitted_at')
        
        # 创建 Excel 工作簿
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = '成绩导出'
        
        # 设置表头
        headers = ['考试名称', '学生姓名', '学号', '得分', '满分', '正确率', '提交时间', '状态']
        ws.append(headers)
        
        # 设置表头样式
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')
            cell.border = thin_border
        
        # 填充数据
        for record in records:
            percentage = (record.final_score / record.exam.max_score * 100) if record.exam.max_score > 0 else 0
            status = '及格' if percentage >= 60 else '不及格'
            
            row = [
                record.exam.title,
                record.student.username,
                record.student.student_id,
                float(record.final_score),
                record.exam.max_score,
                f'{percentage:.1f}%',
                record.submitted_at.strftime('%Y-%m-%d %H:%M') if record.submitted_at else '',
                status
            ]
            ws.append(row)
        
        # 设置列宽
        ws.column_dimensions['A'].width = 30
        ws.column_dimensions['B'].width = 15
        ws.column_dimensions['C'].width = 15
        ws.column_dimensions['D'].width = 10
        ws.column_dimensions['E'].width = 10
        ws.column_dimensions['F'].width = 12
        ws.column_dimensions['G'].width = 20
        ws.column_dimensions['H'].width = 10
        
        # 设置所有单元格的边框
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=8):
            for cell in row:
                cell.border = thin_border
        
        # 返回 Excel 文件
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=scores.xlsx'
        wb.save(response)
        
        return response
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def export_students(request):
    """导出学生名单 Excel"""
    try:
        from django.http import HttpResponse
        import openpyxl
        from openpyxl.styles import Font, Alignment, Border, Side
        
        students = User.objects.filter(role='student').annotate(
            exam_count=Count('exam_records'),
            average_score=Avg('exam_records__final_score')
        ).order_by('student_id')
        
        # 创建 Excel 工作簿
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = '学生名单'
        
        # 设置表头
        headers = ['ID', '姓名', '学号', '邮箱', '考试次数', '平均分', '注册时间', '最近登录']
        ws.append(headers)
        
        # 设置表头样式
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')
            cell.border = thin_border
        
        # 填充数据
        for student in students:
            row = [
                student.id,
                student.username,
                student.student_id,
                student.email or '',
                student.exam_count or 0,
                round(student.average_score or 0, 2),
                student.date_joined.strftime('%Y-%m-%d'),
                student.last_login.strftime('%Y-%m-%d %H:%M') if student.last_login else ''
            ]
            ws.append(row)
        
        # 设置列宽
        ws.column_dimensions['A'].width = 8
        ws.column_dimensions['B'].width = 15
        ws.column_dimensions['C'].width = 15
        ws.column_dimensions['D'].width = 25
        ws.column_dimensions['E'].width = 12
        ws.column_dimensions['F'].width = 10
        ws.column_dimensions['G'].width = 15
        ws.column_dimensions['H'].width = 20
        
        # 设置所有单元格的边框
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=8):
            for cell in row:
                cell.border = thin_border
        
        # 返回 Excel 文件
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=students.xlsx'
        wb.save(response)
        
        return response
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def api_question_list(request):
    """获取题目列表（支持搜索和筛选）"""
    try:
        keyword = request.GET.get('keyword', '')
        question_type = request.GET.get('type', '')
        
        # 获取教师创建的所有题目
        questions = Question.objects.filter(created_by=request.user)
        
        # 搜索和筛选
        if keyword:
            questions = questions.filter(question_text__icontains=keyword)
        if question_type:
            questions = questions.filter(question_type=question_type)
        
        questions = questions.order_by('-created_at')[:100]  # 限制返回数量
        
        questions_data = []
        for q in questions:
            questions_data.append({
                'id': q.id,
                'question_type': q.question_type,
                'question_text': q.question_text,
                'option_a': q.option_a,
                'option_b': q.option_b,
                'option_c': q.option_c,
                'option_d': q.option_d,
                'answer': q.answer,
                'score': q.score
            })
        
        return JsonResponse({
            'success': True,
            'questions': questions_data,
            'total': len(questions_data)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def api_question_detail(request, question_id):
    """获取题目详情"""
    try:
        question = get_object_or_404(Question, id=question_id, created_by=request.user)
        
        return JsonResponse({
            'success': True,
            'question': {
                'id': question.id,
                'question_type': question.question_type,
                'question_text': question.question_text,
                'option_a': question.option_a,
                'option_b': question.option_b,
                'option_c': question.option_c,
                'option_d': question.option_d,
                'answer': question.answer,
                'score': question.score
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def api_question_create(request):
    """创建题目"""
    try:
        data = json.loads(request.body)
        
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
        
        return JsonResponse({
            'success': True,
            'question_id': question.id
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_http_methods(["POST"])
def api_question_update(request, question_id):
    """更新题目"""
    try:
        question = get_object_or_404(Question, id=question_id, created_by=request.user)
        data = json.loads(request.body)
        
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


@login_required
@require_http_methods(["POST"])
def api_question_delete(request, question_id):
    """删除题目"""
    try:
        question = get_object_or_404(Question, id=question_id, created_by=request.user)
        question.delete()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_http_methods(["POST"])
def api_questions_batch(request):
    """批量获取题目信息"""
    try:
        data = json.loads(request.body)
        question_ids = data.get('question_ids', [])
        
        questions = Question.objects.filter(
            id__in=question_ids,
            created_by=request.user
        )
        
        questions_data = []
        for q in questions:
            questions_data.append({
                'id': q.id,
                'question_type': q.question_type,
                'question_text': q.question_text,
                'option_a': q.option_a,
                'option_b': q.option_b,
                'option_c': q.option_c,
                'option_d': q.option_d,
                'answer': q.answer,
                'score': q.score
            })
        
        return JsonResponse({
            'success': True,
            'questions': questions_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_http_methods(["POST"])
def api_questions_import(request):
    """批量导入题目（Excel）"""
    try:
        import openpyxl
        
        if 'file' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': '未选择文件'
            }, status=400)
        
        excel_file = request.FILES['file']
        exam_id = request.POST.get('exam_id')
        exam = None
        if exam_id:
            exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)
        
        # 读取 Excel
        wb = openpyxl.load_workbook(excel_file)
        ws = wb.active
        
        imported_count = 0
        failed_count = 0
        errors = []
        
        # 从第 2 行开始读取（第 1 行是表头）
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            try:
                # 期望的列顺序：题型、题干、选项 A、选项 B、选项 C、选项 D、答案、分值
                question_type = str(row[0]).strip() if row[0] else ''
                question_text = str(row[1]).strip() if row[1] else ''
                option_a = str(row[2]).strip() if len(row) > 2 and row[2] else ''
                option_b = str(row[3]).strip() if len(row) > 3 and row[3] else ''
                option_c = str(row[4]).strip() if len(row) > 4 and row[4] else ''
                option_d = str(row[5]).strip() if len(row) > 5 and row[5] else ''
                answer = str(row[6]).strip() if len(row) > 6 and row[6] else ''
                score = int(row[7]) if len(row) > 7 and row[7] else 5
                
                # 验证必填字段
                if not question_type or not question_text or not answer:
                    errors.append(f'第{row_idx}行：缺少必填字段')
                    failed_count += 1
                    continue
                
                # 验证题型
                type_mapping = {
                    'choice': 'choice',
                    'blank': 'blank',
                    '选择题': 'choice',
                    '填空题': 'blank'
                }
                question_type_en = type_mapping.get(question_type)
                if not question_type_en:
                    errors.append(f'第{row_idx}行：题型必须是 choice/blank 或 选择题/填空题')
                    failed_count += 1
                    continue
                
                # 创建题目
                question = Question.objects.create(
                    created_by=request.user,
                    question_type=question_type_en,
                    question_text=question_text,
                    option_a=option_a,
                    option_b=option_b,
                    option_c=option_c,
                    option_d=option_d,
                    answer=answer,
                    score=score
                )
                
                # 如果选择了考试，添加到考试
                if exam:
                    from exams.models import ExamQuestion
                    # 计算当前考试的题目数量
                    current_order = ExamQuestion.objects.filter(exam=exam).count()
                    ExamQuestion.objects.create(
                        exam=exam,
                        question=question,
                        order=current_order + 1
                    )
                
                imported_count += 1
                
            except Exception as e:
                errors.append(f'第{row_idx}行：{str(e)}')
                failed_count += 1
        
        return JsonResponse({
            'success': True,
            'imported_count': imported_count,
            'failed_count': failed_count,
            'errors': errors[:10]  # 最多返回 10 条错误信息
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'导入失败：{str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def api_generate_qr(request):
    """生成考试二维码"""
    try:
        import qrcode
        from django.core.cache import cache
        import uuid
        
        data = json.loads(request.body)
        exam_id = data.get('exam_id')
        
        if not exam_id:
            return JsonResponse({
                'success': False,
                'error': '缺少考试 ID'
            }, status=400)
        
        exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)
        
        # 生成唯一的 session_id
        session_id = str(uuid.uuid4())
        
        # 生成登录 URL（学生端）
        login_url = request.build_absolute_uri(f'/accounts/login/?session_id={session_id}')
        
        # 生成二维码
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(login_url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # 保存图片到 media 目录
        import os
        from django.conf import settings
        qr_dir = os.path.join(settings.MEDIA_ROOT, 'qr_codes')
        os.makedirs(qr_dir, exist_ok=True)
        
        filename = f'qr_{session_id}.png'
        filepath = os.path.join(qr_dir, filename)
        img.save(filepath)
        
        # 存储 session 信息到缓存，60 秒过期
        cache.set(f'qr_session_{session_id}', {
            'exam_id': exam_id,
            'exam_title': exam.title,
            'created_at': timezone.now().isoformat()
        }, timeout=60)
        
        return JsonResponse({
            'success': True,
            'session_id': session_id,
            'qr_code_url': f'{settings.MEDIA_URL}qr_codes/{filename}',
            'login_url': login_url
        })
        
    except Exception as e:
        import traceback
        print(f"Error in api_generate_qr: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': f'生成失败：{str(e)}'
        }, status=500)


@login_required
def api_qr_stats(request, exam_id):
    """获取二维码扫码统计"""
    try:
        from django.core.cache import cache
        
        exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)
        
        # 从缓存中获取所有 session 信息
        scan_count = 0
        records = []
        
        # 这里可以从数据库或缓存中获取扫码记录
        # 暂时返回空数据，等待学生扫码登录功能实现后再完善
        
        return JsonResponse({
            'success': True,
            'scan_count': scan_count,
            'records': records
        })
        
    except Exception as e:
        import traceback
        print(f"Error in api_qr_stats: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
