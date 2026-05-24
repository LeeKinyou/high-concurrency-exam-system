from functools import wraps

from django.shortcuts import redirect

from core.constants import UserRole

from .models import ExamRecord


def exam_access_required(view_func):
    """验证学生有权访问考试答题页面"""

    @wraps(view_func)
    def wrapper(request, exam_id, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("/accounts/login/")
        if request.user.role != UserRole.STUDENT:
            return redirect("/accounts/login/")
        return view_func(request, exam_id, *args, **kwargs)

    return wrapper
