# Phase 0: security ke chhote helper — mobile number saaf karna, password hash / check, temp password, lockout key.
# Yahan koi route ya DB table nahi; sirf pure functions. Isse app/auth/service.py, cli.py aur routes.py use karte hain.
import hashlib
import hmac
import re
import secrets
import unicodedata

from flask import current_app, request
from werkzeug.security import check_password_hash, generate_password_hash

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128
_MOBILE_RE = re.compile(r"^[6-9][0-9]{9}$")        # Indian mobile: 6-9 se shuru, 10 ASCII digit (Arabic / Devanagari digit nahi — look-alike duplicate roakne ke liye)
_TEMP_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"   # 0/O, 1/l/I jaise confusing akshar nahi


def normalize_mobile(raw):
    # "+91 98765-43210", "098765 43210", "9876543210" -> sab "9876543210". Galat ho to None.
    text = re.sub(r"[\s\-().]", "", raw or "")
    if text.startswith("+"):
        text = text[1:]
    if not (text.isascii() and text.isdigit()):
        return None
    if len(text) == 12 and text.startswith("91"):
        text = text[2:]
    elif len(text) == 11 and text.startswith("0"):
        text = text[1:]
    return text if _MOBILE_RE.match(text) else None


# Dikhne me khaali / chhupe hue akshar jo Cc/Cf category me nahi aate (Braille blank, Hangul filler) — naam me nakal banane ke kaam aate hain
_INVISIBLE_EXTRA = {0x2800, 0x3164, 0x115F, 0x1160, 0xFFA0, 0x180E, 0x034F, 0x061C}


def visible_name_problem(text, what):
    # Role / user ke naam ki safai: hidden, control, bidi aur invisible akshar nahi; kam se kam ek akshar ya ankh (letter/digit) ho.
    # Naam jaisa hai waisa hi store hota hai — Devanagari matras jaise asli akshar rok nahi jate (sirf chhupe hue rokte hain).
    for ch in text:
        if unicodedata.category(ch) in ("Cc", "Cf") or ord(ch) in _INVISIBLE_EXTRA or 0xFE00 <= ord(ch) <= 0xFE0F:
            return "%s cannot contain hidden or control characters." % what
    if not any(ch.isalnum() for ch in text):
        return "%s must contain at least one letter or digit." % what
    return None


def look_alike_key(text):
    # Naam ka "chehra" (skeleton): NFKD me tod ke sirf letters/digits rakho, casefold. "Admin" + combining mark / Braille blank / emoji selector
    # sab "admin" hi ban jate hain — isse nakal-naam (impersonation) pakda jata hai. Sirf compare ke liye, store nahi hota.
    decomposed = unicodedata.normalize("NFKD", text)
    kept = "".join(ch for ch in decomposed if unicodedata.category(ch)[0] in ("L", "N") and ord(ch) not in _INVISIBLE_EXTRA)
    return kept.casefold()


def mask_mobile(mobile):
    # Audit / log me poora number nahi, sirf aakhri 4 digit (privacy — flow doc 11.2)
    mobile = mobile or ""
    return "******" + mobile[-4:] if len(mobile) >= 4 else "******"


def mobile_hash(key_source):
    # Lockout table me mobile ka seedha number nahi, secret-key se bana hash (unknown numbers ke liye bhi row banti hai)
    secret = (current_app.config.get("SECRET_KEY") or "").encode()
    return hmac.new(secret, (key_source or "").encode(), hashlib.sha256).hexdigest()[:48]


def hash_password(password):
    # Pehle scrypt; kisi server par hashlib.scrypt na ho to pbkdf2 (dono ko check_password_hash samajhta hai)
    try:
        return generate_password_hash(password, method="scrypt")
    except Exception:
        return generate_password_hash(password, method="pbkdf2:sha256")


def verify_password(password_hash, password):
    try:
        return check_password_hash(password_hash, password or "")
    except Exception:
        return False


_dummy_hash = None


def dummy_hash():
    # Unknown mobile par bhi ek asli hash check chalate hain, taaki "user hai ya nahi" time se pata na chale
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password(secrets.token_urlsafe(16))
    return _dummy_hash


def password_problem(password, mobile=None):
    # Naye password ki shart. Ek hi jagah, taaki CLI, change-password aur admin reset sab same rule use karein.
    if password is None or len(password) < MIN_PASSWORD_LENGTH:
        return "Password must be at least %d characters." % MIN_PASSWORD_LENGTH
    if len(password) > MAX_PASSWORD_LENGTH:
        return "Password can be at most %d characters." % MAX_PASSWORD_LENGTH
    if not password.strip():
        return "Password cannot be blank."
    if len(set(password)) < 5:
        return "Password is too simple. Use more different characters."
    if password.isdigit():
        return "Password cannot be only digits."
    if mobile and mobile in password:
        return "Password cannot contain the mobile number."
    return None


def generate_temp_password(length=12):
    # Admin / reset ke liye ek baar dikhne wala password. Hamesha policy pass karta hai (digits-only nahi hota).
    while True:
        candidate = "".join(secrets.choice(_TEMP_ALPHABET) for _ in range(length))
        if password_problem(candidate) is None:
            return candidate


def client_ip():
    # ProxyFix (non-dev me) sahi client IP remote_addr me daal deta hai
    return (request.remote_addr or "0.0.0.0")[:45]


def config_problem(secret_key, dev):
    # Live par ERP_SECRET_KEY zaroori hai (dev me nahi). Wapas: problem ka text ya None.
    if dev:
        return None
    if not secret_key:
        return "ERP_SECRET_KEY is not set."
    if len(secret_key) < 32:
        return "ERP_SECRET_KEY is too short (use at least 32 random characters)."
    if secret_key == "dev-wire-soldering-change-later":
        return "ERP_SECRET_KEY is still the public development key."
    return None
