from django.urls import path

from . import teacher_views

app_name = "teacher"

urlpatterns = [
    path("", teacher_views.dashboard, name="dashboard"),
    path("exams/", teacher_views.exam_list, name="exam_list"),
    path("exams/create/", teacher_views.exam_create, name="exam_create"),
    path("exams/<int:exam_id>/edit/", teacher_views.exam_edit, name="exam_edit"),
    path("exams/<int:exam_id>/delete/", teacher_views.exam_delete, name="exam_delete"),
    path("exams/<int:exam_id>/qrcode/", teacher_views.exam_qrcode, name="exam_qrcode"),
    path("questions/", teacher_views.question_list, name="question_list"),
    path("api/questions/import/", teacher_views.question_import, name="question_import"),
    path("classes/", teacher_views.class_list, name="class_list"),
    path("scores/", teacher_views.score_list, name="score_list"),
    path("scores/<int:exam_id>/export/", teacher_views.score_export, name="score_export"),
]
