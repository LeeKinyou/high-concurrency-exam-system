from django.urls import path
from . import teacher_views
from . import api_views
from . import class_views

app_name = 'teacher'

urlpatterns = [
    # 仪表盘
    path('', teacher_views.dashboard, name='dashboard'),

    # 班级管理
    path('classes/', class_views.class_list, name='class_list'),
    path('classes/create/', class_views.class_create, name='class_create'),
    path('classes/<int:class_id>/', class_views.class_detail, name='class_detail'),
    path('classes/<int:class_id>/update/', class_views.class_update, name='class_update'),
    path('classes/<int:class_id>/delete/', class_views.class_delete, name='class_delete'),
    path('classes/<int:class_id>/students/', class_views.class_students, name='class_students'),
    path('classes/<int:class_id>/stats/', class_views.get_class_stats, name='class_stats'),

    # 考试管理
    path('exams/', teacher_views.exam_list, name='exam_list'),
    path('exams/create/', teacher_views.exam_create, name='exam_create'),
    path('exams/<int:exam_id>/edit/', teacher_views.exam_edit, name='exam_edit'),
    path('exams/<int:exam_id>/stats/', teacher_views.exam_stats, name='exam_stats'),
    path('exams/<int:exam_id>/records/', teacher_views.exam_records, name='exam_records'),
    path('exams/<int:exam_id>/questions/', teacher_views.exam_questions, name='exam_questions'),
    path('exams/<int:exam_id>/questions/existing/', teacher_views.get_existing_questions, name='get_existing_questions'),
    path('exams/<int:exam_id>/questions/add-existing/', teacher_views.add_existing_questions, name='add_existing_questions'),
    path('exams/<int:exam_id>/questions/create/', teacher_views.create_question, name='question_create'),
    path('exams/<int:exam_id>/questions/<int:question_id>/', teacher_views.get_question_detail, name='question_detail'),
    path('exams/<int:exam_id>/questions/<int:question_id>/update/', teacher_views.update_question, name='question_update'),
    path('exams/<int:exam_id>/questions/<int:question_id>/delete/', teacher_views.delete_question, name='question_delete'),
    path('exams/<int:exam_id>/questions/<int:question_id>/order/', teacher_views.update_question_order, name='update_question_order'),
    path('exams/<int:exam_id>/questions/batch-add/', teacher_views.batch_add_questions, name='batch_add_questions'),
    path('exams/<int:exam_id>/delete/', teacher_views.delete_exam, name='exam_delete'),
    
    # 题目管理（独立模块）
    path('questions/', teacher_views.questions, name='questions'),
    path('question-bank/', teacher_views.question_bank, name='question_bank'),
    
    # 二维码管理
    path('qrcode/', teacher_views.qrcode, name='qrcode'),
    
    # 学生管理
    path('students/', teacher_views.students, name='students'),
]

# API 路由（放在前面以确保优先匹配）
api_urlpatterns = [
    # 题目 API
    path('api/questions/', api_views.api_question_list, name='api_question_list'),
    path('api/questions/create/', api_views.api_question_create, name='api_question_create'),
    path('api/questions/<int:question_id>/', api_views.api_question_detail, name='api_question_detail'),
    path('api/questions/<int:question_id>/update/', api_views.api_question_update, name='api_question_update'),
    path('api/questions/<int:question_id>/delete/', api_views.api_question_delete, name='api_question_delete'),
    path('api/questions/batch/', api_views.api_questions_batch, name='api_questions_batch'),
    path('api/questions/import/', api_views.api_questions_import, name='api_questions_import'),
    
    # 成绩 API（必须在 scores 页面路由之前）
    path('api/scores/', api_views.api_scores, name='api_scores'),
    path('api/scores/<int:record_id>/detail/', api_views.api_score_detail, name='api_score_detail'),
    path('api/scores/export/', api_views.export_scores, name='export_scores'),
    
    path('api/generate-qr/', api_views.api_generate_qr, name='api_generate_qr'),
    path('api/qr-stats/<int:exam_id>/', api_views.api_qr_stats, name='api_qr_stats'),
    path('api/students/', api_views.api_students, name='api_students'),
    path('api/students/<int:student_id>/', api_views.api_students, name='api_student_detail'),
    path('api/students/<int:student_id>/reset-password/', api_views.api_reset_password, name='api_reset_password'),
    path('api/students/export/', api_views.export_students, name='export_students'),

    # 班级管理 API
    path('api/classes/<int:class_id>/add-student/', class_views.add_student_to_class, name='api_add_student_to_class'),
    path('api/classes/<int:class_id>/batch-add-students/', class_views.batch_add_students_to_class, name='api_batch_add_students_to_class'),
    path('api/classes/<int:class_id>/remove-student/', class_views.remove_student_from_class, name='api_remove_student_from_class'),
]

# 页面路由（放在 API 路由之后）
page_urlpatterns = [
    # 成绩管理页面
    path('scores/', teacher_views.scores, name='scores'),
]

urlpatterns += api_urlpatterns + page_urlpatterns
