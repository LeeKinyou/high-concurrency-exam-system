import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from accounts.decorators import student_required, teacher_required
from accounts.models import User
from core.constants import UserRole


@pytest.mark.django_db
class TestTeacherRequired:
    def test_teacher_passes(self, teacher):
        factory = RequestFactory()

        @teacher_required
        def view(request):
            return HttpResponse("ok")

        request = factory.get("/")
        request.user = teacher
        resp = view(request)
        assert resp.status_code == 200

    def test_student_redirected(self, student):
        factory = RequestFactory()

        @teacher_required
        def view(request):
            return HttpResponse("ok")

        request = factory.get("/")
        request.user = student
        resp = view(request)
        assert resp.status_code == 302

    def test_anonymous_redirected(self):
        from django.contrib.auth.models import AnonymousUser
        factory = RequestFactory()

        @teacher_required
        def view(request):
            return HttpResponse("ok")

        request = factory.get("/")
        request.user = AnonymousUser()
        resp = view(request)
        assert resp.status_code == 302


@pytest.mark.django_db
class TestStudentRequired:
    def test_student_passes(self, student):
        factory = RequestFactory()

        @student_required
        def view(request):
            return HttpResponse("ok")

        request = factory.get("/")
        request.user = student
        resp = view(request)
        assert resp.status_code == 200

    def test_teacher_redirected(self, teacher):
        factory = RequestFactory()

        @student_required
        def view(request):
            return HttpResponse("ok")

        request = factory.get("/")
        request.user = teacher
        resp = view(request)
        assert resp.status_code == 302
