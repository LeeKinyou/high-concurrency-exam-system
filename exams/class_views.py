from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Count, Q
from django.db import transaction
from django.contrib import messages
import json

from .models import ClassInfo, StudentClassRelation, Exam
from accounts.models import User


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
def class_list(request):
    """
    班级列表页面
    显示当前教师创建的所有班级
    """
    classes = ClassInfo.objects.filter(teacher=request.user).annotate(
        student_count=Count('students', filter=Q(students__is_active=True))
    ).order_by('-created_at')

    context = {
        'active_menu': 'classes',
        'classes': classes,
        'total_classes': classes.count()
    }

    return render(request, 'teacher/class_list.html', context)


@teacher_required
@require_http_methods(["POST"])
def class_create(request):
    """
    创建班级 API
    接收班级信息并创建新班级
    """
    try:
        data = json.loads(request.body) if request.body else request.POST

        name = data.get('name')
        description = data.get('description', '')

        if not name:
            return JsonResponse({
                'success': False,
                'error': '班级名称不能为空'
            }, status=400)

        # 检查班级名是否已存在（同一教师下）
        if ClassInfo.objects.filter(teacher=request.user, name=name).exists():
            return JsonResponse({
                'success': False,
                'error': '该班级名称已存在'
            }, status=400)

        class_info = ClassInfo.objects.create(
            name=name,
            description=description,
            teacher=request.user
        )

        return JsonResponse({
            'success': True,
            'message': f'班级"{name}"创建成功',
            'class_id': class_info.id,
            'class_name': class_info.name
        })

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


@teacher_required
@require_http_methods(["POST"])
def class_update(request, class_id):
    """
    更新班级信息 API
    """
    try:
        class_info = get_object_or_404(ClassInfo, id=class_id, teacher=request.user)
        data = json.loads(request.body)

        name = data.get('name')
        description = data.get('description', '')

        if not name:
            return JsonResponse({
                'success': False,
                'error': '班级名称不能为空'
            }, status=400)

        # 检查班级名是否已存在（排除自身）
        if ClassInfo.objects.filter(teacher=request.user, name=name).exclude(id=class_id).exists():
            return JsonResponse({
                'success': False,
                'error': '该班级名称已存在'
            }, status=400)

        class_info.name = name
        class_info.description = description
        class_info.save()

        return JsonResponse({
            'success': True,
            'message': '班级信息已更新'
        })

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


@teacher_required
@require_http_methods(["POST"])
def class_delete(request, class_id):
    """
    删除班级 API
    同时清理关联的学生记录和考试关联
    """
    try:
        class_info = get_object_or_404(ClassInfo, id=class_id, teacher=request.user)
        class_name = class_info.name

        with transaction.atomic():
            # 清理学生-班级关联
            StudentClassRelation.objects.filter(class_info=class_info).delete()

            # 清理考试-班级关联
            class_info.exams.clear()

            # 删除班级
            class_info.delete()

        return JsonResponse({
            'success': True,
            'message': f'班级"{class_name}"已删除'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@teacher_required
def class_detail(request, class_id):
    """
    班级详情页面
    显示班级信息和成员列表
    """
    class_info = get_object_or_404(ClassInfo, id=class_id, teacher=request.user)

    students = StudentClassRelation.objects.filter(
        class_info=class_info,
        is_active=True
    ).select_related('student').order_by('-joined_at')

    context = {
        'active_menu': 'classes',
        'class_info': class_info,
        'students': students,
        'student_count': students.count()
    }

    return render(request, 'teacher/class_detail.html', context)


@teacher_required
def class_students(request, class_id):
    """
    班级学生管理页面
    支持添加/移除学生
    """
    class_info = get_object_or_404(ClassInfo, id=class_id, teacher=request.user)

    # 已加入的学生
    current_students = StudentClassRelation.objects.filter(
        class_info=class_info,
        is_active=True
    ).select_related('student').order_by('student__student_id')

    # 可添加的学生列表（所有学生减去已加入的）
    current_student_ids = current_students.values_list('student_id', flat=True)
    available_students = User.objects.filter(
        role='student'
    ).exclude(id__in=current_student_ids).order_by('student_id')[:50]

    context = {
        'active_menu': 'classes',
        'class_info': class_info,
        'current_students': current_students,
        'available_students': available_students,
        'current_count': current_students.count()
    }

    return render(request, 'teacher/class_students.html', context)


@teacher_required
@require_http_methods(["POST"])
def add_student_to_class(request, class_id):
    """
    添加单个学生到班级
    """
    try:
        class_info = get_object_or_404(ClassInfo, id=class_id, teacher=request.user)
        data = json.loads(request.body)
        student_id = data.get('student_id')

        if not student_id:
            return JsonResponse({
                'success': False,
                'error': '请选择要添加的学生'
            }, status=400)

        student = get_object_or_404(User, id=student_id, role='student')

        # 检查是否已在班级中
        if StudentClassRelation.objects.filter(student=student, class_info=class_info).exists():
            return JsonResponse({
                'success': False,
                'error': '该学生已在班级中'
            }, status=400)

        # 添加学生到班级
        StudentClassRelation.objects.create(
            student=student,
            class_info=class_info
        )

        return JsonResponse({
            'success': True,
            'message': f'{student.username}已加入班级'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@teacher_required
@require_http_methods(["POST"])
def batch_add_students_to_class(request, class_id):
    """
    批量添加学生到班级
    """
    try:
        class_info = get_object_or_404(ClassInfo, id=class_id, teacher=request.user)
        data = json.loads(request.body)
        student_ids = data.get('student_ids', [])

        if not student_ids:
            return JsonResponse({
                'success': False,
                'error': '请选择要添加的学生'
            }, status=400)

        students = User.objects.filter(id__in=student_ids, role='student')

        added_count = 0
        skipped_count = 0

        for student in students:
            # 检查是否已在班级中
            relation, created = StudentClassRelation.objects.get_or_create(
                student=student,
                class_info=class_info
            )
            if created:
                added_count += 1
            else:
                skipped_count += 1

        return JsonResponse({
            'success': True,
            'message': f'成功添加{added_count}名学生，跳过{skipped_count}名（已存在）',
            'added_count': added_count,
            'skipped_count': skipped_count
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@teacher_required
@require_http_methods(["POST"])
def remove_student_from_class(request, class_id):
    """
    从班级移除单个学生
    """
    try:
        class_info = get_object_or_404(ClassInfo, id=class_id, teacher=request.user)
        data = json.loads(request.body)
        student_id = data.get('student_id')

        if not student_id:
            return JsonResponse({
                'success': False,
                'error': '请指定要移除的学生'
            }, status=400)

        relation = get_object_or_404(
            StudentClassRelation,
            student_id=student_id,
            class_info=class_info
        )

        student_name = relation.student.username
        relation.delete()

        return JsonResponse({
            'success': True,
            'message': f'{student_name}已从班级移除'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@teacher_required
def get_class_stats(request, class_id):
    """
    获取班级统计信息（AJAX）
    """
    try:
        class_info = get_object_or_404(ClassInfo, id=class_id, teacher=request.user)

        stats = {
            'total_students': class_info.students.filter(is_active=True).count(),
            'exam_count': class_info.exams.count(),
            'created_at': class_info.created_at.strftime('%Y-%m-%d %H:%M'),
        }

        return JsonResponse({'success': True, **stats})

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
