import asyncio
from services.xray_service import XrayService
from config import settings


async def test_connection():
    print(f"📡 Testing connection to: {settings.PANEL_URL} ...")

    xray = XrayService()

    # 1. تست ساخت کاربر (Add Client)
    print("1️⃣ Trying to add a test user...")
    email = "test-debug-123"
    result = await xray.add_client(email=email, total_gb=1, expire_days=1)

    if result:
        print("✅ User Created Successfully!")
        print(f"   UUID: {result['uuid']}")
        print(f"   Link: {result['link'][:50]}...")  # نمایش خلاصه لینک
    else:
        print("❌ Failed to create user. Check config and logs.")
        return

    # 2. تست دریافت اطلاعات (Get Stats)
    print("\n2️⃣ Checking user stats...")
    stats = await xray.get_client_stats(email)
    if stats:
        print(f"✅ Stats received: {stats}")
    else:
        print("❌ Failed to get stats.")

    # 3. تست حذف کاربر (Cleanup)
    print("\n3️⃣ Cleaning up (Deleting test user)...")
    deleted = await xray.remove_client(email)
    if deleted:
        print("✅ User deleted successfully.")
    else:
        print("❌ Failed to delete user.")

    print("\n🎉 TEST COMPLETE. If you see all green checks, XrayService is perfect.")


if __name__ == "__main__":
    try:
        asyncio.run(test_connection())
    except Exception as e:
        print(f"❌ FATAL ERROR: {e}")