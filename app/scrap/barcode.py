# Code 128 (set B) barcode ko SVG me banata hai — koi library nahi, internet nahi, isliye print label offline bhi chalta hai.
# Scrap label (app/scrap/routes.py) isse batch number ka barcode banata hai; scanner wahi text wapas deta hai.

# Code 128 patterns: har symbol 6 numbers (bar, space, bar, space, bar, space widths); index 0..106 (106 = STOP, 7 numbers)
_PATTERNS = (
    "212222 222122 222221 121223 121322 131222 122213 122312 132212 221213 221312 231212 112232 122132 122231 113222 123122 123221 223211 221132 "
    "221231 213212 223112 312131 311222 321122 321221 312212 322112 322211 212123 212321 232121 111323 131123 131321 112313 132113 132311 211313 "
    "231113 231311 112133 112331 132131 113123 113321 133121 313121 211331 231131 213113 213311 213131 311123 311321 331121 312113 312311 332111 "
    "314111 221411 431111 111224 111422 121124 121421 141122 141221 112214 112412 122114 122411 142112 142211 241211 221114 413111 241112 134111 "
    "111242 121142 121241 114212 124112 124211 411212 421112 421211 212141 214121 412121 111143 111341 131141 114113 114311 411113 411311 113141 "
    "114131 311141 411131 211412 211214 211232 2331112"
).split()
_START_B = 104
_STOP = 106


def code128_svg(text, height=60, module=2):
    """Text (sirf printable ASCII) ka Code 128-B barcode: SVG string. Quiet zone dono taraf 10 module."""
    text = str(text)
    values = [ord(ch) - 32 for ch in text]
    if not values or any(v < 0 or v > 94 for v in values):
        raise ValueError("Barcode text must be printable ASCII.")
    checksum = (_START_B + sum(v * (i + 1) for i, v in enumerate(values))) % 103
    symbols = [_START_B] + values + [checksum, _STOP]
    x = 10 * module
    bars = []
    for symbol in symbols:
        for i, width in enumerate(_PATTERNS[symbol]):
            w = int(width) * module
            if i % 2 == 0:                      # even position = bar (kaala), odd = space
                bars.append(f'<rect x="{x}" y="0" width="{w}" height="{height}"/>')
            x += w
    total = x + 10 * module
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total} {height}" width="{total}" height="{height}" '
            f'role="img" aria-label="Barcode {text}" fill="#000">{"".join(bars)}</svg>')


def decode_widths(text):
    """Test ke liye: har symbol ke widths ka jod 11 hona chahiye (STOP ka 13) — encoding sahi hai ya nahi."""
    return [sum(int(w) for w in p) for p in _PATTERNS]
