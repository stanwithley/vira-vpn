# services/quota_enforcer.py
import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db.mongo import subscriptions_col, users_col
# ایمپورت کلاس جدید
from services.xray_service import XrayService

logger = logging.getLogger(__name__)

# ساخت نمونه از سرویس پنل
xray = XrayService()

BYTES_PER_MB = 1024 * 1024


def _collect_emails(sub: dict) -> list[str]:
    """استخراج لیست ایمیل‌ها از دیتابیس"""
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
    """ارسال پیام اتمام حجم"""
    user = await users_col.find_one({"_id": sub["user_id"]})
    if not user or user.get("tg_id") is None:
        return
    tg_id = int(user["tg_id"])

    quota_mb = int(sub.get("quota_mb") or 0)
    devices = int(sub.get("devices") or 1)

    txt = _rtl(
        "⛔ <b>حجم اشتراک شما به پایان رسید.</b>\n\n"
        f"• ظرفیت کل: {_fa_num(str(quota_mb))} مگ\n"
        f"• مصرف شده: {_fa_num(str(used_mb))} مگ\n"
        f"• تعداد کاربر: {_fa_num(str(devices))}\n"
        "—\n"
        "برای اتصال مجدد، لطفاً اشتراک خود را تمدید کنید."
    )

    kb = InlineKeyboardBuilder()
    kb.button(text=_rtl("🔁 تمدید سرویس"), callback_data="renew:plans")
    kb.button(text=_rtl("🛟 پشتیبانی"), url="https://t.me/viravpnsupport")  # لینک پشتیبانی ثابت
    kb.adjust(1)

    try:
        await bot.send_message(tg_id, txt, reply_markup=kb.as_markup(), parse_mode="HTML")
    except Exception:
        pass


async def _notify_expired(bot: Bot, sub: dict):
    """ارسال پیام انقضای زمان"""
    user = await users_col.find_one({"_id": sub["user_id"]})
    if not user or user.get("tg_id") is None:
        return
    tg_id = int(user["tg_id"])

    txt = _rtl(
        "⏳ <b>مهلت اشتراک شما به پایان رسید.</b>\n"
        "دسترسی سرویس قطع شد. برای ادامه استفاده لطفاً تمدید کنید."
    )

    kb = InlineKeyboardBuilder()
    kb.button(text=_rtl("🔁 تمدید سرویس"), callback_data="renew:plans")
    kb.adjust(1)

    try:
        await bot.send_message(tg_id, txt, reply_markup=kb.as_markup(), parse_mode="HTML")
    except Exception:
        pass


async def _get_current_total_bytes(email: str) -> int:
    """دریافت مجموع مصرف (آپلود + دانلود) از پنل جدید"""
    stats = await xray.get_client_stats(email)
    if stats:
        return int(stats.get("up", 0)) + int(stats.get("down", 0))
    return 0


async def _suspend_and_remove_all(emails: list[str]):
    """حذف یوزرها از پنل (Async)"""
    for em in emails:
        try:
            await xray.remove_client(em)
        except Exception as e:
            logger.error(f"Error removing client {em}: {e}")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def quota_loop(bot: Bot, interval_sec: int = 180):  # هر 3 دقیقه چک میکند
    """
    حلقه اصلی بررسی مصرف و انقضا
    """
    logger.info("⚖️ Quota enforcer loop started.")
    while True:
        try:
            # فقط اشتراک‌های فعال را چک کن
            cursor = subscriptions_col.find({"status": "active"})

            async for sub in cursor:
                # 1. چک کردن تاریخ انقضا
                end_at = sub.get("end_at")
                if end_at:
                    try:
                        # هندل کردن منطقه زمانی
                        now = _now_utc()
                        expiry = end_at if end_at.tzinfo else end_at.replace(tzinfo=timezone.utc)
                        is_expired = now >= expiry
                    except Exception:
                        is_expired = False

                    if is_expired:
                        emails = _collect_emails(sub)
                        if emails:
                            await _suspend_and_remove_all(emails)

                        # آپدیت وضعیت به Suspended
                        already_notified = bool(sub.get("expired_notified"))
                        await subscriptions_col.update_one(
                            {"_id": sub["_id"]},
                            {"$set": {"status": "suspended", "expired_notified": True}}
                        )
                        if not already_notified:
                            await _notify_expired(bot, sub)
                        continue

                # 2. چک کردن حجم مصرفی
                quota_mb = int(sub.get("quota_mb") or 0)
                if quota_mb <= 0:
                    # اگر نامحدود حجمی است، کاری نداریم
                    continue

                emails = _collect_emails(sub)
                if not emails:
                    continue

                # منطق محاسبه افزایشی (Delta)
                # این روش عالیه چون حتی اگه پنل ریست بشه، مصرف کاربر صفر نمیشه
                last_bytes: dict = sub.get("last_bytes") or {}
                consumed_bytes: int = int(sub.get("consumed_bytes") or (int(sub.get("used_mb") or 0) * BYTES_PER_MB))

                new_last_bytes = dict(last_bytes)
                increments_sum = 0

                # دریافت مصرف همه یوزرهای این اشتراک
                for em in emails:
                    cur = await _get_current_total_bytes(em)
                    prev = int(last_bytes.get(em) or 0)

                    if prev == 0:
                        # اولین بار است که داریم چک میکنیم
                        new_last_bytes[em] = cur
                        continue

                    if cur >= prev:
                        # حالت عادی: مصرف زیاد شده
                        inc = cur - prev
                        increments_sum += inc
                        new_last_bytes[em] = cur
                    else:
                        # حالت ریست شدن پنل: پنل صفر شده ولی ما ادامه میدیم
                        # کل مقدار فعلی رو به عنوان مصرف جدید حساب میکنیم
                        increments_sum += cur
                        new_last_bytes[em] = cur

                consumed_bytes += increments_sum
                used_mb = consumed_bytes // BYTES_PER_MB

                # ذخیره در دیتابیس
                await subscriptions_col.update_one(
                    {"_id": sub["_id"]},
                    {"$set": {
                        "used_mb": int(used_mb),
                        "consumed_bytes": int(consumed_bytes),
                        "last_bytes": new_last_bytes
                    }}
                )

                # 3. اعمال محدودیت حجم
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

        except Exception as e:
            logger.error(f"Error in quota_loop: {e}")
            # اجازه نمیدیم لوپ کرش کنه

        await asyncio.sleep(interval_sec)