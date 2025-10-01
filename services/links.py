# services/links.py
from urllib.parse import quote

def vless_ws_link(uuid: str, host: str, port: int, path: str, security: str, tag: str) -> str:
    """
    خروجی نمونه:
    vless://<uuid>@example.com:8081?type=ws&path=/ws8081&encryption=none&security=none#tag
    """
    # تگ را URL-encode کن تا کاراکترهای خاص خراب نکنند
    safe_tag = quote(tag, safe='')
    # path باید با / شروع شود
    if not path.startswith("/"):
        path = "/" + path
    return (
        f"vless://{uuid}@{host}:{int(port)}"
        f"?type=ws&path={path}&encryption=none&security={security}"
        f"#{safe_tag}"
    )
