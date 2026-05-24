import json

import pytest
from django.http import HttpRequest, JsonResponse

from core.exceptions import AuthenticationError, BusinessError, PermissionDeniedError
from core.middleware import ExceptionHandlerMiddleware


class TestExceptionHandlerMiddleware:
    def _make_middleware(self):
        def dummy_get_response(request):
            return JsonResponse({"ok": True})

        return ExceptionHandlerMiddleware(dummy_get_response)

    def test_business_error(self):
        middleware = self._make_middleware()
        request = HttpRequest()

        response = middleware.process_exception(request, BusinessError(message="测试错误"))
        assert response.status_code == 400
        data = json.loads(response.content)
        assert data["code"] == 400
        assert data["message"] == "测试错误"

    def test_auth_error(self):
        middleware = self._make_middleware()
        request = HttpRequest()

        response = middleware.process_exception(request, AuthenticationError())
        assert response.status_code == 401

    def test_permission_error(self):
        middleware = self._make_middleware()
        request = HttpRequest()

        response = middleware.process_exception(request, PermissionDeniedError())
        assert response.status_code == 403

    def test_unhandled_exception(self):
        middleware = self._make_middleware()
        request = HttpRequest()

        response = middleware.process_exception(request, ValueError("unexpected"))
        assert response.status_code == 500
        data = json.loads(response.content)
        assert data["code"] == 500
        assert data["message"] == "服务器内部错误"

    def test_normal_request_passes_through(self):
        middleware = self._make_middleware()
        request = HttpRequest()

        response = middleware(request)
        assert response.status_code == 200
