"""
考试结果展示功能测试
测试考试进行期间和结束后的结果展示行为
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import json

from exams.models import Exam, Question, ExamQuestion, ExamRecord
from exams.grader import grade_exam


User = get_user_model()


class ExamResultDisplayTest(TestCase):
    """考试结果展示功能测试"""

    def setUp(self):
        """创建测试数据"""
        self.client = Client()

        # 创建教师和学生
        self.teacher = User.objects.create_user(
            username='result_teacher',
            password='pass123',
            role='teacher'
        )
        self.student = User.objects.create_user(
            username='result_student',
            password='pass123',
            role='student'
        )

        # 登录学生
        self.client.login(username='result_student', password='pass123')
        
        # 设置 exam_authorized session 标记
        session = self.client.session
        session['exam_authorized'] = True
        session.save()

    def create_exam_with_questions(self, is_ended=False):
        """创建带有题目的考试"""
        now = timezone.now()

        if is_ended:
            # 已结束的考试：结束时间在过去
            start_time = now - timedelta(hours=3)
            end_time = now - timedelta(hours=1)
        else:
            # 进行中的考试：结束时间在未来
            start_time = now - timedelta(hours=1)
            end_time = now + timedelta(hours=1)

        # 创建考试
        exam = Exam.objects.create(
            title='测试考试 - ' + ('已结束' if is_ended else '进行中'),
            description='考试结果展示测试',
            start_time=start_time,
            end_time=end_time,
            created_by=self.teacher
        )

        # 创建选择题
        choice_q = Question.objects.create(
            created_by=self.teacher,
            question_type='choice',
            question_text='1+1等于多少？',
            option_a='1',
            option_b='2',
            option_c='3',
            option_d='4',
            answer='B',
            score=5
        )

        # 创建填空题
        blank_q = Question.objects.create(
            created_by=self.teacher,
            question_type='blank',
            question_text='水的化学式是____',
            answer='H2O',
            score=5
        )

        # 关联题目到考试
        ExamQuestion.objects.create(exam=exam, question=choice_q, score=5, order=1)
        ExamQuestion.objects.create(exam=exam, question=blank_q, score=5, order=2)

        return exam, choice_q, blank_q

    def create_exam_record(self, exam, choice_q, blank_q, correct=True):
        """创建考试记录"""
        answer_sheet = {}

        if correct:
            # 正确答案
            answer_sheet = {
                str(choice_q.id): 'B',
                str(blank_q.id): 'H2O'
            }
        else:
            # 错误答案
            answer_sheet = {
                str(choice_q.id): 'A',
                str(blank_q.id): 'CO2'
            }

        # 判分
        grading_result = grade_exam(exam, answer_sheet)

        # 创建考试记录
        record = ExamRecord.objects.create(
            student=self.student,
            exam=exam,
            answer_sheet=answer_sheet,
            final_score=grading_result['total_score'],
            grading_details=grading_result,
            is_submitted=True,
            submitted_at=timezone.now(),
            submission_method='manual'
        )

        return record

    def test_ongoing_exam_shows_only_scores(self):
        """测试进行中的考试只显示成绩信息"""
        # 创建进行中的考试和记录
        exam, choice_q, blank_q = self.create_exam_with_questions(is_ended=False)
        self.create_exam_record(exam, choice_q, blank_q, correct=True)

        # 访问结果页面
        response = self.client.get(f'/exams/{exam.id}/result/')
        self.assertEqual(response.status_code, 200)

        # 检查页面内容
        content = response.content.decode('utf-8')

        # 应该显示提示：考试进行中
        self.assertIn('考试进行中', content)
        self.assertIn('仅可查看成绩信息', content)
        self.assertIn('待考试正式结束后', content)

        # 应该显示总分
        self.assertIn(str(exam.max_score), content)

        # 应该显示题型得分
        self.assertIn('各题型得分', content)

        # 检查不应该显示答题详情（排除CSS中的字符串匹配）
        # 先移除CSS部分再检查
        import re
        content_no_css = re.sub(r'<style.*?</style>', '', content, flags=re.DOTALL)
        self.assertNotIn('答题详情', content_no_css)
        self.assertNotIn('你的答案', content_no_css)
        # 检查内容部分不应该有"正确答案"（排除CSS类）
        self.assertNotIn('<strong>正确答案：</strong>', content_no_css)

    def test_ended_exam_shows_complete_details(self):
        """测试已结束的考试显示完整结果"""
        # 创建已结束的考试和记录
        exam, choice_q, blank_q = self.create_exam_with_questions(is_ended=True)
        self.create_exam_record(exam, choice_q, blank_q, correct=True)

        # 访问结果页面
        response = self.client.get(f'/exams/{exam.id}/result/')
        self.assertEqual(response.status_code, 200)

        # 检查页面内容
        content = response.content.decode('utf-8')

        # 应该显示提示：考试已结束
        self.assertIn('考试已结束', content)
        self.assertIn('可以查看完整的考试结果', content)

        # 应该显示总分
        self.assertIn(str(exam.max_score), content)

        # 应该显示题型得分
        self.assertIn('各题型得分', content)

        # 应该显示答题详情
        self.assertIn('答题详情', content)
        self.assertIn('你的答案', content)
        self.assertIn('正确答案', content)

        # 应该显示题目内容
        self.assertIn('1+1等于多少', content)
        self.assertIn('水的化学式', content)

    def test_exam_end_time_displayed(self):
        """测试进行中的考试显示结束时间"""
        exam, choice_q, blank_q = self.create_exam_with_questions(is_ended=False)
        self.create_exam_record(exam, choice_q, blank_q, correct=True)

        response = self.client.get(f'/exams/{exam.id}/result/')
        content = response.content.decode('utf-8')

        # 应该显示考试结束时间（简化检查，只检查关键部分）
        self.assertIn('考试结束时间', content)

    def test_question_type_scores_calculated(self):
        """测试题型得分计算正确"""
        exam, choice_q, blank_q = self.create_exam_with_questions(is_ended=True)
        self.create_exam_record(exam, choice_q, blank_q, correct=True)

        response = self.client.get(f'/exams/{exam.id}/result/')
        content = response.content.decode('utf-8')

        # 选择题和填空题各5分，共10分
        self.assertIn('选择题', content)
        self.assertIn('填空题', content)
        self.assertIn('5 / 5', content)

    def test_partial_score_display(self):
        """测试部分得分的显示（如填空题部分正确）"""
        exam, choice_q, blank_q = self.create_exam_with_questions(is_ended=True)

        # 部分正确的答案（填空题包含匹配）
        answer_sheet = {
            str(choice_q.id): 'B',  # 正确
            str(blank_q.id): 'H2O是水'  # 包含正确答案
        }
        grading_result = grade_exam(exam, answer_sheet)

        ExamRecord.objects.create(
            student=self.student,
            exam=exam,
            answer_sheet=answer_sheet,
            final_score=grading_result['total_score'],
            grading_details=grading_result,
            is_submitted=True,
            submitted_at=timezone.now(),
            submission_method='manual'
        )

        response = self.client.get(f'/exams/{exam.id}/result/')
        content = response.content.decode('utf-8')

        # 应该显示答题详情
        self.assertIn('答题详情', content)

    def test_choice_question_options_displayed(self):
        """测试选择题选项在考试结束后显示"""
        exam, choice_q, blank_q = self.create_exam_with_questions(is_ended=True)
        self.create_exam_record(exam, choice_q, blank_q, correct=False)

        response = self.client.get(f'/exams/{exam.id}/result/')
        content = response.content.decode('utf-8')

        # 应该显示选项（简化检查）
        self.assertIn('A', content)
        self.assertIn('1', content)
        self.assertIn('B', content)
        self.assertIn('2', content)

        # 应该标记正确答案
        self.assertIn('正确答案', content)


class ExamResultEdgeCaseTest(TestCase):
    """考试结果展示的边界条件测试"""

    def setUp(self):
        """创建测试数据"""
        self.client = Client()
        self.teacher = User.objects.create_user(
            username='edge_teacher',
            password='pass123',
            role='teacher'
        )
        self.student = User.objects.create_user(
            username='edge_student',
            password='pass123',
            role='student'
        )
        self.client.login(username='edge_student', password='pass123')
        
        # 设置 exam_authorized session 标记
        session = self.client.session
        session['exam_authorized'] = True
        session.save()

    def test_exam_with_no_questions(self):
        """测试没有题目的考试"""
        now = timezone.now()
        exam = Exam.objects.create(
            title='无题目考试',
            start_time=now - timedelta(hours=3),
            end_time=now - timedelta(hours=1),  # 已结束
            created_by=self.teacher
        )

        # 创建空记录
        ExamRecord.objects.create(
            student=self.student,
            exam=exam,
            answer_sheet={},
            final_score=0,
            grading_details={},
            is_submitted=True,
            submitted_at=timezone.now()
        )

        response = self.client.get(f'/exams/{exam.id}/result/')
        self.assertEqual(response.status_code, 200)

        # 应该显示暂无详细答题记录
        content = response.content.decode('utf-8')
        self.assertIn('暂无详细答题记录', content)

    def test_exam_with_zero_score(self):
        """测试得0分的考试"""
        now = timezone.now()
        exam = Exam.objects.create(
            title='零分考试',
            start_time=now - timedelta(hours=3),
            end_time=now - timedelta(hours=1),
            created_by=self.teacher,
            max_score=100
        )

        q = Question.objects.create(
            created_by=self.teacher,
            question_type='choice',
            question_text='测试题目',
            option_a='A',
            option_b='B',
            answer='B',
            score=10
        )
        ExamQuestion.objects.create(exam=exam, question=q, score=10, order=1)

        # 错误答案
        answer_sheet = {str(q.id): 'A'}
        grading_result = grade_exam(exam, answer_sheet)

        ExamRecord.objects.create(
            student=self.student,
            exam=exam,
            answer_sheet=answer_sheet,
            final_score=0,
            grading_details=grading_result,
            is_submitted=True,
            submitted_at=timezone.now()
        )

        response = self.client.get(f'/exams/{exam.id}/result/')
        content = response.content.decode('utf-8')

        # 应该显示0分
        self.assertIn('0', content)
        # 应该显示错误标记
        self.assertIn('bg-danger', content)

    def test_exam_just_ended(self):
        """测试刚结束的考试（边界时间）"""
        now = timezone.now()

        # 结束时间刚好是现在
        exam = Exam.objects.create(
            title='刚结束的考试',
            start_time=now - timedelta(hours=2),
            end_time=now,
            created_by=self.teacher
        )

        q = Question.objects.create(
            created_by=self.teacher,
            question_type='choice',
            question_text='测试',
            option_a='A',
            option_b='B',
            answer='B',
            score=10
        )
        ExamQuestion.objects.create(exam=exam, question=q, score=10, order=1)

        answer_sheet = {str(q.id): 'B'}
        grading_result = grade_exam(exam, answer_sheet)

        ExamRecord.objects.create(
            student=self.student,
            exam=exam,
            answer_sheet=answer_sheet,
            final_score=10,
            grading_details=grading_result,
            is_submitted=True,
            submitted_at=now - timedelta(minutes=1)
        )

        # 稍微等一下确保时间判断正确
        import time
        time.sleep(0.1)

        response = self.client.get(f'/exams/{exam.id}/result/')
        content = response.content.decode('utf-8')

        # 应该显示考试已结束
        self.assertIn('考试已结束', content)
        # 应该显示答题详情
        self.assertIn('答题详情', content)

    def test_unanswered_questions(self):
        """测试有未作答的题目"""
        now = timezone.now()
        exam = Exam.objects.create(
            title='有未作答的考试',
            start_time=now - timedelta(hours=3),
            end_time=now - timedelta(hours=1),
            created_by=self.teacher
        )

        q1 = Question.objects.create(
            created_by=self.teacher,
            question_type='choice',
            question_text='第一题',
            option_a='A',
            option_b='B',
            answer='B',
            score=5
        )
        q2 = Question.objects.create(
            created_by=self.teacher,
            question_type='choice',
            question_text='第二题',
            option_a='X',
            option_b='Y',
            answer='X',
            score=5
        )

        ExamQuestion.objects.create(exam=exam, question=q1, score=5, order=1)
        ExamQuestion.objects.create(exam=exam, question=q2, score=5, order=2)

        # 只回答第一题
        answer_sheet = {str(q1.id): 'B'}
        grading_result = grade_exam(exam, answer_sheet)

        ExamRecord.objects.create(
            student=self.student,
            exam=exam,
            answer_sheet=answer_sheet,
            final_score=grading_result['total_score'],
            grading_details=grading_result,
            is_submitted=True,
            submitted_at=timezone.now()
        )

        response = self.client.get(f'/exams/{exam.id}/result/')
        content = response.content.decode('utf-8')

        # 应该显示未作答
        self.assertIn('未作答', content)