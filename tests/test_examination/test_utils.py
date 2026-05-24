import pytest

from examination.utils import generate_exam_qrcode


class TestGenerateExamQrcode:
    def test_generate_qrcode(self):
        qr_data = generate_exam_qrcode(1, "TEST123")
        assert isinstance(qr_data, bytes)
        assert len(qr_data) > 0
        # PNG 文件头
        assert qr_data[:8] == b"\x89PNG\r\n\x1a\n"

    def test_different_exam_different_qr(self):
        qr1 = generate_exam_qrcode(1, "CODE1")
        qr2 = generate_exam_qrcode(2, "CODE2")
        assert qr1 != qr2
