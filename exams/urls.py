from django.urls import path
from . import views

app_name = 'exams'

urlpatterns = [
    path('', views.exam_list, name='exam_list'),
    path('<int:exam_id>/take/', views.exam_take, name='exam_take'),
    path('<int:exam_id>/save-answer/', views.save_answer, name='save_answer'),
    path('<int:exam_id>/submit/', views.submit_exam, name='submit_exam'),
    path('<int:exam_id>/result/', views.exam_result, name='exam_result'),
    path('<int:exam_id>/', views.exam_detail, name='exam_detail'),
    
    # Excel 题目导入功能
    path('excel/upload/', views.excel_upload, name='excel_upload'),
    path('excel/parse/', views.excel_parse, name='excel_parse'),
    path('excel/import/', views.excel_import_confirm, name='excel_import_confirm'),
    path('questions/import/', views.question_import_list, name='question_import_list'),
]
