import json

from django.contrib.auth import login, logout
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from core.constants import UserRole
from core.responses import error_response, success_response
from core.utils import get_client_ip

from .forms import ChangePasswordForm, LoginForm
from .services import AuthService


def student_login(request):
    if request.user.is_authenticated and request.user.is_student:
        return redirect("/exams/")

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            try:
                user = AuthService.authenticate_user(
                    request,
                    form.cleaned_data["username"],
                    form.cleaned_data["password"],
                    role=UserRole.STUDENT,
                )
                login(request, user)
                if user.must_change_password:
                    return redirect("/accounts/change-password/")
                return redirect("/exams/")
            except Exception as e:
                form.add_error(None, str(e))
    else:
        form = LoginForm()

    return render(request, "accounts/student_login.html", {"form": form})


def teacher_login(request):
    if request.user.is_authenticated and request.user.is_teacher:
        return redirect("/teacher/")

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            try:
                user = AuthService.authenticate_user(
                    request,
                    form.cleaned_data["username"],
                    form.cleaned_data["password"],
                    role=UserRole.TEACHER,
                )
                login(request, user)
                if user.must_change_password:
                    return redirect("/accounts/change-password/")
                return redirect("/teacher/")
            except Exception as e:
                form.add_error(None, str(e))
    else:
        form = LoginForm()

    return render(request, "accounts/teacher_login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("/accounts/login/")


def change_password(request):
    if not request.user.is_authenticated:
        return redirect("/accounts/login/")

    if request.method == "POST":
        form = ChangePasswordForm(request.POST)
        if form.is_valid():
            try:
                AuthService.change_password(
                    request.user,
                    form.cleaned_data["old_password"],
                    form.cleaned_data["new_password"],
                )
                # Redirect based on role
                if request.user.is_teacher:
                    return redirect("/teacher/")
                return redirect("/exams/")
            except Exception as e:
                form.add_error(None, str(e))
    else:
        form = ChangePasswordForm()

    return render(request, "accounts/change_password.html", {"form": form})


@require_POST
def upload_students(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return error_response(403, "权限不足")

    file = request.FILES.get("file")
    if not file:
        return error_response(400, "请上传文件")

    try:
        result = AuthService.import_students_from_excel(file)
        return success_response(
            data={
                "success_count": result["success_count"],
                "errors": result["errors"],
            },
            message=f"成功导入{result['success_count']}名学生",
        )
    except Exception as e:
        return error_response(400, str(e))
