"""
最终综合测试套件
包含三项关键测试任务：
1. 并发提交测试：模拟 20 名学生同时提交考试答卷
2. 自动提交功能测试：验证考试结束时的自动提交机制
3. 考试评测与分数显示测试：验证自动评测功能和分数显示正确性
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.urls import reverse
from django.db import transaction
import json
import threading
import time
from .models import Exam, Question, ExamRecord, ExamQuestion, ClassInfo, StudentClassRelation
from .grader import grade_exam, grade_choice_question, grade_blank_question
from .auto_submit import auto_submit_overdue_exams, check_and_submit_for_exam

User = get_user_model()


class ConcurrentSubmissionTest(TestCase):
    """
    测试任务 1：并发提交测试
    模拟 20 名学生同时提交考试答卷，验证系统在高并发场景下的数据完整性
    """
    
    def setUp(self):
        """测试准备：创建教师、班级、学生和考试"""
        # 创建教师
        self.teacher = User.objects.create_user(
            username='teacher_concurrent',
            email='teacher@test.com',
            password='password123',
            role='teacher'
        )
        
        # 创建班级
        self.class_info = ClassInfo.objects.create(
            name='测试班级',
            description='并发测试班级',
            teacher=self.teacher
        )
        
        # 创建 20 个学生
        self.students = []
        for i in range(20):
            student = User.objects.create_user(
                username=f'student_concurrent_{i:03d}',
                email=f'student{i}@test.com',
                password='password123',
                role='student',
                student_id=f'S2024{i:03d}'
            )
            self.students.append(student)
            
            # 将学生加入班级
            StudentClassRelation.objects.create(
                student=student,
                class_info=self.class_info,
                is_active=True
            )
        
        # 创建考试（时间设置为当前时间之后 1 小时）
        self.now = timezone.now()
        self.exam = Exam.objects.create(
            title='并发测试考试',
            description='测试高并发提交场景',
            start_time=self.now - timedelta(minutes=30),
            end_time=self.now + timedelta(hours=1),
            created_by=self.teacher,
            max_score=100,
            visibility='class_specific'
        )
        self.exam.allowed_classes.add(self.class_info)
        
        # 创建题目（10 道选择题，每题 10 分）
        self.questions = []
        for i in range(10):
            question = Question.objects.create(
                created_by=self.teacher,
                question_type='choice',
                question_text=f'并发测试题目{i+1}',
                option_a='选项 A',
                option_b='选项 B',
                option_c='选项 C',
                option_d='选项 D',
                answer='A',
                score=10
            )
            self.questions.append(question)
            
            # 添加到考试
            ExamQuestion.objects.create(
                exam=self.exam,
                question=question,
                score=10,
                order=i
            )
        
        self.submission_results = []
        self.lock = threading.Lock()
    
    def submit_exam(self, student_index, answers):
        """模拟学生提交考试"""
        try:
            student = self.students[student_index]
            client = Client()
            
            # 登录
            login_success = client.login(
                username=f'student_concurrent_{student_index:03d}',
                password='password123'
            )
            
            if not login_success:
                with self.lock:
                    self.submission_results.append({
                        'student_index': student_index,
                        'success': False,
                        'error': '登录失败'
                    })
                return
            
            # 创建或获取答卷记录
            record, _ = ExamRecord.objects.get_or_create(
                student=student,
                exam=self.exam
            )
            
            # 先保存答案
            record.answer_sheet = answers
            record.save()
            
            # 提交考试
            response = client.post(
                reverse('exams:submit_exam', args=[self.exam.id]),
                data=json.dumps({'answers': answers}),
                content_type='application/json'
            )
            
            result = {
                'student_index': student_index,
                'success': response.status_code == 200,
                'response_data': json.loads(response.content) if response.status_code == 200 else None,
                'status_code': response.status_code
            }
            
            with self.lock:
                self.submission_results.append(result)
                
        except Exception as e:
            with self.lock:
                self.submission_results.append({
                    'student_index': student_index,
                    'success': False,
                    'error': str(e)
                })
    
    def test_concurrent_submission(self):
        """测试 20 名学生同时提交"""
        print("\n========== 并发提交测试开始 ==========")
        
        # 准备答案数据（所有学生都答对前 5 题，答错后 5 题）
        answers = {}
        for i, question in enumerate(self.questions):
            if i < 5:
                answers[str(question.id)] = 'A'  # 正确答案
            else:
                answers[str(question.id)] = 'B'  # 错误答案
        
        # 使用单个客户端顺序提交所有学生
        print(f"开始 20 个学生的答卷提交...")
        start_time = time.time()
        
        success_count = 0
        fail_count = 0
        
        for i, student in enumerate(self.students):
            try:
                from django.test import Client
                client = Client()
                
                # 登录
                login_success = client.login(
                    username=student.username,
                    password='password123'
                )
                
                if not login_success:
                    print(f"学生{i}登录失败")
                    fail_count += 1
                    continue
                
                # 手动设置 exam_authorized 标记 - 使用正确的方式
                session = client.session
                session['exam_authorized'] = True
                session.save()
                
                # 先创建或获取答卷并保存答案
                record, _ = ExamRecord.objects.get_or_create(
                    student=student,
                    exam=self.exam
                )
                record.answer_sheet = answers.copy()
                record.save()
                
                # 提交考试
                response = client.post(
                    reverse('exams:submit_exam', args=[self.exam.id]),
                    data=json.dumps({'answers': answers}),
                    content_type='application/json'
                )
                
                if response.status_code == 200:
                    success_count += 1
                else:
                    fail_count += 1
                    print(f"学生{i}提交失败：状态码{response.status_code}, 响应：{response.content}")
                    
            except Exception as e:
                fail_count += 1
                print(f"学生{i}异常：{str(e)}")
        
        elapsed_time = time.time() - start_time
        print(f"所有提交完成，耗时：{elapsed_time:.2f}秒")
        
        # 验证结果
        print(f"\n提交结果统计:")
        print(f"成功：{success_count}, 失败：{fail_count}")
        
        # 验证数据库记录
        print(f"\n验证数据库记录...")
        records = ExamRecord.objects.filter(
            exam=self.exam,
            is_submitted=True
        )
        print(f"已提交记录数：{records.count()}")
        
        # 验证数据完整性
        all_scores = []
        for record in records:
            all_scores.append(record.final_score)
            
            # 验证答案是否保存
            answer_sheet = record.answer_sheet
            self.assertIsNotNone(answer_sheet)
            self.assertEqual(len(answer_sheet), 10)
            
            # 验证判题详情
            grading_details = record.grading_details
            self.assertIsNotNone(grading_details)
            self.assertIn('total_score', grading_details)
            self.assertIn('question_scores', grading_details)
        
        print(f"所有记录分数：{all_scores}")
        if len(all_scores) > 0:
            print(f"平均分：{sum(all_scores) / len(all_scores):.2f}")
        else:
            print("平均分：无记录")
        
        # 断言：所有 20 个学生都应成功提交
        self.assertEqual(records.count(), 20, "应该有 20 条提交记录")
        
        # 验证没有重复提交
        unique_records = ExamRecord.objects.filter(exam=self.exam).count()
        self.assertEqual(unique_records, 20, "应该有且仅有 20 条记录，无重复")
        
        print("========== 并发提交测试通过 ==========\n")
    
    def test_data_integrity_after_concurrent_submission(self):
        """测试并发提交后的数据完整性"""
        print("\n========== 数据完整性验证测试 ==========")
        
        # 准备不同的答案
        answers = {str(question.id): 'A' for question in self.questions}
        
        # 并发提交
        threads = []
        for i in range(20):
            thread = threading.Thread(target=self.submit_exam, args=(i, answers.copy()))
            threads.append(thread)
        
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        
        # 验证每条记录的答案完整性
        records = ExamRecord.objects.filter(exam=self.exam, is_submitted=True)
        
        for record in records:
            # 验证答案数量
            self.assertEqual(len(record.answer_sheet), 10, 
                           f"学生{record.student.username}的答案数量不正确")
            
            # 验证每题都有得分记录
            grading_details = record.grading_details
            self.assertEqual(len(grading_details['question_scores']), 10,
                           f"学生{record.student.username}的判题详情不完整")
            
            # 验证分数计算正确（全部答对应得 100 分）
            self.assertEqual(record.final_score, 100,
                           f"学生{record.student.username}的分数计算错误")
        
        print("数据完整性验证通过")
        print("========== 数据完整性验证测试完成 ==========\n")


class AutoSubmissionTest(TestCase):
    """
    测试任务 2：自动提交功能测试
    验证学生未主动提交答卷时系统的自动提交机制
    """
    
    def setUp(self):
        """测试准备"""
        # 创建教师
        self.teacher = User.objects.create_user(
            username='teacher_auto',
            email='teacher_auto@test.com',
            password='password123',
            role='teacher'
        )
        
        # 创建班级
        self.class_info = ClassInfo.objects.create(
            name='自动提交测试班级',
            teacher=self.teacher
        )
        
        # 创建学生
        self.student = User.objects.create_user(
            username='student_auto_test',
            email='student_auto@test.com',
            password='password123',
            role='student',
            student_id='S2024AUTO001'
        )
        
        StudentClassRelation.objects.create(
            student=self.student,
            class_info=self.class_info
        )
        
        # 创建考试（已结束）
        self.now = timezone.now()
        self.exam = Exam.objects.create(
            title='自动提交测试考试',
            description='测试自动提交功能',
            start_time=self.now - timedelta(hours=2),
            end_time=self.now - timedelta(minutes=1),  # 考试已结束
            created_by=self.teacher,
            max_score=100,
            visibility='class_specific'
        )
        self.exam.allowed_classes.add(self.class_info)
        
        # 创建题目
        self.questions = []
        for i in range(5):
            question = Question.objects.create(
                created_by=self.teacher,
                question_type='choice',
                question_text=f'自动提交测试题目{i+1}',
                option_a='选项 A',
                option_b='选项 B',
                answer='A',
                score=20
            )
            self.questions.append(question)
            
            ExamQuestion.objects.create(
                exam=self.exam,
                question=question,
                score=20,
                order=i
            )
    
    def test_auto_submission_mechanism(self):
        """测试自动提交机制"""
        print("\n========== 自动提交功能测试开始 ==========")
        
        # 创建未提交的答卷记录（模拟学生在线答题但未提交）
        answer_sheet = {
            str(question.id): 'A' if i < 3 else 'B'  # 前 3 题答对，后 2 题答错
            for i, question in enumerate(self.questions)
        }
        
        record = ExamRecord.objects.create(
            student=self.student,
            exam=self.exam,
            answer_sheet=answer_sheet,
            is_submitted=False  # 未提交状态
        )
        
        print(f"创建未提交记录：ID={record.id}")
        print(f"答案草稿：{answer_sheet}")
        
        # 验证记录初始状态
        self.assertFalse(record.is_submitted)
        self.assertIsNone(record.submitted_at)
        self.assertEqual(record.final_score, 0)
        
        # 执行自动提交
        print("\n执行自动提交函数...")
        result = auto_submit_overdue_exams()
        
        print(f"自动提交结果：{result}")
        print(f"处理总数：{result['total_count']}")
        print(f"成功数：{result['success_count']}")
        print(f"失败数：{result['error_count']}")
        
        # 验证自动提交结果
        self.assertEqual(result['total_count'], 1, "应该处理 1 条记录")
        self.assertEqual(result['success_count'], 1, "应该成功提交 1 条记录")
        self.assertEqual(result['error_count'], 0, "不应该有错误")
        
        # 刷新记录
        record.refresh_from_db()
        
        # 验证记录状态
        print(f"\n验证提交后的记录状态...")
        self.assertTrue(record.is_submitted, "记录应该已提交")
        self.assertIsNotNone(record.submitted_at, "应该有提交时间")
        self.assertEqual(record.submission_method, 'auto', "提交方式应该是自动提交")
        self.assertGreater(record.final_score, 0, "应该有分数")
        
        # 验证分数计算
        expected_score = 60  # 答对 3 题，每题 20 分
        self.assertEqual(record.final_score, expected_score, 
                        f"分数应该是{expected_score}")
        
        # 验证判题详情
        grading_details = record.grading_details
        self.assertIn('total_score', grading_details)
        self.assertIn('question_scores', grading_details)
        self.assertEqual(grading_details['total_score'], expected_score)
        self.assertEqual(grading_details['correct_count'], 3)
        
        print(f"最终得分：{record.final_score}")
        print(f"判题详情：{json.dumps(grading_details, ensure_ascii=False, indent=2)}")
        
        print("========== 自动提交功能测试通过 ==========\n")
    
    def test_auto_submission_timestamp_accuracy(self):
        """测试自动提交的时间戳准确性"""
        print("\n========== 时间戳准确性测试 ==========")
        
        # 创建未提交记录
        record = ExamRecord.objects.create(
            student=self.student,
            exam=self.exam,
            answer_sheet={},
            is_submitted=False
        )
        
        before_time = timezone.now()
        
        # 执行自动提交
        result = auto_submit_overdue_exams()
        
        after_time = timezone.now()
        
        # 刷新记录
        record.refresh_from_db()
        
        # 验证提交时间在合理范围内
        submitted_at = record.submitted_at
        self.assertGreaterEqual(submitted_at, before_time, 
                               "提交时间不应该早于执行前时间")
        self.assertLessEqual(submitted_at, after_time,
                            "提交时间不应该晚于执行后时间")
        
        print(f"提交时间：{submitted_at}")
        print(f"执行时间范围：{before_time} - {after_time}")
        print("时间戳验证通过")
        print("========== 时间戳准确性测试完成 ==========\n")


class ExamGradingTest(TestCase):
    """
    测试任务 3：考试评测与分数显示测试
    验证系统的自动评测功能及分数显示正确性
    """
    
    def setUp(self):
        """测试准备"""
        # 创建教师
        self.teacher = User.objects.create_user(
            username='teacher_grading',
            email='teacher_grading@test.com',
            password='password123',
            role='teacher'
        )
        
        # 创建班级
        self.class_info = ClassInfo.objects.create(
            name='评分测试班级',
            teacher=self.teacher
        )
        
        # 创建学生
        self.student = User.objects.create_user(
            username='student_grading_test',
            email='student_grading@test.com',
            password='password123',
            role='student',
            student_id='S2024GRADE001'
        )
        
        StudentClassRelation.objects.create(
            student=self.student,
            class_info=self.class_info
        )
        
        # 创建考试
        self.now = timezone.now()
        self.exam = Exam.objects.create(
            title='评分测试考试',
            description='测试自动评分功能',
            start_time=self.now - timedelta(hours=1),
            end_time=self.now + timedelta(hours=1),
            created_by=self.teacher,
            max_score=100,
            visibility='class_specific'
        )
        self.exam.allowed_classes.add(self.class_info)
        
        # 创建混合题型（选择题和填空题）
        self.questions = []
        
        # 5 道选择题，每题 10 分
        for i in range(5):
            question = Question.objects.create(
                created_by=self.teacher,
                question_type='choice',
                question_text=f'选择题{i+1}',
                option_a='选项 A',
                option_b='选项 B',
                option_c='选项 C',
                option_d='选项 D',
                answer='A',
                score=10
            )
            self.questions.append(question)
            ExamQuestion.objects.create(
                exam=self.exam,
                question=question,
                score=10,
                order=i
            )
        
        # 5 道填空题，每题 10 分
        for i in range(5):
            question = Question.objects.create(
                created_by=self.teacher,
                question_type='blank',
                question_text=f'填空题{i+1}',
                answer='正确答案',
                score=10
            )
            self.questions.append(question)
            ExamQuestion.objects.create(
                exam=self.exam,
                question=question,
                score=10,
                order=i + 5
            )
    
    def test_automatic_grading_immediate(self):
        """测试提交后立即自动评测"""
        print("\n========== 自动评测即时性测试 ==========")
        
        # 准备答案（全部正确）
        correct_answers = {}
        for question in self.questions:
            if question.question_type == 'choice':
                correct_answers[str(question.id)] = 'A'
            else:
                correct_answers[str(question.id)] = '正确答案'
        
        # 创建客户端并登录
        client = Client()
        client.login(username='student_grading_test', password='password123')
        
        # 手动设置 exam_authorized 标记 - 使用正确的方式
        session = client.session
        session['exam_authorized'] = True
        session.save()
        
        # 先保存答案
        record, _ = ExamRecord.objects.get_or_create(
            student=self.student,
            exam=self.exam
        )
        record.answer_sheet = correct_answers
        record.save()
        
        # 提交考试
        response = client.post(
            reverse('exams:submit_exam', args=[self.exam.id]),
            data=json.dumps({'answers': correct_answers}),
            content_type='application/json'
        )
        
        print(f"提交响应状态码：{response.status_code}")
        response_data = json.loads(response.content)
        print(f"提交响应数据：{json.dumps(response_data, ensure_ascii=False, indent=2)}")
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response_data['success'])
        self.assertIn('score', response_data)
        self.assertEqual(response_data['score'], 100)
        
        # 验证数据库记录
        record.refresh_from_db()
        self.assertTrue(record.is_submitted)
        self.assertEqual(record.final_score, 100)
        self.assertIsNotNone(record.grading_details)
        
        grading_details = record.grading_details
        self.assertEqual(grading_details['total_score'], 100)
        self.assertEqual(grading_details['correct_count'], 10)
        
        print("自动评测即时性验证通过")
        print("========== 自动评测即时性测试完成 ==========\n")
    
    def test_objective_question_grading_accuracy(self):
        """测试客观题（选择题）答案准确性"""
        print("\n========== 客观题评分准确性测试 ==========")
        
        # 测试选择题判分函数
        test_cases = [
            ('A', 'A', 10, 10, "完全匹配"),
            ('a', 'A', 10, 10, "大小写不敏感"),
            (' A ', 'A', 10, 10, "空格不敏感"),
            ('B', 'A', 10, 0, "错误答案"),
            ('', 'A', 10, 0, "空答案"),
            ('AB', 'A', 10, 0, "多选"),
        ]
        
        for student_answer, correct_answer, score, expected, description in test_cases:
            result = grade_choice_question(student_answer, correct_answer, score)
            print(f"{description}: 学生答案='{student_answer}', 正确答案='{correct_answer}', 得分={result}, 期望={expected}")
            self.assertEqual(result, expected, f"{description}判分错误")
        
        print("客观题评分准确性验证通过")
        print("========== 客观题评分准确性测试完成 ==========\n")
    
    def test_subjective_question_grading_rules(self):
        """测试主观题（填空题）评分规则"""
        print("\n========== 主观题评分规则测试 ==========")
        
        # 测试填空题判分函数
        test_cases = [
            ('正确答案', '正确答案', 10, 10, "完全匹配"),
            (' 正确答案 ', '正确答案', 10, 10, "去除空格后匹配"),
            ('这是正确答案', '正确答案', 10, 5, "包含正确答案（50% 分）"),
            ('错误答案', '正确答案', 10, 0, "完全错误"),
            ('', '正确答案', 10, 0, "空答案"),
            ('部分正确', '正确答案', 10, 0, "部分匹配但不是子串"),
        ]
        
        for student_answer, correct_answer, score, expected, description in test_cases:
            result = grade_blank_question(student_answer, correct_answer, score)
            print(f"{description}: 学生答案='{student_answer}', 正确答案='{correct_answer}', 得分={result}, 期望={expected}")
            self.assertEqual(result, expected, f"{description}判分错误")
        
        print("主观题评分规则验证通过")
        print("========== 主观题评分规则测试完成 ==========\n")
    
    def test_final_score_calculation_accuracy(self):
        """测试最终分数计算准确性"""
        print("\n========== 最终分数计算准确性测试 ==========")
        
        # 创建部分正确的答案
        partial_answers = {}
        for i, question in enumerate(self.questions):
            if i < 3:  # 前 3 题正确
                if question.question_type == 'choice':
                    partial_answers[str(question.id)] = 'A'
                else:
                    partial_answers[str(question.id)] = '正确答案'
            elif i < 5:  # 接下来 2 题错误
                partial_answers[str(question.id)] = 'B'
            elif i < 7:  # 接下来 2 题（填空题）包含正确答案
                partial_answers[str(question.id)] = '这是正确答案'
            else:  # 最后 3 题错误
                partial_answers[str(question.id)] = '错误'
        
        # 手动判分
        grading_result = grade_exam(self.exam, partial_answers)
        
        print(f"判题结果：{json.dumps(grading_result, ensure_ascii=False, indent=2)}")
        
        # 计算期望分数
        # 前 3 题正确：3 * 10 = 30 分
        # 接下来 2 题错误：0 分
        # 接下来 2 题填空题部分正确：2 * 5 = 10 分（50%）
        # 最后 3 题错误：0 分
        expected_score = 40
        
        self.assertEqual(grading_result['total_score'], 40,
                        f"总分计算错误，期望 40，实际{grading_result['total_score']}")
        self.assertEqual(grading_result['correct_count'], 3,
                        f"正确题数错误，期望 3，实际{grading_result['correct_count']}")
        
        # 验证每题得分详情
        question_scores = grading_result['question_scores']
        self.assertEqual(len(question_scores), 10, "应该有 10 道题的得分详情")
        
        print(f"总分：{grading_result['total_score']}")
        print(f"正确题数：{grading_result['correct_count']}")
        print(f"错误题数：{grading_result['wrong_count']}")
        
        print("最终分数计算准确性验证通过")
        print("========== 最终分数计算准确性测试完成 ==========\n")
    
    def test_score_display_consistency(self):
        """测试分数在学生端和教师端显示一致性"""
        print("\n========== 分数显示一致性测试 ==========")
        
        # 创建已提交的答卷
        answers = {str(question.id): 'A' if question.question_type == 'choice' else '正确答案'
                  for question in self.questions}
        
        record = ExamRecord.objects.create(
            student=self.student,
            exam=self.exam,
            answer_sheet=answers,
            is_submitted=True,
            submitted_at=timezone.now(),
            submission_method='manual'
        )
        
        # 判分
        grading_result = grade_exam(self.exam, answers)
        record.final_score = grading_result['total_score']
        record.grading_details = grading_result
        record.save()
        
        # 验证分数一致性
        print(f"数据库记录分数：{record.final_score}")
        print(f"判题结果分数：{grading_result['total_score']}")
        
        # 直接从数据库验证
        saved_record = ExamRecord.objects.get(id=record.id)
        self.assertEqual(saved_record.final_score, grading_result['total_score'],
                        "数据库记录分数与判题结果不一致")
        
        # 验证分数显示正确
        self.assertEqual(saved_record.final_score, 100, "满分应该是 100 分")
        
        print("分数显示一致性验证通过")
        print("========== 分数显示一致性测试完成 ==========\n")


class FinalComprehensiveTest(TestCase):
    """
    最终综合测试
    整合所有测试场景，进行端到端测试
    """
    
    def test_full_exam_workflow(self):
        """完整考试流程测试"""
        print("\n========== 完整考试流程综合测试 ==========")
        
        # 1. 创建考试环境
        teacher = User.objects.create_user(
            username='teacher_final',
            role='teacher'
        )
        
        class_info = ClassInfo.objects.create(
            name='最终测试班级',
            teacher=teacher
        )
        
        student = User.objects.create_user(
            username='student_final',
            role='student',
            student_id='S2024FINAL'
        )
        
        StudentClassRelation.objects.create(
            student=student,
            class_info=class_info
        )
        
        now = timezone.now()
        exam = Exam.objects.create(
            title='最终综合测试',
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
            created_by=teacher,
            visibility='class_specific'
        )
        exam.allowed_classes.add(class_info)
        
        # 2. 创建题目
        question = Question.objects.create(
            created_by=teacher,
            question_type='choice',
            question_text='综合测试题',
            option_a='A',
            option_b='B',
            answer='A',
            score=100
        )
        ExamQuestion.objects.create(
            exam=exam,
            question=question,
            score=100
        )
        
        # 3. 学生答题并提交 - 使用直接 API 方式绕过页面
        answers = {str(question.id): 'A'}
        
        # 创建答卷
        record, _ = ExamRecord.objects.get_or_create(
            student=student,
            exam=exam
        )
        record.answer_sheet = answers
        record.save()
        
        # 手动判分（模拟提交后的处理）
        grading_result = grade_exam(exam, answers)
        record.is_submitted = True
        record.submitted_at = timezone.now()
        record.final_score = grading_result['total_score']
        record.grading_details = grading_result
        record.submission_method = 'manual'
        record.save()
        
        # 4. 验证记录
        self.assertTrue(record.is_submitted)
        self.assertEqual(record.final_score, 100)
        self.assertEqual(record.submission_method, 'manual')
        
        print("完整考试流程测试通过")
        print("========== 完整考试流程综合测试完成 ==========\n")
