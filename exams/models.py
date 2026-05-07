from django.db import models
from django.conf import settings


class ClassInfo(models.Model):
    """
    班级信息表
    支持教师创建和管理多个班级
    """
    name = models.CharField(max_length=100, verbose_name='班级名称')
    description = models.TextField(blank=True, verbose_name='班级描述')
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='managed_classes',
        verbose_name='班主任'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')

    class Meta:
        verbose_name = '班级'
        verbose_name_plural = '班级'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['teacher', '-created_at']),
            models.Index(fields=['name']),
        ]
        unique_together = ['teacher', 'name']  # 同一教师下班级名唯一

    def __str__(self):
        return self.name

    def get_student_count(self):
        """获取班级学生数量"""
        return self.students.count()


class StudentClassRelation(models.Model):
    """
    学生-班级关联表
    支持学生同时属于多个班级（多对多关系）
    """
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='class_relations',
        verbose_name='学生'
    )
    class_info = models.ForeignKey(
        ClassInfo,
        on_delete=models.CASCADE,
        related_name='students',
        verbose_name='班级'
    )
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name='加入时间')
    is_active = models.BooleanField(default=True, verbose_name='是否有效')

    class Meta:
        verbose_name = '学生班级关联'
        verbose_name_plural = '学生班级关联'
        unique_together = ['student', 'class_info']  # 防止重复加入
        indexes = [
            models.Index(fields=['student']),
            models.Index(fields=['class_info']),
        ]

    def __str__(self):
        return f"{self.student.username} - {self.class_info.name}"


class Exam(models.Model):
    """
    考试模型
    包含考试的基本信息和时间控制
    支持按班级设置可见性
    """
    VISIBILITY_CHOICES = (
        ('public', '全局可见'),
        ('class_specific', '指定班级可见'),
    )

    title = models.CharField(max_length=100, verbose_name='考试名称')
    description = models.TextField(blank=True, verbose_name='考试描述')
    start_time = models.DateTimeField(verbose_name='开始时间')
    end_time = models.DateTimeField(verbose_name='结束时间')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_exams',
        verbose_name='创建者'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    max_score = models.IntegerField(default=100, verbose_name='满分')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')

    # 班级可见性控制
    visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default='class_specific',
        verbose_name='可见性'
    )
    allowed_classes = models.ManyToManyField(
        ClassInfo,
        blank=True,
        related_name='exams',
        verbose_name='允许访问的班级'
    )
    
    class Meta:
        verbose_name = '考试'
        verbose_name_plural = '考试'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['start_time', 'end_time']),
        ]
    
    def __str__(self):
        return self.title
    
    def is_ongoing(self):
        """考试是否正在进行"""
        from django.utils import timezone
        now = timezone.now()
        return self.start_time <= now <= self.end_time
    
    def is_not_started(self):
        """考试是否未开始"""
        from django.utils import timezone
        return timezone.now() < self.start_time
    
    def is_over(self):
        """考试是否已结束"""
        from django.utils import timezone
        return timezone.now() > self.end_time

    def is_visible_to_student(self, student):
        """
        检查学生是否有权访问该考试
        根据可见性设置判断：
        - public: 所有学生都可以访问
        - class_specific: 只有指定班级的学生可以访问
        """
        if self.visibility == 'public':
            return True

        # 检查学生是否属于允许的班级
        student_class_ids = StudentClassRelation.objects.filter(
            student=student,
            is_active=True
        ).values_list('class_info_id', flat=True)

        return self.allowed_classes.filter(id__in=student_class_ids).exists()


class Question(models.Model):
    """
    题目模型（独立题库）
    支持选择题和填空题两种题型
    题目独立于考试存在，可被多个考试复用
    """
    QUESTION_TYPE_CHOICES = (
        ('choice', '选择题'),
        ('blank', '填空题'),
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_questions',
        verbose_name='创建者'
    )
    question_type = models.CharField(
        max_length=10,
        choices=QUESTION_TYPE_CHOICES,
        verbose_name='题型'
    )
    question_text = models.TextField(verbose_name='题干')
    option_a = models.CharField(max_length=200, blank=True, verbose_name='选项 A')
    option_b = models.CharField(max_length=200, blank=True, verbose_name='选项 B')
    option_c = models.CharField(max_length=200, blank=True, verbose_name='选项 C')
    option_d = models.CharField(max_length=200, blank=True, verbose_name='选项 D')
    answer = models.CharField(max_length=100, verbose_name='正确答案')
    score = models.IntegerField(default=5, verbose_name='默认分值')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '题目'
        verbose_name_plural = '题目'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_by', '-created_at']),
        ]
    
    def __str__(self):
        return f"[{self.get_question_type_display()}] {self.question_text[:30]}"
    
    def clean(self):
        """模型验证"""
        from django.core.exceptions import ValidationError
        if self.question_type == 'choice':
            if not all([self.option_a, self.option_b]):
                raise ValidationError('选择题必须至少包含选项 A 和 B')
    
    def get_options(self):
        """获取所有选项"""
        options = []
        if self.option_a:
            options.append(('A', self.option_a))
        if self.option_b:
            options.append(('B', self.option_b))
        if self.option_c:
            options.append(('C', self.option_c))
        if self.option_d:
            options.append(('D', self.option_d))
        return options


class ExamQuestion(models.Model):
    """
    考试 - 题目关联表（多对多关系）
    用于解耦考试和题目的关系，支持题目复用
    """
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='exam_questions',
        verbose_name='考试'
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='exam_instances',
        verbose_name='题目'
    )
    score = models.IntegerField(default=5, verbose_name='本题分值')
    order = models.IntegerField(default=0, verbose_name='题目顺序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='添加时间')
    
    class Meta:
        verbose_name = '考试题目关联'
        verbose_name_plural = '考试题目关联'
        ordering = ['order', 'id']
        unique_together = ['exam', 'question']  # 同一考试不能添加相同题目
        indexes = [
            models.Index(fields=['exam', 'order']),
            models.Index(fields=['question']),
        ]
    
    def __str__(self):
        return f"{self.exam.title} - {self.question.question_text[:30]}"


class ExamRecord(models.Model):
    """
    考试记录模型
    记录学生的答卷情况和成绩
    """
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='exam_records',
        verbose_name='学生'
    )
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='records',
        verbose_name='考试'
    )
    answer_sheet = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='答题草稿'
    )
    final_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='最终得分'
    )
    is_submitted = models.BooleanField(default=False, verbose_name='是否交卷')
    submitted_at = models.DateTimeField(blank=True, null=True, verbose_name='交卷时间')
    submission_method = models.CharField(
        max_length=10,
        choices=[('manual', '手动提交'), ('auto', '自动提交')],
        default='manual',
        verbose_name='提交方式'
    )
    grading_details = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='判题详情'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '考试记录'
        verbose_name_plural = '考试记录'
        ordering = ['-created_at']
        unique_together = ['student', 'exam']
        indexes = [
            models.Index(fields=['student', 'is_submitted']),
            models.Index(fields=['exam', 'is_submitted']),
        ]
    
    def __str__(self):
        return f"{self.student.username} - {self.exam.title}"
    
    def get_answer(self, question_id):
        """获取某题的答案"""
        return self.answer_sheet.get(str(question_id), '')
    
    def set_answer(self, question_id, answer):
        """设置某题的答案"""
        self.answer_sheet[str(question_id)] = answer
        self.save()
