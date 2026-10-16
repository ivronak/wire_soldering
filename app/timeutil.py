# Time ke helpers — "created_at" (kab entry hui) ke liye.
# Rule: DB me hamesha UTC store hota hai (server ka clock UTC hai, local PC ka IST — dono jagah same rahe),
# aur screen par dikhate waqt India time (IST = UTC + 5:30; India me daylight saving nahi hota) me badal dete hain.
# Use: app/models.py (CreatedAtMixin ka default), app/__init__.py (Jinja filter "ist"), docket ka "Printed on".
from datetime import datetime, timedelta, timezone

IST_OFFSET = timedelta(hours=5, minutes=30)


def utc_now():
    # SQLite timezone nahi rakhta, isliye tzinfo hata ke "naive" UTC datetime dete hain
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_ist(value):
    # DB wala UTC datetime -> IST datetime. Purani rows me created_at khaali (None) hota hai, use None hi rehne do.
    if value is None:
        return None
    return value + IST_OFFSET


def ist_now():
    return to_ist(utc_now())


def format_ist(value):
    # Screen ke liye: "16 Oct 2026, 03:42 PM". Khaali ho to khaali string (template me line hi nahi dikhegi).
    if not value:
        return ""
    return to_ist(value).strftime("%d %b %Y, %I:%M %p")
