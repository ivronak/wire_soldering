/* Auto demo player (/demo): ERP ko iframe me chalata hai aur tour ke saare steps khud karta hai — cursor chalta hai, click / form / post hote hain —
 * aur har step ki Gujarati awaaz (static/audio/gu/<step-id>.mp3) bajti hai. Awaaz parent page se bajti hai (user ne "Shuru" dabaya, isliye
 * browser autoplay nahi rokta, chahe iframe me kitne bhi page badlein). Step data tour.js se (ERP_TOUR_API); yahan sirf player hai.
 */
(function () {
  'use strict';
  document.addEventListener('DOMContentLoaded', main);

  function main() {
    var API = window.ERP_TOUR_API;
    if (!API) { document.body.insertAdjacentHTML('beforeend', '<p style="color:#fff;padding:20px">Tour data load nahi hua.</p>'); return; }
    var $ = function (s) { return document.getElementById(s); };
    var frame = $('dm-frame'), ring = $('dm-ring'), cursor = $('dm-cursor');
    var shades = [$('dm-s0'), $('dm-s1'), $('dm-s2'), $('dm-s3')];

    // ---------------------------------------------------------------- steps (sab chapters ek line me)
    var items = [];
    API.chapters.forEach(function (c) { c.steps.forEach(function (st) { items.push({ ch: c, st: st }); }); });
    var N = items.length;

    var S = { i: 0, running: false, paused: false, skip: false, stopped: false, speed: 1, muted: false, run: 0 };
    var audio = null, cancelSpeech = null, targetEl = null, shadeOn = false, stepIdFor = {};

    // ---------------------------------------------------------------- pause / skip aware waiting
    function sleep(ms) {
      return new Promise(function (res) {
        var left = ms / S.speed, last = Date.now();
        (function tick() {
          if (S.stopped || S.skip) return res();
          var now = Date.now();
          if (!S.paused) left -= now - last;
          last = now;
          if (left <= 0) res(); else setTimeout(tick, 50);
        })();
      });
    }
    function waitWhilePaused() {
      return new Promise(function (res) { (function t() { if (!S.paused || S.stopped || S.skip) res(); else setTimeout(t, 100); })(); });
    }

    // ---------------------------------------------------------------- awaaz
    function speak(id, chars) {
      return new Promise(function (res) {
        var done = false;
        function fin() { if (!done) { done = true; cancelSpeech = null; wave(false); res(); } }
        cancelSpeech = function () { if (audio) { try { audio.pause(); } catch (e) { /* ignore */ } } fin(); };
        function fallback() { wave(true); sleep(Math.max(2500, chars * 70)).then(fin); }
        try {
          audio = new Audio('/static/audio/gu/' + id + '.mp3');
          audio.playbackRate = S.speed;
          audio.muted = S.muted;
          audio.onended = fin;
          audio.onerror = fallback;
          var p = audio.play();
          if (p && p.then) p.then(function () { wave(true); }).catch(fallback);
        } catch (e) { fallback(); }
      });
    }
    function wave(on) { $('dm-wave').classList.toggle('on', !!on); }

    // ---------------------------------------------------------------- iframe helpers
    var loadWaiters = [];
    frame.addEventListener('load', function () {
      try { API.setContext(frame.contentDocument, frame.contentWindow); } catch (e) { /* cross-origin nahi hona chahiye */ }
      var w = loadWaiters; loadWaiters = [];
      w.forEach(function (f) { f(); });
    });
    function fdoc() { return frame.contentDocument; }
    function fwin() { return frame.contentWindow; }
    function nextLoad(ms) {
      return new Promise(function (res) {
        var t = setTimeout(function () { res(false); }, ms || 9000);
        loadWaiters.push(function () { clearTimeout(t); setTimeout(function () { res(true); }, 350); });
      });
    }
    function visible(el) { if (!el) return false; var r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; }
    function poll(fn, ms, every) {
      return new Promise(function (res) {
        var t0 = Date.now();
        (function t() {
          if (S.stopped) return res(null);
          var v; try { v = fn(); } catch (e) { v = null; }
          if (v) return res(v);
          if (Date.now() - t0 > ms) return res(null);
          setTimeout(t, every || 150);
        })();
      });
    }
    function toastsNow() {
      var out = [];
      try {
        fdoc().querySelectorAll('.erp-toast').forEach(function (n) {
          out.push({ type: ((n.className.match(/erp-toast--(\w+)/) || [])[1] || 'info'), msg: (n.querySelector('.erp-toast__msg') || {}).textContent || '' });
        });
      } catch (e) { /* ignore */ }
      return out;
    }

    // ---------------------------------------------------------------- overlay: shade + ring + cursor
    function rectOf(el) {
      var r = el.getBoundingClientRect(), W = frame.clientWidth, H = frame.clientHeight, pad = 6;
      var x = Math.max(0, r.left - pad), y = Math.max(0, r.top - pad);
      return { x: x, y: y, w: Math.max(0, Math.min(W - x, r.width + pad * 2)), h: Math.max(0, Math.min(H - y, r.height + pad * 2)) };
    }
    function layout() {
      var el = targetEl;
      if (!el || !visible(el)) { ring.style.display = 'none'; shades.forEach(function (s) { s.style.display = shadeOn ? 'block' : 'none'; if (shadeOn) { s.style.left = '0'; s.style.top = '0'; s.style.width = '100%'; s.style.height = (s === shades[0] ? '100%' : '0'); } }); return; }
      var q = rectOf(el), W = frame.clientWidth, H = frame.clientHeight;
      ring.style.display = 'block';
      ring.style.left = q.x + 'px'; ring.style.top = q.y + 'px'; ring.style.width = q.w + 'px'; ring.style.height = q.h + 'px';
      if (shadeOn) {
        var set = function (s, l, t, w, h) { s.style.display = 'block'; s.style.left = l + 'px'; s.style.top = t + 'px'; s.style.width = w + 'px'; s.style.height = h + 'px'; };
        set(shades[0], 0, 0, W, q.y); set(shades[1], 0, q.y + q.h, W, Math.max(0, H - q.y - q.h));
        set(shades[2], 0, q.y, q.x, q.h); set(shades[3], q.x + q.w, q.y, Math.max(0, W - q.x - q.w), q.h);
      } else { shades.forEach(function (s) { s.style.display = 'none'; }); }
    }
    (function loop() { try { layout(); } catch (e) { /* ignore */ } requestAnimationFrame(loop); })();

    function setTarget(el, shade) { targetEl = el; shadeOn = !!shade; }
    function moveCursor(el, where) {
      if (!el || !visible(el)) return Promise.resolve();
      var r = el.getBoundingClientRect();
      var x = r.left + (where === 'start' ? Math.min(40, r.width / 2) : r.width / 2), y = r.top + (where === 'start' ? Math.min(40, r.height / 2) : r.height / 2);
      cursor.style.display = 'block';
      cursor.style.left = Math.max(0, x - 4) + 'px'; cursor.style.top = Math.max(0, y - 4) + 'px';
      return sleep(950);
    }
    function ripple(el) {
      if (!el) return;
      var r = el.getBoundingClientRect(), d = document.createElement('div');
      d.className = 'dm-ripple'; d.style.left = (r.left + r.width / 2) + 'px'; d.style.top = (r.top + r.height / 2) + 'px';
      $('dm-overlay').appendChild(d); setTimeout(function () { d.remove(); }, 650);
    }

    // ---------------------------------------------------------------- caption / progress
    function setCaption(item, action) {
      $('dm-chip').textContent = item.ch.title;
      $('dm-title').innerHTML = item.st.title;
      $('dm-text').innerHTML = item.st.text;
      $('dm-act').textContent = action || '';
      $('dm-count').textContent = 'પગલું ' + (S.i + 1) + ' / ' + N;
      $('dm-bar').style.width = Math.round(100 * S.i / N) + '%';
    }

    // ---------------------------------------------------------------- step helpers
    function isNavClick(el) {
      if (!el) return false;
      if (el.closest && el.closest('a[href]')) { var a = el.closest('a[href]'); var h = a.getAttribute('href') || ''; return h && h.charAt(0) !== '#' && h.indexOf('javascript') !== 0; }
      return !!(el.matches && el.matches('.erp-confirm__btn--ok'));
    }
    function findSubmit(form, st) {
      var d = fdoc(), id = form.id, b = null;
      if (id) {
        b = st.submitter ? d.querySelector('[form="' + id + '"][value="' + st.submitter + '"]') : d.querySelector('button[form="' + id + '"]:not([type=button])');
      }
      return b || form.querySelector('button[type=submit], input[type=submit]');
    }
    function stepError(msg) { var e = new Error(msg); e.demo = true; return e; }

    function afterLoadChecks(st) {
      // naye page par toast: error to rok do; success me order no pakdo
      var ts = toastsNow();
      var bad = ts.filter(function (t) { return t.type === 'error' || t.type === 'warning'; })[0];
      if (bad) throw stepError('સિસ્ટમે કહ્યું: ' + bad.msg);
      if (st.capture) {
        var txt = ts.filter(function (t) { return t.type === 'success'; }).map(function (t) { return t.msg; }).join(' ');
        var m = txt.match(new RegExp(st.capture.re));
        if (m) API.setVar(st.capture.as, m[0]);
      }
    }

    // ---------------------------------------------------------------- ek step chalao
    function runStep(item) {
      var st = item.st;
      var chars = (st.text || '').replace(/<[^>]+>/g, '').length;
      setTarget(null, false);
      cursor.style.display = S.i === 0 ? 'none' : cursor.style.display;
      var navPromise = null;

      return Promise.resolve().then(function () {
        setCaption(item, '');
        // 1. sahi page par ho?
        return poll(function () { return API.pathOk(st) && fdoc() && fdoc().readyState === 'complete'; }, 3500).then(function (ok) {
          if (ok) return;
          var url = API.gotoUrl(st);
          var p = nextLoad(9000); fwin().location.href = url; return p;
        });
      }).then(function () {
        // 2. target dhundho
        if (!st.target) return null;
        return poll(function () { var el = API.resolve(st); return visible(el) ? el : null; }, 9000).then(function (el) {
          if (!el) throw stepError('સ્ક્રીન પર "' + st.title.replace(/<[^>]+>/g, '') + '" માટેની જગ્યા મળી નહિ.');
          return el;
        });
      }).then(function (el) {
        // 3. spotlight + (kaam) + awaaz
        if (el) { try { el.scrollIntoView({ block: 'center', behavior: 'auto' }); } catch (e) { /* ignore */ } }
        return sleep(250).then(function () { return el; });
      }).then(function (el) {
        var type = st.type;
        setTarget(el, type === 'info' || type === 'click' || type === 'action');
        var label = { info: '', click: '👆 ક્લિક કરે છે', fill: '✍️ ફોર્મ ભરે છે', submit: '✅ પોસ્ટ કરે છે', action: '⚡ શૉર્ટકટ ચલાવે છે' }[type] || '';
        setCaption(item, label);
        var speech = speak(st.id, chars);
        // pichhle steps ke liye cursor pehle target par
        var move = (type === 'info') ? Promise.resolve() : moveCursor(el, type === 'fill' ? 'start' : 'center');

        if (type === 'info') return speech.then(function () { return sleep(450); });

        if (type === 'click') {
          return Promise.all([speech, move]).then(waitWhilePaused).then(function () {
            if (S.skip) { /* skip: seedha click */ }
            ripple(el);
            var nav = isNavClick(el);
            if (nav) navPromise = nextLoad(9000);
            el.click();
            return nav ? navPromise.then(function () { afterLoadChecks(st); return sleep(150); }) : sleep(750);
          });
        }

        if (type === 'fill') {
          var fill = sleep(900).then(function () { return st.prefill ? st.prefill.run() : null; });
          return Promise.all([speech, move, fill]).then(function () { return sleep(500); });
        }

        if (type === 'submit') {
          // pehle form bharna (agar is step me prefill hai), phir post
          var pre = st.prefill ? sleep(700).then(function () { return st.prefill.run(); }) : Promise.resolve();
          return Promise.all([speech, pre]).then(waitWhilePaused).then(function () {
            var form = API.resolve(st);
            var btn = form && findSubmit(form, st);
            if (!btn) throw stepError('પોસ્ટ બટન મળ્યું નહિ.');
            return moveCursor(btn, 'center').then(function () {
              ripple(btn);
              navPromise = nextLoad(12000);
              btn.click();
              return navPromise;
            }).then(function (loaded) {
              if (!loaded) throw stepError('પેજ બદલાયું નહિ — ફોર્મમાં કોઈ ભૂલ હોઈ શકે.');
              afterLoadChecks(st);
              return sleep(150);
            });
          });
        }

        if (type === 'action') {
          return Promise.all([speech, move]).then(waitWhilePaused).then(function () {
            return st.button.run();
          }).then(function () {
            var p = nextLoad(9000); fwin().location.reload(); return p;
          }).then(function () { afterLoadChecks(st); return sleep(150); });
        }
        return Promise.resolve();
      });
    }

    // ---------------------------------------------------------------- main loop
    function loopFrom(token) {
      if (token !== S.run || S.stopped) return;
      if (S.i >= N) { finish(); return; }
      S.skip = false;
      runStep(items[S.i]).then(function () {
        if (token !== S.run) return;
        S.skip = false; S.i++; loopFrom(token);
      }).catch(function (e) {
        if (token !== S.run || S.stopped) return;
        S.skip = false;
        showError((e && e.message) || String(e), token);
      });
    }
    function showError(msg, token) {
      stopAudio();
      $('dm-err-msg').textContent = msg;
      $('dm-err').classList.add('show');
      $('dm-err-retry').onclick = function () { $('dm-err').classList.remove('show'); loopFrom(token); };
      $('dm-err-skip').onclick = function () { $('dm-err').classList.remove('show'); S.i++; loopFrom(token); };
      $('dm-err-stop').onclick = stop;
    }
    function stopAudio() { if (cancelSpeech) cancelSpeech(); if (audio) { try { audio.pause(); } catch (e) { /* ignore */ } } wave(false); }
    function finish() {
      setTarget(null, false); cursor.style.display = 'none';
      $('dm-bar').style.width = '100%';
      $('dm-end').classList.add('show');
    }
    function stop() { S.stopped = true; S.run++; stopAudio(); location.href = '/production_orders'; }

    function begin() {
      S.i = 0; S.stopped = false; S.paused = false; S.skip = false; S.run++;
      $('dm-start').classList.remove('show'); $('dm-end').classList.remove('show');
      // pehli awaaz ke liye audio unlock (user ne abhi click kiya hai)
      try { var u = new Audio('/static/audio/gu/welcome.mp3'); u.muted = true; u.play().then(function () { u.pause(); }).catch(function () { /* ignore */ }); } catch (e) { /* ignore */ }
      API.setVar('order', undefined);
      try { API.setContext(frame.contentDocument, frame.contentWindow); } catch (e) { /* ignore */ }
      loopFrom(S.run);
    }

    // ---------------------------------------------------------------- controls
    $('dm-ok').addEventListener('change', function () { $('dm-go').disabled = !$('dm-ok').checked; });
    $('dm-go').addEventListener('click', begin);
    $('dm-again').addEventListener('click', function () { $('dm-end').classList.remove('show'); begin(); });
    $('dm-pause').addEventListener('click', togglePause);
    function togglePause() {
      S.paused = !S.paused;
      $('dm-pause').textContent = S.paused ? '▶ ચાલુ' : '⏸ થોભો';
      $('dm-pause').classList.toggle('on', S.paused);
      if (audio) { try { if (S.paused) audio.pause(); else audio.play(); } catch (e) { /* ignore */ } }
    }
    $('dm-skip').addEventListener('click', function () {
      S.skip = true; if (S.paused) togglePause();
      if (cancelSpeech) cancelSpeech();
    });
    $('dm-speed').addEventListener('change', function () { S.speed = parseFloat($('dm-speed').value) || 1; if (audio) audio.playbackRate = S.speed; });
    $('dm-mute').addEventListener('click', function () { S.muted = !S.muted; $('dm-mute').textContent = S.muted ? '🔇' : '🔊'; if (audio) audio.muted = S.muted; });
    $('dm-cc').addEventListener('click', function () { var c = $('dm-caption'); c.classList.toggle('hide'); $('dm-cc').classList.toggle('on', !c.classList.contains('hide')); });
    $('dm-stop').addEventListener('click', function () { if (window.confirm('ડેમો બંધ કરવો છે? (બનેલી એન્ટ્રીઓ સિસ્ટમમાં રહેશે.)')) stop(); });
    document.addEventListener('keydown', function (e) {
      if (e.code === 'Space' && S.run > 0 && !$('dm-start').classList.contains('show') && !/INPUT|SELECT|TEXTAREA|BUTTON/.test((e.target || {}).tagName || '')) { e.preventDefault(); togglePause(); }
    });

    // test ke liye: /demo?speed=4&mute=1 (tez + bina awaaz)
    var q = /[?&]speed=([\d.]+)/.exec(location.search);
    if (q) { S.speed = parseFloat(q[1]) || 1; var o = document.createElement('option'); o.value = String(S.speed); o.textContent = S.speed + '×'; $('dm-speed').appendChild(o); $('dm-speed').value = String(S.speed); }
    if (/[?&]mute=1/.test(location.search)) { S.muted = true; $('dm-mute').textContent = '🔇'; }
    if (/[?&]autostart=1/.test(location.search)) { $('dm-ok').checked = true; $('dm-go').disabled = false; setTimeout(begin, 600); }
    // initial caption + context
    $('dm-count').textContent = 'પગલું 0 / ' + N;
    frame.addEventListener('load', function once() { /* pehla load: context set (upar wala handler karta hai) */ });
    window.__demo = { state: S, items: items, begin: begin };
  }
})();
