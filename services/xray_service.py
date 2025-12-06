import json
import uuid
import time
import logging
import requests  # استفاده از کتابخانه مطمئن requests
from urllib.parse import urlencode

from config import settings

logger = logging.getLogger(__name__)


class XrayService:
    def __init__(self):
        # آدرس پایه (بدون اسلش آخر)
        self.base_url = settings.PANEL_URL.rstrip("/")
        self.username = settings.PANEL_USERNAME
        self.password = settings.PANEL_PASSWORD
        self.inbound_id = settings.INBOUND_ID

        # استفاده از Session برای مدیریت خودکار کوکی‌ها
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/plain, */*"
        })

    def _login(self) -> bool:
        """ورود به پنل (سینکرون)"""
        url = f"{self.base_url}/login"
        payload = {"username": self.username, "password": self.password}
        try:
            resp = self.session.post(url, data=payload, timeout=10)
            if resp.status_code == 200 and resp.json().get('success'):
                # logger.info("✅ Login successful")
                return True
            else:
                logger.error(f"❌ Login failed: {resp.text}")
        except Exception as e:
            logger.error(f"⚠️ Connection error during login: {e}")
        return False

    def _request(self, method: str, endpoint: str, data: dict = None):
        """ارسال درخواست با مدیریت لاگین"""
        # نکته حیاتی: اضافه کردن /panel به آدرس‌ها طبق تست موفق
        url = f"{self.base_url}/panel{endpoint}"

        # تلاش اول
        try:
            if method == "POST":
                resp = self.session.post(url, data=data)
            else:
                resp = self.session.get(url)

            # اگر کوکی منقضی شده بود (معمولا رداریکت میکنه به لاگین یا 401 میده)
            if "login" in resp.url or resp.status_code in [401, 403]:
                logger.warning("Session expired, re-login...")
                if self._login():
                    # تلاش مجدد
                    if method == "POST":
                        resp = self.session.post(url, data=data)
                    else:
                        resp = self.session.get(url)

            if resp.status_code == 200:
                try:
                    return resp.json()
                except:
                    logger.error(f"Invalid JSON response from {url}")
                    return None
            else:
                logger.error(f"API Error {resp.status_code} on {url}: {resp.text}")
                return None

        except Exception as e:
            # اگر کلا لاگین نبودیم، یه بار لاگین کن و دوباره تلاش کن
            if self._login():
                try:
                    if method == "POST":
                        resp = self.session.post(url, data=data)
                    else:
                        resp = self.session.get(url)
                    return resp.json() if resp.status_code == 200 else None
                except:
                    pass
            logger.error(f"Request Error ({endpoint}): {e}")
            return None

    # نکته: توابع رو async تعریف می‌کنیم تا ساختار بقیه ربات بهم نریزه
    # ولی درونش از requests معمولی استفاده می‌کنیم (چون خیلی سریع انجام میشه مشکلی نیست)
    async def add_client(self, email: str, limit_ip: int = 1, total_gb: int = 0, expire_days: int = 30) -> dict | None:
        """ساخت کاربر جدید"""
        client_uuid = str(uuid.uuid4())

        # تولید SubId رندوم
        import random, string
        sub_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))

        total_bytes = int(total_gb) * 1024 * 1024 * 1024
        expiry_time = int((time.time() + (expire_days * 86400)) * 1000) if expire_days > 0 else 0

        # تنظیمات کلاینت (JSON String)
        client_settings_dict = {
            "clients": [
                {
                    "id": client_uuid,
                    "email": email,
                    "limitIp": limit_ip,
                    "totalGB": total_bytes,
                    "expiryTime": expiry_time,
                    "enable": True,
                    "tgId": "",
                    "subId": sub_id,
                    "flow": "",
                    "reset": 0
                }
            ]
        }

        payload = {
            "id": self.inbound_id,
            "settings": json.dumps(client_settings_dict)
        }

        # ارسال به /api/inbounds/addClient (متد _request خودش /panel رو اضافه میکنه)
        resp = self._request("POST", "/api/inbounds/addClient", data=payload)

        if resp and resp.get("success"):
            logger.info(f"User {email} created successfully.")
            return {
                "uuid": client_uuid,
                "email": email,
                "link": self._generate_vless_link(client_uuid, email)
            }
        else:
            return None

    async def remove_client(self, email: str) -> bool:
        """حذف کاربر"""
        client_info = await self.get_client_stats(email)
        if not client_info or not client_info.get("uuid"):
            return False

        payload = {
            "id": self.inbound_id,
            "clientUuid": client_info["uuid"]
        }

        resp = self._request("POST", "/api/inbounds/delClient", data=payload)
        return resp and resp.get("success")

    async def get_client_stats(self, email: str) -> dict | None:
        """دریافت آمار کاربر"""
        resp = self._request("GET", f"/api/inbounds/get/{self.inbound_id}")

        if resp and resp.get("success"):
            obj = resp.get("obj", {})
            settings_json = json.loads(obj.get("settings", "{}"))
            clients = settings_json.get("clients", [])
            client_stats = obj.get("clientStats", [])

            for client in clients:
                if client.get("email") == email:
                    stat = next((s for s in client_stats if s.get("email") == email), {})
                    return {
                        "email": email,
                        "uuid": client.get("id"),
                        "total": client.get("totalGB", 0),
                        "up": stat.get("up", 0),
                        "down": stat.get("down", 0),
                        "expiry": client.get("expiryTime", 0),
                        "enable": client.get("enable", True)
                    }
        return None

    def _generate_vless_link(self, uuid_str: str, name: str) -> str:
        """ساخت لینک VLESS"""
        params = {
            "type": "ws",
            "security": settings.XRAY_SECURITY,
            "path": settings.XRAY_WS_PATH,
            "host": settings.XRAY_DOMAIN,
            "fp": "chrome",
            "alpn": "http/1.1"
        }
        query = urlencode(params)
        return f"vless://{uuid_str}@{settings.XRAY_DOMAIN}:{settings.XRAY_PORT}?{query}#{name}"