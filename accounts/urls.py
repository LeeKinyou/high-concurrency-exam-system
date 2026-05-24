from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.student_login, name="student_login"),
    path("teacher/login/", views.teacher_login, name="teacher_login"),
    path("logout/", views.logout_view, name="logout"),
    path("change-password/", views.change_password, name="change_password"),
    path("upload-students/", views.upload_students, name="upload_students"),
]
