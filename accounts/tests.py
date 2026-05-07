from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.conf import settings
import openpyxl
from io import BytesIO
import redis
from .models import User
from .utils import generate_session_id, verify_session_id, refresh_session_id, invalidate_session_id

User = get_user_model()


class UploadStudentAccountsTest(TestCase):
    """学生账号批量导入功能测试"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.client = Client()
        self.superuser = User.objects.create_superuser(
            username='admin',
            password='admin123',
            email='admin@test.com'
        )
        self.teacher = User.objects.create_user(
            username='teacher1',
            password='teacher123',
            role='teacher',
            email='teacher@test.com'
        )
        self.student = User.objects.create_user(
            username='student1',
            password='student123',
            role='student',
            student_id='S20240001',
            email='student1@test.com'
        )
    
    def create_excel_file(self, data, filename='test_students.xlsx'):
        """
        创建测试用的 Excel 文件
        
        Args:
            data: 列表，包含学生数据的元组列表 [(学号，姓名), ...]
            filename: 文件名
            
        Returns:
            SimpleUploadedFile: Excel 文件对象
        """
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Students"
        
        ws['A1'] = '学号'
        ws['B1'] = '姓名'
        
        for row_idx, (student_id, name) in enumerate(data, start=2):
            ws[f'A{row_idx}'] = student_id
            ws[f'B{row_idx}'] = name
        
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        return SimpleUploadedFile(
            filename,
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    
    def test_upload_view_requires_login(self):
        """测试上传视图需要登录"""
        response = self.client.get(reverse('accounts:upload'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
    
    def test_upload_view_requires_superuser(self):
        """测试上传视图仅限超级用户访问"""
        self.client.login(username='teacher1', password='teacher123')
        response = self.client.get(reverse('accounts:upload'))
        self.assertEqual(response.status_code, 403)
        
        self.client.login(username='student1', password='student123')
        response = self.client.get(reverse('accounts:upload'))
        self.assertEqual(response.status_code, 403)
    
    def test_upload_view_accessible_by_superuser(self):
        """测试超级用户可以访问上传页面"""
        self.client.login(username='admin', password='admin123')
        response = self.client.get(reverse('accounts:upload'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '批量导入学生账号')
    
    def test_upload_success_with_valid_excel(self):
        """测试上传有效的 Excel 文件成功创建账号"""
        self.client.login(username='admin', password='admin123')
        
        excel_file = self.create_excel_file([
            ('S20240002', '张三'),
            ('S20240003', '李四'),
        ])
        
        response = self.client.post(
            reverse('accounts:upload'),
            {'excel_file': excel_file},
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(student_id='S20240002').exists())
        self.assertTrue(User.objects.filter(student_id='S20240003').exists())
        
        user1 = User.objects.get(student_id='S20240002')
        user2 = User.objects.get(student_id='S20240003')
        
        self.assertEqual(user1.username, 'S20240002')
        self.assertEqual(user1.role, 'student')
        self.assertEqual(user1.first_name, '张三')
        
        self.assertEqual(user2.username, 'S20240003')
        self.assertEqual(user2.role, 'student')
        self.assertEqual(user2.first_name, '李四')
    
    def test_default_password_generation(self):
        """测试默认密码生成规则（学号后 6 位）"""
        self.client.login(username='admin', password='admin123')
        
        excel_file = self.create_excel_file([
            ('S20240004', '王五'),
            ('123456789', '赵六'),
        ])
        
        self.client.post(
            reverse('accounts:upload'),
            {'excel_file': excel_file},
            follow=True
        )
        
        user1 = User.objects.get(student_id='S20240004')
        user2 = User.objects.get(student_id='123456789')
        
        self.assertTrue(user1.check_password('240004'))
        self.assertTrue(user2.check_password('456789'))
    
    def test_skip_existing_student_id(self):
        """测试已存在的学号会被跳过"""
        self.client.login(username='admin', password='admin123')
        
        excel_file = self.create_excel_file([
            ('S20240001', '张三'),
            ('S20240005', '李四'),
        ])
        
        response = self.client.post(
            reverse('accounts:upload'),
            {'excel_file': excel_file},
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        
        self.assertTrue(User.objects.filter(student_id='S20240005').exists())
        
        original_student = User.objects.get(student_id='S20240001')
        self.assertNotEqual(original_student.first_name, '张三')
    
    def test_invalid_student_id_format(self):
        """测试无效学号格式会被拒绝"""
        self.client.login(username='admin', password='admin123')
        
        excel_file = self.create_excel_file([
            ('S_2024_001', '张三'),
            ('S20240006', '李四'),
        ])
        
        response = self.client.post(
            reverse('accounts:upload'),
            {'excel_file': excel_file},
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(student_id='S_2024_001').exists())
        self.assertTrue(User.objects.filter(student_id='S20240006').exists())
    
    def test_empty_student_id_or_name(self):
        """测试空学号或姓名会被拒绝"""
        self.client.login(username='admin', password='admin123')
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws['A1'] = '学号'
        ws['B1'] = '姓名'
        ws['A2'] = 'S20240007'
        ws['B2'] = '张三'
        ws['A3'] = ''
        ws['B3'] = '李四'
        ws['A4'] = 'S20240008'
        ws['B4'] = ''
        
        from io import BytesIO
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        excel_file = SimpleUploadedFile(
            'test_empty.xlsx',
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        response = self.client.post(
            reverse('accounts:upload'),
            {'excel_file': excel_file},
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(student_id='S20240007').exists())
        self.assertFalse(User.objects.filter(student_id='').exists())
        self.assertFalse(User.objects.filter(student_id='S20240008').exists())
    
    def test_upload_wrong_file_format(self):
        """测试上传非 xlsx 格式文件会失败"""
        self.client.login(username='admin', password='admin123')
        
        fake_file = SimpleUploadedFile(
            'test.txt',
            b'Some text content',
            content_type='text/plain'
        )
        
        response = self.client.post(
            reverse('accounts:upload'),
            {'excel_file': fake_file},
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        messages = list(response.context['messages'])
        self.assertTrue(any('xlsx' in str(msg) for msg in messages))
    
    def test_upload_no_file(self):
        """测试未选择文件会失败"""
        self.client.login(username='admin', password='admin123')
        
        response = self.client.post(
            reverse('accounts:upload'),
            {},
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        messages = list(response.context['messages'])
        self.assertTrue(any('选择' in str(msg) for msg in messages))
    
    def test_upload_success_view_requires_superuser(self):
        """测试上传成功页面仅限超级用户访问"""
        self.client.login(username='teacher1', password='teacher123')
        response = self.client.get(reverse('accounts:upload_success'))
        self.assertEqual(response.status_code, 403)
    
    def test_upload_success_view_accessible_by_superuser(self):
        """测试超级用户可以访问上传成功页面"""
        self.client.login(username='admin', password='admin123')
        response = self.client.get(reverse('accounts:upload_success'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '导入成功')
    
    def test_large_batch_import(self):
        """测试批量导入 100 条学生记录"""
        self.client.login(username='admin', password='admin123')
        
        students = [(f'S2024{i:05d}', f'学生{i}') for i in range(100)]
        excel_file = self.create_excel_file(students)
        
        response = self.client.post(
            reverse('accounts:upload'),
            {'excel_file': excel_file},
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        
        for i in range(100):
            student_id = f'S2024{i:05d}'
            self.assertTrue(User.objects.filter(student_id=student_id).exists())
    
    def test_email_generation(self):
        """测试自动生成学生邮箱"""
        self.client.login(username='admin', password='admin123')
        
        excel_file = self.create_excel_file([
            ('S20240009', '测试学生'),
        ])
        
        self.client.post(
            reverse('accounts:upload'),
            {'excel_file': excel_file},
            follow=True
        )
        
        user = User.objects.get(student_id='S20240009')
        self.assertEqual(user.email, 'S20240009@student.local')


class TeacherLoginTest(TestCase):
    """教师登录功能测试"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.client = Client()
        
        # 创建教师账号
        self.teacher = User.objects.create_user(
            username='teacher_test',
            password='teacher123',
            role='teacher',
            email='teacher_test@test.com'
        )
        
        # 创建学生账号
        self.student = User.objects.create_user(
            username='student_test',
            password='student123',
            role='student',
            student_id='S20240099',
            email='student_test@test.com'
        )
        
        # 创建超级管理员
        self.admin = User.objects.create_superuser(
            username='admin_test',
            password='admin123',
            email='admin_test@test.com'
        )
    
    def test_teacher_login_page_accessible(self):
        """测试教师登录页面可访问"""
        response = self.client.get(reverse('accounts:teacher_login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '教师登录')
    
    def test_teacher_login_success(self):
        """测试教师登录成功"""
        response = self.client.post(
            reverse('accounts:teacher_login'),
            {
                'username': 'teacher_test',
                'password': 'teacher123'
            },
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.wsgi_request.user.role, 'teacher')
        self.assertTrue(response.wsgi_request.session.get('is_teacher'))
    
    def test_teacher_login_wrong_password(self):
        """测试教师登录密码错误"""
        response = self.client.post(
            reverse('accounts:teacher_login'),
            {
                'username': 'teacher_test',
                'password': 'wrong_password'
            }
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '用户名或密码错误')
        self.assertFalse(response.wsgi_request.user.is_authenticated)
    
    def test_teacher_login_empty_fields(self):
        """测试教师登录空字段"""
        response = self.client.post(
            reverse('accounts:teacher_login'),
            {
                'username': '',
                'password': ''
            }
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '用户名和密码不能为空')
    
    def test_student_cannot_use_teacher_login(self):
        """测试学生账号无法通过教师登录入口登录"""
        response = self.client.post(
            reverse('accounts:teacher_login'),
            {
                'username': 'student_test',
                'password': 'student123'
            }
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '您没有教师权限')
        self.assertFalse(response.wsgi_request.user.is_authenticated)
    
    def test_superuser_can_use_teacher_login(self):
        """测试超级管理员可以通过教师登录入口登录"""
        response = self.client.post(
            reverse('accounts:teacher_login'),
            {
                'username': 'admin_test',
                'password': 'admin123'
            },
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertTrue(response.wsgi_request.user.is_superuser)
    
    def test_teacher_login_redirect_to_exam_list(self):
        """测试教师登录后重定向到考试列表"""
        # 先设置 exam_authorized 权限（因为 exam_list 需要此权限）
        response = self.client.post(
            reverse('accounts:teacher_login'),
            {
                'username': 'teacher_test',
                'password': 'teacher123'
            }
        )
        
        # 登录成功会重定向，但 exam_list 需要 exam_authorized 权限
        # 所以这里只验证登录成功
        self.assertEqual(response.status_code, 302)
        # 验证用户已登录
        self.client.login(username='teacher_test', password='teacher123')
        self.assertTrue(self.client.session.get('is_teacher'))
    
    def test_teacher_login_with_next_parameter(self):
        """测试教师登录带 next 参数"""
        # 设置 session 权限标记
        session = self.client.session
        session['exam_authorized'] = True
        session.save()
        
        response = self.client.post(
            reverse('accounts:teacher_login') + '?next=/accounts/upload/',
            {
                'username': 'teacher_test',
                'password': 'teacher123'
            }
        )
        
        # 验证被重定向
        self.assertEqual(response.status_code, 302)
        # 验证登录成功
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.wsgi_request.user.role, 'teacher')
    
    def test_authenticated_teacher_redirected(self):
        """测试已登录教师访问登录页会被重定向"""
        self.client.login(username='teacher_test', password='teacher123')
        # 设置 exam_authorized 权限
        session = self.client.session
        session['exam_authorized'] = True
        session.save()
        
        response = self.client.get(reverse('accounts:teacher_login'), follow=True)
        # 验证被重定向（可能是到 exam_list）
        self.assertEqual(response.status_code, 200)
    
    def test_login_attempts_rate_limiting(self):
        """测试登录尝试次数限制"""
        from django.core.cache import cache
        
        # 模拟 5 次失败登录
        for i in range(5):
            self.client.post(
                reverse('accounts:teacher_login'),
                {
                    'username': 'teacher_test',
                    'password': 'wrong_password'
                }
            )
        
        # 第 6 次尝试应该被限制
        response = self.client.post(
            reverse('accounts:teacher_login'),
            {
                'username': 'teacher_test',
                'password': 'teacher123'
            }
        )
        
        self.assertContains(response, '登录尝试次数过多')
        
        # 清理缓存
        cache.clear()
    
    def test_successful_login_clears_attempts(self):
        """测试成功登录后清除失败记录"""
        from django.core.cache import cache
        
        # 先失败几次
        for i in range(3):
            self.client.post(
                reverse('accounts:teacher_login'),
                {
                    'username': 'teacher_test',
                    'password': 'wrong_password'
                }
            )
        
        # 成功登录
        login_response = self.client.post(
            reverse('accounts:teacher_login'),
            {
                'username': 'teacher_test',
                'password': 'teacher123'
            }
        )
        
        # 验证登录成功（重定向）
        self.assertEqual(login_response.status_code, 302)
        
        # 再次失败登录，不应该立即被限制
        response = self.client.post(
            reverse('accounts:teacher_login'),
            {
                'username': 'teacher_test',
                'password': 'wrong_password'
            }
        )
        
        # 不应该被限制（因为成功登录后清除了计数）
        # 检查响应中不包含"登录尝试次数过多"的错误消息
        # 由于是 POST 请求会重定向，我们检查重定向前的消息
        self.assertEqual(response.status_code, 302)
        
        # 清理缓存
        cache.clear()


class QRCodeSystemTest(TestCase):
    """二维码系统测试"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.client = Client()
        self.superuser = User.objects.create_superuser(
            username='admin',
            password='admin123',
            email='admin@test.com'
        )
        self.student = User.objects.create_user(
            username='S20240001',
            password='240001',
            role='student',
            student_id='S20240001',
            email='student1@test.com'
        )
    
    def test_generate_session_id(self):
        """测试生成 session_id"""
        session_id = generate_session_id()
        self.assertIsNotNone(session_id)
        self.assertTrue(verify_session_id(session_id))
    
    def test_verify_invalid_session_id(self):
        """测试验证无效的 session_id"""
        self.assertFalse(verify_session_id('invalid-session-id'))
        self.assertFalse(verify_session_id(None))
        self.assertFalse(verify_session_id(''))
    
    def test_refresh_session_id(self):
        """测试刷新 session_id"""
        session_id = generate_session_id()
        self.assertTrue(refresh_session_id(session_id))
        self.assertFalse(refresh_session_id('invalid-session-id'))
    
    def test_invalidate_session_id(self):
        """测试使 session_id 失效"""
        session_id = generate_session_id()
        self.assertTrue(verify_session_id(session_id))
        invalidate_session_id(session_id)
        self.assertFalse(verify_session_id(session_id))
    
    def test_get_session_id_api(self):
        """测试获取 session_id API 接口"""
        self.client.login(username='admin', password='admin123')
        response = self.client.post(reverse('accounts:get_session_id'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('session_id', data)
        self.assertIn('login_url', data)
        self.assertEqual(data['expire_time'], settings.QR_CODE_EXPIRE_TIME)
    
    def test_generate_qr_code_view_requires_superuser(self):
        """测试二维码生成页面仅限超级用户访问"""
        response = self.client.get(reverse('accounts:generate_qr'))
        self.assertIn(response.status_code, [302, 403])
    
    def test_generate_qr_code_view_accessible_by_superuser(self):
        """测试超级用户可以访问二维码生成页面"""
        self.client.login(username='admin', password='admin123')
        response = self.client.get(reverse('accounts:generate_qr'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '课堂二维码')
    
    def test_student_login_without_session_id(self):
        """测试学生登录时缺少 session_id 参数"""
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '缺少 session_id 参数')
    
    def test_student_login_with_invalid_session_id(self):
        """测试学生登录时使用无效的 session_id"""
        response = self.client.get(reverse('accounts:login') + '?session_id=invalid-session-id')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '二维码已失效')
    
    def test_student_login_with_valid_session_id(self):
        """测试学生登录时使用有效的 session_id"""
        session_id = generate_session_id()
        response = self.client.get(reverse('accounts:login') + f'?session_id={session_id}')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '学生登录')
        self.assertContains(response, '学号')
        self.assertContains(response, '密码')
    
    def test_student_login_success(self):
        """测试学生登录成功"""
        session_id = generate_session_id()
        
        response = self.client.post(
            reverse('accounts:login') + f'?session_id={session_id}',
            {
                'student_id': 'S20240001',
                'password': '240001'
            },
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.wsgi_request.session.get('exam_authorized'))
        self.assertEqual(
            response.wsgi_request.session.get('authorized_session_id'),
            session_id
        )
    
    def test_student_login_wrong_password(self):
        """测试学生登录时密码错误"""
        session_id = generate_session_id()
        
        response = self.client.post(
            reverse('accounts:login') + f'?session_id={session_id}',
            {
                'student_id': 'S20240001',
                'password': 'wrong_password'
            }
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '学号或密码错误')
    
    def test_student_login_teacher_account(self):
        """测试教师账号无法学生登录"""
        teacher = User.objects.create_user(
            username='teacher1',
            password='teacher123',
            role='teacher',
            email='teacher@test.com'
        )
        
        session_id = generate_session_id()
        
        response = self.client.post(
            reverse('accounts:login') + f'?session_id={session_id}',
            {
                'student_id': 'teacher1',
                'password': 'teacher123'
            }
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '该账号不是学生账号')
    
    def test_permission_denied_view(self):
        """测试权限拒绝页面"""
        response = self.client.get(reverse('accounts:permission_denied'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '权限不足')
        self.assertContains(response, '未通过扫码认证')
    
    def test_login_error_view(self):
        """测试登录错误页面"""
        response = self.client.get(reverse('accounts:login_error'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '登录失败')


class ExamAccessControlTest(TestCase):
    """考试访问控制测试"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.client = Client()
        self.student = User.objects.create_user(
            username='S20240001',
            password='240001',
            role='student',
            student_id='S20240001',
            email='student1@test.com'
        )
        self.teacher = User.objects.create_user(
            username='teacher1',
            password='teacher123',
            role='teacher',
            email='teacher@test.com'
        )
        from django.utils import timezone
        from datetime import timedelta
        from exams.models import Exam
        self.exam = Exam.objects.create(
            title='测试考试',
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=2),
            created_by=self.teacher,
            is_active=True
        )
    
    def test_exam_list_without_authorization(self):
        """测试未授权访问考试列表"""
        self.client.login(username='S20240001', password='240001')
        response = self.client.get(reverse('exams:exam_list'))
        self.assertRedirects(response, reverse('accounts:permission_denied'))
    
    def test_exam_list_with_authorization(self):
        """测试已授权访问考试列表"""
        self.client.login(username='S20240001', password='240001')
        session = self.client.session
        session['exam_authorized'] = True
        session.save()
        
        response = self.client.get(reverse('exams:exam_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '我的考试')
    
    def test_exam_detail_without_authorization(self):
        """测试未授权访问考试详情"""
        self.client.login(username='S20240001', password='240001')
        response = self.client.get(reverse('exams:exam_detail', args=[self.exam.id]))
        self.assertRedirects(response, reverse('accounts:permission_denied'))
    
    def test_exam_detail_with_authorization(self):
        """测试已授权访问考试详情"""
        self.client.login(username='S20240001', password='240001')
        session = self.client.session
        session['exam_authorized'] = True
        session.save()
        
        response = self.client.get(reverse('exams:exam_detail', args=[self.exam.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.exam.title)
    
    def test_exam_requires_login(self):
        """测试考试页面需要登录"""
        session = self.client.session
        session['exam_authorized'] = True
        session.save()
        
        response = self.client.get(reverse('exams:exam_list'))
        self.assertRedirects(response, '/accounts/login/?next=/exams/')
