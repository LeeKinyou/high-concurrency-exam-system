import re
from unittest.mock import MagicMock

import pytest
from django.utils import timezone

from core.utils import format_datetime, generate_random_password, get_client_ip


class TestGetClientIp:
    def test_remote_addr(self):
        request = MagicMock()
        request.META = {"REMOTE_ADDR": "127.0.0.1"}
        assert get_client_ip(request) == "127.0.0.1"

    def test_x_forwarded_for(self):
        request = MagicMock()
        request.META = {
            "HTTP_X_FORWARDED_FOR": "10.0.0.1, 10.0.0.2",
            "REMOTE_ADDR": "127.0.0.1",
        }
        assert get_client_ip(request) == "10.0.0.1"

    def test_no_ip(self):
        request = MagicMock()
        request.META = {}
        assert get_client_ip(request) == ""


class TestGenerateRandomPassword:
    def test_default_length(self):
        pwd = generate_random_password()
        assert len(pwd) == 12

    def test_custom_length(self):
        pwd = generate_random_password(16)
        assert len(pwd) == 16

    def test_minimum_length(self):
        pwd = generate_random_password(4)
        assert len(pwd) == 8

    def test_complexity(self):
        pwd = generate_random_password()
        assert re.search(r"[A-Z]", pwd), "Missing uppercase"
        assert re.search(r"[a-z]", pwd), "Missing lowercase"
        assert re.search(r"\d", pwd), "Missing digit"
        assert re.search(r"[!@#$%^&*]", pwd), "Missing special char"

    def test_uniqueness(self):
        passwords = {generate_random_password() for _ in range(10)}
        assert len(passwords) == 10


class TestFormatDatetime:
    def test_none(self):
        assert format_datetime(None) == ""

    def test_naive_datetime(self):
        from datetime import datetime

        dt = datetime(2026, 5, 24, 14, 30, 0)
        assert format_datetime(dt) == "2026-05-24 14:30:00"

    def test_aware_datetime(self):
        dt = timezone.now()
        result = format_datetime(dt)
        assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", result)

    def test_custom_format(self):
        from datetime import datetime

        dt = datetime(2026, 5, 24, 14, 30, 0)
        assert format_datetime(dt, "%Y/%m/%d") == "2026/05/24"
