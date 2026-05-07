from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from exams.models import Exam, Question, ExamRecord
import json

User = get_user_model()


class TeacherExamManagementTest(TestCase):
    """教师考试管理功能测试"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.client = Client()
        self.teacher = User.objects.create_user(
            username='teacher_test',
            password='teacher123',
            role='teacher',
            email='teacher@test.com'
        )
        self.student = User.objects.create_user(
            username='student_test',
            password='student123',
            role='student',
            student_id='S20240001',
            email='student@test.com'
        )
        
        # 创建考试
        self.exam = Exam.objects.create(
            title='测试考试',
            description='测试描述',
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=2),
            max_score=100,
            is_active=True,
            created_by=self.teacher
        )
    
    def test_teacher_login(self):
        """测试教师登录"""
        response = self.client.post(
            reverse('accounts:teacher_login'),
            {'username': 'teacher_test', 'password': 'teacher123'},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)
    
    def test_dashboard_access(self):
        """测试访问仪表盘"""
        self.client.login(username='teacher_test', password='teacher123')
        response = self.client.get(reverse('teacher:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '仪表盘')
    
    def test_exam_list_access(self):
        """测试访问考试列表"""
        self.client.login(username='teacher_test', password='teacher123')
        response = self.client.get(reverse('teacher:exam_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '测试考试')
    
    def test_exam_create(self):
        """测试创建考试"""
        self.client.login(username='teacher_test', password='teacher123')
        
        future_start = timezone.now() + timedelta(days=1)
        future_end = timezone.now() + timedelta(days=2)
        
        response = self.client.post(
            reverse('teacher:exam_create'),
            {
                'title': '新考试',
                'description': '新考试描述',
                'start_time': future_start.strftime('%Y-%m-%dT%H:%M'),
                'end_time': future_end.strftime('%Y-%m-%dT%H:%M'),
                'max_score': 100,
                'is_active': 'on'
            },
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Exam.objects.filter(title='新考试').count(), 1)
    
    def test_exam_edit(self):
        """测试编辑考试"""
        self.client.login(username='teacher_test', password='teacher123')
        
        response = self.client.post(
            reverse('teacher:exam_edit', args=[self.exam.id]),
            {
                'title': '修改后的考试',
                'description': self.exam.description,
                'start_time': self.exam.start_time.strftime('%Y-%m-%dT%H:%M'),
                'end_time': self.exam.end_time.strftime('%Y-%m-%dT%H:%M'),
                'max_score': 100,
                'is_active': 'on'
            },
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        updated_exam = Exam.objects.get(id=self.exam.id)
        self.assertEqual(updated_exam.title, '修改后的考试')
    
    def test_exam_delete(self):
        """测试删除考试"""
        self.client.login(username='teacher_test', password='teacher123')
        
        response = self.client.post(
            reverse('teacher:exam_delete', args=[self.exam.id]),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Exam.objects.count(), 0)
    
    def test_exam_delete_other_teacher_exam(self):
        """测试不能删除其他教师的考试"""
        other_teacher = User.objects.create_user(
            username='other_teacher',
            password='teacher123',
            role='teacher',
            email='other@test.com'
        )
        
        other_exam = Exam.objects.create(
            title='其他考试',
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=2),
            created_by=other_teacher
        )
        
        self.client.login(username='teacher_test', password='teacher123')
        response = self.client.post(
            reverse('teacher:exam_delete', args=[other_exam.id]),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Exam.objects.filter(id=other_exam.id).count(), 1)


class QuestionManagementTest(TestCase):
    """题目管理功能测试"""
    
    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            username='teacher_test',
            password='teacher123',
            role='teacher',
            email='teacher@test.com'
        )
        
        self.exam = Exam.objects.create(
            title='测试考试',
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=2),
            max_score=100,
            created_by=self.teacher
        )
    
    def test_questions_page_access(self):
        """测试访问题目管理页面"""
        self.client.login(username='teacher_test', password='teacher123')
        response = self.client.get(reverse('teacher:questions'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '题目管理')
    
    def test_exam_questions_access(self):
        """测试访问考试题目页面"""
        self.client.login(username='teacher_test', password='teacher123')
        response = self.client.get(reverse('teacher:exam_questions', args=[self.exam.id]))
        self.assertEqual(response.status_code, 200)
    
    def test_create_choice_question(self):
        """测试创建选择题"""
        self.client.login(username='teacher_test', password='teacher123')
        
        data = {
            'question_type': 'choice',
            'question_text': '这是一个选择题',
            'option_a': '选项 A',
            'option_b': '选项 B',
            'option_c': '选项 C',
            'option_d': '选项 D',
            'answer': 'A',
            'score': 5
        }
        
        response = self.client.post(
            reverse('teacher:question_create', args=[self.exam.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Question.objects.count(), 1)
        question = Question.objects.first()
        self.assertEqual(question.question_type, 'choice')
        self.assertEqual(question.answer, 'A')
    
    def test_create_blank_question(self):
        """测试创建填空题"""
        self.client.login(username='teacher_test', password='teacher123')
        
        data = {
            'question_type': 'blank',
            'question_text': '这是一个填空题',
            'answer': '正确答案',
            'score': 10
        }
        
        response = self.client.post(
            reverse('teacher:question_create', args=[self.exam.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Question.objects.count(), 1)
        question = Question.objects.first()
        self.assertEqual(question.question_type, 'blank')
    
    def test_update_question(self):
        """测试更新题目"""
        question = Question.objects.create(
            exam=self.exam,
            question_type='choice',
            question_text='原题目',
            option_a='A',
            option_b='B',
            answer='A',
            score=5
        )
        
        self.client.login(username='teacher_test', password='teacher123')
        
        data = {
            'question_type': 'choice',
            'question_text': '修改后的题目',
            'option_a': '选项 A',
            'option_b': '选项 B',
            'answer': 'B',
            'score': 10
        }
        
        response = self.client.post(
            reverse('teacher:question_update', args=[self.exam.id, question.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        updated_question = Question.objects.get(id=question.id)
        self.assertEqual(updated_question.question_text, '修改后的题目')
        self.assertEqual(updated_question.answer, 'B')
    
    def test_delete_question(self):
        """测试删除题目"""
        question = Question.objects.create(
            exam=self.exam,
            question_type='choice',
            question_text='测试题目',
            option_a='A',
            option_b='B',
            answer='A',
            score=5
        )
        
        self.client.login(username='teacher_test', password='teacher123')
        
        response = self.client.post(
            reverse('teacher:question_delete', args=[self.exam.id, question.id])
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Question.objects.count(), 0)


class QRCodeManagementTest(TestCase):
    """二维码管理功能测试"""
    
    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            username='teacher_test',
            password='teacher123',
            role='teacher',
            email='teacher@test.com'
        )
        
        self.exam = Exam.objects.create(
            title='测试考试',
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=2),
            max_score=100,
            is_active=True,
            created_by=self.teacher
        )
    
    def test_qrcode_page_access(self):
        """测试访问二维码管理页面"""
        self.client.login(username='teacher_test', password='teacher123')
        response = self.client.get(reverse('teacher:qrcode'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '二维码管理')
    
    def test_generate_qr_code(self):
        """测试生成二维码"""
        self.client.login(username='teacher_test', password='teacher123')
        
        response = self.client.post(
            reverse('teacher:api_generate_qr'),
            data=json.dumps({'exam_id': self.exam.id}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('session_id', data)
        self.assertIn('qr_code_url', data)
    
    def test_generate_qr_invalid_exam(self):
        """测试生成二维码 - 无效考试 ID"""
        self.client.login(username='teacher_test', password='teacher123')
        
        response = self.client.post(
            reverse('teacher:api_generate_qr'),
            data=json.dumps({'exam_id': 999}),
            content_type='application/json'
        )
        
        # get_object_or_404 会返回 404
        self.assertIn(response.status_code, [404, 500])


class ScoreManagementTest(TestCase):
    """成绩管理功能测试"""
    
    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            username='teacher_test',
            password='teacher123',
            role='teacher',
            email='teacher@test.com'
        )
        self.student = User.objects.create_user(
            username='student_test',
            password='student123',
            role='student',
            student_id='S20240001',
            email='student@test.com'
        )
        
        self.exam = Exam.objects.create(
            title='测试考试',
            start_time=timezone.now() - timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1),
            max_score=100,
            created_by=self.teacher
        )
        
        self.record = ExamRecord.objects.create(
            student=self.student,
            exam=self.exam,
            final_score=85,
            is_submitted=True,
            submitted_at=timezone.now()
        )
    
    def test_scores_page_access(self):
        """测试访问成绩管理页面"""
        self.client.login(username='teacher_test', password='teacher123')
        response = self.client.get(reverse('teacher:scores'))
        self.assertEqual(response.status_code, 200)
    
    def test_scores_api(self):
        """测试获取成绩 API"""
        self.client.login(username='teacher_test', password='teacher123')
        
        # 使用正确的 API URL（带斜杠）
        response = self.client.get('/teacher/scores/')
        
        # 这个 API 返回的是 HTML 页面，不是 JSON
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '成绩管理')
    
    def test_score_detail_api(self):
        """测试获取成绩详情 API"""
        self.client.login(username='teacher_test', password='teacher123')
        
        response = self.client.get(
            reverse('teacher:api_score_detail', args=[self.record.id])
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['score'], 85)


class StudentManagementTest(TestCase):
    """学生管理功能测试"""
    
    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            username='teacher_test',
            password='teacher123',
            role='teacher',
            email='teacher@test.com'
        )
        self.student = User.objects.create_user(
            username='student_test',
            password='student123',
            role='student',
            student_id='S20240001',
            email='student@test.com'
        )
    
    def test_students_page_access(self):
        """测试访问学生管理页面"""
        self.client.login(username='teacher_test', password='teacher123')
        response = self.client.get(reverse('teacher:students'))
        self.assertEqual(response.status_code, 200)
    
    def test_student_detail_api(self):
        """测试获取学生详情 API"""
        self.client.login(username='teacher_test', password='teacher123')
        
        response = self.client.get(
            reverse('teacher:api_student_detail', args=[self.student.id])
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['student_id'], 'S20240001')
    
    def test_reset_password(self):
        """测试重置学生密码"""
        self.client.login(username='teacher_test', password='teacher123')
        
        response = self.client.post(
            reverse('teacher:api_reset_password', args=[self.student.id])
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('new_password', data)
        
        # 验证密码已更新
        self.student.refresh_from_db()
        self.assertTrue(self.student.check_password(data['new_password']))


class PermissionTest(TestCase):
    """权限控制测试"""
    
    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            username='teacher_test',
            password='teacher123',
            role='teacher',
            email='teacher@test.com'
        )
        self.student = User.objects.create_user(
            username='student_test',
            password='student123',
            role='student',
            student_id='S20240001',
            email='student@test.com'
        )
    
    def test_student_cannot_access_teacher_dashboard(self):
        """测试学生不能访问教师仪表盘"""
        self.client.login(username='student_test', password='student123')
        response = self.client.get(reverse('teacher:dashboard'))
        self.assertEqual(response.status_code, 302)  # 重定向到权限拒绝页面
    
    def test_unauthenticated_access(self):
        """测试未登录访问"""
        response = self.client.get(reverse('teacher:dashboard'))
        self.assertEqual(response.status_code, 302)  # 重定向到登录页
    
    def test_teacher_cannot_access_other_teacher_exam(self):
        """测试教师不能访问其他教师的考试"""
        other_teacher = User.objects.create_user(
            username='other_teacher',
            password='teacher123',
            role='teacher',
            email='other@test.com'
        )
        
        other_exam = Exam.objects.create(
            title='其他考试',
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=2),
            created_by=other_teacher
        )
        
        self.client.login(username='teacher_test', password='teacher123')
        response = self.client.get(reverse('teacher:exam_edit', args=[other_exam.id]))
        self.assertEqual(response.status_code, 404)


class QuestionBankTest(TestCase):
    """题库管理功能测试"""
    
    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            username='teacher_test',
            password='teacher123',
            role='teacher',
            email='teacher@test.com'
        )
        
        self.question1 = Question.objects.create(
            created_by=self.teacher,
            question_type='choice',
            question_text='测试题目 1',
            option_a='A',
            option_b='B',
            answer='A',
            score=5
        )
        
        self.question2 = Question.objects.create(
            created_by=self.teacher,
            question_type='blank',
            question_text='测试题目 2',
            answer='答案',
            score=10
        )
    
    def test_question_bank_access(self):
        """测试访问题库管理页面"""
        self.client.login(username='teacher_test', password='teacher123')
        response = self.client.get(reverse('teacher:question_bank'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '题库管理')
    
    def test_api_question_list(self):
        """测试获取题目列表 API"""
        self.client.login(username='teacher_test', password='teacher123')
        
        response = self.client.get(reverse('teacher:api_question_list'))
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['total'], 2)
    
    def test_api_question_search(self):
        """测试题目搜索 API"""
        self.client.login(username='teacher_test', password='teacher123')
        
        response = self.client.get(reverse('teacher:api_question_list'), {'keyword': '题目 1'})
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['total'], 1)
    
    def test_api_question_detail(self):
        """测试获取题目详情 API"""
        self.client.login(username='teacher_test', password='teacher123')
        
        response = self.client.get(reverse('teacher:api_question_detail', args=[self.question1.id]))
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['question']['id'], self.question1.id)
    
    def test_batch_add_questions(self):
        """测试批量添加题目到考试"""
        exam = Exam.objects.create(
            title='测试考试',
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=2),
            created_by=self.teacher
        )
        
        self.client.login(username='teacher_test', password='teacher123')
        
        response = self.client.post(
            reverse('teacher:batch_add_questions', args=[exam.id]),
            data=json.dumps({
                'question_ids': [self.question1.id, self.question2.id]
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['added_count'], 2)
        self.assertEqual(exam.questions.count(), 2)


class QuestionImportTest(TestCase):
    """题目批量导入功能测试"""
    
    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            username='teacher_test',
            password='teacher123',
            role='teacher',
            email='teacher@test.com'
        )
        
        self.exam = Exam.objects.create(
            title='测试考试',
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=2),
            created_by=self.teacher
        )
    
    def test_import_questions_excel(self):
        """测试 Excel 批量导入题目"""
        self.client.login(username='teacher_test', password='teacher123')
        
        # 创建测试 Excel 文件
        import openpyxl
        from io import BytesIO
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['题型', '题干', '选项 A', '选项 B', '选项 C', '选项 D', '答案', '分值'])
        ws.append(['choice', '测试选择题', 'A 选项', 'B 选项', 'C 选项', 'D 选项', 'A', 5])
        ws.append(['blank', '测试填空题', '', '', '', '', '答案', 10])
        
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        from django.core.files.uploadedfile import SimpleUploadedFile
        excel_file = SimpleUploadedFile(
            'test_questions.xlsx',
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        response = self.client.post(
            reverse('teacher:api_questions_import'),
            {
                'file': excel_file,
                'exam_id': self.exam.id
            }
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['imported_count'], 2)
        self.assertEqual(data['failed_count'], 0)
        self.assertEqual(Question.objects.count(), 2)
        self.assertEqual(self.exam.questions.count(), 2)
    
    def test_import_questions_without_exam(self):
        """测试仅导入题库不关联考试"""
        self.client.login(username='teacher_test', password='teacher123')
        
        import openpyxl
        from io import BytesIO
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['题型', '题干', '答案', '分值'])
        ws.append(['blank', '测试填空题', '答案', 5])
        
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        from django.core.files.uploadedfile import SimpleUploadedFile
        excel_file = SimpleUploadedFile(
            'test_questions.xlsx',
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        response = self.client.post(
            reverse('teacher:api_questions_import'),
            {
                'file': excel_file
            }
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['imported_count'], 1)
        self.assertEqual(Question.objects.count(), 1)
    
    def test_import_invalid_file(self):
        """测试导入无效文件"""
        self.client.login(username='teacher_test', password='teacher123')
        
        from django.core.files.uploadedfile import SimpleUploadedFile
        invalid_file = SimpleUploadedFile('test.txt', b'invalid content')
        
        response = self.client.post(
            reverse('teacher:api_questions_import'),
            {'file': invalid_file}
        )
        
        # openpyxl 会抛出异常
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
