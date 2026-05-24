from django.urls import path

from . import views

app_name = "examination"

urlpatterns = [
    path("", views.exam_list, name="exam_list"),
    path("<int:exam_id>/", views.exam_detail, name="exam_detail"),
    path("<int:exam_id>/take/", views.exam_take, name="exam_take"),
    path("<int:exam_id>/submit/", views.exam_submit, name="exam_submit"),
    path("<int:exam_id>/save-answer/", views.exam_save_answer, name="exam_save_answer"),
    path("<int:exam_id>/result/", views.exam_result, name="exam_result"),
    path("<int:exam_id>/enter/", views.exam_enter, name="exam_enter"),
    path("<int:exam_id>/log-action/", views.exam_log_action, name="exam_log_action"),
    path("notifications/<int:notification_id>/read/", views.notification_mark_read, name="notification_mark_read"),
    path("notifications/read-all/", views.notification_mark_all_read, name="notification_mark_all_read"),
]
