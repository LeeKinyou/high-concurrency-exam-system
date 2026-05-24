from io import BytesIO
from unittest.mock import MagicMock

import pytest

from core.exceptions import ValidationError
from core.validators import validate_file_extension, validate_file_size, validate_password_complexity


class TestPasswordComplexityValidator:
    def test_valid_password(self):
        validate_password_complexity("Test@1234")  # Should not raise

    def test_too_short(self):
        with pytest.raises(ValidationError, match="密码长度不能少于8位"):
            validate_password_complexity("T@1a")

    def test_no_uppercase(self):
        with pytest.raises(ValidationError, match="大写字母"):
            validate_password_complexity("test@1234")

    def test_no_lowercase(self):
        with pytest.raises(ValidationError, match="小写字母"):
            validate_password_complexity("TEST@1234")

    def test_no_digit(self):
        with pytest.raises(ValidationError, match="数字"):
            validate_password_complexity("Test@abcd")

    def test_no_special_char(self):
        with pytest.raises(ValidationError, match="特殊字符"):
            validate_password_complexity("Test1234")


class TestFileSizeValidator:
    def test_valid_size(self):
        f = MagicMock()
        f.size = 1024 * 1024  # 1MB
        validate_file_size(f)  # Should not raise

    def test_too_large(self):
        f = MagicMock()
        f.size = 20 * 1024 * 1024  # 20MB
        with pytest.raises(ValidationError, match="文件大小不能超过"):
            validate_file_size(f)

    def test_custom_limit(self):
        f = MagicMock()
        f.size = 3 * 1024 * 1024  # 3MB
        with pytest.raises(ValidationError, match="文件大小不能超过2MB"):
            validate_file_size(f, max_mb=2)


class TestFileExtensionValidator:
    def test_valid_xlsx(self):
        f = MagicMock()
        f.name = "students.xlsx"
        validate_file_extension(f)  # Should not raise

    def test_valid_xls(self):
        f = MagicMock()
        f.name = "data.xls"
        validate_file_extension(f)

    def test_invalid_extension(self):
        f = MagicMock()
        f.name = "file.pdf"
        with pytest.raises(ValidationError, match="不支持的文件格式"):
            validate_file_extension(f)

    def test_custom_extensions(self):
        f = MagicMock()
        f.name = "image.png"
        validate_file_extension(f, allowed_extensions=[".png", ".jpg"])
