from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
import openpyxl
import os
import tempfile

from exams.models import Question
from exams.excel_importer import ExcelQuestionImporter

User = get_user_model()


class ExcelQuestionImporterTest(TestCase):
    """Excel 题目导入器测试"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.client = Client()
        self.teacher = User.objects.create_user(
            username='teacher_import',
            password='teacher123',
            role='teacher',
            email='teacher@test.com'
        )
        self.temp_files = []
    
    def tearDown(self):
        """清理临时文件"""
        for file_path in self.temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass
    
    def create_test_excel(self, questions_data):
        """
        创建测试用的 Excel 文件
        
        Args:
            questions_data: 题目数据列表，每个元素是一个列表，代表一行数据
        
        Returns:
            str: 临时文件路径
        """
        wb = openpyxl.Workbook()
        ws = wb.active
        
        # 写入表头
        ws.append(['题目类型', '题干', '选项 A', '选项 B', '选项 C', '选项 D', '答案'])
        
        # 写入数据
        for row_data in questions_data:
            ws.append(row_data)
        
        # 保存到临时文件
        temp_fd, temp_path = tempfile.mkstemp(suffix='.xlsx')
        os.close(temp_fd)
        wb.save(temp_path)
        wb.close()
        
        self.temp_files.append(temp_path)
        return temp_path
    
    def test_parse_choice_questions(self):
        """测试解析选择题"""
        excel_path = self.create_test_excel([
            ['选择题', '1+1 等于多少？', '1', '2', '3', '4', 'B'],
            ['选择题', '中国的首都是？', '上海', '北京', '广州', '深圳', 'B'],
        ])
        
        importer = ExcelQuestionImporter(excel_path, self.teacher)
        result = importer.parse_excel()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['parsed_count'], 2)
        self.assertEqual(len(result['questions']), 2)
        
        # 验证第一道题
        q1 = result['questions'][0]
        self.assertEqual(q1['question_type'], 'choice')
        self.assertEqual(q1['question_text'], '1+1 等于多少？')
        self.assertEqual(q1['option_a'], '1')
        self.assertEqual(q1['option_b'], '2')
        self.assertEqual(q1['answer'], 'B')
    
    def test_parse_blank_questions(self):
        """测试解析填空题"""
        excel_path = self.create_test_excel([
            ['填空题', '地球是太阳系中的第____大行星', '', '', '', '', '四'],
            ['填空题', '水的化学式是____', '', '', '', '', 'H2O'],
        ])
        
        importer = ExcelQuestionImporter(excel_path, self.teacher)
        result = importer.parse_excel()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['parsed_count'], 2)
        
        # 验证填空题没有选项
        q1 = result['questions'][0]
        self.assertEqual(q1['question_type'], 'blank')
        self.assertEqual(q1['option_a'], '')
        self.assertEqual(q1['answer'], '四')
    
    def test_parse_multiple_choice_answer(self):
        """测试解析多选题答案"""
        excel_path = self.create_test_excel([
            ['选择题', '以下哪些是质数？', '2', '3', '4', '5', 'AB'],
            ['选择题', '以下哪些是偶数？', '1', '2', '3', '4', 'B,D'],
        ])
        
        importer = ExcelQuestionImporter(excel_path, self.teacher)
        result = importer.parse_excel()
        
        self.assertTrue(result['success'])
        
        # 验证答案格式
        q1 = result['questions'][0]
        # 答案'AB'应该被解析为'AB'（排序后）
        self.assertIn(q1['answer'], ['AB'])
        
        q2 = result['questions'][1]
        # 答案'B,D'应该被解析为'BD'（排序后）
        self.assertEqual(q2['answer'], 'BD')
    
    def test_parse_blank_multiple_answers(self):
        """测试解析填空题多个答案"""
        excel_path = self.create_test_excel([
            ['填空题', '1+1=？', '', '', '', '', '2;二;两'],
        ])
        
        importer = ExcelQuestionImporter(excel_path, self.teacher)
        result = importer.parse_excel()
        
        self.assertTrue(result['success'])
        
        q1 = result['questions'][0]
        self.assertEqual(q1['answer'], '2;二;两')
    
    def test_parse_empty_question_text(self):
        """测试解析空题干"""
        excel_path = self.create_test_excel([
            ['选择题', '', 'A', 'B', 'C', 'D', 'A'],
        ])
        
        importer = ExcelQuestionImporter(excel_path, self.teacher)
        result = importer.parse_excel()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['error_count'], 1)
        self.assertEqual(len(result['errors']), 1)
        self.assertIn('题干不能为空', result['errors'][0]['error'])
    
    def test_parse_empty_answer(self):
        """测试解析空答案"""
        excel_path = self.create_test_excel([
            ['选择题', '题目内容', 'A', 'B', 'C', 'D', ''],
        ])
        
        importer = ExcelQuestionImporter(excel_path, self.teacher)
        result = importer.parse_excel()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['error_count'], 1)
        self.assertIn('答案不能为空', result['errors'][0]['error'])
    
    def test_parse_invalid_question_type(self):
        """测试解析无效的题目类型"""
        excel_path = self.create_test_excel([
            ['判断题', '1+1=2', '', '', '', '', '对'],
        ])
        
        importer = ExcelQuestionImporter(excel_path, self.teacher)
        result = importer.parse_excel()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['error_count'], 1)
        self.assertIn('未知的题目类型', result['errors'][0]['error'])
    
    def test_parse_choice_missing_options(self):
        """测试解析缺少选项的选择题"""
        excel_path = self.create_test_excel([
            ['选择题', '题目', 'A', '', '', '', 'A'],
        ])
        
        importer = ExcelQuestionImporter(excel_path, self.teacher)
        result = importer.parse_excel()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['error_count'], 1)
        self.assertIn('选择题必须至少包含选项 A 和 B', result['errors'][0]['error'])
    
    def test_import_questions(self):
        """测试执行题目导入"""
        excel_path = self.create_test_excel([
            ['选择题', '1+1 等于多少？', '1', '2', '3', '4', 'B'],
            ['填空题', '水的化学式是____', '', '', '', '', 'H2O'],
        ])
        
        importer = ExcelQuestionImporter(excel_path, self.teacher)
        parse_result = importer.parse_excel()
        
        self.assertEqual(parse_result['parsed_count'], 2)
        
        # 执行导入（使用行号列表）
        import_result = importer.import_questions([2, 3])
        
        self.assertTrue(import_result['success'])
        self.assertEqual(import_result['imported_count'], 2)
        self.assertEqual(import_result['failed_count'], 0)
        
        # 验证数据库中是否有题目
        self.assertEqual(Question.objects.count(), 2)
        
        # 验证题目内容
        q1 = Question.objects.get(question_type='choice')
        self.assertEqual(q1.question_text, '1+1 等于多少？')
        self.assertEqual(q1.answer, 'B')
        
        q2 = Question.objects.get(question_type='blank')
        self.assertEqual(q2.question_text, '水的化学式是____')
        self.assertEqual(q2.answer, 'H2O')
    
    def test_import_selective_questions(self):
        """测试选择性导入题目"""
        excel_path = self.create_test_excel([
            ['选择题', '题目 1', 'A', 'B', 'C', 'D', 'A'],
            ['选择题', '题目 2', 'A', 'B', 'C', 'D', 'B'],
            ['选择题', '题目 3', 'A', 'B', 'C', 'D', 'C'],
        ])
        
        importer = ExcelQuestionImporter(excel_path, self.teacher)
        parse_result = importer.parse_excel()
        
        # 只导入第 2 和第 3 题（行号）
        selected_rows = [3, 4]
        import_result = importer.import_questions(selected_rows)
        
        self.assertTrue(import_result['success'])
        self.assertEqual(import_result['imported_count'], 2)
        
        # 验证数据库中只有 2 道题目
        self.assertEqual(Question.objects.count(), 2)


class ExcelImportViewTest(TestCase):
    """Excel 导入视图测试"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.client = Client()
        self.teacher = User.objects.create_user(
            username='teacher_view_test',
            password='teacher123',
            role='teacher',
            email='teacher@test.com'
        )
    
    def test_excel_upload_page_access(self):
        """测试访问上传页面"""
        self.client.login(username='teacher_view_test', password='teacher123')
        response = self.client.get(reverse('exams:excel_upload'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'exams/excel_upload.html')
    
    def test_excel_parse_success(self):
        """测试 Excel 解析成功"""
        self.client.login(username='teacher_view_test', password='teacher123')
        
        # 创建测试 Excel
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['题目类型', '题干', '选项 A', '选项 B', '选项 C', '选项 D', '答案'])
        ws.append(['选择题', '测试题目', 'A', 'B', 'C', 'D', 'A'])
        
        temp_fd, temp_path = tempfile.mkstemp(suffix='.xlsx')
        os.close(temp_fd)
        wb.save(temp_path)
        wb.close()
        
        # 上传文件
        with open(temp_path, 'rb') as f:
            excel_file = SimpleUploadedFile(
                'test.xlsx',
                f.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        
        response = self.client.post(
            reverse('exams:excel_parse'),
            {'file': excel_file}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['parsed_count'], 1)
        
        # 清理
        os.remove(temp_path)
    
    def test_excel_parse_invalid_format(self):
        """测试上传不支持的文件格式"""
        self.client.login(username='teacher_view_test', password='teacher123')
        
        # 创建 txt 文件
        temp_fd, temp_path = tempfile.mkstemp(suffix='.txt')
        os.close(temp_fd)
        with open(temp_path, 'w') as f:
            f.write('test content')
        
        with open(temp_path, 'rb') as f:
            txt_file = SimpleUploadedFile('test.txt', f.read(), content_type='text/plain')
        
        response = self.client.post(
            reverse('exams:excel_parse'),
            {'file': txt_file}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('不支持的文件格式', data['error'])
        
        # 清理
        os.remove(temp_path)
    
    def test_excel_parse_no_file(self):
        """测试未上传文件"""
        self.client.login(username='teacher_view_test', password='teacher123')
        
        response = self.client.post(reverse('exams:excel_parse'))
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], '未找到上传文件')
    
    def test_excel_import_confirm(self):
        """测试确认导入"""
        self.client.login(username='teacher_view_test', password='teacher123')
        
        # 先上传并解析文件
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['题目类型', '题干', '选项 A', '选项 B', '选项 C', '选项 D', '答案'])
        ws.append(['选择题', '测试题目', 'A', 'B', 'C', 'D', 'A'])
        
        temp_fd, temp_path = tempfile.mkstemp(suffix='.xlsx')
        os.close(temp_fd)
        wb.save(temp_path)
        wb.close()
        
        with open(temp_path, 'rb') as f:
            excel_file = SimpleUploadedFile(
                'test.xlsx',
                f.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        
        response = self.client.post(
            reverse('exams:excel_parse'),
            {'file': excel_file}
        )
        
        self.assertEqual(response.status_code, 200)
        
        # 确认导入
        response = self.client.post(
            reverse('exams:excel_import_confirm'),
            data={'selected_rows': [2]},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['imported_count'], 1)
        
        # 验证题目已导入
        self.assertEqual(Question.objects.count(), 1)
        
        # 清理
        os.remove(temp_path)
    
    def test_excel_import_no_selection(self):
        """测试未选择题目时导入"""
        self.client.login(username='teacher_view_test', password='teacher123')
        
        response = self.client.post(
            reverse('exams:excel_import_confirm'),
            data={'selected_rows': []},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], '未选择要导入的题目')
    
    def test_excel_import_session_expired(self):
        """测试会话过期时导入"""
        self.client.login(username='teacher_view_test', password='teacher123')
        
        response = self.client.post(
            reverse('exams:excel_import_confirm'),
            data={'selected_rows': [1, 2, 3]},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], '会话已过期，请重新上传文件')
    
    def test_question_import_list_page(self):
        """测试题库导入页面访问"""
        self.client.login(username='teacher_view_test', password='teacher123')
        response = self.client.get(reverse('exams:question_import_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'exams/question_import.html')


class ExcelImportIntegrationTest(TestCase):
    """Excel 导入功能集成测试"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.client = Client()
        self.teacher = User.objects.create_user(
            username='teacher_integration',
            password='teacher123',
            role='teacher',
            email='teacher@test.com'
        )
    
    def test_full_import_workflow(self):
        """测试完整的导入流程"""
        self.client.login(username='teacher_integration', password='teacher123')
        
        # 1. 访问上传页面
        response = self.client.get(reverse('exams:excel_upload'))
        self.assertEqual(response.status_code, 200)
        
        # 2. 创建并上传 Excel 文件
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['题目类型', '题干', '选项 A', '选项 B', '选项 C', '选项 D', '答案'])
        ws.append(['选择题', '1+1 等于多少？', '1', '2', '3', '4', 'B'])
        ws.append(['填空题', '地球是太阳系中的第____大行星', '', '', '', '', '四'])
        
        temp_fd, temp_path = tempfile.mkstemp(suffix='.xlsx')
        os.close(temp_fd)
        wb.save(temp_path)
        wb.close()
        
        with open(temp_path, 'rb') as f:
            excel_file = SimpleUploadedFile(
                'test.xlsx',
                f.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        
        response = self.client.post(
            reverse('exams:excel_parse'),
            {'file': excel_file}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['parsed_count'], 2)
        
        # 3. 确认导入
        response = self.client.post(
            reverse('exams:excel_import_confirm'),
            data={'selected_rows': [2, 3]},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['imported_count'], 2)
        
        # 4. 验证导入结果
        self.assertEqual(Question.objects.count(), 2)
        
        choice_question = Question.objects.get(question_type='choice')
        self.assertEqual(choice_question.question_text, '1+1 等于多少？')
        self.assertEqual(choice_question.answer, 'B')
        
        blank_question = Question.objects.get(question_type='blank')
        self.assertEqual(blank_question.question_text, '地球是太阳系中的第____大行星')
        self.assertEqual(blank_question.answer, '四')
        
        # 清理
        os.remove(temp_path)
    
    def test_import_with_errors(self):
        """测试包含错误的导入"""
        self.client.login(username='teacher_integration', password='teacher123')
        
        # 创建包含错误数据的 Excel
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['题目类型', '题干', '选项 A', '选项 B', '选项 C', '选项 D', '答案'])
        ws.append(['选择题', '有效题目', 'A', 'B', 'C', 'D', 'A'])  # 有效
        ws.append(['选择题', '', 'A', 'B', 'C', 'D', 'A'])  # 无效：空题干
        ws.append(['填空题', '有效填空题', '', '', '', '', '答案'])  # 有效
        
        temp_fd, temp_path = tempfile.mkstemp(suffix='.xlsx')
        os.close(temp_fd)
        wb.save(temp_path)
        wb.close()
        
        with open(temp_path, 'rb') as f:
            excel_file = SimpleUploadedFile(
                'test.xlsx',
                f.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        
        response = self.client.post(
            reverse('exams:excel_parse'),
            {'file': excel_file}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['parsed_count'], 2)  # 2 道有效
        self.assertEqual(data['data']['error_count'], 1)   # 1 道错误
        
        # 导入有效题目
        response = self.client.post(
            reverse('exams:excel_import_confirm'),
            data={'selected_rows': [2, 4]},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['imported_count'], 2)
        
        # 验证
        self.assertEqual(Question.objects.count(), 2)
        
        # 清理
        os.remove(temp_path)
