class BusinessError(Exception):
    """Base exception for all business logic errors."""

    default_message = "业务错误"
    default_code = 400

    def __init__(self, message: str | None = None, code: int | None = None):
        self.message = message or self.default_message
        self.code = code or self.default_code
        super().__init__(self.message)


class AuthenticationError(BusinessError):
    """Raised when authentication fails."""
    default_message = "认证失败"
    default_code = 401


class PermissionDeniedError(BusinessError):
    """Raised when a user lacks permission for an action."""
    default_message = "权限不足"
    default_code = 403


class NotFoundError(BusinessError):
    """Raised when a requested resource is not found."""
    default_message = "资源不存在"
    default_code = 404


class ValidationError(BusinessError):
    """Raised when input data validation fails."""
    default_message = "数据验证失败"
    default_code = 400


class RateLimitError(BusinessError):
    """Raised when rate limit is exceeded."""
    default_message = "请求过于频繁，请稍后再试"
    default_code = 429


class ExamNotStartedError(BusinessError):
    """Raised when attempting to access an exam that hasn't started."""
    default_message = "考试尚未开始"
    default_code = 400


class ExamFinishedError(BusinessError):
    """Raised when attempting to submit to a finished exam."""
    default_message = "考试已结束"
    default_code = 400


class DuplicateSubmissionError(BusinessError):
    """Raised when a student tries to submit an exam twice."""
    default_message = "请勿重复提交"
    default_code = 400
