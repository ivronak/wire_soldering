# Rupee amount ko English words me (Indian system: lakh, crore). Receipt / invoice print par "Rupees ... only" ke liye.
ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen",
        "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _below_thousand(n):
    words = []
    if n >= 100:
        words.append(ONES[n // 100] + " Hundred")
        n %= 100
    if n >= 20:
        words.append(TENS[n // 10] + (" " + ONES[n % 10] if n % 10 else ""))
    elif n > 0:
        words.append(ONES[n])
    return " ".join(words)


def _whole(n):
    if n == 0:
        return "Zero"
    parts = []
    for unit, size in (("Crore", 10_000_000), ("Lakh", 100_000), ("Thousand", 1000)):
        if n >= size:
            parts.append(_below_thousand(n // size) + " " + unit)
            n %= size
    if n:
        parts.append(_below_thousand(n))
    return " ".join(parts)


def rupees_in_words(amount):
    """25606.5 -> 'Rupees Twenty Five Thousand Six Hundred Six and Fifty Paise Only'"""
    paise_total = int(round(abs(amount) * 100))
    rupees, paise = divmod(paise_total, 100)
    text = "Rupees " + _whole(rupees)
    if paise:
        text += " and " + _whole(paise) + " Paise"
    return text + " Only"
