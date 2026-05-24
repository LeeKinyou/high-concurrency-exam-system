import random
import string
from datetime import datetime

from django.utils import timezone


def get_client_ip(request) -> str:
    """Extract client IP from request, respecting X-Forwarded-For header."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def generate_random_password(length: int = 12) -> str:
    """Generate a random password meeting complexity requirements."""
    if length < 8:
        length = 8

    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    # Ensure at least one of each required type
    password = [
        random.choice(string.ascii_uppercase),
        random.choice(string.ascii_lowercase),
        random.choice(string.digits),
        random.choice("!@#$%^&*"),
    ]
    password.extend(random.choice(chars) for _ in range(length - 4))
    random.shuffle(password)
    return "".join(password)


def format_datetime(dt: datetime | None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format a datetime object to string."""
    if dt is None:
        return ""
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    return dt.strftime(fmt)
