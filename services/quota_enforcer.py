# services/quota_enforcer.py
import asyncio
from datetime import datetime, timezone

from aiogram import Bot

from db.mongo import subscriptions_col, users_col
from services.xray_service import get_user_traffic_bytes, remove_client

BYTES_PER_MB = 1024 * 1024


def _collect_emails(sub: dict) -> list[str]:
    """
    از فیلد sub["xray"] (می‌تونه list یا dict باشه) ایمیل‌ها را استخراج می‌کند.
    """
    x = sub.get("xray") or []
    if isinstance(x, dict):
        return [x.get("email")] if x.get("email") else []
    elif isinstance(x, list):
        return [xi.get("email") for xi in x if xi and xi.get("email")]
    return []


def _rtl(s: str) -> str:
    return "\u200F" + s


def _fa_num(s: str) -> str:
    tbl = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
    return str(s).translate(tbl)


async def _notify_quota_exhausted(bot: Bot, sub: dict, used_mb: int):
    """
    پیام اتمام حجم (فقط یک بار).
    """
    user = await users_col.find_one({"_id": sub["user_id"]})
    if not user or user.get("tg_id") is None:
        return
    tg_id = int(user["tg_id"])

    quota_mb = int(sub.get("quota_mb") or 0)
    devices = int(sub.get("devices") or 1)

    txt = _rtl(
        "⛔ حجم اشتراک شما به پایان رسید.\n\n"
        f"• ظرفیت: {_fa_num(quota_mb)} مگ\n"
        f"• مصرف‌شده: {_fa_num(used_mb)} مگ\n"
        f"• دستگاه: {_fa_num(devices)}\n"
        "—\n"
        "برای ادامه استفاده، اشتراک را تمدید یا پلن بزرگ‌تر تهیه کنید."
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb = InlineKeyboardBuilder()
    kb.button(text=_rtl("🔁 تمدید/خرید"), callback_data="renew:plans")
    kb.button(text=_rtl("🛟 پشتیبانی"), callback_data="support_open")
    kb.adjust(1)

    try:
        await bot.send_message(tg_id, txt, reply_markup=kb.as_markup())
    except Exception:
        pass


async def _notify_expired(bot: Bot, sub: dict):
    """
    پیام پایان تاریخ اشتراک.
    """
    user = await users_col.find_one({"_id": sub["user_id"]})
    if not user or user.get("tg_id") is None:
        return
    tg_id = int(user["tg_id"])

    txt = _rtl(
        "⏳ مدت اشتراک شما به پایان رسید و دسترسی غیرفعال شد.\n"
        "برای ادامه استفاده، لطفاً تمدید کنید."
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb = InlineKeyboardBuilder()
    kb.button(text=_rtl("🔁 تمدید/خرید"), callback_data="renew:plans")
    kb.button(text=_rtl("🛟 پشتیبانی"), callback_data="support_open")
    kb.adjust(1)

    try:
        await bot.send_message(tg_id, txt, reply_markup=kb.as_markup())
    except Exception:
        pass


async def _current_total_bytes(email: str) -> int:
    """
    گرفتن ترافیک کل (uplink+downlink) از Xray (در ترد جدا).
    """
    _, __, tot = await asyncio.to_thread(get_user_traffic_bytes, email)
    return int(tot or 0)


async def _suspend_and_remove_all(emails: list[str]):
    """
    حذف دسترسی همه ایمیل‌ها از Xray در ترد جدا.
    """
    tasks = [asyncio.to_thread(remove_client, em) for em in emails]
    # در صورت بروز خطا، نمی‌خوایم کل لوپ بترکه
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except Exception:
        pass


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def quota_loop(bot: Bot, interval_sec: int = 120):
    """
    هر interval_sec ثانیه:
      - اگر end_at گذشته → تعلیق + حذف کاربر از Xray + نوتیف انقضا
      - در غیر این صورت مصرف را با اتکا به last_bytes/consumed_bytes بروزرسانی می‌کند.
      - اگر used_mb >= quota_mb → تعلیق + حذف از Xray + نوتیف اتمام حجم (یک‌باره)
    """
    while True:
        try:
            cursor = subscriptions_col.find({"status": "active"})
            async for sub in cursor:
                # ---------- چک تاریخ انقضا ----------
                end_at = sub.get("end_at")
                if end_at:
                    # end_at ممکن است naive باشد؛ با now UTC مقایسه‌ی ساده
                    try:
                        is_expired = _now_utc() >= (end_at if end_at.tzinfo else end_at.replace(tzinfo=timezone.utc))
                    except Exception:
                        is_expired = _now_utc() >= _now_utc()  # fallback بی‌معنا؛ فقط نذاره بترکه
                    if is_expired:
                        emails = _collect_emails(sub)
                        if emails:
                            await _suspend_and_remove_all(emails)

                        # اگر قبلاً ساسپند نشده بود، به user خبر بده
                        already_notified = bool(sub.get("expired_notified"))
                        await subscriptions_col.update_one(
                            {"_id": sub["_id"]},
                            {"$set": {"status": "suspended", "expired_notified": True}}
                        )
                        if not already_notified:
                            await _notify_expired(bot, sub)
                        # وقتی منقضی شد، ادامه‌ی محاسبه‌ی مصرف لازم نیست
                        continue

                # ---------- محاسبه‌ی مصرف با تحمل ری‌استارت ----------
                quota_mb = int(sub.get("quota_mb") or 0)
                if quota_mb <= 0:
                    # اگر سهمیه تعریف نشده/صفره، فقط used_mb را صفر نگه دار
                    await subscriptions_col.update_one(
                        {"_id": sub["_id"]},
                        {"$set": {"used_mb": 0}}
                    )
                    continue

                emails = _collect_emails(sub)
                if not emails:
                    # ایمیلی ثبت نشده؛ نمی‌شه مصرف را حساب کرد
                    continue

                # حالت قبلی را از DB بخوان
                last_bytes: dict = sub.get("last_bytes") or {}
                consumed_bytes: int = int(sub.get("consumed_bytes") or (int(sub.get("used_mb") or 0) * BYTES_PER_MB))

                # مجموع افزایشی مصرف از آخرین اندازه‌گیری
                new_last_bytes = dict(last_bytes)  # کپی برای آپدیت
                increments_sum = 0

                # به صورت موازی از Xray بگیر
                totals = await asyncio.gather(*[_current_total_bytes(em) for em in emails], return_exceptions=True)

                for em, cur in zip(emails, totals):
                    if isinstance(cur, Exception):
                        # اگر نتونستیم بگیریم، این ایمیل رو نادیده بگیر
                        continue
                    cur = int(cur or 0)
                    prev = int(last_bytes.get(em) or 0)

                    if prev == 0:
                        # اولین بار است یا baseline نداریم → baseline را می‌گذاریم، افزایشی 0
                        new_last_bytes[em] = cur
                        continue

                    if cur >= prev:
                        inc = cur - prev
                        increments_sum += inc
                        new_last_bytes[em] = cur
                    else:
                        # ری‌استارت Xray یا ریست شدن شمارنده → baseline جدید
                        new_last_bytes[em] = cur
                        # افزایشی 0 تا دو بار حساب نشه

                consumed_bytes += increments_sum
                used_mb = consumed_bytes // BYTES_PER_MB

                # ---------- ذخیره‌ی وضعیت ----------
                await subscriptions_col.update_one(
                    {"_id": sub["_id"]},
                    {"$set": {
                        "used_mb": int(used_mb),
                        "consumed_bytes": int(consumed_bytes),
                        "last_bytes": new_last_bytes
                    }}
                )

                # ---------- اعمال محدودیت سهمیه ----------
                if used_mb >= quota_mb:
                    emails = _collect_emails(sub)
                    if emails:
                        await _suspend_and_remove_all(emails)

                    already_notified = bool(sub.get("quota_notified"))
                    await subscriptions_col.update_one(
                        {"_id": sub["_id"]},
                        {"$set": {"status": "suspended", "quota_notified": True}}
                    )
                    if not already_notified:
                        await _notify_quota_exhausted(bot, sub, used_mb)

        except Exception:
            # اجازه نمی‌دهیم لوپ از کار بیفتد
            pass

        await asyncio.sleep(interval_sec)
