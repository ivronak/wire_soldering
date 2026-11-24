# Product Category ke liye flat icons (ek chhota fixed set). Category me ek icon chuno, to us category ke har product ke saath wahi icon dikhta hai
# (Finished goods, Product master, Category list). Icon sirf dikhane ke liye hai, business data nahi; isliye code me fixed library theek hai.
# Har icon: (label, svg ke andar ka hissa, icon ka rang, tile ka halka rang). viewBox 24x24, fill = currentColor.
# Rang: theme.js ke categorical tokens (cat1..cat7) + default box = brand accent. Status rang (red/green/amber) jaan-boojh ke nahi liye,
# kyunki category icon ka matlab 'status' nahi hota. Kuch icons ek rang share karte hain (14 icons, 9 rang) — shape alag hai.
from markupsafe import Markup

ICONS = {
    "wire": ("Wire coil", '<path fill-rule="evenodd" d="M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zm0 4.5a4.5 4.5 0 1 1 0 9 4.5 4.5 0 0 1 0-9z"/><circle cx="12" cy="12" r="1.7"/>', "#8A5A2B", "#F6EEE6"),
    "spool": ("Spool", '<rect x="4" y="3" width="16" height="3.5" rx="1.2"/><rect x="4" y="17.5" width="16" height="3.5" rx="1.2"/><rect x="7.5" y="6.5" width="9" height="11"/>', "#475569", "#EEF2F6"),
    "box": ("Box", '<path d="M12 2.5 20.5 7 12 11.5 3.5 7z"/><path opacity=".65" d="M3.5 8.8 11 12.9v8.4L3.5 17z"/><path opacity=".4" d="M20.5 8.8 13 12.9v8.4l7.5-4.3z"/>', "#0B5BEF", "#EDF3FF"),
    "package": ("Package", '<path d="M5 3h14l2 3.5H3z" opacity=".6"/><path fill-rule="evenodd" d="M3 9a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zm7 0v3.5h4V9z"/>', "#6D28D9", "#F1EAFD"),
    "layers": ("Layers", '<path d="M12 2.5 22 8l-10 5.5L2 8z"/><path opacity=".65" d="M3.6 11.6 12 16.2l8.4-4.6L22 12.5l-10 5.5L2 12.5z"/><path opacity=".4" d="M3.6 16 12 20.6l8.4-4.6L22 17l-10 5.5L2 17z"/>', "#3730A3", "#E0E7FF"),
    "bolt": ("Electric", '<path d="M13.5 2 5 13.5h5.5L9.5 22 19 9.5h-5.8z"/>', "#A21CAF", "#FAEAFB"),
    "flask": ("Flux / chemical", '<path d="M9 2.5h6v2h-1V9l5.2 9.3A2 2 0 0 1 17.5 21h-11a2 2 0 0 1-1.7-2.7L10 9V4.5H9z"/>', "#4338CA", "#EEF0FD"),
    "drop": ("Liquid", '<path d="M12 2.5S5.5 10 5.5 14.5a6.5 6.5 0 0 0 13 0C18.5 10 12 2.5 12 2.5z"/>', "#0E7490", "#E6F6F8"),
    "tag": ("Tag", '<path fill-rule="evenodd" d="M3 4a1 1 0 0 1 1-1h7.6a1 1 0 0 1 .7.3l8.4 8.4a1 1 0 0 1 0 1.4l-7.6 7.6a1 1 0 0 1-1.4 0L3.3 12.3A1 1 0 0 1 3 11.6zm4.5 2a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z"/>', "#BE185D", "#FCE9F1"),
    "cog": ("Machine part", '<path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58a.49.49 0 0 0 .12-.61l-1.92-3.32a.488.488 0 0 0-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.484.484 0 0 0-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58a.49.49 0 0 0-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/>', "#475569", "#EEF2F6"),
    "shield": ("Shield", '<path d="M12 2.5 4 5.5v6c0 5 3.4 8.6 8 10 4.6-1.4 8-5 8-10v-6z"/>', "#4338CA", "#EEF0FD"),
    "clock": ("Clock", '<path fill-rule="evenodd" d="M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zm1 4v5.6l3.5 2-1 1.7L11 13.7V7z"/>', "#475569", "#EEF2F6"),
    "factory": ("Factory", '<path d="M3 21V11l6 3.5V11l6 3.5V5h4v16z"/>', "#8A5A2B", "#F6EEE6"),
    "star": ("Star", '<path d="m12 2.5 2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 17.4l-5.9 3.1 1.2-6.5L2.5 9.4l6.6-.9z"/>', "#A21CAF", "#FAEAFB"),
}
DEFAULT_ICON = "box"


def icon_choices():
    # Category form ke picker ke liye: [(key, label)]
    return [(key, value[0]) for key, value in ICONS.items()]


def clean_icon(key):
    # Form se aaya icon key sahi hai to wahi, warna None (icon nahi)
    key = (key or "").strip()
    return key if key in ICONS else None


def icon_svg(key, size=20):
    # Sirf svg (currentColor me)
    inner = ICONS.get(key or DEFAULT_ICON, ICONS[DEFAULT_ICON])[1]
    return Markup(f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" fill="currentColor" aria-hidden="true">{inner}</svg>')


def icon_tile(key, size=40):
    # Rang-birangi chhoti tile me icon (category ka icon na ho to default box)
    key = key if key in ICONS else DEFAULT_ICON
    _label, _inner, fg, bg = ICONS[key]
    glyph = round(size * 0.55)
    return Markup(f'<span class="cat-icon" title="{ICONS[key][0]}" style="display:inline-flex;align-items:center;justify-content:center;flex:none;'
                  f'width:{size}px;height:{size}px;border-radius:{round(size * 0.28)}px;background:{bg};color:{fg}">{icon_svg(key, glyph)}</span>')
