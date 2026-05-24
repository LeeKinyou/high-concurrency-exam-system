import logging
import traceback

from django.http import JsonResponse

from core.exceptions import BusinessError

logger = logging.getLogger(__name__)


class ExceptionHandlerMiddleware:
    """Catch unhandled exceptions and return structured JSON responses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if isinstance(exception, BusinessError):
            return JsonResponse(
                {"code": exception.code, "message": exception.message, "data": None},
                status=exception.code,
            )

        logger.error(
            "Unhandled exception: %s\n%s",
            str(exception),
            traceback.format_exc(),
        )
        return JsonResponse(
            {"code": 500, "message": "服务器内部错误", "data": None},
            status=500,
        )
