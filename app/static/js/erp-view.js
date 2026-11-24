/* erp-view.js — saare masters ke liye ek hi READ-ONLY "View details" drawer.
 *
 * Kaise kaam karta hai: row me ek button hota hai (macro view_btn, app/templates/_row_actions.html):
 *   <button class="act-btn js-view-details" data-view-title="Unit details" data-view-subtitle="KG"
 *           data-view='[["Code","KG"],["Name","Kilogram"],["Status","Active","success"]]'>
 * Click par yeh file drawer banati hai (pehli baar), pairs ko label/value rows me dikhati hai.
 *   - pair = [label, value]  ya  [label, value, tone]   tone: success | warning | stop | accent | neutral  (chhota chip banta hai)
 *   - khaali value "—" dikhti hai.
 * Security: sab kuch textContent se daalte hain (innerHTML me user data nahi), isliye data me < > ho to bhi script nahi chalti.
 * Keyboard: Esc se band, band hone par focus wapas usi eye-button par.
 */
(function () {
  var root, titleEl, subEl, bodyEl, closeBtn, lastFocus = null;

  function build() {
    root = document.createElement('div');
    root.className = 'vd-root';
    root.setAttribute('aria-hidden', 'true');
    // Yahan sirf fixed markup hai (user data nahi) — isliye innerHTML safe hai
    root.innerHTML =
      '<div class="vd-backdrop"></div>' +
      '<div class="vd-panel" role="dialog" aria-modal="true" aria-labelledby="vd-title">' +
        '<div class="vd-head"><div><h2 class="vd-title" id="vd-title"></h2><p class="vd-sub"></p></div>' +
        '<button type="button" class="vd-x" aria-label="Close">&times;</button></div>' +
        '<div class="vd-body"></div>' +
        '<div class="vd-foot"><button type="button" class="vd-close">Close</button></div>' +
      '</div>';
    document.body.appendChild(root);
    titleEl = root.querySelector('.vd-title');
    subEl = root.querySelector('.vd-sub');
    bodyEl = root.querySelector('.vd-body');
    closeBtn = root.querySelector('.vd-x');
    root.querySelector('.vd-backdrop').addEventListener('click', close);
    root.querySelector('.vd-x').addEventListener('click', close);
    root.querySelector('.vd-close').addEventListener('click', close);
  }

  function close() {
    if (!root) return;
    root.classList.remove('is-open');
    root.setAttribute('aria-hidden', 'true');
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  function open(btn) {
    if (!root) build();
    var pairs = [];
    try { pairs = JSON.parse(btn.getAttribute('data-view') || '[]'); } catch (e) { pairs = []; }
    titleEl.textContent = btn.getAttribute('data-view-title') || 'Details';
    subEl.textContent = btn.getAttribute('data-view-subtitle') || '';
    bodyEl.textContent = '';
    pairs.forEach(function (p) {
      var row = document.createElement('div'); row.className = 'vd-row';
      var lab = document.createElement('div'); lab.className = 'vd-label'; lab.textContent = p[0];
      var val = document.createElement('div'); val.className = 'vd-value';
      var text = (p[1] === null || p[1] === undefined || String(p[1]).trim() === '') ? '' : String(p[1]);
      if (!text) { val.classList.add('is-empty'); val.textContent = '—'; }
      else if (p[2]) { var chip = document.createElement('span'); chip.className = 'vd-chip ' + p[2]; chip.textContent = text; val.appendChild(chip); }
      else { val.textContent = text; }
      row.appendChild(lab); row.appendChild(val); bodyEl.appendChild(row);
    });
    lastFocus = btn;
    root.classList.add('is-open');
    root.setAttribute('aria-hidden', 'false');
    closeBtn.focus();
  }

  document.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('.js-view-details') : null;
    if (b) { e.preventDefault(); open(b); }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && root && root.classList.contains('is-open')) close();
  });
})();
