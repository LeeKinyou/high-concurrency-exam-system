from django.contrib import admin
from .models import Exam, Question, ExamRecord, ExamQuestion, ClassInfo, StudentClassRelation


class StudentClassRelationInline(admin.TabularInline):
    """
    学生-班级关联内联编辑器
    用于在班级管理页面直接管理学生成员
    """
    model = StudentClassRelation
    extra = 1
    fields = ['student', 'is_active']
    autocomplete_fields = ['student']


@admin.register(ClassInfo)
class ClassInfoAdmin(admin.ModelAdmin):
    """
    班级管理后台
    """
    list_display = [
        'name',
        'teacher',
        'student_count_display',
        'is_active',
        'created_at'
    ]
    list_filter = ['is_active', 'teacher', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [StudentClassRelationInline]
    ordering = ['-created_at']

    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'description', 'teacher', 'is_active')
        }),
        ('元数据', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def student_count_display(self, obj):
        """显示班级学生数量"""
        return obj.get_student_count()
    student_count_display.short_description = '学生数'


@admin.register(StudentClassRelation)
class StudentClassRelationAdmin(admin.ModelAdmin):
    """
    学生-班级关联管理后台
    """
    list_display = [
        'student',
        'class_info',
        'is_active',
        'joined_at'
    ]
    list_filter = ['is_active', 'class_info__teacher', 'joined_at']
    search_fields = ['student__username', 'student__student_id', 'class_info__name']
    readonly_fields = ['joined_at']
    ordering = ['-joined_at']

    def get_queryset(self, request):
        """优化查询"""
        queryset = super().get_queryset(request)
        return queryset.select_related('student', 'class_info')


class ExamQuestionInline(admin.TabularInline):
    """
    考试题目关联内联编辑器
    用于在考试管理页面直接添加/编辑题目关联
    """
    model = ExamQuestion
    extra = 1
    fields = [
        'question',
        'score',
        'order'
    ]
    ordering = ['order']
    autocomplete_fields = ['question']  # 使用自动完成选择已有题目


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    """
    考试管理后台
    支持班级可见性控制
    """
    list_display = [
        'title',
        'created_by',
        'visibility_display',
        'start_time',
        'end_time',
        'max_score',
        'is_active',
        'created_at',
        'is_ongoing'
    ]
    list_filter = ['is_active', 'visibility', 'created_by', 'start_time']
    search_fields = ['title', 'description']
    readonly_fields = ['created_by', 'created_at', 'updated_at']
    inlines = [ExamQuestionInline]
    filter_horizontal = ['allowed_classes']  # 多选框用于选择允许的班级
    ordering = ['-created_at']

    fieldsets = (
        ('基本信息', {
            'fields': ('title', 'description', 'max_score', 'is_active')
        }),
        ('可见性设置', {
            'fields': ('visibility', 'allowed_classes'),
            'description': '设置考试的可见范围：全局可见或仅指定班级可见'
        }),
        ('时间设置', {
            'fields': ('start_time', 'end_time')
        }),
        ('元数据', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        """保存考试时自动设置创建者"""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def is_ongoing(self, obj):
        """显示考试是否正在进行"""
        if obj.is_ongoing():
            return '🟢 进行中'
        elif obj.is_not_started():
            return '🔵 未开始'
        else:
            return '🔴 已结束'
    is_ongoing.short_description = '状态'

    def visibility_display(self, obj):
        """显示考试可见性"""
        if obj.visibility == 'public':
            return '🌐 全局可见'
        else:
            count = obj.allowed_classes.count()
            return f'🎯 指定班级 ({count}个)'
    visibility_display.short_description = '可见性'


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    """
    题目管理后台（独立题库）
    """
    list_display = [
        'id',
        'created_by',
        'question_type',
        'question_text_short',
        'answer',
        'score',
        'created_at'
    ]
    list_filter = ['question_type', 'created_by']
    search_fields = ['question_text', 'answer']
    ordering = ['-created_at']
    
    def question_text_short(self, obj):
        """显示题干前 30 个字符"""
        return obj.question_text[:30] + '...' if len(obj.question_text) > 30 else obj.question_text
    question_text_short.short_description = '题干'


@admin.register(ExamQuestion)
class ExamQuestionAdmin(admin.ModelAdmin):
    """
    考试题目关联管理后台
    """
    list_display = [
        'exam',
        'question',
        'score',
        'order',
        'created_at'
    ]
    list_filter = ['exam', 'question__question_type']
    search_fields = ['exam__title', 'question__question_text']
    ordering = ['exam', 'order']
    autocomplete_fields = ['question']


@admin.register(ExamRecord)
class ExamRecordAdmin(admin.ModelAdmin):
    """
    考试记录管理后台
    """
    list_display = [
        'student',
        'exam',
        'final_score',
        'is_submitted',
        'submitted_at',
        'created_at'
    ]
    list_filter = ['is_submitted', 'exam', 'created_at']
    search_fields = ['student__username', 'student__student_id', 'exam__title']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    def get_queryset(self, request):
        """优化查询，使用 select_related"""
        queryset = super().get_queryset(request)
        return queryset.select_related('student', 'exam')
