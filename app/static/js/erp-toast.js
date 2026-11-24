/**
 * erp-toast.js — shared toast + confirm (Chrome alert/confirm ki jagah).
 * Use: showToast('Saved successfully', 'success' | 'error' | 'warning' | 'info')
 * Use: showConfirm('Remove…?', { confirmText: 'Remove', cancelText: 'Cancel' }).then(ok => …)
 * Theme: Ink / Accent (blue) / Info / Success / Warning / Stop — app/static/js/theme.js ke tokens ke saath match (yahan JS string me exact hex hain).
 * Confirm variants: 'danger' (default, laal — Remove / Cancel jaise destructive), 'warning' (amber), 'neutral' (accent blue — Post / Start jaise constructive).
 */
(function () {
  if (window.showToast) return;

  var STYLE_ID = 'erp-toast-styles';
  var ROOT_ID = 'erp-toast-root';
  var CONFIRM_ID = 'erp-confirm-root';

  function ensureDom() {
    if (!document.getElementById(STYLE_ID)) {
      var style = document.createElement('style');
      style.id = STYLE_ID;
      style.textContent = [
        '#erp-toast-root{position:fixed;z-index:9999;top:1rem;right:1rem;display:flex;flex-direction:column;gap:0.5rem;max-width:min(22rem,calc(100vw - 2rem));pointer-events:none;}',
        '.erp-toast{pointer-events:auto;display:flex;align-items:flex-start;gap:0.65rem;padding:0.75rem 0.85rem;border-radius:8px;border:1px solid;box-shadow:0 8px 24px rgba(11,18,32,0.12);background:#fff;font-family:\'IBM Plex Sans\',ui-sans-serif,system-ui,sans-serif;font-size:13.5px;line-height:1.4;color:#0B1220;animation:erpToastIn 0.22s ease-out;}',
        '.erp-toast.is-out{animation:erpToastOut 0.18s ease-in forwards;}',
        '.erp-toast__icon{flex-shrink:0;width:1.25rem;height:1.25rem;margin-top:1px;}',
        '.erp-toast__body{flex:1;min-width:0;white-space:pre-line;}',
        '.erp-toast__title{font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:2px;}',
        '.erp-toast__msg{color:#0B1220;}',
        '.erp-toast__close{flex-shrink:0;border:none;background:transparent;color:#5A6577;cursor:pointer;font-size:1.1rem;line-height:1;padding:0 2px;border-radius:4px;}',
        '.erp-toast__close:hover{background:#F1F5F9;color:#0B1220;}',
        '.erp-toast--success{border-color:#B7E0C7;background:#E6F5EC;}',
        '.erp-toast--success .erp-toast__title{color:#1F7A4D;}',
        '.erp-toast--error{border-color:#F0C4C0;background:#FCEBEA;}',
        '.erp-toast--error .erp-toast__title{color:#B42318;}',
        '.erp-toast--warning{border-color:#FBD9A5;background:#FEF3E2;}',
        '.erp-toast--warning .erp-toast__title{color:#B45309;}',
        '.erp-toast--info{border-color:#B2DDE4;background:#E6F6F8;}',
        '.erp-toast--info .erp-toast__title{color:#0B7285;}',
        '@keyframes erpToastIn{from{opacity:0;transform:translateY(-8px);}to{opacity:1;transform:translateY(0);}}',
        '@keyframes erpToastOut{to{opacity:0;transform:translateY(-6px);}}',
        /* Confirm dialog — toast jaisa look, center overlay */
        '#erp-confirm-root{position:fixed;inset:0;z-index:10000;display:none;align-items:center;justify-content:center;padding:1rem;font-family:\'IBM Plex Sans\',ui-sans-serif,system-ui,sans-serif;}',
        '#erp-confirm-root.is-open{display:flex;}',
        '.erp-confirm__backdrop{position:absolute;inset:0;background:rgba(11,18,32,0.4);}',
        '.erp-confirm__panel{position:relative;width:100%;max-width:22rem;border-radius:10px;border:1px solid #F0C4C0;background:#FCEBEA;box-shadow:0 16px 40px rgba(11,18,32,0.18);padding:1rem 1.05rem;animation:erpToastIn 0.22s ease-out;}',
        /* Panel ka rang variant se: default = danger (laal), warning = amber, neutral = accent-soft */
        '.erp-confirm__panel--warning{border-color:#FBD9A5;background:#FEF3E2;}',
        '.erp-confirm__panel--neutral{border-color:#BCD2FA;background:#EDF3FF;}',
        '.erp-confirm__panel--wide{max-width:26rem;}',
        '.erp-confirm__top{display:flex;align-items:flex-start;gap:0.65rem;}',
        '.erp-confirm__title{font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:0.04em;color:#B42318;margin-bottom:4px;}',
        '.erp-confirm__panel--warning .erp-confirm__title{color:#B45309;}',
        '.erp-confirm__panel--neutral .erp-confirm__title{color:#0A3CA6;}',
        '.erp-confirm__msg{font-size:13.5px;line-height:1.45;color:#0B1220;white-space:pre-line;}',
        '.erp-confirm__msg p{margin:0 0 0.55rem;}',
        '.erp-confirm__msg p:last-child{margin-bottom:0;}',
        '.erp-confirm__card{background:#fff;border:1px solid #F0C4C0;border-radius:8px;padding:0.7rem 0.8rem;margin:0.55rem 0;}',
        '.erp-confirm__panel--warning .erp-confirm__card{border-color:#FBD9A5;}',
        '.erp-confirm__panel--neutral .erp-confirm__card{border-color:#BCD2FA;}',
        '.erp-confirm__card-title{font-weight:600;font-size:13.5px;color:#0B1220;margin-bottom:0.45rem;}',
        '.erp-confirm__card-code{font-weight:500;font-size:11.5px;color:#5A6577;font-family:ui-monospace,monospace;}',
        '.erp-confirm__row{display:flex;justify-content:space-between;gap:0.75rem;font-size:13px;padding:0.15rem 0;color:#475266;}',
        '.erp-confirm__row strong{color:#0B1220;font-variant-numeric:tabular-nums;}',
        '.erp-confirm__row--warn{color:#B45309;font-weight:600;}',
        '.erp-confirm__row--warn strong{color:#B45309;}',
        '.erp-confirm__hint{font-size:12.5px;color:#5A6577;line-height:1.4;margin-top:0.35rem;}',
        '.erp-confirm__actions{display:flex;justify-content:flex-end;gap:0.5rem;margin-top:1rem;}',
        '.erp-confirm__btn{font-size:13.5px;font-weight:600;padding:0.45rem 0.85rem;border-radius:6px;border:1px solid;cursor:pointer;font-family:inherit;}',
        '.erp-confirm__btn--cancel{background:#fff;border-color:#CBD5E1;color:#475266;}',
        '.erp-confirm__btn--cancel:hover{background:#F1F5F9;}',
        '.erp-confirm__btn--ok{background:#B42318;border-color:#912018;color:#fff;}',
        '.erp-confirm__btn--ok:hover{background:#912018;}',
        '.erp-confirm__btn--ok.erp-confirm__btn--warning{background:#B45309;border-color:#92400E;}',
        '.erp-confirm__btn--ok.erp-confirm__btn--warning:hover{background:#92400E;}',
        '.erp-confirm__btn--ok.erp-confirm__btn--neutral{background:#0B5BEF;border-color:#0843C2;}',
        '.erp-confirm__btn--ok.erp-confirm__btn--neutral:hover{background:#0843C2;}'
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
    info: '<svg class="erp-toast__icon" fill="none" stroke="#0B7285" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'
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

  /**
   * Toast-style confirm (browser confirm() ki jagah).
   * options: { title, confirmText, cancelText, variant: 'danger'|'warning'|'neutral', wide, html }
   * variant: danger (default) = laal panel + laal button; warning = amber; neutral = accent blue (Post / Start jaise constructive confirm)
   * html:true → message ko HTML maan lo (sirf trusted/app-built HTML)
   * Returns Promise<boolean>
   */
  window.showConfirm = function (message, options) {
    options = options || {};
    var variant = (options.variant === 'warning' || options.variant === 'neutral') ? options.variant : 'danger';
    // Icon bhi variant ke rang me: danger = laal triangle, warning = amber triangle, neutral = accent info icon
    var icon = variant === 'warning' ? ICONS.warning
      : variant === 'neutral' ? ICONS.info.replace('#0B7285', '#0B5BEF')
      : ICONS.warning.replace('#B45309', '#B42318');
    ensureDom();

    return new Promise(function (resolve) {
      var existing = document.getElementById(CONFIRM_ID);
      if (existing) existing.parentNode.removeChild(existing);

      var root = document.createElement('div');
      root.id = CONFIRM_ID;
      root.className = 'is-open';
      root.setAttribute('role', 'dialog');
      root.setAttribute('aria-modal', 'true');
      root.innerHTML =
        '<div class="erp-confirm__backdrop" data-erp-confirm="cancel"></div>' +
        '<div class="erp-confirm__panel erp-confirm__panel--' + variant + (options.wide ? ' erp-confirm__panel--wide' : '') + '">' +
          '<div class="erp-confirm__top">' +
            icon +
            '<div style="min-width:0;flex:1">' +
              '<div class="erp-confirm__title"></div>' +
              '<div class="erp-confirm__msg"></div>' +
            '</div>' +
          '</div>' +
          '<div class="erp-confirm__actions">' +
            '<button type="button" class="erp-confirm__btn erp-confirm__btn--cancel" data-erp-confirm="cancel"></button>' +
            '<button type="button" class="erp-confirm__btn erp-confirm__btn--ok" data-erp-confirm="ok"></button>' +
          '</div>' +
        '</div>';

      root.querySelector('.erp-confirm__title').textContent = options.title || 'Please confirm';
      var msgEl = root.querySelector('.erp-confirm__msg');
      if (options.html) {
        msgEl.style.whiteSpace = 'normal';
        msgEl.innerHTML = message == null ? '' : String(message);
      } else {
        msgEl.textContent = message == null ? '' : String(message);
      }
      root.querySelector('[data-erp-confirm="cancel"].erp-confirm__btn').textContent = options.cancelText || 'Cancel';
      var okBtn = root.querySelector('[data-erp-confirm="ok"]');
      okBtn.textContent = options.confirmText || 'Confirm';
      if (variant !== 'danger') {
        okBtn.classList.add('erp-confirm__btn--' + variant);
      }

      function finish(ok) {
        document.removeEventListener('keydown', onKey);
        if (root.parentNode) root.parentNode.removeChild(root);
        resolve(!!ok);
      }

      function onKey(e) {
        if (e.key === 'Escape') finish(false);
        if (e.key === 'Enter') finish(true);
      }

      root.addEventListener('click', function (e) {
        var action = e.target.getAttribute('data-erp-confirm');
        if (action === 'cancel') finish(false);
        if (action === 'ok') finish(true);
      });

      document.addEventListener('keydown', onKey);
      document.body.appendChild(root);
      okBtn.focus();
    });
  };

  // Soft-delete / confirm forms: class="js-confirm-submit" + data-confirm-message
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form || !form.classList || !form.classList.contains('js-confirm-submit')) return;
    if (form.getAttribute('data-erp-confirmed') === '1') return;

    e.preventDefault();
    var msg = form.getAttribute('data-confirm-message') || 'Are you sure?';
    var title = form.getAttribute('data-confirm-title') || 'Please confirm';
    var okText = form.getAttribute('data-confirm-ok') || 'Confirm';
    // Variant: form par data-confirm-variant ho to wahi; warna button ke text se andaza — Post / Start / Release jaise constructive kaam neutral (accent),
    // baaki (Remove / Cancel ...) danger (laal) hi rehte hain jaisa pehle tha.
    var variant = form.getAttribute('data-confirm-variant') ||
      (/^(post|start|resume|reopen|release|receive|open pack|issue|approve|finali[sz]e|dispatch|complete)/i.test(okText) ? 'neutral' : 'danger');

    window.showConfirm(msg, {
      title: title,
      confirmText: okText,
      variant: variant,
      cancelText: 'Cancel'
    }).then(function (ok) {
      if (!ok) return;
      form.setAttribute('data-erp-confirmed', '1');
      form.submit();
    });
  });
})();
