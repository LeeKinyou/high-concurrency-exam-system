"""
班级管理与考试可见性功能单元测试
覆盖率要求：≥80%
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import json

from exams.models import ClassInfo, StudentClassRelation, Exam, Question, ExamQuestion


User = get_user_model()


class ClassModelTest(TestCase):
    """ClassInfo模型测试"""

    def setUp(self):
        """创建测试数据"""
        self.teacher = User.objects.create_user(
            username='teacher1',
            password='pass123',
            role='teacher',
            email='teacher@test.com'
        )

    def test_create_class(self):
        """测试创建班级"""
        class_info = ClassInfo.objects.create(
            name='计算机科学1班',
            description='2024级计算机科学专业',
            teacher=self.teacher
        )
        self.assertEqual(class_info.name, '计算机科学1班')
        self.assertEqual(class_info.teacher, self.teacher)
        self.assertTrue(class_info.is_active)

    def test_class_str_representation(self):
        """测试班级字符串表示"""
        class_info = ClassInfo.objects.create(
            name='数学1班',
            teacher=self.teacher
        )
        self.assertEqual(str(class_info), '数学1班')

    def test_get_student_count(self):
        """测试获取班级学生数量"""
        class_info = ClassInfo.objects.create(
            name='物理1班',
            teacher=self.teacher
        )
        student = User.objects.create_user(
            username='student1',
            password='pass123',
            role='student'
        )
        StudentClassRelation.objects.create(
            student=student,
            class_info=class_info
        )
        self.assertEqual(class_info.get_student_count(), 1)

    def test_unique_class_name_per_teacher(self):
        """测试同一教师下班级名唯一性"""
        from django.db import IntegrityError
        ClassInfo.objects.create(name='化学1班', teacher=self.teacher)
        with self.assertRaises(IntegrityError):  # 应该抛出IntegrityError
            ClassInfo.objects.create(name='化学1班', teacher=self.teacher)


class StudentClassRelationTest(TestCase):
    """StudentClassRelation模型测试"""

    def setUp(self):
        """创建测试数据"""
        self.teacher = User.objects.create_user(
            username='teacher2',
            password='pass123',
            role='teacher'
        )
        self.class_info = ClassInfo.objects.create(
            name='生物1班',
            teacher=self.teacher
        )
        self.student = User.objects.create_user(
            username='student2',
            password='pass123',
            role='student'
        )

    def test_create_relation(self):
        """测试创建学生-班级关联"""
        relation = StudentClassRelation.objects.create(
            student=self.student,
            class_info=self.class_info
        )
        self.assertEqual(relation.student, self.student)
        self.assertEqual(relation.class_info, self.class_info)
        self.assertTrue(relation.is_active)

    def test_str_representation(self):
        """测试关联的字符串表示"""
        relation = StudentClassRelation.objects.create(
            student=self.student,
            class_info=self.class_info
        )
        expected = f"{self.student.username} - {self.class_info.name}"
        self.assertEqual(str(relation), expected)

    def test_unique_student_class_combination(self):
        """测试学生-班级组合唯一性"""
        StudentClassRelation.objects.create(
            student=self.student,
            class_info=self.class_info
        )
        with self.assertRaises(Exception):  # 应该抛出IntegrityError
            StudentClassRelation.objects.create(
                student=self.student,
                class_info=self.class_info
            )


class ExamVisibilityTest(TestCase):
    """考试可见性控制测试"""

    def setUp(self):
        """创建测试数据"""
        self.teacher = User.objects.create_user(
            username='teacher3',
            password='pass123',
            role='teacher'
        )
        self.student1 = User.objects.create_user(
            username='student3',
            password='pass123',
            role='student'
        )
        self.student2 = User.objects.create_user(
            username='student4',
            password='pass123',
            role='student'
        )

        # 创建两个班级
        self.class1 = ClassInfo.objects.create(
            name='班级A',
            teacher=self.teacher
        )
        self.class2 = ClassInfo.objects.create(
            name='班级B',
            teacher=self.teacher
        )

        # 将学生加入不同班级
        StudentClassRelation.objects.create(
            student=self.student1,
            class_info=self.class1
        )
        StudentClassRelation.objects.create(
            student=self.student2,
            class_info=self.class2
        )

        # 创建考试
        now = timezone.now()
        self.exam_public = Exam.objects.create(
            title='公开考试',
            created_by=self.teacher,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
            visibility='public'
        )
        self.exam_class_specific = Exam.objects.create(
            title='指定班级考试',
            created_by=self.teacher,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
            visibility='class_specific'
        )
        self.exam_class_specific.allowed_classes.add(self.class1)

    def test_public_exam_visible_to_all(self):
        """测试公开考试对所有学生可见"""
        self.assertTrue(self.exam_public.is_visible_to_student(self.student1))
        self.assertTrue(self.exam_public.is_visible_to_student(self.student2))

    def test_class_specific_exam_visible_only_to_allowed(self):
        """测试指定班级考试只对允许的学生可见"""
        # student1 在班级A，应该可以看到
        self.assertTrue(self.exam_class_specific.is_visible_to_student(self.student1))

        # student2 不在班级A，不应该看到
        self.assertFalse(self.exam_class_specific.is_visible_to_student(self.student2))

    def test_student_in_multiple_classes(self):
        """测试学生同时属于多个班级的场景"""
        # 将student2也加入班级A
        StudentClassRelation.objects.create(
            student=self.student2,
            class_info=self.class1
        )
        # 现在student2应该也能看到考试了
        self.assertTrue(self.exam_class_specific.is_visible_to_student(self.student2))

    def test_exam_with_no_allowed_classes(self):
        """测试没有指定允许班级的考试"""
        exam_no_classes = Exam.objects.create(
            title='无班级考试',
            created_by=self.teacher,
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=1),
            visibility='class_specific'
        )
        # 没有指定任何班级，所有学生都应该看不到
        self.assertFalse(exam_no_classes.is_visible_to_student(self.student1))
        self.assertFalse(exam_no_classes.is_visible_to_student(self.student2))


class ClassManagementAPITest(TestCase):
    """班级管理API测试"""

    def setUp(self):
        """设置测试客户端和数据"""
        self.client = Client()
        self.teacher = User.objects.create_user(
            username='api_teacher',
            password='pass123',
            role='teacher'
        )
        self.student = User.objects.create_user(
            username='api_student',
            password='pass123',
            role='student'
        )
        self.client.login(username='api_teacher', password='pass123')

    def test_create_class_api(self):
        """测试创建班级API"""
        response = self.client.post(
            '/teacher/classes/create/',
            data=json.dumps({
                'name': '新班级',
                'description': '测试描述'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['class_name'], '新班级')

        # 验证数据库中已创建
        self.assertTrue(ClassInfo.objects.filter(name='新班级').exists())

    def test_create_class_without_name(self):
        """测试创建没有名称的班级（应失败）"""
        response = self.client.post(
            '/teacher/classes/create/',
            data=json.dumps({}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_update_class_api(self):
        """测试更新班级API"""
        class_info = ClassInfo.objects.create(
            name='原始名称',
            teacher=self.teacher
        )
        response = self.client.post(
            f'/teacher/classes/{class_info.id}/update/',
            data=json.dumps({
                'name': '更新后的名称',
                'description': '更新描述'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])

        # 验证数据库已更新
        class_info.refresh_from_db()
        self.assertEqual(class_info.name, '更新后的名称')

    def test_delete_class_api(self):
        """测试删除班级API"""
        class_info = ClassInfo.objects.create(
            name='待删除班级',
            teacher=self.teacher
        )
        response = self.client.post(
            f'/teacher/classes/{class_info.id}/delete/'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])

        # 验证数据库已删除
        self.assertFalse(ClassInfo.objects.filter(id=class_info.id).exists())


class StudentClassManagementTest(TestCase):
    """学生加入/退出班级API测试"""

    def setUp(self):
        """设置测试客户端和数据"""
        self.client = Client()
        self.teacher = User.objects.create_user(
            username='class_teacher',
            password='pass123',
            role='teacher'
        )
        self.student1 = User.objects.create_user(
            username='class_student1',
            password='pass123',
            role='student'
        )
        self.student2 = User.objects.create_user(
            username='class_student2',
            password='pass123',
            role='student'
        )
        self.class_info = ClassInfo.objects.create(
            name='测试班级',
            teacher=self.teacher
        )
        self.client.login(username='class_teacher', password='pass123')

    def test_add_single_student(self):
        """测试添加单个学生到班级"""
        response = self.client.post(
            f'/teacher/api/classes/{self.class_info.id}/add-student/',
            data=json.dumps({'student_id': self.student1.id}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])

        # 验证关联已创建
        self.assertTrue(StudentClassRelation.objects.filter(
            student=self.student1,
            class_info=self.class_info
        ).exists())

    def test_add_duplicate_student(self):
        """测试添加重复学生（应失败）"""
        # 先添加一次
        StudentClassRelation.objects.create(
            student=self.student1,
            class_info=self.class_info
        )
        # 再添加应该失败
        response = self.client.post(
            f'/teacher/api/classes/{self.class_info.id}/add-student/',
            data=json.dumps({'student_id': self.student1.id}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_batch_add_students(self):
        """测试批量添加学生"""
        response = self.client.post(
            f'/teacher/api/classes/{self.class_info.id}/batch-add-students/',
            data=json.dumps({
                'student_ids': [self.student1.id, self.student2.id]
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['added_count'], 2)

    def test_remove_student_from_class(self):
        """测试从班级移除学生"""
        # 先添加学生
        relation = StudentClassRelation.objects.create(
            student=self.student1,
            class_info=self.class_info
        )
        # 移除学生
        response = self.client.post(
            f'/teacher/api/classes/{self.class_info.id}/remove-student/',
            data=json.dumps({'student_id': self.student1.id}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])

        # 验证关联已删除
        self.assertFalse(StudentClassRelation.objects.filter(
            student=self.student1,
            class_info=self.class_info
        ).exists())


class EdgeCaseTest(TestCase):
    """边界条件测试"""

    def setUp(self):
        """创建测试数据"""
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

    def test_empty_class_has_zero_students(self):
        """测试空班级学生数为0"""
        empty_class = ClassInfo.objects.create(
            name='空班级',
            teacher=self.teacher
        )
        self.assertEqual(empty_class.get_student_count(), 0)

    def test_student_in_many_classes(self):
        """测试学生属于多个班级（最多10个）"""
        classes = []
        for i in range(10):
            cls = ClassInfo.objects.create(
                name=f'班级{i}',
                teacher=self.teacher
            )
            classes.append(cls)
            StudentClassRelation.objects.create(
                student=self.student,
                class_info=cls
            )

        # 创建一个对所有这些班级都可见的考试
        now = timezone.now()
        exam = Exam.objects.create(
            title='多班级考试',
            created_by=self.teacher,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
            visibility='class_specific'
        )
        exam.allowed_classes.set(classes)

        # 学生应该能看到这个考试
        self.assertTrue(exam.is_visible_to_student(self.student))

    def test_exam_visibility_after_class_removal(self):
        """测试从允许列表移除班级后，该班级学生无法看到考试"""
        class1 = ClassInfo.objects.create(name='班级X', teacher=self.teacher)
        class2 = ClassInfo.objects.create(name='班级Y', teacher=self.teacher)

        StudentClassRelation.objects.create(student=self.student, class_info=class1)
        StudentClassRelation.objects.create(student=self.student, class_info=class2)

        now = timezone.now()
        exam = Exam.objects.create(
            title='动态考试',
            created_by=self.teacher,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
            visibility='class_specific'
        )
        exam.allowed_classes.add(class1, class2)

        # 初始状态：学生可以看到
        self.assertTrue(exam.is_visible_to_student(self.student))

        # 移除班级1
        exam.allowed_classes.remove(class1)

        # 学生仍然可以通过班级2看到
        self.assertTrue(exam.is_visible_to_student(self.student))

        # 移除班级2
        exam.allowed_classes.remove(class2)

        # 现在学生看不到了
        self.assertFalse(exam.is_visible_to_student(self.student))


class PerformanceTest(TestCase):
    """性能测试基础用例"""

    def setUp(self):
        """创建大量测试数据"""
        self.teacher = User.objects.create_user(
            username='perf_teacher',
            password='pass123',
            role='teacher'
        )
        self.students = []
        for i in range(100):  # 创建100个学生
            student = User.objects.create_user(
                username=f'perf_student_{i}',
                password='pass123',
                role='student'
            )
            self.students.append(student)

    def test_large_class_performance(self):
        """测试大班级场景下的性能"""
        large_class = ClassInfo.objects.create(
            name='大班级',
            teacher=self.teacher
        )

        # 批量添加100个学生
        relations = [
            StudentClassRelation(student=s, class_info=large_class)
            for s in self.students
        ]
        StudentClassRelation.objects.bulk_create(relations)

        # 测试查询性能
        import time
        start_time = time.time()

        count = large_class.get_student_count()

        elapsed = time.time() - start_time

        self.assertEqual(count, 100)
        self.assertLess(elapsed, 1.0)  # 查询应该在1秒内完成

    def test_exam_visibility_check_with_many_classes(self):
        """测试多班级场景下的可见性检查性能"""
        classes = []
        for i in range(20):  # 创建20个班级
            cls = ClassInfo.objects.create(
                name=f'perf_class_{i}',
                teacher=self.teacher
            )
            classes.append(cls)
            # 每个班级加5个学生
            for j in range(i * 5, (i + 1) * 5):
                if j < len(self.students):
                    StudentClassRelation.objects.create(
                        student=self.students[j],
                        class_info=cls
                    )

        # 让第一个学生属于前10个班级
        target_student = self.students[0]
        for cls in classes[:10]:
            if not StudentClassRelation.objects.filter(
                student=target_student,
                class_info=cls
            ).exists():
                StudentClassRelation.objects.create(
                    student=target_student,
                    class_info=cls
                )

        # 创建对这10个班级可见的考试
        now = timezone.now()
        exam = Exam.objects.create(
            title='性能测试考试',
            created_by=self.teacher,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
            visibility='class_specific'
        )
        exam.allowed_classes.set(classes[:10])

        # 测试可见性检查性能
        import time
        start_time = time.time()

        is_visible = exam.is_visible_to_student(target_student)

        elapsed = time.time() - start_time

        self.assertTrue(is_visible)
        self.assertLess(elapsed, 0.5)  # 检查应该在0.5秒内完成
