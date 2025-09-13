# services/qrcode_gen.py
import io
import segno

def make_qr_png_bytes(text: str, scale: int = 6, border: int = 2) -> bytes:
    """
    از رشتهٔ ورودی (مثلاً vless://...) QR می‌سازد و PNG برمی‌گرداند.
    """
    q = segno.make(text, micro=False)
    buf = io.BytesIO()
    q.save(buf, kind="png", scale=scale, border=border)
    return buf.getvalue()
