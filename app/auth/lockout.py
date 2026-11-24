# Phase 0: galat password ki ginti aur lockout. Counter (mobile-hash, IP) par hai, sirf account par nahi —
# taaki koi bahar se kisi Admin / Developer ka number daal-daal ke use lock na kar sake (flow doc 10.5).
# Ginti DB me hai (login_attempts table) aur UPDATE atomic hai, kyunki server par 2 workers chalte hain.
from datetime import timedelta

from sqlalchemy import case, update
from sqlalchemy.exc import IntegrityError

from app.auth.security import mobile_hash
from app.extensions import db
from app.models import LoginAttempt
from app.timeutil import utc_now

MAX_FAILS = 5                       # itni galat koshish ke baad lock
LOCK_MINUTES = 15                   # sab ke liye ek hi lock (Developer ke liye alag nahi — warna lock ka time dekh ke Developer ka number pata chalta, audit 23 Nov)
WINDOW_MINUTES = 30                 # itne time se purani galat koshish ginti me nahi


def _row(key, ip):
    return LoginAttempt.query.filter_by(mobile_hash=mobile_hash(key), ip=ip).first()


def seconds_locked(key, ip):
    # Abhi kitne second lock hai (0 = lock nahi). Lock khatam ho gaya ho to counter zero kar deta hai.
    row = _row(key, ip)
    if row is None or row.locked_until is None:
        return 0
    now = utc_now()
    if row.locked_until > now:
        return int((row.locked_until - now).total_seconds()) + 1
    row.failed_count = 0
    row.locked_until = None
    db.session.commit()
    return 0


IP_KEY = "ip-all"                   # ek IP se sab mobiles ki galat koshish ek saath: random numbers badal-badal ke guess karne se bachav (review 23 Nov)
IP_MAX_FAILS = 40                   # ek IP se itni galat koshish (kisi bhi number par) ke baad us IP par 15 min lock


def register_failure(key, ip, max_fails=MAX_FAILS):
    # Ek galat koshish: ginti +1 (atomic), max_fails par lock. Wapas: nayi ginti.
    hashed = mobile_hash(key)
    now = utc_now()
    window_start = now - timedelta(minutes=WINDOW_MINUTES)
    stale = (LoginAttempt.last_failed_at == None) | (LoginAttempt.last_failed_at < window_start)  # noqa: E711
    bump = update(LoginAttempt).where(LoginAttempt.mobile_hash == hashed, LoginAttempt.ip == ip).values(
        failed_count=case((stale, 1), else_=LoginAttempt.failed_count + 1), last_failed_at=now)
    if db.session.execute(bump).rowcount == 0:
        try:
            with db.session.begin_nested():
                db.session.add(LoginAttempt(mobile_hash=hashed, ip=ip, failed_count=1, last_failed_at=now))
            # Nayi row bani: purani (1 din se purani, lock khatam) rows saaf — bot se table bhar na jaye
            LoginAttempt.query.filter(LoginAttempt.last_failed_at < now - timedelta(days=1),
                                      (LoginAttempt.locked_until == None) | (LoginAttempt.locked_until < now)).delete(synchronize_session=False)  # noqa: E711
        except IntegrityError:
            db.session.execute(bump)     # dusre worker ne row bana di thi — ab sirf +1
    row = LoginAttempt.query.filter_by(mobile_hash=hashed, ip=ip).first()
    count = row.failed_count
    if count >= max_fails:
        row.locked_until = now + timedelta(minutes=LOCK_MINUTES)
    db.session.commit()
    return count


def clear(key, ip):
    # Sahi login ke baad is (mobile, IP) ki ginti saaf
    LoginAttempt.query.filter_by(mobile_hash=mobile_hash(key), ip=ip).delete()
    db.session.commit()


def clear_all_for_mobile(mobile):
    # Admin / CLI "Unlock": is mobile ki saari IP ki ginti saaf
    # Login ka lock aur change-password ka lock ("pw:" + mobile) dono — warna reset ke baad user change-password par atka rehta
    hashes = [mobile_hash(mobile), mobile_hash("pw:" + mobile)]
    removed = LoginAttempt.query.filter(LoginAttempt.mobile_hash.in_(hashes)).delete(synchronize_session=False)
    db.session.commit()
    return removed
