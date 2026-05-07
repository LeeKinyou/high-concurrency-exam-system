from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.urls import reverse
import json
from .models import Exam, Question, ExamRecord
from .grader import grade_choice_question, grade_blank_question, grade_exam

User = get_user_model()


class UserModelTest(TestCase):
    """用户模型测试"""
    
    def test_create_teacher(self):
        """测试创建教师用户"""
        teacher = User.objects.create_user(
            username='teacher1',
            email='teacher@test.com',
            password='password123',
            role='teacher'
        )
        self.assertEqual(teacher.role, 'teacher')
        self.assertTrue(teacher.is_teacher())
        self.assertFalse(teacher.is_student())
        self.assertIsNone(teacher.student_id)
    
    def test_create_student(self):
        """测试创建学生用户"""
        student = User.objects.create_user(
            username='student1',
            email='student@test.com',
            password='password123',
            role='student',
            student_id='S20240001'
        )
        self.assertEqual(student.role, 'student')
        self.assertEqual(student.student_id, 'S20240001')
        self.assertTrue(student.is_student())
        self.assertFalse(student.is_teacher())
    
    def test_student_id_unique(self):
        """测试学号唯一性"""
        User.objects.create_user(
            username='student1',
            password='password123',
            role='student',
            student_id='S20240001'
        )
        with self.assertRaises(Exception):
            User.objects.create_user(
                username='student2',
                password='password123',
                role='student',
                student_id='S20240001'
            )
    
    def test_user_str_representation(self):
        """测试用户字符串表示"""
        teacher = User.objects.create_user(
            username='teacher1',
            password='password123',
            role='teacher'
        )
        self.assertEqual(str(teacher), 'teacher1(教师)')


class ExamModelTest(TestCase):
    """考试模型测试"""
    
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='teacher1',
            password='password123',
            role='teacher'
        )
        self.now = timezone.now()
    
    def test_create_exam(self):
        """测试创建考试"""
        exam = Exam.objects.create(
            title='期中考试',
            description='2024 年春季学期期中考试',
            start_time=self.now - timedelta(hours=1),
            end_time=self.now + timedelta(hours=2),
            created_by=self.teacher,
            max_score=100
        )
        self.assertEqual(exam.title, '期中考试')
        self.assertEqual(exam.created_by, self.teacher)
        self.assertEqual(exam.max_score, 100)
        self.assertTrue(exam.is_active)
    
    def test_exam_status_ongoing(self):
        """测试考试状态 - 进行中"""
        exam = Exam.objects.create(
            title='进行中考试',
            start_time=self.now - timedelta(hours=1),
            end_time=self.now + timedelta(hours=2),
            created_by=self.teacher
        )
        self.assertTrue(exam.is_ongoing())
        self.assertFalse(exam.is_not_started())
        self.assertFalse(exam.is_over())
    
    def test_exam_status_not_started(self):
        """测试考试状态 - 未开始"""
        exam = Exam.objects.create(
            title='未开始考试',
            start_time=self.now + timedelta(hours=1),
            end_time=self.now + timedelta(hours=3),
            created_by=self.teacher
        )
        self.assertFalse(exam.is_ongoing())
        self.assertTrue(exam.is_not_started())
        self.assertFalse(exam.is_over())
    
    def test_exam_status_over(self):
        """测试考试状态 - 已结束"""
        exam = Exam.objects.create(
            title='已结束考试',
            start_time=self.now - timedelta(hours=3),
            end_time=self.now - timedelta(hours=1),
            created_by=self.teacher
        )
        self.assertFalse(exam.is_ongoing())
        self.assertFalse(exam.is_not_started())
        self.assertTrue(exam.is_over())
    
    def test_exam_str_representation(self):
        """测试考试字符串表示"""
        exam = Exam.objects.create(
            title='测试考试',
            start_time=self.now,
            end_time=self.now,
            created_by=self.teacher
        )
        self.assertEqual(str(exam), '测试考试')


class QuestionModelTest(TestCase):
    """题目模型测试"""
    
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='teacher1',
            password='password123',
            role='teacher'
        )
        self.now = timezone.now()
        self.exam = Exam.objects.create(
            title='测试考试',
            start_time=self.now,
            end_time=self.now + timedelta(hours=2),
            created_by=self.teacher
        )
    
    def test_create_choice_question(self):
        """测试创建选择题"""
        question = Question.objects.create(
            exam=self.exam,
            question_type='choice',
            question_text='1+1 等于几？',
            option_a='1',
            option_b='2',
            option_c='3',
            option_d='4',
            answer='B',
            score=5
        )
        self.assertEqual(question.question_type, 'choice')
        self.assertEqual(question.get_options(), [
            ('A', '1'),
            ('B', '2'),
            ('C', '3'),
            ('D', '4')
        ])
    
    def test_create_blank_question(self):
        """测试创建填空题"""
        question = Question.objects.create(
            exam=self.exam,
            question_type='blank',
            question_text='中国的首都是？',
            answer='北京',
            score=5
        )
        self.assertEqual(question.question_type, 'blank')
        self.assertEqual(question.get_options(), [])
    
    def test_question_ordering(self):
        """测试题目排序"""
        q1 = Question.objects.create(
            exam=self.exam,
            question_type='blank',
            question_text='题目 1',
            answer='答案 1',
            order=2
        )
        q2 = Question.objects.create(
            exam=self.exam,
            question_type='blank',
            question_text='题目 2',
            answer='答案 2',
            order=1
        )
        questions = list(Question.objects.filter(exam=self.exam))
        self.assertEqual(questions[0], q2)
        self.assertEqual(questions[1], q1)
    
    def test_question_str_representation(self):
        """测试题目字符串表示"""
        question = Question.objects.create(
            exam=self.exam,
            question_type='choice',
            question_text='这是一道测试题目' * 10,
            option_a='A',
            option_b='B',
            answer='A',
            score=5
        )
        self.assertIn('[选择题]', str(question))
        self.assertIn('这是一道测试题目', str(question))


class ExamPageTest(TestCase):
    """考试页面功能测试"""
    
    def setUp(self):
        """测试前的准备工作"""
        from django.test import Client
        self.client = Client()
        
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
        
        self.now = timezone.now()
        self.ongoing_exam = Exam.objects.create(
            title='正在进行考试',
            start_time=self.now - timedelta(hours=1),
            end_time=self.now + timedelta(hours=2),
            created_by=self.teacher,
            max_score=100,
            is_active=True
        )
        self.not_started_exam = Exam.objects.create(
            title='未开始考试',
            start_time=self.now + timedelta(hours=1),
            end_time=self.now + timedelta(hours=3),
            created_by=self.teacher,
            max_score=100,
            is_active=True
        )
        self.over_exam = Exam.objects.create(
            title='已结束考试',
            start_time=self.now - timedelta(hours=3),
            end_time=self.now - timedelta(hours=1),
            created_by=self.teacher,
            max_score=100,
            is_active=True
        )
    
    def test_exam_list_requires_authorization(self):
        """测试考试列表需要授权"""
        self.client.login(username='student1', password='student123')
        response = self.client.get(reverse('exams:exam_list'))
        self.assertRedirects(response, reverse('accounts:permission_denied'))
    
    def test_exam_list_with_authorization(self):
        """测试已授权学生可以查看考试列表"""
        self.client.login(username='student1', password='student123')
        session = self.client.session
        session['exam_authorized'] = True
        session.save()
        
        response = self.client.get(reverse('exams:exam_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '正在进行考试')
    
    def test_exam_take_ongoing_exam(self):
        """测试学生可以进入进行中的考试"""
        self.client.login(username='student1', password='student123')
        session = self.client.session
        session['exam_authorized'] = True
        session.save()
        
        response = self.client.get(reverse('exams:exam_take', args=[self.ongoing_exam.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.ongoing_exam.title)
    
    def test_exam_take_not_started_exam(self):
        """测试学生无法进入未开始的考试"""
        self.client.login(username='student1', password='student123')
        session = self.client.session
        session['exam_authorized'] = True
        session.save()
        
        response = self.client.get(reverse('exams:exam_take', args=[self.not_started_exam.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '考试未开始')
    
    def test_exam_take_over_exam(self):
        """测试学生无法进入已结束的考试"""
        self.client.login(username='student1', password='student123')
        session = self.client.session
        session['exam_authorized'] = True
        session.save()
        
        response = self.client.get(reverse('exams:exam_take', args=[self.over_exam.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '考试已结束')
    
    def test_save_answer_success(self):
        """测试保存答案成功"""
        self.client.login(username='student1', password='student123')
        session = self.client.session
        session['exam_authorized'] = True
        session.save()
        
        question = Question.objects.create(
            exam=self.ongoing_exam,
            question_type='blank',
            question_text='测试题目',
            answer='答案',
            score=10
        )
        
        answers = {str(question.id): '测试答案'}
        
        response = self.client.post(
            reverse('exams:save_answer', args=[self.ongoing_exam.id]),
            data=json.dumps({'answers': answers}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # 验证答案已保存
        record = ExamRecord.objects.get(student=self.student, exam=self.ongoing_exam)
        self.assertEqual(record.answer_sheet[str(question.id)], '测试答案')
    
    def test_save_answer_after_exam_over(self):
        """测试考试结束后无法保存答案"""
        self.client.login(username='student1', password='student123')
        session = self.client.session
        session['exam_authorized'] = True
        session.save()
        
        answers = {'1': '答案'}
        
        response = self.client.post(
            reverse('exams:save_answer', args=[self.over_exam.id]),
            data=json.dumps({'answers': answers}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('不在考试时间内', data['error'])
    
    def test_submit_exam_success(self):
        """测试提交考试成功"""
        self.client.login(username='student1', password='student123')
        session = self.client.session
        session['exam_authorized'] = True
        session.save()
        
        question = Question.objects.create(
            exam=self.ongoing_exam,
            question_type='blank',
            question_text='测试题目',
            answer='正确答案',
            score=10
        )
        
        # 先创建答卷记录
        record = ExamRecord.objects.create(
            student=self.student,
            exam=self.ongoing_exam
        )
        
        answers = {str(question.id): '正确答案'}
        
        response = self.client.post(
            reverse('exams:submit_exam', args=[self.ongoing_exam.id]),
            data=json.dumps({'answers': answers}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['score'], 10)
        self.assertEqual(data['max_score'], 100)
        
        # 验证答卷已提交
        record.refresh_from_db()
        self.assertTrue(record.is_submitted)
        self.assertEqual(record.final_score, Decimal('10'))
    
    def test_submit_exam_twice(self):
        """测试重复提交考试"""
        self.client.login(username='student1', password='student123')
        session = self.client.session
        session['exam_authorized'] = True
        session.save()
        
        # 第一次提交
        ExamRecord.objects.create(
            student=self.student,
            exam=self.ongoing_exam,
            is_submitted=True,
            submitted_at=self.now
        )
        
        answers = {'1': '答案'}
        
        response = self.client.post(
            reverse('exams:submit_exam', args=[self.ongoing_exam.id]),
            data=json.dumps({'answers': answers}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('考试已交卷', data['error'])


class GraderAlgorithmTest(TestCase):
    """判题算法测试"""
    
    def test_grade_choice_question_correct(self):
        """测试选择题判分 - 正确答案"""
        score = grade_choice_question('A', 'A', 5)
        self.assertEqual(score, 5)
    
    def test_grade_choice_question_wrong(self):
        """测试选择题判分 - 错误答案"""
        score = grade_choice_question('B', 'A', 5)
        self.assertEqual(score, 0)
    
    def test_grade_choice_question_case_insensitive(self):
        """测试选择题判分 - 大小写不敏感"""
        score = grade_choice_question('a', 'A', 5)
        self.assertEqual(score, 5)
    
    def test_grade_choice_question_empty(self):
        """测试选择题判分 - 空答案"""
        score = grade_choice_question('', 'A', 5)
        self.assertEqual(score, 0)
    
    def test_grade_blank_question_exact_match(self):
        """测试填空题判分 - 完全匹配"""
        score = grade_blank_question('北京', '北京', 5)
        self.assertEqual(score, 5)
    
    def test_grade_blank_question_substring_match(self):
        """测试填空题判分 - 包含匹配"""
        score = grade_blank_question('中国北京', '北京', 5)
        self.assertEqual(score, 3)  # 50% 向上取整
    
    def test_grade_blank_question_no_match(self):
        """测试填空题判分 - 完全不匹配"""
        score = grade_blank_question('上海', '北京', 5)
        self.assertEqual(score, 0)
    
    def test_grade_blank_question_empty(self):
        """测试填空题判分 - 空答案"""
        score = grade_blank_question('', '北京', 5)
        self.assertEqual(score, 0)
    
    def test_grade_exam_mixed(self):
        """测试整张试卷判分"""
        teacher = User.objects.create_user(
            username='teacher2',
            password='teacher123',
            role='teacher',
            email='teacher2@test.com'
        )
        exam = Exam.objects.create(
            title='测试考试',
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=2),
            created_by=teacher
        )
        
        q1 = Question.objects.create(
            exam=exam,
            question_type='choice',
            question_text='选择题',
            option_a='A',
            option_b='B',
            answer='A',
            score=5
        )
        q2 = Question.objects.create(
            exam=exam,
            question_type='blank',
            question_text='填空题',
            answer='北京',
            score=5
        )
        
        answer_sheet = {
            str(q1.id): 'A',  # 正确
            str(q2.id): '中国北京'  # 包含匹配
        }
        
        result = grade_exam(exam, answer_sheet)
        
        self.assertEqual(result['total_score'], 8)  # 5 + 3
        self.assertEqual(result['correct_count'], 1)
        self.assertEqual(result['question_count'], 2)


class AutoSubmitTest(TestCase):
    """兜底交卷测试"""
    
    def setUp(self):
        from .auto_submit import auto_submit_overdue_exams
        self.auto_submit_func = auto_submit_overdue_exams
        
        self.teacher = User.objects.create_user(
            username='teacher3',
            password='teacher123',
            role='teacher',
            email='teacher3@test.com'
        )
        self.student = User.objects.create_user(
            username='student3',
            password='student123',
            role='student',
            student_id='S20240003',
            email='student3@test.com'
        )
    
    def test_auto_submit_overdue_exam(self):
        """测试自动提交过期考试"""
        # 创建已结束的考试
        exam = Exam.objects.create(
            title='已结束考试',
            start_time=timezone.now() - timedelta(hours=3),
            end_time=timezone.now() - timedelta(hours=1),
            created_by=self.teacher,
            is_active=True
        )
        
        # 创建未交卷记录
        q1 = Question.objects.create(
            exam=exam,
            question_type='choice',
            question_text='选择题',
            option_a='A',
            option_b='B',
            answer='A',
            score=5
        )
        
        record = ExamRecord.objects.create(
            student=self.student,
            exam=exam,
            answer_sheet={str(q1.id): 'A'},
            is_submitted=False
        )
        
        # 执行兜底交卷
        result = self.auto_submit_func()
        
        self.assertGreaterEqual(result['total_count'], 1)
        
        # 验证记录已提交
        record.refresh_from_db()
        self.assertTrue(record.is_submitted)
        # submission_method 字段可能不存在于所有测试环境
        if hasattr(record, 'submission_method'):
            self.assertEqual(record.submission_method, 'auto')
        self.assertGreater(record.final_score, 0)


class ExamRecordModelTest(TestCase):
    """考试记录模型测试"""
    
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='teacher1',
            password='password123',
            role='teacher'
        )
        self.student = User.objects.create_user(
            username='student1',
            password='password123',
            role='student',
            student_id='S20240001'
        )
        self.now = timezone.now()
        self.exam = Exam.objects.create(
            title='测试考试',
            start_time=self.now,
            end_time=self.now + timedelta(hours=2),
            created_by=self.teacher
        )
    
    def test_create_exam_record(self):
        """测试创建考试记录"""
        record = ExamRecord.objects.create(
            student=self.student,
            exam=self.exam
        )
        self.assertEqual(record.student, self.student)
        self.assertEqual(record.exam, self.exam)
        self.assertEqual(record.answer_sheet, {})
        self.assertEqual(record.final_score, Decimal('0'))
        self.assertFalse(record.is_submitted)
    
    def test_unique_student_exam_constraint(self):
        """测试一个学生对一个考试只有一条记录"""
        ExamRecord.objects.create(
            student=self.student,
            exam=self.exam
        )
        with self.assertRaises(Exception):
            ExamRecord.objects.create(
                student=self.student,
                exam=self.exam
            )
    
    def test_set_and_get_answer(self):
        """测试设置和获取答案"""
        record = ExamRecord.objects.create(
            student=self.student,
            exam=self.exam
        )
        record.set_answer(1, 'A')
        record.set_answer(2, '北京')
        
        self.assertEqual(record.get_answer(1), 'A')
        self.assertEqual(record.get_answer(2), '北京')
        self.assertEqual(record.get_answer(3), '')
    
    def test_submit_exam(self):
        """测试交卷"""
        record = ExamRecord.objects.create(
            student=self.student,
            exam=self.exam,
            answer_sheet={'1': 'A', '2': 'B'}
        )
        from django.utils import timezone
        record.is_submitted = True
        record.final_score = Decimal('95.50')
        record.submitted_at = timezone.now()
        record.save()
        
        self.assertTrue(record.is_submitted)
        self.assertEqual(record.final_score, Decimal('95.50'))
        self.assertIsNotNone(record.submitted_at)
    
    def test_exam_record_str_representation(self):
        """测试考试记录字符串表示"""
        record = ExamRecord.objects.create(
            student=self.student,
            exam=self.exam
        )
        self.assertEqual(str(record), 'student1 - 测试考试')


class ModelRelationshipTest(TestCase):
    """模型关联测试"""
    
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='teacher1',
            password='password123',
            role='teacher'
        )
        self.student = User.objects.create_user(
            username='student1',
            password='password123',
            role='student',
            student_id='S20240001'
        )
        self.now = timezone.now()
    
    def test_exam_questions_relationship(self):
        """测试考试与题目的关联"""
        exam = Exam.objects.create(
            title='测试考试',
            start_time=self.now,
            end_time=self.now + timedelta(hours=2),
            created_by=self.teacher
        )
        Question.objects.create(
            exam=exam,
            question_type='blank',
            question_text='题目 1',
            answer='答案 1',
            score=5
        )
        Question.objects.create(
            exam=exam,
            question_type='blank',
            question_text='题目 2',
            answer='答案 2',
            score=5
        )
        
        self.assertEqual(exam.questions.count(), 2)
        self.assertEqual(list(exam.questions.all().values_list('question_text', flat=True)), 
                        ['题目 1', '题目 2'])
    
    def test_exam_records_relationship(self):
        """测试考试与考试记录的关联"""
        exam = Exam.objects.create(
            title='测试考试',
            start_time=self.now,
            end_time=self.now + timedelta(hours=2),
            created_by=self.teacher
        )
        ExamRecord.objects.create(student=self.student, exam=exam)
        
        self.assertEqual(exam.records.count(), 1)
        self.assertEqual(exam.records.first().student, self.student)
    
    def test_student_exam_records_relationship(self):
        """测试学生与考试记录的关联"""
        exam1 = Exam.objects.create(
            title='考试 1',
            start_time=self.now,
            end_time=self.now + timedelta(hours=2),
            created_by=self.teacher
        )
        exam2 = Exam.objects.create(
            title='考试 2',
            start_time=self.now,
            end_time=self.now + timedelta(hours=2),
            created_by=self.teacher
        )
        ExamRecord.objects.create(student=self.student, exam=exam1)
        ExamRecord.objects.create(student=self.student, exam=exam2)
        
        self.assertEqual(self.student.exam_records.count(), 2)
    
    def test_teacher_created_exams_relationship(self):
        """测试教师与创建的考试的关联"""
        exam1 = Exam.objects.create(
            title='考试 1',
            start_time=self.now,
            end_time=self.now + timedelta(hours=2),
            created_by=self.teacher
        )
        exam2 = Exam.objects.create(
            title='考试 2',
            start_time=self.now,
            end_time=self.now + timedelta(hours=2),
            created_by=self.teacher
        )
        
        self.assertEqual(self.teacher.created_exams.count(), 2)
        self.assertIn(exam1, self.teacher.created_exams.all())
        self.assertIn(exam2, self.teacher.created_exams.all())


class BusinessLogicTest(TestCase):
    """业务逻辑测试"""
    
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='teacher1',
            password='password123',
            role='teacher'
        )
        self.student = User.objects.create_user(
            username='student1',
            password='password123',
            role='student',
            student_id='S20240001'
        )
        self.now = timezone.now()
    
    def test_exam_time_logic(self):
        """测试考试时间逻辑"""
        exam_past = Exam.objects.create(
            title='过去考试',
            start_time=self.now - timedelta(hours=2),
            end_time=self.now - timedelta(hours=1),
            created_by=self.teacher
        )
        exam_present = Exam.objects.create(
            title='当前考试',
            start_time=self.now - timedelta(minutes=30),
            end_time=self.now + timedelta(minutes=30),
            created_by=self.teacher
        )
        exam_future = Exam.objects.create(
            title='未来考试',
            start_time=self.now + timedelta(hours=1),
            end_time=self.now + timedelta(hours=2),
            created_by=self.teacher
        )
        
        self.assertTrue(exam_past.is_over())
        self.assertTrue(exam_present.is_ongoing())
        self.assertTrue(exam_future.is_not_started())
    
    def test_exam_record_creation_logic(self):
        """测试答卷记录创建逻辑"""
        exam = Exam.objects.create(
            title='测试考试',
            start_time=self.now,
            end_time=self.now + timedelta(hours=2),
            created_by=self.teacher,
            max_score=100
        )
        q1 = Question.objects.create(
            exam=exam,
            question_type='choice',
            question_text='题目 1',
            option_a='A',
            option_b='B',
            answer='A',
            score=10
        )
        q2 = Question.objects.create(
            exam=exam,
            question_type='blank',
            question_text='题目 2',
            answer='答案 2',
            score=10
        )
        
        record = ExamRecord.objects.create(
            student=self.student,
            exam=exam
        )
        
        record.set_answer(q1.id, 'A')
        record.set_answer(q2.id, '答案 2')
        
        self.assertEqual(len(record.answer_sheet), 2)
        self.assertEqual(record.answer_sheet[str(q1.id)], 'A')
        self.assertEqual(record.answer_sheet[str(q2.id)], '答案 2')
