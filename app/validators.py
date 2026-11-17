# Yeh file GSTIN / PAN / IFSC ka format check karti hai — Vendor aur Customer dono masters yahin se check karte hain.
# Kyun: pehle koi bhi cheez (jaise "ABC123") GSTIN me save ho jaati thi; ab server hi galat format rok dega
# (sirf frontend pe bharosa nahi — CLAUDE.md rule 5.4).
import re

# GSTIN = 15 chars: 2 digit state code + 10 char PAN + 1 entity no. + 'Z' + 1 check char
GSTIN_RE = re.compile(r'^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$')
# PAN = 5 letters + 4 digits + 1 letter
PAN_RE = re.compile(r'^[A-Z]{5}\d{4}[A-Z]$')
# IFSC = 4 letters (bank) + '0' + 6 letters/digits (branch)
IFSC_RE = re.compile(r'^[A-Z]{4}0[A-Z0-9]{6}$')


def check_tax_ids(gstin, pan, ifsc, old_gstin=None, old_pan=None, old_ifsc=None):
    """Teeno values (already strip + UPPER) check karta hai.
    Galat ho to English error message (string) lautata hai, sab theek ho to None.
    old_* sirf EDIT me: agar value badli hi nahi to purana data dobara reject nahi karte
    (taaki purani entry wale party ka koi aur field edit karna block na ho)."""
    if gstin and gstin != (old_gstin or ""):
        if not GSTIN_RE.match(gstin):
            return "GSTIN is not valid. It must be 15 characters, like 24ABCDE1234F1Z5."
    if pan and pan != (old_pan or ""):
        if not PAN_RE.match(pan):
            return "PAN is not valid. It must be 10 characters, like ABCDE1234F."
    if ifsc and ifsc != (old_ifsc or ""):
        if not IFSC_RE.match(ifsc):
            return "IFSC code is not valid. It must be 11 characters, like HDFC0001234."
    # GSTIN ke beech ke 10 akshar hi PAN hote hain — dono diye hon to match hona chahiye
    if gstin and pan and GSTIN_RE.match(gstin) and PAN_RE.match(pan):
        if gstin[2:12] != pan:
            return "PAN does not match the GSTIN. Characters 3 to 12 of the GSTIN must be the PAN."
    return None
