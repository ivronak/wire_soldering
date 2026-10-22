/* Demo tour (Gujarati) — ERP me hi chalne wala guided tour.
 * User asli me step karta hai (click / form bharna / post karna); tour spotlight dikhata hai aur Gujarati me samjhata hai.
 * State localStorage me (page badalne par bhi tour aage chalta hai). Koi library nahi, sirf vanilla JS.
 *
 * Step ke prakar:
 *   info   -> padho, "આગળ" dabao
 *   click  -> target par asli click karo (link / button); click hote hi tour aage badhta hai
 *   submit -> form asli me submit karo (valid hone par); error aaya to tour wapas us step par le jaata hai
 *   action -> tour ka button (demo shortcut) kuch kaam karta hai
 */
(function () {
  'use strict';
  var KEY = 'erpTourV1';
  var DEV_KEY = 'erpTourAuto';
  var toasts = [];                 // is page load par jo toast aaye (type + message) — submit ka natija jaanchne ke liye
  var infoCache = null;

  // ---------------------------------------------------------------- toast observer (jaldi lagao, flash toast pehle aate hain)
  new MutationObserver(function (muts) {
    muts.forEach(function (m) {
      m.addedNodes.forEach(function (n) {
        if (n.nodeType !== 1 || !n.classList || !n.classList.contains('erp-toast')) return;
        var type = (n.className.match(/erp-toast--(\w+)/) || [])[1] || 'info';
        var msg = (n.querySelector('.erp-toast__msg') || {}).textContent || '';
        toasts.push({ type: type, msg: msg });
      });
    });
  }).observe(document.documentElement, { childList: true, subtree: true });

  // ---------------------------------------------------------------- helpers
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function path() { return location.pathname; }
  function setVal(el, value) {
    if (!el) return;
    el.value = value;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }
  function load() { try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { return null; } }
  function save(s) { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) { /* private mode */ } }
  function clearState() { try { localStorage.removeItem(KEY); } catch (e) { /* ignore */ } }
  function getInfo() {
    if (infoCache) return Promise.resolve(infoCache);
    return fetch('/tour/info').then(function (r) { return r.json(); }).then(function (j) { infoCache = j; return j; });
  }
  function navLink(href) { return 'aside a.nav-link[href="' + href + '"]'; }
  // Is order wala card (production queue / issue / routing / output ... ka koi bhi card)
  function orderCard(sel) {
    var cards = $$(sel);
    var no = state && state.vars && state.vars.order;
    if (no) {
      for (var i = 0; i < cards.length; i++) if (cards[i].textContent.indexOf(no) !== -1) return cards[i];
    }
    return cards[0] || null;
  }
  function inCard(sel, inner) { return function () { var c = orderCard(sel); return c ? $(inner, c) : null; }; }

  // ---------------------------------------------------------------- chapters (Gujarati)
  var CH = [];

  CH.push({
    id: 'intro', title: 'ERP ની ઓળખ', desc: 'ટૂર કેવી રીતે ચાલે છે અને મેનુ કેવું છે — ૩ પગલાં.',
    steps: [
      { id: 'welcome', type: 'info', title: 'ડેમો ટૂરમાં સ્વાગત છે! 🎓',
        text: 'આ ટૂરમાં તમે <b>સ્ટોકથી લઈને તૈયાર માલ, સ્ક્રેપ અને તફાવત (variance)</b> સુધી બધું <b>જાતે કરીને</b> શીખશો.<br>દરેક પગલું આ કાર્ડમાં સરળ ગુજરાતીમાં સમજાવ્યું છે. જ્યાં <b>નારંગી ચમકતી લાઇન</b> દેખાય, ત્યાં જ તમારે ક્લિક કરવાનું છે.',
        warn: 'ધ્યાન: ટૂર <b>સાચી એન્ટ્રીઓ</b> બનાવશે (સ્ટોક, ઓર્ડર વગેરે). તેથી ટ્રેનિંગ / ડેમો માટે જ ચલાવો.' },
      { id: 'sidebar', type: 'info', target: 'aside', title: 'ડાબી બાજુનું મેનુ',
        text: 'આખું ERP આ મેનુમાંથી ચાલે છે. ત્રણ ભાગ છે:<ul><li><b>Procurement</b> — ખરીદી (PO, GRN, QC, બિલ)</li><li><b>Inventory</b> — સ્ટોક</li><li><b>Manufacturing</b> — ઉત્પાદન</li></ul>આપણે <b>Inventory (સ્ટોક)</b> થી શરૂ કરીશું.' },
      { id: 'howto', type: 'info', title: 'ટૂર કેવી રીતે વાપરવી',
        text: '<ul><li><b>આગળ</b> — વાંચીને આગળ વધો</li><li>જ્યારે કહ્યું હોય કે <b>"ક્લિક કરો"</b>, ત્યારે ચમકતી જગ્યાએ જાતે ક્લિક કરો — પછી ટૂર આપોઆપ આગળ જશે</li><li><b>ડેમો વેલ્યુ ભરો</b> બટન ફોર્મ ઝડપથી ભરી આપે છે (તમે બદલી પણ શકો)</li><li>અટકી જાઓ તો <b>પગલું છોડો</b> કે <b>પાછળ</b> દબાવો; ગમે ત્યારે <b>બહાર નીકળો</b></li></ul>' }
    ]
  });

  CH.push({
    id: 'stock', title: 'સ્ટોક (Inventory)', desc: 'Opening stock ચઢાવો, Stock ledger, લોટ, Valuation, Transfer, Adjustment.',
    steps: [
      { id: 'os-link', type: 'click', target: navLink('/opening_stock'), title: 'Opening stock ખોલો',
        text: 'ડાબા મેનુમાં <b>Inventory</b> હેઠળ <b>Opening stock</b> દેખાય છે.', todo: 'ક્લિક કરો: Opening stock' },
      { id: 'os-what', type: 'info', path: '/opening_stock', target: 'main h1', title: 'Opening stock એટલે શું?',
        text: 'સોફ્ટવેર શરૂ કરતાં પહેલાં તમારા ગોડાઉનમાં જે માલ પડ્યો હતો, તે પહેલી વાર અહીંથી સોફ્ટવેરમાં ચઢાવવાનો હોય છે. એ પછી ખરીદી (GRN) થી માલ આપોઆપ આવતો રહે છે.' },
      { id: 'os-new', type: 'click', path: '/opening_stock', target: '#btn-new-os', title: 'નવો Opening stock',
        text: 'ઉપર <b>+ New opening stock</b> બટન છે.', todo: 'ક્લિક કરો: + New opening stock' },
      { id: 'os-fill', type: 'fill', path: '/opening_stock', target: '#os-form', title: 'માલની વિગત ભરો',
        text: 'તારીખ, <b>ગોડાઉન (Store)</b>, અને દરેક material માટે <b>Quantity</b> તથા <b>Cost</b> (પ્રતિ યુનિટ ભાવ) ભરો.<br>નીચેનું બટન દબાવશો તો ડેમો ઓર્ડર માટે જોઈતો કાચો માલ (Tin, Lead, Flux) આપોઆપ ભરાઈ જશે.',
        prefill: { label: 'ડેમો વેલ્યુ ભરો', run: prefillOpeningStock } },
      { id: 'os-post', type: 'submit', path: '/opening_stock', target: '#os-form', submitter: 'post', retryTo: 'os-new', title: 'Post કરો',
        text: 'બધું બરાબર ભર્યું હોય તો નીચે <b>Post</b> બટન દબાવો. <b>Post</b> કરતાં જ માલ તમારા સ્ટોકમાં ચઢી જાય છે. (<b>Save as draft</b> માં માત્ર સેવ થાય, સ્ટોક ન વધે.)', todo: 'ક્લિક કરો: Post' },
      { id: 'os-done', type: 'info', path: '/opening_stock', target: 'main table tbody tr', title: 'સરસ! સ્ટોક ચઢી ગયો ✅',
        text: 'તમારી એન્ટ્રી <b>Posted</b> થઈ. હવે આ માલ સ્ટોકમાં દેખાશે અને ઉત્પાદનમાં વાપરી શકાશે. (ભૂલ થાય તો અહીંથી <b>Cancel</b> થઈ શકે — જો માલ વપરાયો ન હોય તો.)' },
      { id: 'st-link', type: 'click', target: navLink('/inventory/stock'), title: 'Stock ledger ખોલો', text: 'હવે જોઈએ કે સ્ટોકમાં માલ ક્યાં કેટલો છે.', todo: 'ક્લિક કરો: Stock ledger' },
      { id: 'st-kpi', type: 'info', path: '/inventory/stock', target: '.sc-card', title: 'ઉપરના ચાર કાર્ડ',
        text: 'આખા સ્ટોકનો એક નજરમાં હિસાબ: <b>કેટલા material</b>, <b>સ્ટોકની કિંમત</b>, <b>QC માટે રાહ જોતા લોટ</b> અને <b>રિજેક્ટ થયેલા લોટ</b>. જો કોઈ material ઓછો થઈ જાય તો નીચે <b>"Needs attention"</b> માં લાલ ચેતવણી પણ આવે છે.' },
      { id: 'st-card', type: 'info', path: '/inventory/stock', target: '.stock-card', title: 'Material પ્રમાણે સ્ટોક',
        text: 'દરેક material નું કાર્ડ: <ul><li><b>Available</b> — વાપરવા લાયક માલ (સ્ટોરમાં)</li><li><b>Waiting for QC</b> — ખરીદી આવી, QC બાકી</li><li><b>In production</b> — ઉત્પાદનમાં (WIP) ગયેલો માલ</li><li><b>Rejected</b> — QC માં નાપાસ</li></ul>' },
      { id: 'st-lot', type: 'info', path: '/inventory/stock', target: '.lot-row', title: 'લોટ (Lot) એટલે શું?',
        text: 'દરેક <b>લોટ</b> = માલનો એક જથ્થો (<code>LOT-0001</code>). Opening stock અને દરેક ખરીદીનો પોતાનો લોટ બને છે, જેથી <b>કયો માલ ક્યાંથી આવ્યો અને ક્યાં ગયો</b> તે હંમેશા ખબર પડે (traceability).' },
      { id: 'st-hist', type: 'click', path: '/inventory/stock', target: '.lot-row a[href*="/inventory/stock/"]', title: 'લોટની History જુઓ', text: 'આ લોટની પાસબુક ખોલો.', todo: 'ક્લિક કરો: History' },
      { id: 'st-hist-info', type: 'info', path: /^\/inventory\/stock\/\d+$/, target: 'main', title: 'લોટની પાસબુક',
        text: 'બેંક પાસબુકની જેમ આ લોટની <b>દરેક હલચલ</b> લખાઈ છે — આવ્યો, QC પાસ થયો, ઉત્પાદનમાં ગયો, પાછો આવ્યો વગેરે. આ ખાતાની એન્ટ્રી <b>ક્યારેય ભૂંસાતી નથી</b>; ભૂલ થાય તો સામી (ઉલટી) એન્ટ્રી પડે.' },
      { id: 'val-link', type: 'click', target: navLink('/inventory/valuation'), title: 'Stock valuation', text: 'સ્ટોકની કિંમતનો રિપોર્ટ.', todo: 'ક્લિક કરો: Stock valuation' },
      { id: 'val-info', type: 'info', path: '/inventory/valuation', target: 'main', title: 'Valuation — સ્ટોકની કિંમત',
        text: 'અહીં <b>દરેક લોટની કિંમત</b> (Quantity × ભાવ) અને કુલ સ્ટોકની કિંમત દેખાય છે. ઉત્પાદન કરતાં માલ ઓછો થાય ત્યારે તેની કિંમત પણ સાથે જ જાય છે.' },
      { id: 'tr-link', type: 'click', target: navLink('/stock_transfers'), title: 'Stock transfer', text: 'એક ગોડાઉનથી બીજા ગોડાઉનમાં માલ મોકલવા માટે.', todo: 'ક્લિક કરો: Stock transfer' },
      { id: 'tr-info', type: 'info', path: '/stock_transfers', target: 'main h1', title: 'Transfer કેવી રીતે ચાલે છે',
        text: 'Transfer ના ત્રણ તબક્કા: <b>Draft → In transit (માલ નીકળ્યો) → Received (સામે પહોંચ્યો)</b>. રસ્તામાં હોય ત્યારે પણ માલ સ્ટોકના હિસાબમાં રહે છે.' },
      { id: 'adj-link', type: 'click', target: navLink('/stock_adjustments'), title: 'Stock adjustment', text: 'ગણતરીમાં ફરક પડે ત્યારે સ્ટોક સુધારવા.', todo: 'ક્લિક કરો: Stock adjustment' },
      { id: 'adj-info', type: 'info', path: '/stock_adjustments', target: 'main h1', title: 'Adjustment — સ્ટોક સુધારો',
        text: 'ગોડાઉનમાં ગણતરી કરતાં ફરક મળે (તૂટ-ફૂટ, ચોરી, ભૂલ) તો <b>કારણ લખીને</b> સ્ટોક વધારી/ઘટાડી શકાય. દરેક સુધારો <b>મંજૂરી અને ઓડિટ</b> સાથે નોંધાય છે.' }
    ]
  });

  CH.push({
    id: 'order', title: 'પ્રોડક્શન ઓર્ડર અને Queue', desc: 'નવો ઓર્ડર બનાવો, કતાર (queue), કાચા માલનું ચેક, Release.',
    steps: [
      { id: 'po-link', type: 'click', target: navLink('/production_orders'), title: 'Production order ખોલો', text: 'હવે ઉત્પાદન શરૂ કરીએ. <b>Manufacturing</b> હેઠળ <b>Production order</b>.', todo: 'ક્લિક કરો: Production order' },
      { id: 'po-queue', type: 'info', path: '/production_orders', target: '.po-kpi', title: 'આ Production queue છે',
        text: 'બધા ઓર્ડર <b>કતારમાં</b> (queue) હોય છે — #1 પહેલો ચાલે. ઉપરના કાર્ડ: કેટલા ઓર્ડર કતારમાં, કેટલા <b>ચાલુ</b>, કેટલાને <b>માલ જોઈએ</b> અને કેટલા <b>મોડા</b> છે.' },
      { id: 'po-new', type: 'click', path: '/production_orders', target: '#btn-add-mo', title: 'નવો ઓર્ડર', text: 'ઉપર જમણે <b>New production order</b> બટન.', todo: 'ક્લિક કરો: New production order' },
      { id: 'po-fill', type: 'fill', path: '/production_orders', target: '#mo-form', title: 'ઓર્ડર ભરો',
        text: '<b>૧.</b> Product category પસંદ કરો, પછી attributes (Alloy, Thickness…) એક પછી એક — ફક્ત મળતા options જ દેખાય.<br><b>૨.</b> કેટલું બનાવવું (Quantity).<br>નીચેનું બટન ડેમો માટે <b>100 KG</b> ભરી આપશે.',
        prefill: { label: 'ડેમો વેલ્યુ ભરો', run: prefillOrder } },
      { id: 'po-plan', type: 'info', path: '/production_orders', target: '#mo-plan', title: 'Stages અને Machines',
        text: 'આ product કયા <b>સ્ટેજમાંથી</b> પસાર થશે અને દરેકમાં <b>કયા મશીન</b> વાપરવા તે અહીં છે (✓ ટિક કરેલા). વધુ મશીન = ઓછો સમય. <b>Time</b> દરેક મશીનની ક્ષમતા (KG/કલાક) પરથી આપોઆપ નીકળે છે.' },
      { id: 'po-side', type: 'info', path: '/production_orders', target: '.po-side', title: 'Order summary',
        text: 'જમણી બાજુ સારાંશ: <b>કુલ સમય, રોજનું વધુમાં વધુ ઉત્પાદન</b> અને <b>કાચા માલનું ચેક</b>. "In store" કૉલમમાં દેખાય છે કે સ્ટોકમાં માલ છે કે નહિ — <b>Short</b> લખ્યું હોય તો માલ ઓછો છે.' },
      { id: 'po-save', type: 'submit', path: '/production_orders', target: '#mo-form', retryTo: 'po-new', capture: { re: 'PROD-[0-9]{4}-[0-9]+', as: 'order' }, title: 'કતારમાં સેવ કરો',
        text: 'નીચે <b>Save to queue</b> દબાવો. નવો ઓર્ડર કતારના <b>છેડે</b> જોડાશે.', todo: 'ક્લિક કરો: Save to queue' },
      { id: 'po-card', type: 'info', path: '/production_orders', target: function () { return orderCard('.po-card'); }, title: 'તમારો ઓર્ડર કતારમાં છે',
        text: 'એક જ લાઇનમાં બધું: <b>કતારનો નંબર</b> (▲▼ થી આગળ-પાછળ કરી શકાય), <b>Status</b>, <b>કાચા માલની સ્થિતિ</b> (Stock OK / PO coming / Need to buy), અને <b>શરૂ-પૂર્ણ થવાની તારીખ</b> (કતાર + મશીન + માલ પરથી આપોઆપ).' },
      { id: 'po-open', type: 'click', path: '/production_orders', target: inCard('.po-card', '.po-chev'), title: 'વિગત ખોલો', text: 'કાર્ડના જમણા છેડે <b>▾</b> તીર છે.', todo: 'ક્લિક કરો: ▾' },
      { id: 'po-detail', type: 'info', path: '/production_orders', target: inCard('.po-card', '.po-detail'), title: 'Plan અને કાચો માલ',
        text: 'ડાબે <b>Production plan</b> — દરેક સ્ટેજ, મશીન, કલાક અને તારીખ. જમણે <b>Raw material</b> — દરેક માલ સ્ટોકમાં છે (<b>In stock</b>), PO માં આવી રહ્યો છે કે ખરીદવો પડશે (<b>Buy</b>).' },
      { id: 'po-rel', type: 'click', path: '/production_orders', target: inCard('.po-card', 'form[action*="/release/"] button'), title: 'Release કરો',
        text: 'ઓર્ડર હમણાં <b>Draft</b> છે. <b>Release</b> કરશો પછી જ સ્ટોરમાંથી તેનો કાચો માલ આપી શકાશે.', todo: 'ક્લિક કરો: Release' },
      { id: 'po-rel-ok', type: 'click', target: '#erp-confirm-root.is-open .erp-confirm__btn--ok', retryTo: 'po-rel', title: 'પુષ્ટિ કરો', text: 'ખાતરી માટે પૂછશે. <b>Release</b> દબાવો.', todo: 'ક્લિક કરો: Release (પુષ્ટિ)' },
      { id: 'po-rel-done', type: 'info', path: '/production_orders', target: function () { return orderCard('.po-card'); }, title: 'ઓર્ડર Released ✅',
        text: 'Status હવે <b>Released</b>. હવે <b>Material issue</b> માંથી તેનો માલ આપીએ.' }
    ]
  });

  CH.push({
    id: 'issue', title: 'માલ આપવો અને પાછો લેવો', desc: 'Material issue, Issue all available, Print slip, Material return.',
    steps: [
      { id: 'mi-link', type: 'click', target: navLink('/material_issues'), title: 'Material issue', text: 'સ્ટોરમાંથી ઉત્પાદનમાં માલ આપવાની જગ્યા.', todo: 'ક્લિક કરો: Material issue' },
      { id: 'mi-kpi', type: 'info', path: '/material_issues', target: '.mi-kpi', title: 'ઉપરના કાર્ડ અને ટૅબ',
        text: '<b>To issue</b> — જે ઓર્ડરોને માલ આપવાનો બાકી (કતારના ક્રમમાં), <b>Issued</b> — અપાઈ ગયેલા, <b>Returns</b> — પાછા આવેલા. "Short of stock" માં માલ ઓછો હોય તેવા ઓર્ડર દેખાય.' },
      { id: 'mi-open', type: 'click', path: '/material_issues', target: inCard('.mi-card', '.btn-issue'), title: 'Issue material', text: 'તમારા ઓર્ડરના કાર્ડમાં <b>Issue material</b> બટન.', todo: 'ક્લિક કરો: Issue material' },
      { id: 'mi-fill', type: 'fill', path: '/material_issues', target: '#mi-form', title: 'કેટલો માલ આપવો',
        text: 'દરેક material માટે <b>Issue now</b> માં જથ્થો લખાયેલો છે (જેટલો જોઈએ, પણ સ્ટોરમાં છે એનાથી વધુ નહિ). <b>Issued by</b> (સ્ટોરમાંથી કોણે આપ્યું) અને <b>Received by</b> (ઉત્પાદનમાં કોણે લીધું) લખો — પ્રિન્ટમાં આવશે.',
        prefill: { label: 'ડેમો વેલ્યુ ભરો', run: function () { setVal($('#mi-form [name=issued_by]'), 'સ્ટોર ઇન્ચાર્જ'); setVal($('#mi-form [name=received_by]'), 'પ્રોડક્શન સુપરવાઇઝર'); var f = $('#mi-fill'); if (f) f.click(); return Promise.resolve(); } } },
      { id: 'mi-post', type: 'submit', path: '/material_issues', target: '#mi-form', submitter: 'post', retryTo: 'mi-open', title: 'Post issue',
        text: '<b>Post issue</b> દબાવો. Post થતાં જ માલ <b>Store → WIP</b> (ઉત્પાદનમાં) આપોઆપ ચાલ્યો જાય છે — અલગથી Stock transfer કરવાની જરૂર નથી. લોટ <b>જૂનો પહેલો</b> (FIFO) આપમેળે પસંદ થાય.', todo: 'ક્લિક કરો: Post issue' },
      { id: 'mi-done', type: 'info', path: '/material_issues', target: function () { return orderCard('.mi-card'); }, title: 'માલ આપાઈ ગયો ✅',
        text: 'આ <b>Issued</b> ટૅબ છે. દરેક issue લોટ-વાર નોંધાય છે. સ્ટોકમાં હવે તે માલ <b>"In production"</b> માં દેખાશે.' },
      { id: 'mi-print', type: 'info', path: '/material_issues', target: inCard('.mi-card', 'a[href*="/material_issues/print/"]'), title: 'Print slip',
        text: '<b>Print slip</b> થી Nrupex ના લેટરહેડ પર સ્લિપ નીકળે છે — લોટ, જથ્થો અને <b>Issued by / Received by</b> ની સહી માટે જગ્યા સાથે.' },
      { id: 'mi-menu', type: 'click', path: '/material_issues', target: inCard('.mi-card', 'details.mi-menu summary'), title: 'બચેલો માલ પાછો', text: 'ઉત્પાદનમાં માલ વધે (ના વપરાયો) તો પાછો સ્ટોરમાં આવી શકે. <b>⋯</b> મેનુ ખોલો.', todo: 'ક્લિક કરો: ⋯' },
      { id: 'mi-ret', type: 'click', path: '/material_issues', target: inCard('.mi-card', '.btn-return'), title: 'Return material', text: '<b>Return material to store</b> પસંદ કરો.', todo: 'ક્લિક કરો: Return material to store' },
      { id: 'mi-ret-fill', type: 'fill', path: '/material_issues', target: '#mr-form', title: 'કેટલો પાછો',
        text: 'જે <b>લોટમાંથી</b> માલ ગયો હતો તે જ લોટમાં પાછો જશે. <b>કારણ</b> પસંદ કરો અને <b>Return now</b> માં જથ્થો લખો. ડેમો માટે 1 KG પાછો મોકલીશું.',
        prefill: { label: 'ડેમો વેલ્યુ ભરો', run: function () { var q = $('#mr-lines .mr-qty'); if (q) setVal(q, '1'); setVal($('#mr-form [name=returned_by]'), 'પ્રોડક્શન'); return Promise.resolve(); } } },
      { id: 'mi-ret-post', type: 'submit', path: '/material_issues', target: '#mr-form', retryTo: 'mi-menu', title: 'Post return', text: '<b>Post return</b> દબાવો. માલ WIP માંથી સ્ટોરમાં પાછો આવી જશે.', todo: 'ક્લિક કરો: Post return' },
      { id: 'mi-ret-done', type: 'info', path: '/material_issues', target: '.mi-card', title: 'Return નોંધાયું ✅',
        text: 'હવે <b>Returns</b> ટૅબમાં આ MR (Material return) દેખાય છે. આ ઓર્ડરનો ગણાતો "આપેલો માલ" 1 KG ઘટ્યો, એટલે ફરી થોડો માલ આપવાનો બાકી છે.' },
      { id: 'mi-to', type: 'click', path: '/material_issues', target: '.mi-tabs a[href*="tab=issue"]', title: 'ફરી To issue ટૅબ', text: 'બાકીનો 1 KG ફરી આપી દઈએ.', todo: 'ક્લિક કરો: To issue' },
      { id: 'mi-all', type: 'click', path: '/material_issues', target: inCard('.mi-card', 'form[action*="/material_issues/add"] button'), title: 'Issue all available',
        text: 'આ બટન <b>એક ક્લિકમાં</b> બાકી રહેલો બધો માલ (જે સ્ટોરમાં છે તેટલો) આપી દે છે.', todo: 'ક્લિક કરો: Issue all available' },
      { id: 'mi-all-ok', type: 'click', target: '#erp-confirm-root.is-open .erp-confirm__btn--ok', retryTo: 'mi-all', title: 'પુષ્ટિ', text: '<b>Issue now</b> દબાવો.', todo: 'ક્લિક કરો: Issue now' },
      { id: 'mi-end', type: 'info', path: '/material_issues', target: 'main h1', title: 'માલ પૂરો અપાઈ ગયો ✅', text: 'હવે ઓર્ડરને ઉત્પાદનમાં <b>Start</b> કરી શકાય.' }
    ]
  });

  CH.push({
    id: 'routing', title: 'Start અને Routing (સ્ટેજ)', desc: 'ઓર્ડર Start કરો, દરેક સ્ટેજમાં ઓપરેટર, મશીન, qty, scrap.',
    steps: [
      { id: 'st-po', type: 'click', target: navLink('/production_orders'), title: 'ફરી Production order', text: 'ઓર્ડરને હવે <b>Start</b> કરવાનો.', todo: 'ક્લિક કરો: Production order' },
      { id: 'st-start', type: 'click', path: '/production_orders', target: inCard('.po-card', 'form[action*="/start/"] button'), title: 'Start production',
        text: 'માલ આપાઈ ગયો હોય તો <b>Start</b> દેખાય છે. Start થતાં ઓર્ડરની <b>તારીખો આજથી નક્કી</b> થઈ જાય, અને બાકી ઓર્ડરો તેની આસપાસ ગોઠવાય.', todo: 'ક્લિક કરો: Start' },
      { id: 'st-start-ok', type: 'click', target: '#erp-confirm-root.is-open .erp-confirm__btn--ok', retryTo: 'st-start', title: 'પુષ્ટિ', text: '<b>Start</b> દબાવો.', todo: 'ક્લિક કરો: Start (પુષ્ટિ)' },
      { id: 'st-run', type: 'info', path: '/production_orders', target: function () { return orderCard('.po-card'); }, title: 'ઓર્ડર ચાલુ થઈ ગયો ✅',
        text: 'Status <b>In production</b>. હવે તેને Move/Cancel/Reschedule થઈ ન શકે (તારીખો ફિક્સ). ઉત્પાદનમાં દરેક સ્ટેજનું કામ <b>Routing</b> માં નોંધાય છે.' },
      { id: 'rt-link', type: 'click', target: navLink('/routing'), title: 'Routing / stages', text: 'સ્ટેજ-વાર ખરું કામ અહીં નોંધાય.', todo: 'ક્લિક કરો: Routing / stages' },
      { id: 'rt-pipe', type: 'info', path: '/routing', target: inCard('.rt-card', '.rt-pipe'), title: 'સ્ટેજની પાઇપલાઇન',
        text: 'ઓર્ડર જે સ્ટેજમાંથી પસાર થવાનો તે હરોળમાં છે: <b>✓ Done</b> (લીલું), <b>In progress</b> (નારંગી), <b>Pending</b> (રાખોડી). દરેકમાં આયોજિત કલાક અને પછી <b>ખરા કલાક</b> દેખાશે. સ્ટેજ <b>એક પછી એક</b> જ ચાલે.' },
      { id: 'rt-start', type: 'click', path: '/routing', target: inCard('.rt-card', '.rt-act'), title: 'પહેલું સ્ટેજ Start કરો', text: 'કાર્ડના જમણે નારંગી <b>Start …</b> બટન.', todo: 'ક્લિક કરો: Start (સ્ટેજ)' },
      { id: 'rt-start-fill', type: 'fill', path: '/routing', target: '#rt-form', title: 'ઓપરેટર અને સમય',
        text: '<b>Operator</b> — આ સ્ટેજ કોણ ચલાવે છે તેનું નામ. <b>Started at</b> — ડિફોલ્ટ હમણાંનો સમય (મોડું નોંધતા હો તો બદલી શકાય).',
        prefill: { label: 'ડેમો વેલ્યુ ભરો', run: function () { setVal($('#rt-operator'), 'રમેશભાઈ'); return Promise.resolve(); } } },
      { id: 'rt-start-post', type: 'submit', path: '/routing', target: '#rt-form', retryTo: 'rt-start', title: 'Start stage', text: '<b>Start stage</b> દબાવો.', todo: 'ક્લિક કરો: Start stage' },
      { id: 'rt-comp', type: 'click', path: '/routing', target: inCard('.rt-card', '.rt-act'), title: 'સ્ટેજ પૂરું કરો', text: 'હવે એ જ જગ્યાએ <b>Complete …</b> બટન છે.', todo: 'ક્લિક કરો: Complete (સ્ટેજ)' },
      { id: 'rt-comp-fill', type: 'fill', path: '/routing', target: '#rt-form', title: 'પૂરું કરવાની વિગત',
        text: '<ul><li><b>Machines used</b> — ખરેખર કયા મશીન ચાલ્યા (ન ચાલ્યું તે અનટિક કરો)</li><li><b>Quantity out</b> — આ સ્ટેજમાંથી કેટલો KG માલ આગળ ગયો</li><li><b>Scrap</b> — કેટલો બગડ્યો; બગડ્યો હોય તો <b>પ્રકાર</b> અને <b>વેચી શકાય (Saleable)</b> કે <b>Process loss</b> પસંદ કરો</li></ul>ડેમો માટે 1 KG scrap (Metal slag) ભરાશે.',
        prefill: { label: 'ડેમો વેલ્યુ ભરો', run: prefillStageComplete } },
      { id: 'rt-comp-post', type: 'submit', path: '/routing', target: '#rt-form', retryTo: 'rt-comp', title: 'Complete stage', text: '<b>Complete stage</b> દબાવો.', todo: 'ક્લિક કરો: Complete stage' },
      { id: 'rt-done1', type: 'info', path: '/routing', target: inCard('.rt-card', '.rt-head'), title: 'પહેલું સ્ટેજ પૂરું ✅',
        text: 'પ્રગતિ-બાર વધ્યો. <b>Behind / On track</b> ચિપ કહે છે કે આયોજન કરતાં મોડા છો કે નહિ, અને <b>Forecast</b> કહે છે કે ઓર્ડર ક્યારે પૂરો થવાની શક્યતા છે. કાર્ડ ખોલશો તો સ્ટેજ-વાર ખરા કલાક, ઓપરેટર, મશીન અને yield % દેખાય.' },
      { id: 'rt-shortcut', type: 'action', path: '/routing', target: inCard('.rt-card', '.rt-pipe'), title: 'બાકીના સ્ટેજ (ડેમો શૉર્ટકટ)',
        text: 'બાકીના 7 સ્ટેજ પણ આ જ રીતે (Start → Complete) થાય. ટૂરનો સમય બચાવવા આ <b>ડેમો શૉર્ટકટ</b> બટન બાકીના બધા સ્ટેજ આપમેળે પૂરા કરી દેશે.',
        button: { label: 'બાકીના સ્ટેજ આપમેળે પૂરા કરો', run: finishStagesDemo } },
      { id: 'rt-alldone', type: 'info', path: '/routing', target: '.rt-tabs', title: 'બધા સ્ટેજ પૂરા ✅',
        text: 'ઓર્ડર <b>Running</b> ટૅબમાંથી નીકળીને <b>All stages done</b> માં ગયો. હવે તૈયાર થયેલા માલની (output) નોંધ કરવાની.' },
      { id: 'rt-tab', type: 'click', path: '/routing', target: '.rt-tabs a[href*="tab=done"]', title: 'All stages done', text: 'આ ટૅબ ખોલો.', todo: 'ક્લિક કરો: All stages done' },
      { id: 'rt-rec', type: 'info', path: '/routing', target: inCard('.rt-card', '.rt-head'), title: 'Output નોંધવા તૈયાર',
        text: 'કુલ કલાક (આયોજિત vs ખરા), કુલ scrap અને અંતિમ <b>yield</b> દેખાય છે. જમણે <b>Record output →</b> બટન છે — ત્યાં જઈએ.' }
    ]
  });

  CH.push({
    id: 'output', title: 'Output, તૈયાર માલ, Scrap, Variance', desc: 'Production output, Finished goods, Scrap, Consumption variance.',
    steps: [
      { id: 'ou-link', type: 'click', target: navLink('/production_output'), title: 'Production output', text: 'ઓર્ડર પૂરો થયો — કેટલું બન્યું તે નોંધવાની જગ્યા.', todo: 'ક્લિક કરો: Production output' },
      { id: 'ou-open', type: 'click', path: '/production_output', target: inCard('.ou-card', '.ou-act'), title: 'Record output', text: 'તમારા ઓર્ડરના કાર્ડમાં <b>Record output</b>.', todo: 'ક્લિક કરો: Record output' },
      { id: 'ou-fill', type: 'fill', path: '/production_output', target: '#ou-form', title: 'શું બન્યું?',
        text: 'Routing માંથી આંકડા પહેલેથી ભર્યા છે:<ul><li><b>Good</b> — વેચાણ લાયક (તૈયાર માલમાં જશે)</li><li><b>Rework</b> — ફરી કામ કરવું પડે (હાલ ફક્ત નોંધ)</li><li><b>Scrap</b> — વેચી શકાય તેવો કચરો (Scrap yard માં)</li><li><b>Process loss</b> — નાનું નુકસાન (ફક્ત નોંધ)</li></ul>જમણે લખ્યું છે કે Record કરતાં શું થશે.',
        prefill: { label: 'ડેમો વેલ્યુ ભરો', run: function () { setVal($('#ou-by'), 'સુરેશભાઈ'); return Promise.resolve(); } } },
      { id: 'ou-side', type: 'info', path: '/production_output', target: '.ou-side', title: '"Record કરતાં શું થશે?"',
        text: '૧) ઉત્પાદનમાં આપેલો <b>કાચો માલ "વપરાયો"</b> ગણાશે, ૨) <b>Good</b> તૈયાર માલમાં (batch નંબર સાથે), ૩) <b>Scrap</b> Scrap yard માં, ૪) ઓર્ડર <b>Completed</b>. નીચે <b>અંદાજિત ખર્ચ</b> પણ છે: કાચા માલની કિંમત ÷ Good જથ્થો.' },
      { id: 'ou-post', type: 'submit', path: '/production_output', target: '#ou-form', retryTo: 'ou-open', title: 'Record output', text: 'નીચે <b>Record output</b> દબાવો.', todo: 'ક્લિક કરો: Record output' },
      { id: 'ou-done', type: 'info', path: '/production_output', target: '.ou-card', title: 'Output નોંધાયું ✅',
        text: 'આ <b>Recorded</b> ટૅબ છે. અહીં <b>OUT નંબર, Batch નંબર</b> (<code>BATCH-WS-તારીખ-001</code>), Good/Rework/Scrap અને <b>પ્રતિ યુનિટ ખર્ચ</b> દેખાય છે. <b>Print batch slip</b> થી બેચ-સ્લિપ નીકળે. ભૂલ હોય તો <b>Cancel</b> (જ્યાં સુધી માલ વેચાયો ન હોય).' },
      { id: 'fg-link', type: 'click', target: navLink('/finished_goods'), title: 'Finished goods', text: 'તૈયાર માલનો સ્ટોક.', todo: 'ક્લિક કરો: Finished goods' },
      { id: 'fg-info', type: 'info', path: '/finished_goods', target: '.fg-card', title: 'તૈયાર માલની બેચ',
        text: 'દરેક <b>બેચ</b> એક ઓર્ડરનો Good માલ છે: કેટલો બચ્યો, <b>પ્રતિ યુનિટ ખર્ચ</b>, કુલ કિંમત અને કયા ગોડાઉનમાં. આગળ <b>Sales</b> માં આ બેચમાંથી જ માલ ગ્રાહકને જશે.' },
      { id: 'fg-scrap', type: 'click', path: '/finished_goods', target: '.fg-tabs a[href*="tab=scrap"]', title: 'Scrap yard', text: 'બીજું ટૅબ <b>Scrap yard</b> ખોલો.', todo: 'ક્લિક કરો: Scrap yard' },
      { id: 'fg-scrap-info', type: 'info', path: '/finished_goods', target: '.fg-card', title: 'Scrap નો સ્ટોક', text: 'Output માં નોંધેલો <b>વેચી શકાય તેવો scrap</b> અહીં સ્ટોક તરીકે આવ્યો (કિંમત શૂન્ય ગણાય). આ ભવિષ્યમાં Sales માં વેચી શકાશે.' },
      { id: 'sc-link', type: 'click', target: navLink('/scrap'), title: 'Scrap / waste', text: 'બધા scrap નો હિસાબ.', todo: 'ક્લિક કરો: Scrap / waste' },
      { id: 'sc-kpi', type: 'info', path: '/scrap', target: '.sc-kpi', title: 'Scrap ના કાર્ડ',
        text: '<b>In scrap yard</b> (સ્ટોકમાં), <b>On the floor</b> (ચાલુ ઓર્ડરનો), <b>Process loss</b> (નોંધ માત્ર) અને <b>Scrap rate %</b> (બેચના વજન સામે).' },
      { id: 'sc-box', type: 'info', path: '/scrap', target: '.sc-box', title: 'ક્યાં સૌથી વધુ બગાડ?',
        text: 'બાર-ચાર્ટ કહે છે <b>કયા પ્રકારનો</b> scrap વધુ છે અને <b>કયું સ્ટેજ</b> સૌથી વધુ બગાડે છે — સુધારા માટે સીધો સંકેત.' },
      { id: 'sc-reg', type: 'info', path: '/scrap', target: '.sc-card', title: 'Scrap register', text: 'દરેક scrap: કયો ઓર્ડર, કયું સ્ટેજ, શું પ્રકાર, કેટલો, અને <b>અત્યારે ક્યાં</b> છે (Floor / Scrap yard / Not stocked).' },
      { id: 'cv-link', type: 'click', target: navLink('/consumption_variance'), title: 'Consumption variance', text: 'કાચો માલ <b>આયોજન મુજબ</b> વપરાયો કે નહિ?', todo: 'ક્લિક કરો: Consumption variance' },
      { id: 'cv-view', type: 'click', path: '/consumption_variance', target: inCard('.cv-card', '.cv-view'), title: 'તફાવત જુઓ', text: 'તમારા ઓર્ડરના કાર્ડમાં <b>View details</b>.', todo: 'ક્લિક કરો: View details' },
      { id: 'cv-info', type: 'info', path: '/consumption_variance', target: '#cv-body', title: 'Planned vs Actual',
        text: '<b>તફાવત = Actual − Planned</b>. Planned રેસિપીમાંથી, Actual ખરેખર વપરાયું. <ul><li><b>In short</b> — સાદી ભાષામાં સારાંશ</li><li><b>Used more / less / On plan</b> (±2% સુધી "On plan")</li><li><b>Yield %</b> અને <b>Mass balance</b> — કેટલો માલ ગયો અને કેટલો નીકળ્યો; હિસાબ ન મળે તે KG અહીં દેખાય</li></ul>' },
      { id: 'cv-review', type: 'submit', path: '/consumption_variance', target: '#cv-body form', retryTo: 'cv-view', title: 'Reviewed તરીકે માર્ક કરો',
        text: 'તફાવત જોઈ લીધા પછી તમારું નામ લખીને <b>Mark reviewed</b> દબાવો.', todo: 'ક્લિક કરો: Mark reviewed',
        prefill: { label: 'ડેમો વેલ્યુ ભરો', run: function () { setVal($('#cv-body [name=reviewed_by]'), 'મેનેજર'); setVal($('#cv-body [name=review_note]'), 'ડેમો ટૂર'); return Promise.resolve(); } } },
      { id: 'cv-done', type: 'info', path: '/consumption_variance', target: '.cv-card', title: 'Reviewed ✅', text: 'કાર્ડ પર <b>Reviewed</b> દેખાય છે અને "not reviewed" ગણતરી ઘટી.' },
      { id: 'po-final', type: 'click', target: navLink('/production_orders'), title: 'છેલ્લું: Production order', text: 'ઓર્ડર હવે કતારમાં નથી — <b>Completed</b> ટૅબમાં છે.', todo: 'ક્લિક કરો: Production order' },
      { id: 'po-final-tab', type: 'click', path: '/production_orders', target: '.po-tabs a[href*="tab=completed"]', title: 'Completed ટૅબ', text: 'આ ટૅબ ખોલો.', todo: 'ક્લિક કરો: Completed' },
      { id: 'end', type: 'info', path: '/production_orders', target: function () { return orderCard('.po-card'); }, title: 'અભિનંદન! 🎉 ટૂર પૂરી',
        text: 'તમે જાતે આખું ચક્ર કર્યું: <b>Opening stock → Production order → માલ આપવો/પાછો → Start → Routing → Output → તૈયાર માલ → Scrap → Variance</b>.<br>ઓર્ડર <b>Completed</b> છે અને તેનો <b>Batch નંબર, ખર્ચ</b> અહીં દેખાય છે.<br><br>આગળ આવશે: <b>Sales</b> (Quotation → Order → Delivery → Invoice) અને Login/Roles.' }
    ]
  });

  // ---------------------------------------------------------------- prefill / action helpers
  function prefillOpeningStock() {
    return getInfo().then(function (info) {
      if (!info.ok) throw new Error(info.message);
      var form = $('#os-form');
      setVal($('#os-date', form), ($('#os-date', form).max || new Date().toISOString().slice(0, 10)));
      setVal($('[name=warehouse_id]', form), String(info.store_warehouse_id));
      // lines
      var rows = $$('#os-lines tr.os-line');
      var need = info.product.recipe.length;
      while (rows.length < need) { $('#os-add-line').click(); rows = $$('#os-lines tr.os-line'); }
      info.product.recipe.forEach(function (item, i) {
        var row = rows[i];
        var qty = Math.ceil(item.ratio * 5);          // 500 KG ke order jitna (ratio % x 5)
        setVal($('.os-material', row), String(item.rm_id));
        setVal($('.os-qty', row), String(qty));
        setVal($('.os-cost', row), String(item.unit === 'KG' ? 100 : 400));
        setVal($('.os-batch', row), 'DEMO-' + (i + 1));
      });
      setVal($('[name=remarks]', form), 'Demo tour');
    });
  }

  function prefillOrder() {
    return getInfo().then(function (info) {
      if (!info.ok) throw new Error(info.message);
      var cat = $('#mo-category');
      setVal(cat, String(info.product.category_id));
      for (var i = 0; i < 8; i++) {
        $$('#mo-cascade select').forEach(function (s) {
          if (!s.value && s.options.length > 1) setVal(s, s.options[1].value);
        });
      }
      var prod = $('#mo-product');
      if (!prod.value) {
        // category me kai product hon to demo wala
        var opt = $$('option', prod).filter(function (o) { return o.value === String(info.product.id); })[0];
        if (opt) setVal(prod, opt.value);
      }
      setVal($('#mo-qty'), '100');
      setVal($('#mo-remarks'), 'Demo tour');
    });
  }

  function prefillStageComplete() {
    return sleep(50).then(function () {
      var scrapInput = $('#rt-scrap'), qtyOut = $('#rt-qty-out');
      var qtyIn = parseFloat(($('#rt-qty-in') || {}).textContent) || 0;
      setVal(scrapInput, '1');
      setVal(qtyOut, String(Math.round((qtyIn - 1) * 1000) / 1000));
      var type = $('#rt-scrap-type');
      var pick = $$('option', type).filter(function (o) { return /slag/i.test(o.textContent); })[0] || $$('option', type)[1];
      if (pick) setVal(type, pick.value);
      var saleable = $('input[name=scrap_kind][value="Saleable"]'); if (saleable) saleable.checked = true;
    });
  }

  function finishStagesDemo() {
    var card = orderCard('.rt-card');
    var act = card && $('.rt-act', card);
    var stageId = act ? act.getAttribute('data-stage') : null;
    // order id nikalne ka tareeka: production_orders list ke bajay /routing page ka data nahi deta — isliye server se order no se dhoondo
    return fetch('/tour/order_id?no=' + encodeURIComponent(state.vars.order || '')).then(function (r) { return r.json(); }).then(function (j) {
      if (!j.ok) throw new Error(j.message || 'Order not found');
      return fetch('/tour/finish_stages/' + j.id, { method: 'POST' });
    }).then(function (r) { return r.json(); }).then(function (j) {
      if (!j.ok) throw new Error(j.message);
      return j;
    });
  }

  // ---------------------------------------------------------------- state / navigation
  var state = load();
  var els = {};
  var ticker = null;
  var currentKey = '';

  function chapterById(id) { return CH.filter(function (c) { return c.id === id; })[0]; }
  function runList() { return (state && state.run) || []; }
  function chapter() { return chapterById(runList()[state.ci]); }
  function step() { var c = chapter(); return c ? c.steps[state.si] : null; }
  function totalSteps() { return runList().reduce(function (n, id) { return n + chapterById(id).steps.length; }, 0); }
  function doneSteps() {
    var n = 0;
    for (var i = 0; i < state.ci; i++) n += chapterById(runList()[i]).steps.length;
    return n + state.si;
  }
  function indexOfStep(id) {
    var c = chapter();
    for (var i = 0; i < c.steps.length; i++) if (c.steps[i].id === id) return i;
    return -1;
  }
  function advance() {
    state.si++;
    var c = chapter();
    if (!c || state.si >= c.steps.length) {
      state.ci++;
      state.si = 0;
    }
    save(state);
  }
  function finish() {
    clearState();
    state = null;
    teardown();
    showToastSafe('ટૂર પૂરી થઈ. તમે ગમે ત્યારે ફરી શરૂ કરી શકો છો.', 'success');
  }
  function showToastSafe(msg, type) { if (window.showToast) window.showToast(msg, type); }

  function start(chapterIds, fromChapter) {
    state = { on: true, run: chapterIds, ci: 0, si: 0, vars: {}, notice: null, pending: null };
    save(state);
    closeMenu();
    render();
    startTicker();
  }

  // ---------------------------------------------------------------- DOM: shade, ring, card
  function mk(tag, cls, parent) { var e = document.createElement(tag); if (cls) e.className = cls; (parent || document.body).appendChild(e); return e; }
  function ensureDom() {
    if (els.card) return;
    els.shades = [mk('div', 'tour-shade'), mk('div', 'tour-shade'), mk('div', 'tour-shade'), mk('div', 'tour-shade')];
    els.full = mk('div', 'tour-shade');
    els.ring = mk('div', 'tour-ring');
    els.card = mk('div', 'tour-card tour-gu');
    hideShades();
  }
  function showFull() { var f = els.full; f.style.display = 'block'; f.style.left = '0'; f.style.top = '0'; f.style.width = '100vw'; f.style.height = '100vh'; }
  function hideShades() { els.shades.forEach(function (s) { s.style.display = 'none'; }); els.full.style.display = 'none'; els.ring.style.display = 'none'; }
  function teardown() {
    if (ticker) { clearInterval(ticker); ticker = null; }
    ['card', 'ring', 'full'].forEach(function (k) { if (els[k] && els[k].parentNode) els[k].parentNode.removeChild(els[k]); });
    (els.shades || []).forEach(function (s) { if (s.parentNode) s.parentNode.removeChild(s); });
    els = {};
    currentKey = '';
  }

  function resolveTarget(st) {
    var t = st.target;
    if (!t) return null;
    try { return typeof t === 'function' ? t() : $(t); } catch (e) { return null; }
  }
  function visible(el) { if (!el) return false; var r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; }

  function pathOk(st) {
    if (!st.path) return true;
    return st.path instanceof RegExp ? st.path.test(path()) : path() === st.path;
  }
  function gotoUrl(st) {
    if (typeof st.goto === 'function') return st.goto(state.vars);
    if (st.goto) return st.goto;
    return typeof st.path === 'string' ? st.path : '/';
  }

  // ---------------------------------------------------------------- render
  function render() {
    if (!state || !state.on) return;
    ensureDom();
    var c = chapter(), st = step();
    if (!st) { finish(); return; }
    var key = state.ci + ':' + state.si;
    var total = totalSteps(), at = doneSteps() + 1;

    // pichhla submit / confirm ka natija (error to wapas)
    if (state.pending) {
      var p = state.pending; state.pending = null;
      var err = toasts.filter(function (t) { return t.type === 'error' || t.type === 'warning'; })[0];
      if (err && p.retryTo) {
        var back = indexOfStep(p.retryTo);
        if (back >= 0) { state.si = back; state.notice = 'એન્ટ્રીમાં સમસ્યા: ' + err.msg + ' — ફરી પ્રયત્ન કરો.'; }
        save(state);
        return render();
      }
      var okToast = toasts.filter(function (t) { return t.type === 'success'; });
      if (p.capture) {
        var txt = okToast.map(function (t) { return t.msg; }).join(' ');
        var m = txt.match(new RegExp(p.capture.re));          // capture state me JSON ban ke jaata hai, isliye re string hai
        if (m) state.vars[p.capture.as] = m[0];
      }
      save(state);
      return render();
    }

    if (key !== currentKey) { currentKey = key; st._ready = false; }
    var shown = !pathOk(st) ? 'goto' : 'step';
    drawCard(c, st, at, total, shown);
    if (shown === 'goto') { hideShades(); showFull(); placeCenter(); return; }
    place(st);
  }

  function btn(label, cls, fn) { var b = document.createElement('button'); b.type = 'button'; b.className = 'tour-btn ' + (cls || ''); b.textContent = label; b.addEventListener('click', fn); return b; }

  function drawCard(c, st, at, total, mode) {
    var card = els.card;
    card.innerHTML = '';
    var bar = mk('div', 'bar', card); bar.innerHTML = '<i style="width:' + Math.round(100 * (at - 1) / total) + '%"></i>';
    var head = mk('div', 'head', card);
    head.innerHTML = '<span class="chip">' + esc(c.title) + '</span><span>પગલું ' + at + ' / ' + total + '</span>';
    if (mode === 'goto') {
      mk('h3', '', card).textContent = 'આ પગલા માટે બીજા પેજ પર જાઓ';
      var b0 = mk('div', 'body', card);
      b0.innerHTML = 'ટૂરનું આગળનું પગલું <b>' + esc(st.title) + '</b> છે, જે બીજા પેજ પર કરવાનું છે. નીચેનું બટન દબાવીને ત્યાં જાઓ.';
      var f0 = mk('div', 'foot', card);
      var l0 = mk('div', 'left', f0), r0 = mk('div', 'right', f0);
      l0.appendChild(btn('બહાર નીકળો', 'link', exitTour));
      r0.appendChild(btn('પેજ ખોલો →', 'primary', function () { location.href = gotoUrl(st); }));
      return;
    }
    mk('h3', '', card).innerHTML = st.title;
    var body = mk('div', 'body', card); body.innerHTML = st.text;
    if (st.warn) { mk('div', 'warn', card).innerHTML = st.warn; }
    if (state.notice) { mk('div', 'warn', card).textContent = state.notice; }
    if (st.todo) {
      var d = mk('div', 'do', card); d.innerHTML = '<span class="dot"></span><span>' + st.todo + '</span>';
    } else if (st.type === 'fill' || st.type === 'submit') {
      var d2 = mk('div', 'do', card); d2.innerHTML = '<span class="dot"></span><span>ફોર્મ ભરો, પછી નીચે બટન દબાવો</span>';
    }
    var foot = mk('div', 'foot', card);
    var left = mk('div', 'left', foot), right = mk('div', 'right', foot);
    left.appendChild(btn('બહાર નીકળો', 'link', exitTour));
    if (state.si > 0 || state.ci > 0) left.appendChild(btn('← પાછળ', '', goBack));
    if (st.type !== 'info') left.appendChild(btn('પગલું છોડો', 'link', skipStep));
    if (st.prefill) {
      var pb = btn(st.prefill.label, 'teal', function () {
        pb.disabled = true;
        Promise.resolve().then(function () { return st.prefill.run(); }).then(function () {
          var ok = mk('div', 'ok', card); ok.textContent = 'ફોર્મ ભરાઈ ગયું ✓ — હવે તપાસીને આગળ વધો.';
        }).catch(function (e) {
          pb.disabled = false;
          var w = mk('div', 'warn', card); w.textContent = 'ભરી શકાયું નહિ: ' + (e && e.message ? e.message : e);
        });
      });
      right.appendChild(pb);
    }
    if (st.button) {
      var ab = btn(st.button.label, 'primary', function () {
        ab.disabled = true; ab.textContent = 'ચાલુ છે…';
        Promise.resolve().then(function () { return st.button.run(); }).then(function () { advance(); location.reload(); }).catch(function (e) {
          ab.disabled = false; ab.textContent = st.button.label;
          var w = mk('div', 'warn', card); w.textContent = 'થઈ શક્યું નહિ: ' + (e && e.message ? e.message : e);
        });
      });
      right.appendChild(ab);
    }
    if (st.type === 'info') {
      right.appendChild(btn(isLastStep() ? 'પૂરું કરો ✓' : 'આગળ →', 'primary', function () { state.notice = null; advance(); render(); }));
    }
    if (st.type === 'fill') {
      right.appendChild(btn('ભરાઈ ગયું, આગળ →', 'primary', function () { state.notice = null; advance(); render(); }));
    }
  }
  function isLastStep() { return state.ci === runList().length - 1 && state.si === chapter().steps.length - 1; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  function goBack() {
    if (state.si > 0) state.si--;
    else if (state.ci > 0) { state.ci--; state.si = chapter().steps.length - 1; }
    state.notice = null;
    save(state);
    var st = step();
    if (!pathOk(st)) { location.href = gotoUrl(st); return; }
    render();
  }
  function skipStep() { state.notice = null; advance(); render(); }
  function exitTour() {
    if (!window.confirm('ટૂર બંધ કરવી છે? (બનેલી એન્ટ્રીઓ સિસ્ટમમાં રહેશે.)')) return;
    clearState(); state = null; teardown();
  }

  // ---------------------------------------------------------------- placement
  function placeCenter() {
    var card = els.card;
    card.style.left = Math.max(12, (window.innerWidth - card.offsetWidth) / 2) + 'px';
    card.style.top = Math.max(12, (window.innerHeight - card.offsetHeight) / 3) + 'px';
  }
  function place(st) {
    var el = resolveTarget(st);
    var card = els.card;
    if (!el || !visible(el)) {
      // target abhi nahi (page / drawer load ho raha) — card beech me, shade halka
      hideShades(); if (st.type === 'info') showFull(); else els.full.style.display = 'none';
      placeCenter();
      return;
    }
    if (!st._scrolled) {
      st._scrolled = true;
      var rr = el.getBoundingClientRect();
      if (rr.top < 60 || rr.bottom > window.innerHeight - 40) el.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
    var r = el.getBoundingClientRect(), pad = 6;
    var x = Math.max(0, r.left - pad), y = Math.max(0, r.top - pad), w = Math.min(window.innerWidth - x, r.width + pad * 2), h = Math.min(window.innerHeight - y, r.height + pad * 2);
    var ring = els.ring; ring.style.display = 'block';
    ring.style.left = x + 'px'; ring.style.top = y + 'px'; ring.style.width = w + 'px'; ring.style.height = h + 'px';
    // shade sirf info / click steps me (form wale steps me user ko poori chhoot chahiye)
    var useShade = st.type === 'info' || st.type === 'click' || st.type === 'action';
    els.full.style.display = 'none';
    var S = els.shades;
    if (useShade) {
      var rect = function (el, l, t, wd, ht) { el.style.display = 'block'; el.style.left = l + 'px'; el.style.top = t + 'px'; el.style.width = wd + 'px'; el.style.height = ht + 'px'; };
      rect(S[0], 0, 0, window.innerWidth, y);
      rect(S[1], 0, y + h, window.innerWidth, Math.max(0, window.innerHeight - y - h));
      rect(S[2], 0, y, x, h);
      rect(S[3], x + w, y, Math.max(0, window.innerWidth - x - w), h);
    } else {
      S.forEach(function (s) { s.style.display = 'none'; });
    }
    // card ki jagah: pehle target ke side me, jagah na ho to kone me
    var cw = card.offsetWidth, ch = card.offsetHeight, gap = 16, vw = window.innerWidth, vh = window.innerHeight;
    var big = r.width > vw * 0.62 && r.height > vh * 0.5;
    var pos = null;
    if (!big) {
      if (vw - r.right - gap >= cw) pos = [r.right + gap, Math.min(Math.max(12, r.top), vh - ch - 12)];
      else if (r.left - gap >= cw) pos = [r.left - gap - cw, Math.min(Math.max(12, r.top), vh - ch - 12)];
      else if (vh - r.bottom - gap >= ch) pos = [Math.min(Math.max(12, r.left), vw - cw - 12), r.bottom + gap];
      else if (r.top - gap >= ch) pos = [Math.min(Math.max(12, r.left), vw - cw - 12), r.top - gap - ch];
    }
    if (!pos) pos = [14, vh - ch - 14];                  // kone me, neeche-baayen (drawer ke Save buttons dayen taraf rehte hain)
    // kone me hone par card ko drawer ke baayen kinare tak hi rakho (taaki form ke labels na dhakein)
    card.style.width = (pos[0] === 14 && r.left >= 300) ? Math.min(372, r.left - 28) + 'px' : '';
    card.style.left = Math.max(8, pos[0]) + 'px';
    card.style.top = Math.max(8, pos[1]) + 'px';
  }

  // ---------------------------------------------------------------- event listeners (click / submit)
  document.addEventListener('click', function (e) {
    if (!state || !state.on) return;
    var st = step();
    if (!st || st.type !== 'click' || !pathOk(st)) return;
    if (els.card && els.card.contains(e.target)) return;
    var el = resolveTarget(st);
    if (!el || !el.contains(e.target)) return;
    // is click ke baad page reload (link / confirm) ho sakta hai — pehle state save
    if (st.retryTo) state.pending = { retryTo: st.retryTo };
    state.notice = null;
    advance();
    setTimeout(function () { if (state && state.on) render(); }, 250);
  }, true);

  document.addEventListener('submit', function (e) {
    if (!state || !state.on) return;
    var st = step();
    if (!st || st.type !== 'submit' || !pathOk(st)) return;
    var el = resolveTarget(st);
    if (!el || e.target !== el) return;
    if (st.submitter && !(e.submitter && e.submitter.value === st.submitter)) return;
    if (e.target.classList && e.target.classList.contains('js-confirm-submit')) return;
    state.pending = { retryTo: st.retryTo, capture: st.capture };
    state.notice = null;
    advance();                                    // page reload hoga; naye page par render() natija jaanchega
  }, true);

  // ---------------------------------------------------------------- ticker: target / path badalne par card ko sahi jagah rakho
  function startTicker() {
    if (ticker) return;
    ticker = setInterval(function () {
      if (!state || !state.on || !els.card) return;
      var st = step();
      if (!st) return;
      var wantGoto = !pathOk(st);
      var isGoto = els.card.querySelector('h3') && els.card.querySelector('h3').textContent === 'આ પગલા માટે બીજા પેજ પર જાઓ';
      if (wantGoto !== isGoto) { currentKey = ''; render(); return; }
      if (!wantGoto) place(st);
      // dev autoplay
      if (localStorage.getItem(DEV_KEY) === '1') autoStep(st);
    }, 300);
    window.addEventListener('resize', function () { if (state && state.on) { var st = step(); if (st && pathOk(st)) place(st); } });
  }

  // ---------------------------------------------------------------- dev autoplay (testing ke liye; ?tourauto=1 se on)
  var autoBusy = false;
  function autoStep(st) {
    if (autoBusy || !pathOk(st)) return;
    var el = resolveTarget(st);
    autoBusy = true;
    var done = function () { setTimeout(function () { autoBusy = false; }, 700); };
    var p = Promise.resolve();
    if (st.type === 'info') { p = sleep(150).then(function () { advance(); render(); }); }
    else if (st.type === 'action') { p = st.button.run().then(function () { advance(); location.reload(); }); }
    else if (!el || !visible(el)) { autoBusy = false; return; }
    else if (st.type === 'click') { p = sleep(150).then(function () { el.click(); }); }
    else if (st.type === 'fill') { p = (st.prefill ? st.prefill.run() : Promise.resolve()).then(function () { advance(); render(); }); }
    else if (st.type === 'submit') {
      p = (st.prefill ? st.prefill.run() : Promise.resolve()).then(function () {
        var sub = st.submitter ? $('[form="' + el.id + '"][value="' + st.submitter + '"], #' + el.id + ' [value="' + st.submitter + '"]') : null;
        if (sub) sub.click(); else if (el.requestSubmit) el.requestSubmit(); else el.submit();
      });
    }
    p.then(done, function (e) { console.error('[tour auto]', st.id, e); window.__tourErrors = (window.__tourErrors || []).concat(st.id + ': ' + e); done(); });
  }
  // 'fill' step ko autoplay me aage badhana: fill ke baad agla step submit hota hai, isliye fill => advance
  // (asli user flow me 'fill' step ka "agla" button khud user ke submit karne se aata hai; 'fill' me "આગળ" nahi hota)

  // ---------------------------------------------------------------- chapter menu + launcher
  var menuEl = null;
  function openMenu() {
    closeMenu();
    menuEl = mk('div', 'tour-menu-back tour-gu');
    var box = mk('div', 'tour-menu', menuEl);
    box.innerHTML = '<div class="top"><h2>🎓 ડેમો ટૂર (ગુજરાતી)</h2><p>સ્ટોકથી લઈને તૈયાર માલ, Scrap અને Variance સુધીનું બધું <b>જાતે કરીને</b> શીખો. દરેક પગલું ગુજરાતીમાં સમજાવેલું છે.</p></div>' +
      '<div class="alert">⚠️ ટૂર <b>સાચી એન્ટ્રીઓ</b> બનાવશે — સ્ટોક, પ્રોડક્શન ઓર્ડર, માલ આપવો/પાછો, રૂટિંગ, output વગેરે. ટ્રેનિંગ / ડેમો માટે જ ચલાવો.<label><input type="checkbox" id="tour-ok"> હું સમજું છું કે ટૂર સાચી એન્ટ્રીઓ બનાવશે.</label></div>';
    var list = mk('div', '', box);
    CH.forEach(function (c, i) {
      var row = mk('div', 'tour-ch', list);
      row.innerHTML = '<div class="n">' + (i + 1) + '</div><div class="t"><b>' + esc(c.title) + '</b><span>' + esc(c.desc) + ' · ' + c.steps.length + ' પગલાં</span></div>';
      var b = btn('શરૂ કરો', 'teal', function () { if (!okBox().checked) return warnBox(); start(['intro'].concat(c.id === 'intro' ? [] : [c.id])); });
      b.classList.add('tour-start-one'); b.disabled = true;
      row.appendChild(b);
    });
    var bottom = mk('div', 'bottom', box);
    var all = btn('▶ આખો ટૂર શરૂ કરો (બધા ભાગ ક્રમમાં)', 'primary', function () { if (!okBox().checked) return warnBox(); start(CH.map(function (c) { return c.id; })); });
    all.disabled = true; all.id = 'tour-all';
    bottom.appendChild(btn('બંધ કરો', '', closeMenu));
    bottom.appendChild(all);
    okBox().addEventListener('change', function () {
      $$('.tour-start-one, #tour-all', box).forEach(function (b) { b.disabled = !okBox().checked; });
    });
    menuEl.addEventListener('click', function (e) { if (e.target === menuEl) closeMenu(); });
    var note = mk('div', 'alert', box);
    note.style.background = '#EAF3F3'; note.style.borderColor = '#C5D9DA'; note.style.color = '#1F5558';
    note.innerHTML = 'સૂચન: <b>"આખો ટૂર"</b> ક્રમમાં ચલાવવો — પછીના ભાગ આગળના ભાગમાં બનેલા ઓર્ડર/સ્ટોક પર આધારિત છે. અલગ ભાગ ચલાવો તો પહેલાં ઓર્ડર બનેલો હોવો જોઈએ.';
  }
  function okBox() { return $('#tour-ok'); }
  function warnBox() { var a = $('.tour-menu .alert'); if (a) { a.style.outline = '3px solid #C46B2D'; setTimeout(function () { a.style.outline = ''; }, 1200); } }
  function closeMenu() { if (menuEl && menuEl.parentNode) menuEl.parentNode.removeChild(menuEl); menuEl = null; }

  function addLauncher() {
    if ($('#tour-launch')) return;
    var nav = $('aside nav');
    var b = document.createElement('button');
    b.type = 'button'; b.id = 'tour-launch'; b.className = 'tour-launch tour-gu';
    b.innerHTML = '<span style="font-size:20px">🎓</span><span>ડેમો ટૂર<small>ગુજરાતી · જાતે કરીને શીખો</small></span>';
    b.addEventListener('click', function () {
      if (state && state.on) { render(); return; }
      openMenu();
    });
    if (nav) nav.insertBefore(b, nav.firstChild);
    else { b.style.cssText = 'position:fixed;left:12px;bottom:12px;z-index:9970;width:auto'; document.body.appendChild(b); }
  }

  // ---------------------------------------------------------------- init
  function init() {
    addLauncher();
    if (/[?&]tourauto=1/.test(location.search)) localStorage.setItem(DEV_KEY, '1');
    if (/[?&]tourauto=0/.test(location.search)) localStorage.removeItem(DEV_KEY);
    if (state && state.on) { render(); startTicker(); }
    window.__tour = { state: function () { return state; }, step: step, chapters: CH, resolve: function () { return resolveTarget(step()); }, errors: function () { return window.__tourErrors || []; }, start: start };
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
