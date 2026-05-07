import re
import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.cache import cache
from .models import User
from .utils import generate_session_id, verify_session_id, refresh_session_id
import openpyxl
from openpyxl.utils import get_column_letter


@login_required
def upload_student_accounts(request):
    """
    教师批量导入学生账号视图
    仅限超级用户访问
    """
    if not request.user.is_superuser:
        raise PermissionDenied
    
    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        
        if not excel_file:
            messages.error(request, '请选择要上传的 Excel 文件')
            return render(request, 'accounts/upload.html')
        
        if not excel_file.name.endswith('.xlsx'):
            messages.error(request, '请上传 .xlsx 格式的 Excel 文件')
            return render(request, 'accounts/upload.html')
        
        try:
            result = process_excel_file(excel_file)
            
            success_count = result['success_count']
            skip_count = result['skip_count']
            error_count = result['error_count']
            
            if success_count > 0:
                messages.success(
                    request,
                    f'成功创建 {success_count} 个学生账号，跳过 {skip_count} 个重复学号，{error_count} 条错误记录'
                )
            
            if result['errors']:
                for error in result['errors']:
                    messages.warning(request, error)
            
            return redirect('accounts:upload_success')
            
        except Exception as e:
            messages.error(request, f'导入失败：{str(e)}')
            return render(request, 'accounts/upload.html')
    
    return render(request, 'accounts/upload.html')


def process_excel_file(excel_file):
    """
    处理 Excel 文件并批量创建学生账号
    
    Args:
        excel_file: 上传的 Excel 文件对象
        
    Returns:
        dict: 包含处理结果统计信息
            - success_count: 成功创建的账号数
            - skip_count: 跳过的重复学号数
            - error_count: 错误记录数
            - errors: 错误信息列表
    """
    wb = openpyxl.load_workbook(excel_file)
    ws = wb.active
    
    header_row = ws[1]
    headers = [cell.value for cell in header_row]
    
    try:
        student_id_col = headers.index('学号') + 1
        name_col = headers.index('姓名') + 1
    except ValueError:
        raise ValueError('Excel 文件必须包含"学号"和"姓名"两列')
    
    success_count = 0
    skip_count = 0
    error_count = 0
    errors = []
    created_users = []
    
    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        student_id = row[student_id_col - 1]
        name = row[name_col - 1]
        
        if not student_id or not name:
            error_count += 1
            errors.append(f'第{row}行：学号或姓名为空')
            continue
        
        student_id = str(student_id).strip()
        name = str(name).strip()
        
        if not re.match(r'^[a-zA-Z0-9]+$', student_id):
            error_count += 1
            errors.append(f'第{row}行：学号格式不正确（只能包含字母和数字）')
            continue
        
        if User.objects.filter(student_id=student_id).exists():
            skip_count += 1
            errors.append(f'第{row}行：学号 {student_id} 已存在，已跳过')
            continue
        
        username = student_id
        default_password = student_id[-6:] if len(student_id) >= 6 else student_id
        
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=name,
                    password=default_password,
                    role='student',
                    student_id=student_id,
                    first_name=name,
                    email=f'{username}@stu.cqupt.edu.cn'
                )
                created_users.append(user)
                success_count += 1
        except Exception as e:
            error_count += 1
            errors.append(f'第{row}行：创建账号失败 - {str(e)}')
    
    return {
        'success_count': success_count,
        'skip_count': skip_count,
        'error_count': error_count,
        'errors': errors,
        'created_users': created_users
    }


@login_required
def upload_success(request):
    """
    上传成功提示页面
    """
    if not request.user.is_superuser:
        raise PermissionDenied
    return render(request, 'accounts/upload_success.html')


@login_required
def generate_qr_code(request):
    """
    教师端二维码生成页面
    仅限超级用户访问
    """
    if not request.user.is_superuser:
        raise PermissionDenied
    
    # 如果携带了 session_id，说明是扫码后跳转，重定向到登录页
    session_id = request.GET.get('session_id')
    if session_id:
        return redirect('accounts:login', session_id=session_id)
    
    return render(request, 'accounts/generate_qr.html')


@require_http_methods(["GET", "POST"])
@csrf_exempt
def get_session_id(request):
    """
    生成 session_id API 接口
    每次请求生成唯一的 session_id 并存储于 Redis，设置 10 秒过期时间
    """
    try:
        session_id = generate_session_id()
        login_url = request.build_absolute_uri(f'/login/?session_id={session_id}')
        
        return JsonResponse({
            'success': True,
            'session_id': session_id,
            'login_url': login_url,
            'expire_time': settings.QR_CODE_EXPIRE_TIME
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def student_login(request, session_id=None):
    """
    学生登录视图
    必须携带有效的 session_id 参数
    session_id 可以通过 GET 参数或 URL 路径参数传递
    """
    # 优先使用路径参数，如果没有则从 GET 参数获取
    if not session_id:
        session_id = request.GET.get('session_id')
    
    # 如果是 POST 提交，优先从 session 中获取已验证的 session_id
    if request.method == 'POST':
        # POST 时使用 session 中缓存的 session_id，不验证时间限制
        session_id = request.session.get('pending_session_id')
        if not session_id:
            return render(request, 'accounts/login_error.html', {
                'error_message': '登录会话已过期，请重新扫码'
            })
    else:
        # GET 请求：必须验证 session_id 有效性（10 秒内有效）
        if not session_id:
            # 没有 session_id，显示错误页面而不是登录页面
            return render(request, 'accounts/login_error.html', {
                'error_message': '缺少 session_id 参数，请通过扫描二维码登录'
            })
        
        if not verify_session_id(session_id):
            # 如果 session_id 失效，清除 session 中的缓存
            if 'pending_session_id' in request.session:
                del request.session['pending_session_id']
            return render(request, 'accounts/login_error.html', {
                'error_message': '二维码已失效，请重新扫描'
            })
        
        # 将有效的 session_id 暂存到 session，允许后续登录操作
        request.session['pending_session_id'] = session_id
    
    if request.method == 'POST':
        # 学生登录：使用姓名 + 密码
        name = request.POST.get('name')
        password = request.POST.get('password')
        
        if not name or not password:
            return render(request, 'accounts/login.html', {
                'session_id': session_id,
                'error_message': '姓名和密码不能为空'
            })
        
        user = authenticate(request, username=name, password=password)
        
        if user is not None:
            if user.role != 'student':
                return render(request, 'accounts/login.html', {
                    'session_id': session_id,
                    'error_message': '该账号不是学生账号'
                })
            
            login(request, user)
            
            request.session['exam_authorized'] = True
            request.session['authorized_session_id'] = session_id
            
            refresh_session_id(session_id)
            
            # 清除临时 session
            if 'pending_session_id' in request.session:
                del request.session['pending_session_id']
            
            return redirect('exams:exam_list')
        else:
            return render(request, 'accounts/login.html', {
                'session_id': session_id,
                'error_message': '学号或密码错误'
            })
    
    return render(request, 'accounts/login.html', {
        'session_id': session_id
    })


def login_error(request):
    """
    登录错误页面
    """
    return render(request, 'accounts/login_error.html')


def permission_denied(request):
    """
    权限拒绝页面
    """
    return render(request, 'accounts/permission_denied.html')


def teacher_login(request):
    """
    教师专用登录视图
    基于用户名和密码的身份验证
    仅限教师角色访问
    
    Args:
        request: HTTP 请求对象
        
    Returns:
        HttpResponse: 登录页面或重定向响应
    """
    # 如果已登录，直接重定向到教师主页
    if request.user.is_authenticated:
        if request.user.role == 'teacher' or request.user.is_superuser:
            return redirect('exams:exam_list')
        else:
            messages.error(request, '您没有教师权限')
            return redirect('accounts:teacher_login')
    
    # 获取登录尝试次数（用于防暴力破解）
    login_attempts = get_login_attempts(request)
    
    # 如果尝试次数过多，显示验证码或限制登录
    if login_attempts >= 5:
        messages.warning(request, '登录尝试次数过多，请稍后再试')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # 基础验证
        if not username or not password:
            return render(request, 'accounts/teacher_login.html', {
                'error_message': '用户名和密码不能为空'
            })
        
        # 检查登录限制
        if login_attempts >= 5:
            return render(request, 'accounts/teacher_login.html', {
                'error_message': '登录尝试次数过多，请稍后再试（10 分钟）'
            })
        
        # 身份验证
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # 验证角色
            if user.role != 'teacher' and not user.is_superuser:
                # 记录失败尝试
                increment_login_attempts(request)
                return render(request, 'accounts/teacher_login.html', {
                    'error_message': '您没有教师权限，请使用学生登录入口'
                })
            
            # 登录成功
            login(request, user)
            
            # 清除登录失败记录
            clear_login_attempts(request)
            
            # 设置教师权限标记和考试授权标记
            request.session['is_teacher'] = True
            request.session['exam_authorized'] = True
            
            messages.success(request, f'欢迎，{user.username}老师！')
            
            # 重定向到教师管理后台
            return redirect('teacher:dashboard')
        else:
            # 登录失败，记录尝试次数
            increment_login_attempts(request)
            return render(request, 'accounts/teacher_login.html', {
                'error_message': '用户名或密码错误'
            })
    
    return render(request, 'accounts/teacher_login.html')


@login_required
def teacher_logout(request):
    """
    教师登出视图
    
    Args:
        request: HTTP 请求对象
        
    Returns:
        HttpResponse: 登出后重定向到登录页
    """
    from django.contrib.auth import logout
    logout(request)
    messages.success(request, '您已成功退出登录')
    return redirect('accounts:teacher_login')


def get_login_attempts(request):
    """
    获取登录尝试次数（基于 IP 地址）
    
    Args:
        request: HTTP 请求对象
        
    Returns:
        int: 登录尝试次数
    """
    ip = get_client_ip(request)
    key = f'login_attempts:{ip}'
    return cache.get(key, 0)


def increment_login_attempts(request):
    """
    增加登录尝试次数
    
    Args:
        request: HTTP 请求对象
    """
    ip = get_client_ip(request)
    key = f'login_attempts:{ip}'
    attempts = cache.get(key, 0) + 1
    cache.set(key, attempts, 600)  # 10 分钟后过期


def clear_login_attempts(request):
    """
    清除登录尝试记录
    
    Args:
        request: HTTP 请求对象
    """
    ip = get_client_ip(request)
    key = f'login_attempts:{ip}'
    cache.delete(key)


def get_client_ip(request):
    """
    获取客户端 IP 地址
    
    Args:
        request: HTTP 请求对象
        
    Returns:
        str: 客户端 IP 地址
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
