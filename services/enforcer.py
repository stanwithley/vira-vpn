# services/enforcer.py
import asyncio
from datetime import datetime, timezone
from db.mongo import subscriptions_col
from services.xray_service import remove_client

async def expire_loop(interval_sec: int = 180):
    while True:
        now = datetime.now(timezone.utc)
        cursor = subscriptions_col.find({
            "status": "active",
            "end_at": {"$lte": now}
        })
        count = 0
        async for s in cursor:
            # پشتیبانی از چند دستگاه (لیست ایمیل‌ها)
            x = s.get("xray") or {}
            emails = []
            if isinstance(x, list):  # مدل جدید چنددستگاهی
                emails = [xi.get("email") for xi in x if xi.get("email")]
            elif isinstance(x, dict):  # مدل قدیم تک‌دستگاهی
                if x.get("email"):
                    emails = [x["email"]]

            for em in emails:
                try:
                    remove_client(em)
                except Exception:
                    pass

            await subscriptions_col.update_one(
                {"_id": s["_id"]},
                {"$set": {"status": "expired"}}
            )
            count += 1

        await asyncio.sleep(interval_sec)
