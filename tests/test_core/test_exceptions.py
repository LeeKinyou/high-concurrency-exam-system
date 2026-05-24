import pytest

from core.exceptions import (
    AuthenticationError,
    BusinessError,
    DuplicateSubmissionError,
    ExamFinishedError,
    ExamNotStartedError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ValidationError,
)


class TestBusinessError:
    def test_default_message(self):
        err = BusinessError()
        assert err.message == "业务错误"
        assert err.code == 400

    def test_custom_message(self):
        err = BusinessError(message="自定义消息", code=422)
        assert err.message == "自定义消息"
        assert err.code == 422

    def test_is_exception(self):
        assert issubclass(BusinessError, Exception)


class TestSubExceptions:
    @pytest.mark.parametrize(
        "exc_class,expected_msg,expected_code",
        [
            (AuthenticationError, "认证失败", 401),
            (PermissionDeniedError, "权限不足", 403),
            (NotFoundError, "资源不存在", 404),
            (ValidationError, "数据验证失败", 400),
            (RateLimitError, "请求过于频繁，请稍后再试", 429),
            (ExamNotStartedError, "考试尚未开始", 400),
            (ExamFinishedError, "考试已结束", 400),
            (DuplicateSubmissionError, "请勿重复提交", 400),
        ],
    )
    def test_default_values(self, exc_class, expected_msg, expected_code):
        err = exc_class()
        assert err.message == expected_msg
        assert err.code == expected_code
        assert isinstance(err, BusinessError)

    def test_custom_message_override(self):
        err = ExamNotStartedError(message="考试将在10分钟后开始")
        assert err.message == "考试将在10分钟后开始"
        assert err.code == 400
