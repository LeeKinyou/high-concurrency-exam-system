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
    path("exams/<int:exam_id>/audit/", teacher_views.audit_logs, name="audit_logs"),
    path("questions/", teacher_views.question_list, name="question_list"),
    path("questions/create/", teacher_views.question_create, name="question_create"),
    path("questions/<int:question_id>/delete/", teacher_views.question_delete, name="question_delete"),
    path("questions/<int:question_id>/link-exam/", teacher_views.question_link_exam, name="question_link_exam"),
    path("api/questions/import/", teacher_views.question_import, name="question_import"),
    path("api/questions/sample/", teacher_views.question_sample_excel, name="question_sample"),
    path("classes/", teacher_views.class_list, name="class_list"),
    path("classes/create/", teacher_views.class_create, name="class_create"),
    path("classes/<int:class_id>/edit/", teacher_views.class_edit, name="class_edit"),
    path("classes/<int:class_id>/delete/", teacher_views.class_delete, name="class_delete"),
    path("classes/<int:class_id>/add-student/", teacher_views.class_add_student, name="class_add_student"),
    path("classes/<int:class_id>/remove-student/<int:student_id>/", teacher_views.class_remove_student, name="class_remove_student"),
    path("classes/<int:class_id>/import-students/", teacher_views.class_import_students, name="class_import_students"),
    path("api/students/search/", teacher_views.student_search_api, name="student_search_api"),
    path("scores/", teacher_views.score_list, name="score_list"),
    path("scores/<int:exam_id>/export/", teacher_views.score_export, name="score_export"),
    path("students/", teacher_views.student_list, name="student_list"),
    path("students/upload/", teacher_views.student_upload, name="student_upload"),
]
