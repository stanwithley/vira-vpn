# services/quota_enforcer.py
import asyncio
from aiogram import Bot
from db.mongo import subscriptions_col, users_col
from services.xray_service import get_user_traffic_bytes, remove_client

BYTES_PER_MB = 1024 * 1024

def _collect_emails(sub: dict) -> list[str]:
    x = sub.get("xray") or []
    if isinstance(x, dict):
        return [x.get("email")] if x.get("email") else []
    elif isinstance(x, list):
        return [xi.get("email") for xi in x if xi and xi.get("email")]
    return []

def _rtl(s: str) -> str: return "\u200F" + s
def _fa_num(s: str) -> str:
    tbl = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
    return str(s).translate(tbl)

async def _notify_quota_exhausted(bot: Bot, sub: dict, used_mb: int):
    """به کاربر پیام بده که حجمش تمام شده (فقط یک‌بار)."""
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
    kb.button(text=_rtl("🛟 پشتیبانی"), callback_data="support_open")  # یا URL پشتیبانی اگر داری
    kb.adjust(1)

    try:
        await bot.send_message(tg_id, txt, reply_markup=kb.as_markup())
    except Exception:
        pass

async def quota_loop(bot: Bot, interval_sec: int = 120):
    """
    هر interval_sec ثانیه مصرف را از Xray می‌کشد، used_mb را آپدیت می‌کند،
    و در صورت عبور از quota_mb => remove_client + status="suspended" + نوتیف یک‌باره.
    """
    while True:
        try:
            cursor = subscriptions_col.find({"status": "active"})
            async for s in cursor:
                quota_mb = int(s.get("quota_mb") or 0)
                if quota_mb <= 0:
                    continue

                emails = _collect_emails(s)
                if not emails:
                    continue

                # مجموع ترافیک همه دستگاه‌های این اشتراک
                total_bytes = 0
                for em in emails:
                    _, __, tot = get_user_traffic_bytes(em)
                    total_bytes += tot
                used_mb = total_bytes // BYTES_PER_MB

                # آپدیت used_mb برای UI
                await subscriptions_col.update_one(
                    {"_id": s["_id"]},
                    {"$set": {"used_mb": int(used_mb)}}
                )

                if used_mb >= quota_mb:
                    # اگر قبلاً نوتیف داده نشده:
                    already_notified = bool(s.get("quota_notified"))
                    # حذف دسترسی‌ها
                    for em in emails:
                        try:
                            remove_client(em)
                        except Exception:
                            pass

                    # ساسپند + علامت‌گذاری که نوتیف داده شده
                    await subscriptions_col.update_one(
                        {"_id": s["_id"]},
                        {"$set": {"status": "suspended", "quota_notified": True}}
                    )

                    if not already_notified:
                        await _notify_quota_exhausted(bot, s, used_mb)

        except Exception:
            # نذار لوپ از کار بیفته
            pass

        await asyncio.sleep(interval_sec)
