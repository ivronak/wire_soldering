/**
 * csrf.js — Phase 0 (P0-5): har POST ke saath CSRF token jaata hai, taaki koi dusri site hamare logged-in user ki taraf se
 * form / fetch bhej na sake. Token <meta name="csrf-token"> me hota hai (base.html / plain.html).
 *  1. Har <form method="post"> me hidden input "csrf_token" (page load par, aur baad me JS se bane forms me bhi).
 *  2. form.submit() (JS se seedha submit) aur normal submit dono se pehle token laga do.
 *  3. fetch() / XMLHttpRequest ke non-GET calls me header X-CSRFToken, aur sabhi fetch me "X-Requested-With: fetch"
 *     (isse server jaanta hai ki JSON jawab chahiye — session khatam ho to HTML redirect nahi, JSON 401).
 * GET forms (search / filter) me token nahi lagta — warna token URL me leak hota.
 */
(function () {
  'use strict';
  if (window.__erpCsrfLoaded) return;
  window.__erpCsrfLoaded = true;

  function token() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  }

  function isPostForm(form) {
    return form && form.tagName === 'FORM' && String(form.getAttribute('method') || '').toLowerCase() === 'post';
  }

  function sameOrigin(url) {
    try {
      return new URL(url, window.location.href).origin === window.location.origin;
    } catch (e) {
      return true;
    }
  }

  function addToken(form) {
    if (!isPostForm(form)) return;
    var value = token();
    if (!value) return;
    var existing = form.querySelector('input[name="csrf_token"]');
    if (existing) {
      existing.value = value;
      return;
    }
    var input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'csrf_token';
    input.value = value;
    form.appendChild(input);
  }

  function addAll(root) {
    var forms = (root || document).querySelectorAll ? (root || document).querySelectorAll('form') : [];
    for (var i = 0; i < forms.length; i++) addToken(forms[i]);
  }

  // 1) page load par + baad me JS se aaye forms (modal, runtime form) par
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { addAll(document); });
  } else {
    addAll(document);
  }
  document.addEventListener('DOMContentLoaded', function () {
    if (!window.MutationObserver) return;
    new MutationObserver(function (records) {
      records.forEach(function (record) {
        record.addedNodes.forEach(function (node) {
          if (node.nodeType !== 1) return;
          if (node.tagName === 'FORM') addToken(node);
          else if (node.querySelectorAll) addAll(node);
        });
      });
    }).observe(document.documentElement, { childList: true, subtree: true });
  });

  // 2) submit se pehle (user click) — capture phase me, taaki baaki handlers ke baad bhi form ke paas token ho
  document.addEventListener('submit', function (event) { addToken(event.target); }, true);

  // form.submit() event nahi chalata, isliye prototype patch
  var nativeSubmit = HTMLFormElement.prototype.submit;
  HTMLFormElement.prototype.submit = function () {
    addToken(this);
    return nativeSubmit.apply(this, arguments);
  };

  // 3) fetch wrapper
  if (window.fetch) {
    var nativeFetch = window.fetch;
    window.fetch = function (input, init) {
      init = init || {};
      var url = typeof input === 'string' ? input : (input && input.url) || '';
      if (sameOrigin(url)) {
        var method = String(init.method || (input && input.method) || 'GET').toUpperCase();
        var headers = new Headers(init.headers || (input && input.headers) || {});
        headers.set('X-Requested-With', 'fetch');
        if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') headers.set('X-CSRFToken', token());
        init.headers = headers;
        if (!init.credentials) init.credentials = 'same-origin';
      }
      return nativeFetch.call(this, input, init).then(function (response) {
        // Session khatam: JSON 401 aaya to user ko batao aur login par bhejo (page ka JS baaki jawab par na atke)
        if (response.status === 401 && response.headers.get('content-type') && response.headers.get('content-type').indexOf('json') !== -1) {
          if (window.showToast) window.showToast('Your session has ended. Please log in again.', 'error');
          setTimeout(function () { window.location.href = '/login?next=' + encodeURIComponent(window.location.pathname + window.location.search); }, 1200);
        }
        return response;
      });
    };
  }

  // XMLHttpRequest (agar kahin use ho)
  if (window.XMLHttpRequest) {
    var nativeOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (method, url) {
      this.__erpMethod = String(method || 'GET').toUpperCase();
      this.__erpUrl = url;
      return nativeOpen.apply(this, arguments);
    };
    var nativeSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function () {
      if (sameOrigin(this.__erpUrl || '')) {
        try {
          this.setRequestHeader('X-Requested-With', 'fetch');
          if (this.__erpMethod !== 'GET' && this.__erpMethod !== 'HEAD') this.setRequestHeader('X-CSRFToken', token());
        } catch (e) { /* open se pehle send hua to ignore */ }
      }
      return nativeSend.apply(this, arguments);
    };
  }
})();
