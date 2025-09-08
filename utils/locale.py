# utils/locale.py
from datetime import datetime
from zoneinfo import ZoneInfo

TEHRAN = ZoneInfo("Asia/Tehran")
PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

def fa_num(s: str) -> str:
    return str(s).translate(PERSIAN_DIGITS)

def to_tehran(dt: datetime) -> datetime:
    # فرض: dt در UTC است
    return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(TEHRAN)

def fmt_dt(dt: datetime, with_time: bool = True) -> str:
    t = to_tehran(dt)
    s = t.strftime("%Y-%m-%d %H:%M") if with_time else t.strftime("%Y-%m-%d")
    return fa_num(s)

def rtl(s: str) -> str:
    return "\u200F" + s  # RTL mark
