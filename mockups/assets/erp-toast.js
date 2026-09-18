/**
 * erp-toast.js — shared in-app toast (Chrome alert() ki jagah).
 * Use: showToast('Saved successfully', 'success' | 'error' | 'warning' | 'info')
 * Theme: Ink / Copper / Success / Stop — mockups ke saath match.
 */
(function () {
  if (window.showToast) return;

  var STYLE_ID = 'erp-toast-styles';
  var ROOT_ID = 'erp-toast-root';

  function ensureDom() {
    if (!document.getElementById(STYLE_ID)) {
      var style = document.createElement('style');
      style.id = STYLE_ID;
      style.textContent = [
        '#erp-toast-root{position:fixed;z-index:9999;top:1rem;right:1rem;display:flex;flex-direction:column;gap:0.5rem;max-width:min(22rem,calc(100vw - 2rem));pointer-events:none;}',
        '.erp-toast{pointer-events:auto;display:flex;align-items:flex-start;gap:0.65rem;padding:0.75rem 0.85rem;border-radius:8px;border:1px solid;box-shadow:0 8px 24px rgba(15,47,50,0.12);background:#fff;font-family:\'IBM Plex Sans\',ui-sans-serif,system-ui,sans-serif;font-size:13.5px;line-height:1.4;color:#0F2F32;animation:erpToastIn 0.22s ease-out;}',
        '.erp-toast.is-out{animation:erpToastOut 0.18s ease-in forwards;}',
        '.erp-toast__icon{flex-shrink:0;width:1.25rem;height:1.25rem;margin-top:1px;}',
        '.erp-toast__body{flex:1;min-width:0;white-space:pre-line;}',
        '.erp-toast__title{font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:2px;}',
        '.erp-toast__msg{color:#1C2B2D;}',
        '.erp-toast__close{flex-shrink:0;border:none;background:transparent;color:#6B7F82;cursor:pointer;font-size:1.1rem;line-height:1;padding:0 2px;border-radius:4px;}',
        '.erp-toast__close:hover{background:#F4F6F5;color:#0F2F32;}',
        '.erp-toast--success{border-color:#B7E0C7;background:#E6F5EC;}',
        '.erp-toast--success .erp-toast__title{color:#1F7A4D;}',
        '.erp-toast--error{border-color:#F0C4C0;background:#FCEBEA;}',
        '.erp-toast--error .erp-toast__title{color:#B42318;}',
        '.erp-toast--warning{border-color:#FBD9A5;background:#FEF3E2;}',
        '.erp-toast--warning .erp-toast__title{color:#B45309;}',
        '.erp-toast--info{border-color:#C5D9DA;background:#EAF3F3;}',
        '.erp-toast--info .erp-toast__title{color:#2A6B6E;}',
        '@keyframes erpToastIn{from{opacity:0;transform:translateY(-8px);}to{opacity:1;transform:translateY(0);}}',
        '@keyframes erpToastOut{to{opacity:0;transform:translateY(-6px);}}'
      ].join('');
      document.head.appendChild(style);
    }
    var root = document.getElementById(ROOT_ID);
    if (!root) {
      root = document.createElement('div');
      root.id = ROOT_ID;
      root.setAttribute('aria-live', 'polite');
      root.setAttribute('aria-relevant', 'additions');
      document.body.appendChild(root);
    }
    return root;
  }

  var TITLES = {
    success: 'Success',
    error: 'Error',
    warning: 'Check',
    info: 'Info'
  };

  var ICONS = {
    success: '<svg class="erp-toast__icon" fill="none" stroke="#1F7A4D" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
    error: '<svg class="erp-toast__icon" fill="none" stroke="#B42318" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
    warning: '<svg class="erp-toast__icon" fill="none" stroke="#B45309" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/></svg>',
    info: '<svg class="erp-toast__icon" fill="none" stroke="#2A6B6E" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'
  };

  /**
   * message: string (\\n allowed)
   * type: success | error | warning | info (default success)
   * durationMs: optional, default 3800 (0 = stay until close)
   */
  window.showToast = function (message, type, durationMs) {
    type = type || 'success';
    if (!ICONS[type]) type = 'info';
    if (durationMs === undefined) durationMs = 3800;

    var root = ensureDom();
    var el = document.createElement('div');
    el.className = 'erp-toast erp-toast--' + type;
    el.setAttribute('role', type === 'error' ? 'alert' : 'status');
    el.innerHTML =
      ICONS[type] +
      '<div class="erp-toast__body"><div class="erp-toast__title">' + TITLES[type] + '</div><div class="erp-toast__msg"></div></div>' +
      '<button type="button" class="erp-toast__close" aria-label="Dismiss">&times;</button>';
    el.querySelector('.erp-toast__msg').textContent = message == null ? '' : String(message);

    function dismiss() {
      if (el._gone) return;
      el._gone = true;
      el.classList.add('is-out');
      setTimeout(function () {
        if (el.parentNode) el.parentNode.removeChild(el);
      }, 180);
    }

    el.querySelector('.erp-toast__close').addEventListener('click', dismiss);
    root.appendChild(el);

    if (durationMs > 0) {
      setTimeout(dismiss, durationMs);
    }
    return { dismiss: dismiss };
  };
})();
