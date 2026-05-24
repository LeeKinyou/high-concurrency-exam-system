from functools import wraps

from django.shortcuts import redirect

from core.constants import UserRole


def _check_role(request, role: str):
    if not request.user.is_authenticated:
        return redirect("/accounts/login/")
    if request.user.role != role:
        return redirect("/accounts/login/")
    return None


def teacher_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        result = _check_role(request, UserRole.TEACHER)
        if result:
            return result
        return view_func(request, *args, **kwargs)

    return wrapper


def student_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        result = _check_role(request, UserRole.STUDENT)
        if result:
            return result
        return view_func(request, *args, **kwargs)

    return wrapper
