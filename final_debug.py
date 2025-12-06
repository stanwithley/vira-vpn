import requests
import json
import uuid

# === تنظیمات دستی (برای اطمینان) ===
BASE_URL = "http://193.180.211.230:54321/cWrhkR40LuKobweVYO"
USERNAME = "hatef"
PASSWORD = "hatef1381"
INBOUND_ID = 1


def debug_request():
    print("🚀 Starting Final Debug...")

    # استفاده از Session برای نگهداری خودکار کوکی‌ها
    session = requests.Session()

    # هدرهای شبیه مرورگر
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest"
    })

    # 1. لاگین
    print(f"1️⃣ Logging in to {BASE_URL}/login ...")
    login_payload = {"username": USERNAME, "password": PASSWORD}
    try:
        resp = session.post(f"{BASE_URL}/login", data=login_payload, timeout=10)
        print(f"   Status: {resp.status_code}")

        if resp.status_code == 200 and resp.json().get('success'):
            print("   ✅ Login Success! Cookies saved.")
        else:
            print(f"   ❌ Login Failed: {resp.text}")
            return
    except Exception as e:
        print(f"   ❌ Connection Error: {e}")
        return

    # 2. تست ساخت کاربر (با آدرس دقیق مرورگر)
    target_url = f"{BASE_URL}/panel/api/inbounds/addClient"
    print(f"\n2️⃣ Trying to add user via: {target_url}")

    # دیتای دقیقاً مشابه cURL
    client_uuid = str(uuid.uuid4())
    email = "debug-final-user"

    settings_json = json.dumps({
        "clients": [{
            "id": client_uuid,
            "email": email,
            "limitIp": 1,
            "totalGB": 0,
            "expiryTime": 0,
            "enable": True,
            "tgId": "",
            "subId": "debugsub123",
            "flow": "",
        }]
    })

    payload = {
        "id": INBOUND_ID,
        "settings": settings_json
    }

    try:
        # نکته کلیدی: استفاده از data= (نه json=)
        resp = session.post(target_url, data=payload)

        print(f"   Status: {resp.status_code}")
        print(f"   Response: {resp.text[:200]}...")  # نمایش ۲۰۰ کاراکتر اول

        if resp.status_code == 200 and resp.json().get('success'):
            print("\n🎉🎉🎉 SUCCESS! It works.")
            print(f"   UUID Created: {client_uuid}")
            # پاک کردن یوزر تست
            del_payload = {"id": INBOUND_ID, "clientUuid": client_uuid}
            session.post(f"{BASE_URL}/panel/api/inbounds/delClient", data=del_payload)
            print("   (Test user deleted)")
        else:
            print("\n❌ Failed again.")

    except Exception as e:
        print(f"   ❌ Error: {e}")


if __name__ == "__main__":
    debug_request()