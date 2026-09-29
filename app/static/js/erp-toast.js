/**
 * erp-toast.js — shared toast + confirm (Chrome alert/confirm ki jagah).
 * Use: showToast('Saved successfully', 'success' | 'error' | 'warning' | 'info')
 * Use: showConfirm('Remove…?', { confirmText: 'Remove', cancelText: 'Cancel' }).then(ok => …)
 * Theme: Ink / Copper / Success / Stop — mockups ke saath match.
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
        '@keyframes erpToastOut{to{opacity:0;transform:translateY(-6px);}}',
        /* Confirm dialog — toast jaisa look, center overlay */
        '#erp-confirm-root{position:fixed;inset:0;z-index:10000;display:none;align-items:center;justify-content:center;padding:1rem;font-family:\'IBM Plex Sans\',ui-sans-serif,system-ui,sans-serif;}',
        '#erp-confirm-root.is-open{display:flex;}',
        '.erp-confirm__backdrop{position:absolute;inset:0;background:rgba(15,47,50,0.4);}',
        '.erp-confirm__panel{position:relative;width:100%;max-width:22rem;border-radius:10px;border:1px solid #FBD9A5;background:#FEF3E2;box-shadow:0 16px 40px rgba(15,47,50,0.18);padding:1rem 1.05rem;animation:erpToastIn 0.22s ease-out;}',
        '.erp-confirm__panel--wide{max-width:26rem;}',
        '.erp-confirm__top{display:flex;align-items:flex-start;gap:0.65rem;}',
        '.erp-confirm__title{font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:0.04em;color:#B45309;margin-bottom:4px;}',
        '.erp-confirm__msg{font-size:13.5px;line-height:1.45;color:#1C2B2D;white-space:pre-line;}',
        '.erp-confirm__msg p{margin:0 0 0.55rem;}',
        '.erp-confirm__msg p:last-child{margin-bottom:0;}',
        '.erp-confirm__card{background:#fff;border:1px solid #FBD9A5;border-radius:8px;padding:0.7rem 0.8rem;margin:0.55rem 0;}',
        '.erp-confirm__card-title{font-weight:600;font-size:13.5px;color:#0F2F32;margin-bottom:0.45rem;}',
        '.erp-confirm__card-code{font-weight:500;font-size:11.5px;color:#6B7F82;font-family:ui-monospace,monospace;}',
        '.erp-confirm__row{display:flex;justify-content:space-between;gap:0.75rem;font-size:13px;padding:0.15rem 0;color:#3D5A5D;}',
        '.erp-confirm__row strong{color:#0F2F32;font-variant-numeric:tabular-nums;}',
        '.erp-confirm__row--warn{color:#B45309;font-weight:600;}',
        '.erp-confirm__row--warn strong{color:#B45309;}',
        '.erp-confirm__hint{font-size:12.5px;color:#6B7F82;line-height:1.4;margin-top:0.35rem;}',
        '.erp-confirm__actions{display:flex;justify-content:flex-end;gap:0.5rem;margin-top:1rem;}',
        '.erp-confirm__btn{font-size:13.5px;font-weight:600;padding:0.45rem 0.85rem;border-radius:6px;border:1px solid;cursor:pointer;font-family:inherit;}',
        '.erp-confirm__btn--cancel{background:#fff;border-color:#CBD5E1;color:#3D5A5D;}',
        '.erp-confirm__btn--cancel:hover{background:#F4F6F5;}',
        '.erp-confirm__btn--ok{background:#B42318;border-color:#912018;color:#fff;}',
        '.erp-confirm__btn--ok:hover{background:#912018;}',
        '.erp-confirm__btn--ok.erp-confirm__btn--warning{background:#C46B2D;border-color:#A35522;}',
        '.erp-confirm__btn--ok.erp-confirm__btn--warning:hover{background:#A35522;}'
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

  /**
   * Toast-style confirm (browser confirm() ki jagah).
   * options: { title, confirmText, cancelText, variant: 'danger'|'warning', wide, html }
   * html:true → message ko HTML maan lo (sirf trusted/app-built HTML)
   * Returns Promise<boolean>
   */
  window.showConfirm = function (message, options) {
    options = options || {};
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
        '<div class="erp-confirm__panel' + (options.wide ? ' erp-confirm__panel--wide' : '') + '">' +
          '<div class="erp-confirm__top">' +
            ICONS.warning +
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
      if (options.variant === 'warning') {
        okBtn.classList.add('erp-confirm__btn--warning');
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

    window.showConfirm(msg, {
      title: title,
      confirmText: okText,
      cancelText: 'Cancel'
    }).then(function (ok) {
      if (!ok) return;
      form.setAttribute('data-erp-confirmed', '1');
      form.submit();
    });
  });
})();
