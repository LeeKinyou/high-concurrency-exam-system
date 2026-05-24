import os
import re

from core.constants import ALLOWED_EXCEL_EXTENSIONS, MAX_UPLOAD_FILE_SIZE_MB
from core.exceptions import ValidationError


def validate_password_complexity(password: str) -> None:
    """Validate password meets complexity requirements.

    Rules: at least 8 chars, contains uppercase, lowercase, digit, and special char.
    """
    if len(password) < 8:
        raise ValidationError("密码长度不能少于8位")
    if not re.search(r"[A-Z]", password):
        raise ValidationError("密码必须包含大写字母")
    if not re.search(r"[a-z]", password):
        raise ValidationError("密码必须包含小写字母")
    if not re.search(r"\d", password):
        raise ValidationError("密码必须包含数字")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        raise ValidationError("密码必须包含特殊字符")


def validate_file_size(file, max_mb: int = MAX_UPLOAD_FILE_SIZE_MB) -> None:
    """Validate uploaded file size."""
    if file.size > max_mb * 1024 * 1024:
        raise ValidationError(f"文件大小不能超过{max_mb}MB")


def validate_file_extension(file, allowed_extensions: list[str] | None = None) -> None:
    """Validate uploaded file extension."""
    if allowed_extensions is None:
        allowed_extensions = ALLOWED_EXCEL_EXTENSIONS

    ext = os.path.splitext(file.name)[1].lower()
    if ext not in allowed_extensions:
        raise ValidationError(f"不支持的文件格式，仅支持: {', '.join(allowed_extensions)}")
