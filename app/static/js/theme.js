/* theme.js — poore ERP ka COLOUR THEME ek hi jagah (Nrupex logo se: kaala wordmark + azure -> royal blue "X").
 *
 * Kya karta hai:
 *   1) Tailwind ke colour tokens (bg-accent, text-ink-muted, border-stop-border ...) define karta hai.
 *   2) Wahi colours CSS variables bana deta hai (--accent, --ink, --line ...) taaki page ke apne <style> blocks
 *      var(--accent) use kar sakein — kisi page me hex type karne ki zaroorat nahi.
 *
 * Kaise load hota hai: base.html aur auth/plain.html dono me tailwind CDN ke BAAD:
 *   <script src="{{ url_for('static', filename='js/theme.js') }}"></script>
 *
 * Rang badalna ho to SIRF yahin badlo. (Print pages apne alag CSS use karte hain — print_base.html.)
 *
 * Roles (kaun sa rang kis kaam ke liye):
 *   accent  = brand / primary button / link / selected / "running" (logo ka royal blue)
 *   info    = open / informational read-only boxes (cyan — accent se alag, teal ki jagah)
 *   done    = settled / ordered / credited (violet)
 *   success = good / done / posted (green)      warning = needs attention / pending (amber)
 *   stop    = error / breakdown / overdue / destructive (red)      neutral = draft / inactive / cancelled (cool grey)
 *   ink     = text (logo ke kaale wordmark jaisa near-black), mist = page background
 */
(function () {
  var T = {
    ink:     { DEFAULT: '#0B1220', soft: '#1B2538', muted: '#475266', faint: '#5A6577' },
    // accent: white ke saath 5.6:1 (button text readable). Logo ka azure (#00A0F8) text/button ke liye bahut halka hai (2.8:1),
    // isliye woh sirf gradient / glow / decoration me aata hai (logo.azure), button/link me royal-leaning blue.
    accent:  { DEFAULT: '#0B5BEF', dark: '#0843C2', soft: '#EDF3FF', border: '#BCD2FA', text: '#0A3CA6' },
    logo:    { azure: '#00A0F8', royal: '#0000F8' },
    mist:    '#F3F6FB',
    info:    { DEFAULT: '#0B7285', bg: '#E6F6F8', border: '#B2DDE4' },
    done:    { DEFAULT: '#5B21B6', bg: '#EDE9FE', border: '#DDD6FE' },
    success: { DEFAULT: '#1F7A4D', bg: '#E6F5EC', border: '#B7E0C7' },
    stop:    { DEFAULT: '#B42318', bg: '#FCEBEA', border: '#F0C4C0' },
    warning: { DEFAULT: '#B45309', bg: '#FEF3E2', border: '#FBD9A5' },
    neutral: { DEFAULT: '#475569', bg: '#F1F5F9', border: '#E2E8F0' },
    // Categorical (kisi cheez ko pehchaan ke liye, status nahi): Gantt lanes, warehouse type, category icons.
    // Isme red / green / amber / royal-blue nahi hai — woh status aur brand ke liye reserved hain.
    cat1:    { DEFAULT: '#4338CA', bg: '#EEF0FD', border: '#C7CCF5' },   // indigo
    cat2:    { DEFAULT: '#0E7490', bg: '#E6F6F8', border: '#B2DDE4' },   // cyan
    cat3:    { DEFAULT: '#6D28D9', bg: '#F1EAFD', border: '#D9C8F7' },   // violet
    cat4:    { DEFAULT: '#A21CAF', bg: '#FAEAFB', border: '#EBC3F0' },   // magenta
    cat5:    { DEFAULT: '#BE185D', bg: '#FCE9F1', border: '#F3BFD6' },   // rose
    cat6:    { DEFAULT: '#475569', bg: '#EEF2F6', border: '#CBD5E1' },   // slate
    cat7:    { DEFAULT: '#8A5A2B', bg: '#F6EEE6', border: '#E3CDB6' }    // brown
  };

  if (window.tailwind) {
    window.tailwind.config = { theme: { extend: { colors: T } } };
  }

  // Tokens -> CSS variables  (ink: --ink, --ink-soft ...; accent: --accent, --accent-dark ...; mist: --mist)
  var root = document.documentElement.style;
  Object.keys(T).forEach(function (name) {
    var v = T[name];
    if (typeof v === 'string') { root.setProperty('--' + name, v); return; }
    Object.keys(v).forEach(function (k) {
      root.setProperty(k === 'DEFAULT' ? '--' + name : '--' + name + '-' + k, v[k]);
    });
  });

  // Neutral surfaces / lines (table, card, input) — cool grey, logo ke saath match
  var N = {
    '--line': '#D4DBE6', '--line-soft': '#E2E8F1', '--line-strong': '#C7D0DE',
    '--surface': '#FFFFFF', '--surface-2': '#F8FAFD', '--surface-3': '#E9EEF6'
  };
  Object.keys(N).forEach(function (k) { root.setProperty(k, N[k]); });
})();
