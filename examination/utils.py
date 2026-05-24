import io
import logging

import qrcode
from django.conf import settings

logger = logging.getLogger(__name__)


def generate_exam_qrcode(exam_id: int, exam_code: str) -> bytes:
    """生成考试二维码。

    二维码内容为考试入口 URL，学生扫码后可直接进入考试。

    Args:
        exam_id: 考试 ID
        exam_code: 考试码

    Returns:
        PNG 图片字节数据
    """
    base_url = getattr(settings, "SITE_URL", "http://localhost:8000")
    url = f"{base_url}/exams/{exam_id}/enter/?code={exam_code}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()
