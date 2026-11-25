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
  // Demo player (/demo) ERP ko iframe me chalata hai — us iframe ke andar manual tour / launcher nahi chahiye
  if (window.self !== window.top) return;
  var PLAYER = !!window.__ERP_DEMO_PLAYER;      // /demo page: yahan sirf step data + helpers chahiye, engine nahi
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
  // ctx: step ke target kis document me dhundhne hain (normal tour me yehi page; demo player me iframe ka page)
  var ctx = { doc: document, win: window };
  function $(sel, root) { return (root || ctx.doc).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || ctx.doc).querySelectorAll(sel)); }
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function path() { return ctx.win.location.pathname; }
  function setVal(el, value) {
    if (!el) return;
    el.value = value;
    el.dispatchEvent(new ctx.win.Event('input', { bubbles: true }));
    el.dispatchEvent(new ctx.win.Event('change', { bubbles: true }));
  }
  // W2 person dropdown (Users list): demo me pehla asli option chuno (login user pehle se selected ho to wahi rehne do)
  function setPerson(el) {
    if (!el || el.tagName !== 'SELECT') return '';
    if (!el.value) {
      for (var i = 0; i < el.options.length; i++) { if (el.options[i].value) { setVal(el, el.options[i].value); break; } }
    }
    return el.value;
  }
  function load() { try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { return null; } }
  function save(s) { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) { /* private mode */ } }
  function clearState() { try { localStorage.removeItem(KEY); } catch (e) { /* ignore */ } }
  function getInfo() {
    if (infoCache) return Promise.resolve(infoCache);
    return fetch('/tour/info').then(function (r) { return r.json(); }).then(function (j) { infoCache = j; return j; });
  }
  // Step sirf tab chalta hai jab uska `when()` true ho (jaise Production line ka modal tabhi jab lines bani hon)
  function stepOn(st) { try { return !st.when || !!st.when(); } catch (e) { return true; } }
  // Sidebar ke link tak jaate waqt uske drawers khol do (band drawer me link chhupa hota hai)
  function navLink(href) {
    var sel = 'aside a.nav-link[href="' + href + '"]';
    return function () { var el = document.querySelector(sel); if (el && window.ErpNav) window.ErpNav.reveal(el); return el; };
  }
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
  // Procurement pages (PO / GRN / QC / bill): wo hilaar jisme demo ka PO number (state.vars.po) likha ho
  function rowOf(sel, key) {
    var rows = $$(sel), v = state && state.vars && state.vars[key];
    if (v) for (var i = 0; i < rows.length; i++) if (rows[i].textContent.indexOf(v) !== -1) return rows[i];
    return rows[0] || null;
  }
  function inRow(sel, key, inner) { return function () { var r = rowOf(sel, key); return r ? $(inner, r) : null; }; }

  // Naye features ke steps tabhi jab /tour/info ka flag (lines / racks / scrap_later / wd_split) true ho
  function flag(name) { return function () { return !!(infoCache && infoCache[name]); }; }
  // Table tabhi jab dikh rahi ho (khaali page par table chhupi rehti hai, tab title dikhao)
  function tableOrTitle() { var t = $('main table'); return (t && t.offsetWidth > 0) ? t : $('main h1'); }
  // Material plan / Scrap page ke dabbe (class same hai, isliye likhe hue text se pehchano)
  function boxWith(sel, text) { var b = $$(sel).filter(function (x) { return x.textContent.indexOf(text) !== -1; })[0]; return b || null; }

  // ---------------------------------------------------------------- chapters (Gujarati)
  var CH = [];

  CH.push({
    id: 'intro', title: 'ERP ની ઓળખ', desc: 'ટૂર કેવી રીતે ચાલે છે અને મેનુ કેવું છે — ૩ પગલાં.',
    steps: [
      { id: 'welcome', type: 'info', title: 'ડેમો ટૂરમાં સ્વાગત છે! 🎓',
        text: 'આ ટૂરમાં તમે <b>ખરીદી (Purchase order) થી લઈને તૈયાર માલ, સ્ક્રેપ અને તફાવત (variance)</b> સુધી બધું <b>જાતે કરીને</b> શીખશો.<br>દરેક પગલું આ કાર્ડમાં સરળ ગુજરાતીમાં સમજાવ્યું છે. જ્યાં <b>નારંગી ચમકતી લાઇન</b> દેખાય, ત્યાં જ તમારે ક્લિક કરવાનું છે.',
        warn: 'ધ્યાન: ટૂર <b>સાચી એન્ટ્રીઓ</b> બનાવશે (સ્ટોક, ઓર્ડર વગેરે). તેથી ટ્રેનિંગ / ડેમો માટે જ ચલાવો.' },
      { id: 'sidebar', type: 'info', target: 'aside', title: 'ડાબી બાજુનું મેનુ',
        text: 'આખું ERP આ મેનુમાંથી ચાલે છે. ત્રણ ભાગ છે:<ul><li><b>Procurement</b> — ખરીદી (PO, GRN, QC, બિલ)</li><li><b>Inventory</b> — સ્ટોક</li><li><b>Manufacturing</b> — ઉત્પાદન</li></ul>આપણે <b>Procurement (ખરીદી)</b> થી શરૂ કરીશું.' },
      { id: 'ch-overview', type: 'info', title: 'ક્લાયન્ટના ફેરફારો: પહેલા અને હવે',
        text: '<ul><li><b>Production Line</b> — પહેલા ફક્ત મશીનો; હવે Line 1 / Line 2, દરેકની પોતાની મશીનો અને રોજની ક્ષમતા</li><li><b>Packing material</b> — recipe માં સ્પૂલ, સ્લીવ, બોક્સ</li><li><b>30 દિવસનો Material plan</b> — PO ક્યાં સુધીમાં નાખવો તે અગાઉથી</li><li><b>Flux અને Melting અલગ</b>, <b>Lab QC + TC</b> વગર આગળ નહિ</li><li><b>Scrap</b> — ફક્ત scrap લખવાનું, barcode, દિવસનું પેક</li><li><b>Rack</b> અને <b>Tally જેવો તૈયાર માલ</b> (ઓછા / વધુ સ્ટોકની ચેતવણી)</li><li><b>Spare %</b> દરેક કાચા માલનું, <b>વપરાયેલો માલ</b> સ્ટેજ પૂરું કરતાં એક જ એન્ટ્રી, બચેલો માલ આઉટપુટ પહેલાં <b>પાછો</b></li></ul>આખી ટૂરમાં દરેક પેજ પર આ ફેરફાર <b>જાતે ચલાવીને</b> બતાવીશું.' },
      { id: 'howto', type: 'info', title: 'ટૂર કેવી રીતે વાપરવી',
        text: '<ul><li><b>આગળ</b> — વાંચીને આગળ વધો</li><li>જ્યારે કહ્યું હોય કે <b>"ક્લિક કરો"</b>, ત્યારે ચમકતી જગ્યાએ જાતે ક્લિક કરો — પછી ટૂર આપોઆપ આગળ જશે</li><li><b>ડેમો વેલ્યુ ભરો</b> બટન ફોર્મ ઝડપથી ભરી આપે છે (તમે બદલી પણ શકો)</li><li>અટકી જાઓ તો <b>પગલું છોડો</b> કે <b>પાછળ</b> દબાવો; ગમે ત્યારે <b>બહાર નીકળો</b></li></ul>' }
    ]
  });

  CH.push({
    id: 'masters', title: 'નવા અને બદલાયેલા માસ્ટર', desc: 'Production line, Machine, Work stage, Rack, Vendor lead time, Product — પહેલા શું હતું અને હવે શું.',
    steps: [
      { id: 'ma-line-link', type: 'click', target: navLink('/production_lines'), title: 'Production lines ખોલો', text: 'સૌથી પહેલા નવો માસ્ટર: <b>Production lines</b>.', todo: 'ક્લિક કરો: Production lines' },
      { id: 'ma-line-info', type: 'info', path: '/production_lines', target: tableOrTitle, title: 'Production line (નવું)',
        text: '<b>પહેલા:</b> મશીનોની ફક્ત યાદી; ઓર્ડર કઈ લાઇનમાં ચાલશે તે ખબર નહિ.<br><b>હવે:</b> <b>Line 1</b> અને <b>Line 2</b>. દરેક લાઇન પાસે બધા સ્ટેજનો પોતાનો પૂરો સેટ, પોતાની મશીનો, <b>રોજની ક્ષમતા (KG/દિવસ)</b> અને <b>handler</b>. એક મશીન ફક્ત એક જ લાઇનની.' },
      { id: 'ma-mc-link', type: 'click', target: navLink('/machines'), title: 'Machines ખોલો', text: 'હવે <b>Machines</b>.', todo: 'ક્લિક કરો: Machines' },
      { id: 'ma-mc-info', type: 'info', path: '/machines', target: tableOrTitle, title: 'Machines — લાઇન પ્રમાણે',
        text: '<b>પહેલા:</b> દરેક સ્ટેજની એક મશીન, કોઈ લાઇન સાથે નહિ.<br><b>હવે:</b> દરેક સ્ટેજમાં <b>2 મશીન</b> — એક Line 1 ની, એક Line 2 ની. ક્ષમતા <b>KG/કલાક</b> માં, જેથી ઓર્ડરનો સમય આપમેળે નીકળે. (ક્ષમતા હાલ અંદાજ છે — પ્લાન્ટ પાસેથી પાક્કી કરવાની.)' },
      { id: 'ma-ws-link', type: 'click', target: navLink('/work_stages'), title: 'Work stages ખોલો', text: 'હવે <b>Work stages</b>.', todo: 'ક્લિક કરો: Work stages' },
      { id: 'ma-ws-info', type: 'info', path: '/work_stages', target: tableOrTitle, title: 'Work stage — નવા નિશાન',
        text: '<b>પહેલા:</b> Wire Drawing એક જ સ્ટેજ.<br><b>હવે:</b> ક્લાયન્ટની 3 મશીન એક લાઇનમાં છે, એટલે <b>Wire Drawing 1 / 2 / 3</b> — દરેક પાસનો ઓપરેટર અને scrap અલગ.<br><b>Melting &amp; Alloying</b> પર 3 નિશાન: <b>Batch</b> (ભઠ્ઠીની ક્ષમતા મુજબ લોટ), <b>Lab QC</b> (TC વગર આગળ નહિ), <b>Scrap later</b> (scrap ઇન્ગોટ કાસ્ટિંગ પછી લખાય).' },
      { id: 'ma-rack-link', type: 'click', target: navLink('/racks'), title: 'Racks ખોલો', text: 'હવે નવો માસ્ટર <b>Racks</b>.', todo: 'ક્લિક કરો: Racks' },
      { id: 'ma-rack-info', type: 'info', path: '/racks', target: tableOrTitle, title: 'Rack (નવું)',
        text: '<b>પહેલા:</b> માલ ગોડાઉનમાં ક્યાં પડ્યો તે ખબર નહિ.<br><b>હવે:</b> દરેક ગોડાઉનની અંદર રેક — <b>A, B, C</b> કે <b>1, 2, 3</b>. ફક્ત નામ, ક્ષમતા નહિ. GRN અને તૈયાર માલ વખતે રેક ચૂંટાય, એટલે દરેક લોટ / બેચ હંમેશા મળે.' },
      { id: 'ma-vendor-link', type: 'click', target: navLink('/vendors'), title: 'Vendors ખોલો', text: 'હવે <b>Vendors</b>.', todo: 'ક્લિક કરો: Vendors' },
      { id: 'ma-vendor-info', type: 'info', path: '/vendors', target: tableOrTitle, title: 'Vendor — Lead time',
        text: '<b>પહેલા:</b> માલ કેટલા દિવસે આવે તે ક્યાંય નહિ.<br><b>હવે:</b> દરેક vendor માં <b>Lead time (days)</b> — Edit માં ભરાય (15–20 દિવસ). Material plan તેના પરથી કહેશે કે <b>PO ક્યાં સુધીમાં નાખવો</b>.' },
      { id: 'ma-prod-link', type: 'click', target: navLink('/products'), title: 'Products ખોલો', text: 'હવે <b>Product master</b>.', todo: 'ક્લિક કરો: Products' },
      { id: 'ma-prod-info', type: 'info', path: '/products', target: tableOrTitle, title: 'Product — 3 નવી વાત',
        text: '<b>૧.</b> Recipe માં <b>stage</b>: Tin / Lead = Melting, ફક્ત Flux = Flux Preparation.<br><b>૨.</b> <b>Packing material</b> (સ્પૂલ, બોક્સ) — ઓર્ડરમાં આપમેળે ગણાય.<br><b>૩.</b> <b>Min / Max stock</b> — તૈયાર માલમાં ઓછા / વધુ સ્ટોકની ચેતવણી.' }
    ]
  });

  CH.push({
    id: 'procure', title: 'ખરીદી (Procurement)', desc: 'Purchase order, GRN (માલ આવ્યો), Inward QC, Purchase bill, Purchase return — એક PO થી સ્ટોક સુધી.',
    steps: [
      { id: 'pr-intro', type: 'info', title: 'આખી વાર્તા: ખરીદીથી તૈયાર માલ સુધી',
        text: 'હવે આપણે <b>શરૂઆતથી</b> જોઈશું — એક <b>Purchase Order</b> થી. વાર્તા આ ક્રમમાં ચાલશે:<ul><li><b>૧. ખરીદી</b> — PO બનાવો → માલ આવે (GRN) → QC પાસ → vendor નું બિલ</li><li><b>૨. સ્ટોક</b> — પાસ થયેલો માલ સ્ટોરમાં</li><li><b>૩. ઉત્પાદન</b> — ઓર્ડર, માલ આપવો, સ્ટેજ</li><li><b>૪. તૈયાર માલ</b> — Output, FG, Scrap, Variance</li></ul>' },
      { id: 'pr-po-link', type: 'click', target: navLink('/purchase_orders'), title: 'Purchase order ખોલો',
        text: 'ડાબા મેનુમાં <b>Procurement</b> હેઠળ <b>Purchase order</b>.', todo: 'ક્લિક કરો: Purchase order' },
      { id: 'pr-po-what', type: 'info', path: '/purchase_orders', target: 'main h1', title: 'Purchase order (PO) એટલે શું?',
        text: 'Vendor પાસેથી માલ મંગાવવા માટે આપેલો <b>ઑર્ડર</b> = PO. તેમાં કયો માલ, કેટલો, કયા ભાવે અને GST કેટલો — બધું લખાય છે.<br>PO પહેલાં <b>Draft</b> બને છે; vendor નું બિલ મળે ત્યારે તેને <b>Confirm</b> કરવાનો હોય છે.' },
      { id: 'pr-po-new', type: 'click', path: '/purchase_orders', target: '#btn-add-po', title: 'નવો Purchase order',
        text: 'ઉપર જમણે <b>New purchase order</b> બટન.', todo: 'ક્લિક કરો: New purchase order' },
      { id: 'pr-po-fill', type: 'fill', path: '/purchase_orders', target: '#po-form', title: 'ઑર્ડરની વિગત ભરો',
        text: 'ઉપર <b>PO date</b>, <b>Vendor</b> અને <b>Warehouse</b> (માલ આખરે ક્યાં રહેશે) પસંદ કરો. નીચે દરેક માલની એક <b>લાઇન</b>: material, quantity, rate. <b>Unit અને GST</b> material પસંદ કરતાં જ આપોઆપ આવી જાય છે.<br>નીચેનું બટન દબાવશો તો ડેમો ઓર્ડર માટેનો કાચો માલ (Tin, Lead, Flux) ભરાઈ જશે.',
        prefill: { label: 'ડેમો વેલ્યુ ભરો', run: prefillPO } },
      { id: 'pr-po-save', type: 'submit', path: '/purchase_orders', target: '#po-form', retryTo: 'pr-po-new', capture: { re: 'PO-[0-9]{4}-[0-9]+', as: 'po' }, title: 'PO સેવ કરો',
        text: 'બધું બરાબર હોય તો <b>Save purchase order</b> દબાવો. PO <b>Draft</b> તરીકે સેવ થાય છે.', todo: 'ક્લિક કરો: Save purchase order' },
      { id: 'pr-po-draft', type: 'info', path: '/purchase_orders', target: function () { return rowOf('#po-tbody tr', 'po'); }, title: 'તમારો PO બની ગયો ✅',
        text: 'નવો PO નંબર (<code>PO-…</code>) મળ્યો અને સ્થિતિ <b>Draft</b> છે. Draft માં હજી ફેરફાર થઈ શકે. હવે vendor નું બિલ મળે એટલે PO ને <b>Confirm</b> કરવો પડે.' },
      { id: 'pr-po-confirm', type: 'click', path: '/purchase_orders', target: inRow('#po-tbody tr', 'po', '.btn-confirm-po'), title: 'PO Confirm કરો',
        text: 'તમારા PO ની હરોળમાં <b>Confirm</b> બટન.', todo: 'ક્લિક કરો: Confirm' },
      { id: 'pr-po-cfill', type: 'fill', path: '/purchase_orders', target: '#confirm-po-form', title: 'Vendor નું બિલ જોડો',
        text: 'Confirm કરવા માટે vendor ના <b>બિલ / invoice ની કૉપી</b> (PDF કે ફોટો) જોડવી <b>ફરજિયાત</b> છે — એટલે ખાતરી રહે કે vendor એ ઑર્ડર સ્વીકાર્યો છે. બિલ નંબર અને તારીખ વૈકલ્પિક છે.<br>ડેમો માટે નમૂનાની ફાઇલ આપોઆપ જોડાઈ જશે.',
        prefill: { label: 'ડેમો ફાઇલ જોડો', run: prefillConfirmPO } },
      { id: 'pr-po-csubmit', type: 'submit', path: '/purchase_orders', target: '#confirm-po-form', retryTo: 'pr-po-confirm', title: 'Confirm દબાવો',
        text: 'હવે નીચે <b>Confirm — move to Open</b> દબાવો. PO <b>Open</b> થઈ જશે અને માલ આવવાની રાહ જોશે.', todo: 'ક્લિક કરો: Confirm — move to Open' },
      { id: 'pr-po-tab', type: 'click', path: '/purchase_orders', target: 'main a[href*="tab=completed"]', title: 'Completed ટૅબ',
        text: 'Confirm થયેલા PO Draft યાદીમાંથી નીકળી <b>Completed</b> ટૅબમાં જાય છે.', todo: 'ક્લિક કરો: Completed' },
      { id: 'pr-po-open', type: 'info', path: '/purchase_orders', target: function () { return rowOf('#po-tbody tr', 'po'); }, title: 'PO હવે Open છે ✅',
        text: 'તમારો PO <b>Open</b> છે. હવે તેનો માલ <b>GRN</b> પેજ પર "આવવાનો બાકી" તરીકે દેખાશે. ધારો કે ટ્રક ગેટ પર આવી ગઈ!' },

      { id: 'pr-grn-link', type: 'click', target: navLink('/grns'), title: 'Gate inward / GRN ખોલો',
        text: 'માલ ગેટ પર આવે ત્યારે <b>Gate inward / GRN</b> માં નોંધ થાય.', todo: 'ક્લિક કરો: Gate inward / GRN' },
      { id: 'pr-grn-what', type: 'info', path: '/grns', target: 'main h1', title: 'GRN એટલે શું?',
        text: '<b>GRN (Goods Receipt Note)</b> = માલ ખરેખર ગેટ પર આવ્યો તેની રસીદ. PO માં ૧૦૦ લખ્યું હોય પણ ટ્રકમાં ૯૦ આવ્યો, તો GRN માં <b>૯૦</b> જ લખાય. નીચે <b>Pending</b> માં એ PO દેખાય છે જેનો માલ આવવાનો બાકી છે.' },
      { id: 'pr-grn-recv', type: 'click', path: '/grns', target: inRow('tr.grn-row', 'po', '.btn-receive'), title: 'Receive goods',
        text: 'તમારા PO ની હરોળમાં <b>Receive goods</b>.', todo: 'ક્લિક કરો: Receive goods' },
      { id: 'pr-grn-fill', type: 'fill', path: '/grns', target: '#grn-form', title: 'શું આવ્યું તે ભરો',
        text: 'તારીખ, vendor નો <b>challan નંબર</b>, ગાડી / ટ્રાન્સપોર્ટરની વિગત, અને દરેક material માટે <b>ખરેખર આવેલી quantity</b> તથા <b>Batch / Lot નંબર</b> ભરો. Lot નંબર vendor ના માલ પર લખેલો હોય છે — એનાથી પછી પણ ખબર પડે કે માલ ક્યાંથી આવ્યો.',
        prefill: { label: 'ડેમો વેલ્યુ ભરો', run: prefillGRN } },
      { id: 'pr-grn-rack', type: 'info', path: '/grns', target: '#grn-form .line-rack', title: 'Rack (નવું)',
        text: '<b>પહેલા:</b> માલ ફક્ત ગોડાઉનમાં આવતો.<br><b>હવે:</b> દરેક લાઇનમાં <b>Rack</b> ચૂંટાય — QC પાસ પછી માલ તે ગોડાઉનના કયા રેકમાં મૂકવો. ફરજિયાત નથી.' },
      { id: 'pr-grn-post', type: 'submit', path: '/grns', target: '#grn-form', submitter: 'post', retryTo: 'pr-grn-recv', title: 'Post GRN',
        text: 'હવે <b>Post GRN</b> દબાવો. માલ સ્ટોકમાં આવી જાય છે, પણ <b>QC Hold</b> ગોડાઉનમાં — એટલે ચકાસણી પૂરી ન થાય ત્યાં સુધી ઉત્પાદનમાં વાપરી શકાતો નથી.', todo: 'ક્લિક કરો: Post GRN' },
      { id: 'pr-grn-done', type: 'info', path: '/grns', target: 'main h1', title: 'GRN પોસ્ટ થઈ ✅',
        text: 'GRN બની ગઈ (Completed ટૅબમાં). માલ હવે <b>QC માટે રાહ જોતા</b> લોટ તરીકે સ્ટોકમાં છે. આગળનું પગલું: <b>Inward QC</b> — માલ સારો છે કે નહિ તે તપાસવું.' },

      { id: 'pr-qc-link', type: 'click', target: navLink('/inward_qc'), title: 'Inward QC ખોલો',
        text: 'આવેલા માલની ગુણવત્તા અહીં તપાસાય.', todo: 'ક્લિક કરો: Inward QC' },
      { id: 'pr-qc-what', type: 'info', path: '/inward_qc', target: function () { return rowOf('tr.qc-row', 'po'); }, title: 'તપાસવા માટેના લોટ',
        text: 'GRN ની <b>દરેક લાઇન (લોટ)</b> અલગ તપાસાય છે. "Not inspected" એટલે ચકાસણી બાકી. દરેક material ના <b>test</b> (જેમ કે purity, ભેજ) Raw material માસ્ટરમાં નક્કી કરેલા હોય છે.' },
      { id: 'pr-qc-open', type: 'click', path: '/inward_qc', target: inRow('tr.qc-row', 'po', '.btn-inspect-line'), title: 'પહેલો લોટ Inspect કરો',
        text: 'તમારા PO ના પહેલા લોટની હરોળમાં <b>Inspect</b>.', todo: 'ક્લિક કરો: Inspect' },
      { id: 'pr-qc-fill', type: 'fill', path: '/inward_qc', target: '#inspect-form', title: 'QC નું પરિણામ ભરો',
        text: 'ઇન્સ્પેક્ટરનું નામ, <b>Sample size</b>, અને <b>Passed / Rejected</b> quantity ભરો. નીચે દરેક <b>test</b> નું પરિણામ (માપ કે Pass/Fail) લખવું જરૂરી છે — માપ નક્કી હદ (Min–Max) ની બહાર હોય તો <b>Fail</b> દેખાય. ફક્ત <b>Passed</b> qty જ વાપરવા લાયક સ્ટોરમાં જાય છે; Rejected નહિ.',
        prefill: { label: 'ડેમો વેલ્યુ ભરો', run: prefillQC } },
      { id: 'pr-qc-submit', type: 'submit', path: '/inward_qc', target: '#inspect-form', submitter: 'submit', retryTo: 'pr-qc-open', title: 'Submit result',
        text: 'બધા test ભરાયા પછી <b>Submit result</b> દબાવો. (<b>Save draft</b> માં માત્ર સેવ થાય, સ્ટોક ન ફરે.)', todo: 'ક્લિક કરો: Submit result' },
      { id: 'pr-qc-rest', type: 'action', path: '/inward_qc', target: 'main h1', title: 'બાકીના લોટ (ડેમો શૉર્ટકટ)',
        text: 'બાકીના લોટ પણ આ જ રીતે તપાસવાના છે. સમય બચાવવા નીચેનું બટન બાકીના લોટનું QC આ જ નિયમોથી એક ક્લિકમાં કરી આપશે (બધા test Pass).',
        button: { label: 'બાકીના લોટ તપાસો', run: qcRestDemo } },
      { id: 'pr-qc-done', type: 'info', path: '/inward_qc', target: 'main h1', title: 'QC પૂરું ✅',
        text: 'બધા લોટ <b>Passed</b> થયા (Completed ટૅબમાં). માલ હવે QC Hold માંથી નીકળીને <b>Store</b> માં <b>Available</b> થઈ ગયો — ઉત્પાદનમાં વાપરી શકાય. કોઈ qty reject થાય તો <b>Rejection memo</b> આપોઆપ બને છે અને માલ vendor ને પાછો જઈ શકે.' },

      { id: 'pr-pi-link', type: 'click', target: navLink('/purchase_invoices'), title: 'Purchase invoice ખોલો',
        text: 'માલ પાસ થયો, હવે vendor નું બિલ નોંધીએ.', todo: 'ક્લિક કરો: Purchase invoice' },
      { id: 'pr-pi-what', type: 'info', path: '/purchase_invoices', target: function () { return rowOf('tr.pi-row', 'po'); }, title: 'બિલ બનાવવાનું બાકી',
        text: 'જે GRN નું બિલ બાકી છે તે <b>To bill</b> માં દેખાય છે. અહીં vendor નું બિલ નોંધી હિસાબમાં <b>vendor ને કેટલા ચૂકવવાના</b> (payable) તે નક્કી થાય છે.' },
      { id: 'pr-pi-create', type: 'click', path: '/purchase_invoices', target: inRow('tr.pi-row', 'po', '.btn-create-bill'), title: 'Create bill',
        text: 'તમારા GRN ની હરોળમાં <b>Create bill</b>.', todo: 'ક્લિક કરો: Create bill' },
      { id: 'pr-pi-fill', type: 'fill', path: '/purchase_invoices', target: '#pi-form', title: 'બિલની વિગત',
        text: 'બિલની લાઇનો GRN માંથી આપોઆપ આવી ગઈ છે — માલ, qty, PO નો ભાવ અને GST. તમારે ફક્ત <b>Vendor invoice no.</b> અને તારીખ લખવાની. ભાડું વગેરે વધારાનો ખર્ચ હોય તો <b>+ Add charge</b>. નીચે <b>Bill total</b> દેખાય છે.',
        prefill: { label: 'ડેમો વેલ્યુ ભરો', run: prefillBill } },
      { id: 'pr-pi-post', type: 'submit', path: '/purchase_invoices', target: '#pi-form', submitter: 'post', confirm: true, retryTo: 'pr-pi-create', title: 'Post bill',
        text: 'હવે <b>Post bill</b> દબાવો અને પુષ્ટિમાં ફરી <b>Post bill</b>. પોસ્ટ કરતાં vendor નું <b>payable</b> (ચૂકવવાની રકમ) વધે છે.', todo: 'ક્લિક કરો: Post bill' },
      { id: 'pr-pi-done', type: 'info', path: '/purchase_invoices', target: 'main h1', title: 'બિલ પોસ્ટ થયું ✅',
        text: 'બિલ પોસ્ટ થયું અને GRN હવે "To bill" માંથી નીકળી ગઈ. Vendor નું ચૂકવવાનું (payable) નોંધાઈ ગયું. આમ <b>PO → GRN → QC → Bill</b> નું ચક્ર પૂરું.' },
      { id: 'pr-ret-link', type: 'click', target: navLink('/purchase_returns'), title: 'Purchase return',
        text: 'કોઈ વાર માલ vendor ને પાછો પણ મોકલવો પડે.', todo: 'ક્લિક કરો: Purchase return' },
      { id: 'pr-ret-info', type: 'info', path: '/purchase_returns', target: 'main h1', title: 'Purchase return — માલ vendor ને પાછો',
        text: 'માલ ખરાબ નીકળે કે વધારે આવી જાય તો <b>vendor ને પાછો</b> મોકલવા માટે. તે Purchase invoice પેજના <b>Return</b> બટનથી બનાવાય છે. પાછો ગયેલો માલ સ્ટોકમાંથી ઘટે છે અને vendor નું payable પણ ઘટે છે.<br>(આપણો માલ ઉત્પાદનમાં વાપરવો છે, એટલે ડેમોમાં return કરતા નથી.)' }
    ]
  });

  CH.push({
    id: 'stock', title: 'સ્ટોક (Inventory)', desc: 'Stock ledger, લોટ, Valuation, Transfer, Adjustment, Opening stock.',
    steps: [
      { id: 'st-link', type: 'click', target: navLink('/inventory/stock'), title: 'Stock ledger ખોલો', text: 'હવે જોઈએ કે સ્ટોકમાં માલ ક્યાં કેટલો છે.', todo: 'ક્લિક કરો: Stock ledger' },
      { id: 'st-from-po', type: 'info', path: '/inventory/stock', target: 'main h1', title: 'ખરીદીથી આવેલો માલ',
        text: 'જુઓ — આપણે PO થી મંગાવેલો માલ હવે અહીં <b>Available</b> તરીકે સ્ટોકમાં છે. Opening stock કર્યો નથી, છતાં સ્ટોક છે — કારણ કે <b>GRN + QC પાસ</b> થતાં જ માલ આપોઆપ સ્ટોકમાં ચઢે છે.' },
      { id: 'st-kpi', type: 'info', path: '/inventory/stock', target: '.sc-card', title: 'ઉપરના ચાર કાર્ડ',
        text: 'આખા સ્ટોકનો એક નજરમાં હિસાબ: <b>કેટલા material</b>, <b>સ્ટોકની કિંમત</b>, <b>QC માટે રાહ જોતા લોટ</b> અને <b>રિજેક્ટ થયેલા લોટ</b>. જો કોઈ material ઓછો થઈ જાય તો નીચે <b>"Needs attention"</b> માં લાલ ચેતવણી પણ આવે છે.' },
      { id: 'st-card', type: 'info', path: '/inventory/stock', target: '.stock-card', title: 'Material પ્રમાણે સ્ટોક',
        text: 'દરેક material નું કાર્ડ: <ul><li><b>Available</b> — વાપરવા લાયક માલ (સ્ટોરમાં)</li><li><b>Waiting for QC</b> — ખરીદી આવી, QC બાકી</li><li><b>In production</b> — ઉત્પાદનમાં (WIP) ગયેલો માલ</li><li><b>Rejected</b> — QC માં નાપાસ</li></ul>' },
      { id: 'st-open', type: 'click', path: '/inventory/stock', target: function () { var cards = $$('.stock-card'); return cards.filter(function (c) { return parseInt(c.getAttribute('data-live') || '0', 10) > 0; })[0] || cards[0] || null; }, title: 'કાર્ડ પર ક્લિક — બધા લોટ',
        text: 'હવે <b>કોઈ પણ માલના કાર્ડ પર ક્લિક</b> કરો — તે માલના <b>બધા લોટ</b> બધા કાર્ડની નીચે ખુલે છે. વપરાઈ ગયેલા લોટ ડિફોલ્ટ રૂપે છુપાયેલા રહે છે; જોઈએ તો <b>Show used-up lots</b> થી બતાવો.', todo: 'ક્લિક કરો: માલનું કાર્ડ' },
      { id: 'st-lot', type: 'info', path: '/inventory/stock', target: '.lot-row', title: 'લોટ (Lot) એટલે શું?',
        text: 'દરેક <b>લોટ</b> = માલનો એક જથ્થો (<code>LOT-0001</code>). Opening stock અને દરેક ખરીદીનો પોતાનો લોટ બને છે, જેથી <b>કયો માલ ક્યાંથી આવ્યો અને ક્યાં ગયો</b> તે હંમેશા ખબર પડે (traceability).' },
      { id: 'st-rack', type: 'info', path: '/inventory/stock', target: function () { var r = $('.lot-row'); return r ? r.children[2] : null; }, title: 'Rack કૉલમ (નવું)',
        text: '<b>પહેલા:</b> લોટ મળતો, પણ ક્યાં પડ્યો તે નહિ.<br><b>હવે:</b> દરેક લોટની સામે <b>Rack</b> લખેલો દેખાય છે, અને તેનાથી શોધી પણ શકાય.' },
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
        text: 'ગોડાઉનમાં ગણતરી કરતાં ફરક મળે (તૂટ-ફૂટ, ચોરી, ભૂલ) તો <b>કારણ લખીને</b> સ્ટોક વધારી/ઘટાડી શકાય. દરેક સુધારો <b>મંજૂરી અને ઓડિટ</b> સાથે નોંધાય છે.' },
      { id: 'os-link', type: 'click', target: navLink('/opening_stock'), title: 'Opening stock',
        text: 'છેલ્લે એક જોવા જેવું: ડાબા મેનુમાં <b>Inventory</b> હેઠળ <b>Opening stock</b>.', todo: 'ક્લિક કરો: Opening stock' },
      { id: 'os-what', type: 'info', path: '/opening_stock', target: 'main h1', title: 'Opening stock એટલે શું?',
        text: 'સોફ્ટવેર શરૂ કરતાં પહેલાં ગોડાઉનમાં જે માલ પડ્યો હતો, તે <b>એક જ વાર</b> અહીંથી ચઢાવાય. એ પછી બધો માલ <b>ખરીદી (PO → GRN → QC)</b> થી જ આવે છે — જેમ આપણે હમણાં જોયું. આપણા ડેમોમાં અહીં કંઈ કરવાનું નથી.' }
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
        text: '<b>૧.</b> Product category પસંદ કરો, પછી attributes (Alloy, Thickness…) એક પછી એક — ફક્ત મળતા options જ દેખાય.<br><b>૨.</b> કેટલું બનાવવું (Quantity).<br><b>૩.</b> લાઇન અને મશીન અહીં ચૂંટવાના નથી — એ <b>Production planning</b> માં ચૂંટાય (નવું!).<br>નીચેનું બટન ડેમો માટે <b>100 KG</b> ભરી આપશે.',
        prefill: { label: 'ડેમો વેલ્યુ ભરો', run: prefillOrder } },
      { id: 'po-allow', type: 'info', path: '/production_orders', target: '#mo-lines', title: 'Spare % — દરેક માલનું અલગ',
        text: '<b>પહેલા:</b> બગાડ માટે વધારાનો માલ ગણવાનો કોઈ રસ્તો નહિ; ખૂટે તો નવો issue / PO.<br><b>હવે:</b> દરેક કાચા માલની સામે <b>Spare %</b> — જેમ કે Tin 10%, Lead 0%, Flux 25%. એટલો વધારાનો માલ issue થઈ શકે; <b>વપરાય નહિ તો store માં પાછો</b>. (ડેમો ઓર્ડરમાં spare 0 રાખ્યું છે.)' },
      { id: 'po-expected', type: 'info', path: '/production_orders', target: '#sum-expected', title: 'Expected delivery (નવું)',
        text: '<b>પહેલા:</b> ઓર્ડર ભરનારે લાઇન અને મશીન ચૂંટવા પડતા.<br><b>હવે:</b> ફક્ત <b>Expected delivery</b> — આ ઓર્ડર કતારના છેડે મૂકીએ તો ક્યારે તૈયાર થશે. કતાર, મશીન અને કાચો માલ ગણીને સિસ્ટમ જ તારીખ કાઢે છે. લાઇન અને મશીન પછી <b>Production planning</b> માં production manager ચૂંટે.' },
      { id: 'po-side', type: 'info', path: '/production_orders', target: '.po-side', title: 'Order summary',
        text: 'જમણી બાજુ સારાંશ: <b>કુલ સમય, રોજનું વધુમાં વધુ ઉત્પાદન</b> અને <b>કાચા માલનું ચેક</b>. "In store" કૉલમમાં દેખાય છે કે સ્ટોકમાં માલ છે કે નહિ — <b>Short</b> લખ્યું હોય તો માલ ઓછો છે.' },
      { id: 'po-bundle', type: 'info', path: '/production_orders', target: 'button[name="add_another"]', title: 'Bundle — એક પાર્ટી, ઘણા પ્રોડક્ટ (નવું)',
        text: '<b>પહેલા:</b> પાર્ટીના એક ઓર્ડરમાં ઘણા પ્રોડક્ટ હોય તો દરેકનો ઓર્ડર અલગ, કોઈ સંબંધ નહિ.<br><b>હવે:</b> <b>Save &amp; add another item</b> દબાવો — ઓર્ડર સેવ થાય, <b>BND-વર્ષ-નંબર</b> બને અને ફોર્મ ફરી ખુલે. દરેક item નો પોતાનો PROD ઓર્ડર, રેસિપી અને plan; કાર્ડ પર <b>Bundle</b> ચિપથી બધા item એકસાથે જોવાય. (ડેમોમાં આપણે એક જ item સેવ કરીશું.)' },
      { id: 'po-save', type: 'submit', path: '/production_orders', target: '#mo-form', retryTo: 'po-new', capture: { re: 'PROD-[0-9]{4}-[0-9]+', as: 'order' }, title: 'કતારમાં સેવ કરો',
        text: 'નીચે <b>Save to queue</b> દબાવો. નવો ઓર્ડર કતારના <b>છેડે</b> જોડાશે.', todo: 'ક્લિક કરો: Save to queue' },
      { id: 'po-card', type: 'info', path: '/production_orders', target: function () { return orderCard('.po-card'); }, title: 'તમારો ઓર્ડર કતારમાં છે',
        text: 'એક જ લાઇનમાં: <b>કતારનો નંબર</b>, <b>Status</b> અને <b>શરૂ-પૂર્ણ થવાની તારીખ</b> (કતાર + મશીન + માલ પરથી આપોઆપ). Draft પર નારંગી <b>Needs planning</b> ચિપ — લાઇન-મશીન હજી ચૂંટાયા નથી. આ પેજ ઓર્ડર ઉમેરવા અને <b>શું થયું</b> તે જોવા માટે છે; Plan, Release, Start, ▲▼ અને Cancel (Released પછી) <b>Production planning</b> પેજ પર.' },
      { id: 'po-open', type: 'click', path: '/production_orders', target: inCard('.po-card', '.po-chev'), title: 'વિગત ખોલો', text: 'કાર્ડના જમણા છેડે <b>▾</b> તીર છે.', todo: 'ક્લિક કરો: ▾' },
      { id: 'po-detail', type: 'info', path: '/production_orders', target: inCard('.po-card', '.po-detail'), title: 'Plan અને કાચો માલ',
        text: 'ડાબે <b>Production plan</b> — દરેક સ્ટેજ, મશીન, કલાક અને તારીખ. જમણે <b>Raw material</b> — દરેક માલની જરૂર અને કેટલો અપાઈ ગયો. સ્ટોક / ખરીદીની સ્થિતિ <b>Production planning</b> પર.' },
      { id: 'pl-note', type: 'info', path: '/production_orders', target: inCard('.po-card', 'a[href*="production_planning"]'), when: flag('plan_needed'), title: 'Plan અને Release — Production planning પર (નવું)',
        text: 'ઓર્ડર <b>Draft</b> છે. અહીં Release / Plan બટન નથી — ઓર્ડર sales/office ભરે છે, <b>Production manager</b> લાઇન-મશીન ચૂંટીને Release કરે છે. તેના માટે <b>Planning →</b> લિંક.' },
      { id: 'pl-link', type: 'click', target: navLink('/production_planning'), when: flag('plan_needed'), title: 'Production planning ખોલો', text: 'ડાબા મેનુમાં <b>Production planning</b> (નવું).', todo: 'ક્લિક કરો: Production planning' },
      { id: 'pl-page', type: 'info', path: '/production_planning', target: function () { return orderCard('.pp-card'); }, when: flag('plan_needed'), title: 'Production planning પેજ',
        text: 'ઉપર ચાર કાર્ડ: <b>Needs planning</b>, <b>Ready to release</b>, <b>Need material</b>, <b>Will be late</b>. દરેક ઓર્ડરમાં <b>Expected delivery</b>, <b>needed-by</b> પ્રમાણે On time / Late, અને <b>કાચા માલની</b> સ્થિતિ. ડાબે ▲▼ થી કતાર બદલાય; જમણે <b>Plan</b>, Make first, Cancel.' },
      { id: 'pl-plan', type: 'click', path: '/production_planning', target: inCard('.pp-card', '.btn-resched'), when: flag('plan_needed'), title: 'Plan દબાવો', text: 'આ ઓર્ડર માટે લાઇન અને મશીન ચૂંટીએ.', todo: 'ક્લિક કરો: Plan' },
      { id: 'pl-fill', type: 'fill', path: '/production_planning', target: '#rs-form', when: flag('plan_needed'), title: 'લાઇન અને મશીન ચૂંટો',
        text: 'ઉપર <b>Production line</b> ચૂંટો — ફક્ત તે લાઇનની મશીનો ટિક થાય. નીચે દરેક સ્ટેજના મશીન અને <b>કલાક</b>. વધુ મશીન = ઓછો સમય.',
        prefill: { label: 'પહેલી લાઇન ચૂંટો', run: function () { var l = $('#rs-line'); if (l && !l.value && l.options.length > 1) setVal(l, l.options[1].value); return sleep(300); } } },
      { id: 'pl-save', type: 'submit', path: '/production_planning', target: '#rs-form', retryTo: 'pl-plan', when: flag('plan_needed'), title: 'Save plan', text: '<b>Save plan</b> દબાવો. પ્લાન પાકો થઈ ગયો અને પાછા Production planning પર આવીશું.', todo: 'ક્લિક કરો: Save plan' },
      { id: 'pl-tab', type: 'click', path: '/production_planning', target: '.pp-tabs a[href*="tab=ready"]', when: flag('plan_needed'), title: 'Ready to release', text: 'પ્લાન થઈ ગયેલો ઓર્ડર હવે <b>Ready to release</b> ટૅબમાં છે.', todo: 'ક્લિક કરો: Ready to release' },
      { id: 'pl-ready', type: 'info', path: '/production_planning', target: function () { return orderCard('.pp-card'); }, when: flag('plan_needed'), title: 'પ્લાન પાકો ✅',
        text: 'કાર્ડમાં હવે <b>Planned · લાઇનનું નામ</b>, અને <b>Change plan</b> તથા <b>Release</b> બટન.' },
      { id: 'po-rel', type: 'click', path: /^\/production_(planning|orders)$/, goto: '/production_planning?tab=ready', target: inCard('.pp-card', 'form[action*="/release/"] button'), title: 'Release કરો',
        text: 'હવે <b>Release</b> કરો. આ પછી જ સ્ટોરમાંથી તેનો કાચો માલ આપી શકાશે.', todo: 'ક્લિક કરો: Release' },
      { id: 'po-rel-ok', type: 'click', target: '#erp-confirm-root.is-open .erp-confirm__btn--ok', retryTo: 'po-rel', title: 'પુષ્ટિ કરો', text: 'ખાતરી માટે પૂછશે. <b>Release</b> દબાવો.', todo: 'ક્લિક કરો: Release (પુષ્ટિ)' },
      { id: 'po-rel-done', type: 'info', path: '/production_planning', goto: '/production_planning?tab=queue', target: function () { return orderCard('.pp-card'); }, title: 'ઓર્ડર Released ✅',
        text: 'ઓર્ડર હવે <b>Released &amp; running</b> ટૅબમાં છે (Release પછી પણ તમે Production planning પર જ રહો છો). હવે <b>Material issue</b> માંથી તેનો માલ આપીએ.' }
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
        prefill: { label: 'ડેમો વેલ્યુ ભરો', run: function () { setPerson($('#mi-form [name=issued_by_user_id]')); setPerson($('#mi-form [name=received_by_user_id]')); var f = $('#mi-fill'); if (f) f.click(); return Promise.resolve(); } } },
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
        prefill: { label: 'ડેમો વેલ્યુ ભરો', run: function () { var q = $('#mr-lines .mr-qty'); if (q) setVal(q, '1'); setPerson($('#mr-form [name=returned_by_user_id]')); return Promise.resolve(); } } },
      { id: 'mi-ret-post', type: 'submit', path: '/material_issues', target: '#mr-form', retryTo: 'mi-menu', title: 'Post return', text: '<b>Post return</b> દબાવો. માલ WIP માંથી સ્ટોરમાં પાછો આવી જશે.', todo: 'ક્લિક કરો: Post return' },
      { id: 'mi-ret-done', type: 'info', path: '/material_issues', target: '.mi-card', title: 'Return નોંધાયું ✅',
        text: 'હવે <b>Returns</b> ટૅબમાં આ MR (Material return) દેખાય છે. આ ઓર્ડરનો ગણાતો "આપેલો માલ" 1 KG ઘટ્યો, એટલે ફરી થોડો માલ આપવાનો બાકી છે.' },
      { id: 'mi-to', type: 'click', path: '/material_issues', target: '.mi-tabs a[href*="tab=issue"]', title: 'ફરી To issue ટૅબ', text: 'બાકીનો 1 KG ફરી આપી દઈએ.', todo: 'ક્લિક કરો: To issue' },
      { id: 'mi-all', type: 'click', path: '/material_issues', target: inCard('.mi-card', 'form[action*="/material_issues/add"] button'), title: 'Issue all available',
        text: 'આ બટન <b>એક ક્લિકમાં</b> બાકી રહેલો બધો માલ (જે સ્ટોરમાં છે તેટલો) આપી દે છે.', todo: 'ક્લિક કરો: Issue all available' },
      { id: 'mi-all-ok', type: 'click', target: '#erp-confirm-root.is-open .erp-confirm__btn--ok', retryTo: 'mi-all', title: 'પુષ્ટિ', text: '<b>Issue now</b> દબાવો.', todo: 'ક્લિક કરો: Issue now' },
      { id: 'mi-extra', type: 'info', path: '/material_issues', target: 'main h1', title: 'Spare અને Extra issue',
        text: '<b>પહેલા:</b> જેટલો જોઈએ તેટલો જ issue, પછી રસ્તો બંધ.<br><b>હવે:</b> ૧) <b>Needed</b> અને <b>Spare</b> અલગ દેખાય; spare લેવો જરૂરી નથી (<b>Fill with spare</b>). ૨) ચાલુ ઓર્ડરનો બધો માલ અપાઈ ગયો હોય તોય <b>Issue extra material</b> બટન મળે — જરૂરી + spare થી વધુ આપવો હોય તો <b>Remarks</b> માં કારણ લખવાનું.' },
      { id: 'mi-end', type: 'info', path: '/material_issues', target: 'main h1', title: 'માલ પૂરો અપાઈ ગયો ✅', text: 'હવે ઓર્ડરને ઉત્પાદનમાં <b>Start</b> કરી શકાય.' }
    ]
  });

  CH.push({
    id: 'routing', title: 'Start અને Routing (સ્ટેજ)', desc: 'ઓર્ડર Start કરો, દરેક સ્ટેજમાં ઓપરેટર, મશીન, qty, scrap.',
    steps: [
      { id: 'st-po', type: 'click', target: navLink('/production_planning'), title: 'ફરી Production planning', text: 'ઓર્ડરને હવે <b>Start</b> કરવાનો — તે <b>Production planning</b> પર છે.', todo: 'ક્લિક કરો: Production planning' },
      { id: 'st-tab', type: 'click', path: '/production_planning', target: '.pp-tabs a[href*="tab=queue"]', title: 'Released & running', text: 'Release થયેલા ઓર્ડર આ ટૅબમાં.', todo: 'ક્લિક કરો: Released & running' },
      { id: 'st-start', type: 'click', path: '/production_planning', target: inCard('.pp-card', 'form[action*="/start/"] button, .btn-start-line'), title: 'Start production',
        text: 'માલ આપાઈ ગયો હોય તો <b>Start</b> દેખાય છે. Start થતાં ઓર્ડરની <b>તારીખો આજથી નક્કી</b> થઈ જાય, અને બાકી ઓર્ડરો તેની આસપાસ ગોઠવાય.', todo: 'ક્લિક કરો: Start' },
      { id: 'st-line', type: 'submit', path: '/production_planning', target: '#start-form', retryTo: 'st-start',
        when: function () { var m = $('#start-modal'); return !!m && !m.classList.contains('hidden'); },
        title: 'Production line ચૂંટો',
        text: 'ઓર્ડર બનાવતાં ચૂંટેલી <b>Production line</b> અહીં પહેલેથી ચૂંટાયેલી છે (બીજી લાઇનો ઝાંખી). દરેક લાઇન પર <b>હાલ કયો ઓર્ડર ચાલે છે</b>, કેટલો માલ બાકી છે અને લાઇન <b>ક્યારથી ખાલી</b> થશે તે દેખાય છે.',
        prefill: { label: 'પહેલી લાઇન ચૂંટો', run: function () { var r = $('#start-form input[name=line_id]:checked') || $('#start-form input[name=line_id]:not(:disabled)'); if (r) { r.checked = true; r.dispatchEvent(new ctx.win.Event('change', { bubbles: true })); } return sleep(150).then(function () { var t = $('#start-reason'); if (t && !t.closest('.hidden')) setVal(t, 'Demo order - no other order waiting'); }); } } },
      { id: 'st-start-ok', type: 'click', when: function () { return !!$('#erp-confirm-root.is-open'); }, target: '#erp-confirm-root.is-open .erp-confirm__btn--ok', retryTo: 'st-start', title: 'પુષ્ટિ', text: '<b>Start</b> દબાવો.', todo: 'ક્લિક કરો: Start (પુષ્ટિ)' },
      { id: 'st-run', type: 'info', path: '/production_planning', target: function () { return orderCard('.pp-card'); }, title: 'ઓર્ડર ચાલુ થઈ ગયો ✅',
        text: 'Status <b>In production</b> (ઉપર "In production" ગ્રુપમાં). હવે તેને Move/Cancel/Reschedule થઈ ન શકે (તારીખો ફિક્સ). ઉત્પાદનમાં દરેક સ્ટેજનું કામ <b>Routing</b> માં નોંધાય છે.' },
      { id: 'rt-link', type: 'click', target: navLink('/routing'), title: 'Routing / stages', text: 'સ્ટેજ-વાર ખરું કામ અહીં નોંધાય.', todo: 'ક્લિક કરો: Routing / stages' },
      { id: 'rt-pipe', type: 'info', path: '/routing', target: inCard('.rt-card', '.rt-pipe'), title: 'સ્ટેજની પાઇપલાઇન',
        text: 'ઓર્ડર જે સ્ટેજમાંથી પસાર થવાનો તે હરોળમાં છે: <b>✓ Done</b> (લીલું), <b>In progress</b> (નારંગી), <b>Pending</b> (રાખોડી). દરેકમાં આયોજિત કલાક અને પછી <b>ખરા કલાક</b> દેખાશે. સ્ટેજ <b>એક પછી એક</b> જ ચાલે.' },
      { id: 'rt-wd', type: 'info', path: '/routing', target: inCard('.rt-card', '.rt-pipe'), when: flag('wd_split'), title: 'Wire Drawing — 3 સ્ટેજ',
        text: '<b>પહેલા:</b> Wire Drawing એક સ્ટેજ (8 સ્ટેજ).<br><b>હવે:</b> પાઇપલાઇનમાં <b>Wire Drawing 1 → 2 → 3</b> (કુલ 10 સ્ટેજ). ત્રણ મશીન એક લાઇનમાં, એક પછી એક પાસ — દરેકનો ઓપરેટર અને scrap અલગ નોંધાય.' },
      { id: 'rt-start', type: 'click', path: '/routing', target: inCard('.rt-card', '.rt-act'), title: 'પહેલું સ્ટેજ Start કરો', text: 'કાર્ડના જમણે નારંગી <b>Start …</b> બટન.', todo: 'ક્લિક કરો: Start (સ્ટેજ)' },
      { id: 'rt-start-fill', type: 'fill', path: '/routing', target: '#rt-form', title: 'ઓપરેટર અને સમય',
        text: '<b>Operator</b> — આ સ્ટેજ કોણ ચલાવે છે તેનું નામ. <b>Started at</b> — ડિફોલ્ટ હમણાંનો સમય (મોડું નોંધતા હો તો બદલી શકાય).',
        prefill: { label: 'ડેમો વેલ્યુ ભરો', run: function () { setPerson($('#rt-operator')); return Promise.resolve(); } } },
      { id: 'rt-start-post', type: 'submit', path: '/routing', target: '#rt-form', retryTo: 'rt-start', title: 'Start stage', text: '<b>Start stage</b> દબાવો.', todo: 'ક્લિક કરો: Start stage' },
      { id: 'db-link', type: 'click', target: navLink('/dashboard'), title: 'Dashboard ખોલો (નવું)', text: 'સ્ટેજ ચાલુ છે. હવે જોઈએ કે મશીન પર શું ચાલે છે — ડાબા મેનુમાં <b>Dashboard</b>.', todo: 'ક્લિક કરો: Dashboard' },
      { id: 'db-board', type: 'info', path: '/dashboard', target: '.db-kpi', title: 'Live machine dashboard',
        text: '<b>પહેલા:</b> કયું મશીન ચાલે છે તે જાણવા Routing પેજ ખોલવું પડતું.<br><b>હવે:</b> બધી <b>Production line</b> અને તેના મશીન એક સ્ક્રીન પર — <b>Running</b>, <b>Free</b>, <b>Inactive</b>. ચાલુ મશીન પર ઓર્ડર, <b>ટાઇમર</b>, ઓપરેટર અને પછીનું સ્ટેજ. પેજ જાતે અપડેટ થાય છે.' },
      { id: 'db-tile', type: 'info', path: '/dashboard', target: function () { var no = state && state.vars && state.vars.order; var t = $$('.db-tile.running'); return t.filter(function (x) { return no && x.textContent.indexOf(no) !== -1; })[0] || t[0] || null; }, title: 'ચાલુ મશીન',
        text: 'આ મશીન પર <b>તમારો ઓર્ડર</b> ચાલે છે. ટાઇમર પ્લાન કરેલા સમય સામે દોડે છે; સમય વધી જાય તો <b>over plan</b> ચિપ દેખાય. એક મશીન પર એક જ ઓર્ડર — બીજો ઓર્ડર એ જ મશીન પર ચલાવવા જાઓ તો સિસ્ટમ અટકાવે (clash lock).' },
      { id: 'db-open', type: 'click', path: '/dashboard', target: function () { var no = state && state.vars && state.vars.order; var t = $$('.db-tile.running'); return t.filter(function (x) { return no && x.textContent.indexOf(no) !== -1; })[0] || t[0] || null; }, title: 'મશીન પર ક્લિક', text: 'મશીન કાર્ડ પર ક્લિક કરો.', todo: 'ક્લિક કરો: મશીન કાર્ડ' },
      { id: 'db-pop', type: 'info', path: '/dashboard', target: '#db-body', title: 'મશીનની Queue અને ઝડપ',
        text: 'ઉપર <b>Learned speed</b> — છેલ્લા રનમાં મશીન ખરેખર કેટલા KG/કલાક ચાલ્યું (ફક્ત બતાવવા માટે, પ્લાન ક્ષમતા પરથી જ ચાલે). નીચે <b>Queue for this machine</b> — આ મશીન પર આગળ કયો ઓર્ડર આવશે; <b>▲ ▼</b> થી Released ઓર્ડરનો વારો બદલી શકાય.' },
      { id: 'db-close', type: 'click', path: '/dashboard', target: '#db-close', title: 'બંધ કરો', text: '<b>Close</b> દબાવો.', todo: 'ક્લિક કરો: Close' },
      { id: 'db-back', type: 'click', target: navLink('/routing'), title: 'પાછા Routing પર', text: 'સ્ટેજ પૂરું કરવા પાછા <b>Routing / stages</b>.', todo: 'ક્લિક કરો: Routing / stages' },
      { id: 'rt-hold', type: 'info', path: '/routing', target: inCard('.rt-card', '.rt-reason[data-do="hold"]'), title: 'Hold / Resume (નવું)',
        text: 'ચાલુ સ્ટેજ પર <b>Hold</b> (લાઇટ ગઈ, મશીન બગડ્યું…) — કારણ લખવું જરૂરી. Hold દરમિયાન <b>ટાઇમર અટકે</b> અને અટકેલો સમય કલાકમાં ગણાતો નથી; Dashboard પર મશીન લાલ <b>On hold</b>. <b>Resume</b> થી ફરી ચાલે. ભૂલથી Start થયું હોય તો <b>Cancel run</b>. અત્યારે ચાલુ રાખીએ.' },
      { id: 'rt-comp', type: 'click', path: '/routing', target: inCard('.rt-card', '.rt-act'), title: 'સ્ટેજ પૂરું કરો', text: 'હવે એ જ જગ્યાએ <b>Complete …</b> બટન છે.', todo: 'ક્લિક કરો: Complete (સ્ટેજ)' },
      { id: 'rt-used', type: 'info', path: '/routing', target: '#rt-mat-box', when: function () { var b = $('#rt-mat-box'); return !!(b && b.offsetParent); }, title: 'Raw material used — એક જ એન્ટ્રી',
        text: '<b>પહેલા:</b> સ્ટેજમાં કાચો માલ કેટલો વપર્યો તે ક્યાંય નહિ; Output વખતે બધો માલ વપરાયેલો ગણાતો.<br><b>હવે:</b> આ સ્ટેજમાં ખરેખર વપરાયેલો માલ <b>એક જ વાર</b> લખવાનો (સ્ટેજ બે વાર ચાલ્યું તોય કુલ એક એન્ટ્રી). Issued થી વધુ લખાય નહિ — વધુ જોઈએ તો પહેલાં <b>Material issue</b>. નીચે <b>Came into this stage</b> વપરાયેલા માલ પ્રમાણે બને, પછી scrap બાદ થઈ Good output.' },
      { id: 'rt-hours', type: 'info', path: '/routing', target: '#rt-hours-box', title: 'Working hours',
        text: 'Start થી Finish સુધીના <b>કલાક આપોઆપ</b> ભરાય છે. સ્ટેજ વચ્ચે અટક્યું હોય તો આંકડો <b>બદલી</b> શકાય.' },
      { id: 'rt-comp-fill', type: 'fill', path: '/routing', target: '#rt-form', title: 'પૂરું કરવાની વિગત',
        text: '<ul><li><b>Machines used</b> — ખરેખર કયા મશીન ચાલ્યા (ન ચાલ્યું તે અનટિક કરો)</li><li><b>Good output</b> — આપોઆપ ગણાય છે (આવેલો માલ − scrap), લખવાનું નથી</li><li><b>Scrap</b> — ફક્ત આ જ લખવાનું: કેટલો બગડ્યો; બગડ્યો હોય તો <b>પ્રકાર</b> અને <b>વેચી શકાય (Saleable)</b> કે <b>Process loss</b> પસંદ કરો</li></ul>ડેમો માટે 1 KG scrap (Metal slag) ભરાશે.',
        prefill: { label: 'ડેમો વેલ્યુ ભરો', run: prefillStageComplete } },
      { id: 'rt-comp-post', type: 'submit', path: '/routing', target: '#rt-form', retryTo: 'rt-comp', title: 'Complete stage', text: '<b>Complete stage</b> દબાવો.', todo: 'ક્લિક કરો: Complete stage' },
      { id: 'rt-done1', type: 'info', path: '/routing', target: inCard('.rt-card', '.rt-head'), title: 'પહેલું સ્ટેજ પૂરું ✅',
        text: 'પ્રગતિ-બાર વધ્યો. <b>Behind / On track</b> ચિપ કહે છે કે આયોજન કરતાં મોડા છો કે નહિ, અને <b>Forecast</b> કહે છે કે ઓર્ડર ક્યારે પૂરો થવાની શક્યતા છે. કાર્ડ ખોલશો તો સ્ટેજ-વાર ખરા કલાક, ઓપરેટર, મશીન અને yield % દેખાય.' },
      { id: 'rt-shortcut', type: 'action', path: '/routing', target: inCard('.rt-card', '.rt-pipe'), title: 'બાકીના સ્ટેજ (ડેમો શૉર્ટકટ)',
        text: 'બાકીના બધા સ્ટેજ પણ આ જ રીતે (Start → Complete) થાય. ટૂરનો સમય બચાવવા આ <b>ડેમો શૉર્ટકટ</b> બટન બાકીના બધા સ્ટેજ આપમેળે પૂરા કરી દેશે.',
        button: { label: 'બાકીના સ્ટેજ આપમેળે પૂરા કરો', run: finishStagesDemo } },
      { id: 'rt-labqc', type: 'info', when: function () { return !!(infoCache && infoCache.lab_qc); }, title: 'Lab QC અને TC',
        text: 'મેલ્ટિંગ પછી તરત <b>Lab QC</b>: સેમ્પલ લેબમાં જાય, અને <b>Pass</b> થાય ત્યારે <b>Test Certificate (TC)</b> અપલોડ કરવું પડે. <b>TC વગર આગળનું સ્ટેજ (Ingot Casting) શરૂ થઈ શકતું નથી.</b> આ TC હંમેશા આ ઓર્ડર અને લોટ સાથે જોડાયેલું રહે છે. ડેમો શૉર્ટકટે આપણા માટે એક Pass ટેસ્ટ અને TC નાખી દીધું છે.' },
      { id: 'rt-scraplater', type: 'info', when: flag('scrap_later'), title: 'Melting નો scrap — પછીથી લખાય',
        text: '<b>પહેલા:</b> દરેક સ્ટેજમાં આવેલો-ગયેલો બંને લખવો પડતો.<br><b>હવે:</b> ફક્ત <b>scrap</b> લખવાનો; Good output આપમેળે (આવેલો − scrap). Melting નો scrap (dross / slag) ભઠ્ઠી ખાલી થયા પછી, એટલે <b>Ingot Casting પૂરું કરતી વખતે</b> લખાય — ફોર્મમાં અલગ ખાનું આવે, અને Melting નો output અને Casting નો input આપમેળે સુધરે.' },
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
        prefill: { label: 'ડેમો વેલ્યુ ભરો', run: function () { setPerson($('#ou-by')); var rk = $('#ou-rack'); if (rk && rk.options.length > 1) setVal(rk, rk.options[1].value); return Promise.resolve(); } } },
      { id: 'ou-rack', type: 'info', path: '/production_output', target: '#ou-rack', title: 'Rack (નવું)',
        text: '<b>પહેલા:</b> તૈયાર માલ ફક્ત ગોડાઉનમાં જતો.<br><b>હવે:</b> <b>Rack</b> ચૂંટો — Good માલ FG ગોડાઉનના કયા રેકમાં મૂક્યો. એટલે તૈયાર માલ પણ હંમેશા શોધી શકાય.' },
      { id: 'ou-side', type: 'info', path: '/production_output', target: '.ou-side', title: '"Record કરતાં શું થશે?"',
        text: '૧) ઉત્પાદનમાં આપેલો <b>કાચો માલ "વપરાયો"</b> ગણાશે, ૨) <b>Good</b> તૈયાર માલમાં (batch નંબર સાથે), ૩) <b>Scrap</b> Scrap yard માં, ૪) ઓર્ડર <b>Completed</b>. નીચે <b>અંદાજિત ખર્ચ</b> પણ છે: કાચા માલની કિંમત ÷ Good જથ્થો.' },
      { id: 'ou-return', type: 'info', path: '/production_output', target: '#ou-form', title: 'બચેલો માલ પહેલાં પાછો',
        text: '<b>નવો નિયમ:</b> issue થયો પણ <b>વપરાયો નહિ</b> (બચેલું spare) તે Output પહેલાં <b>Material return</b> થી store માં પાછો જવો જોઈએ — નહિ તો Output નોંધાતું નથી. Output માં ફક્ત <b>ખરેખર વપરાયેલો</b> માલ ગણાય, એટલે તૈયાર માલની <b>કિંમત</b> અને <b>Variance</b> સાચા આવે.' },
      { id: 'ou-post', type: 'submit', path: '/production_output', target: '#ou-form', retryTo: 'ou-open', title: 'Record output', text: 'નીચે <b>Record output</b> દબાવો.', todo: 'ક્લિક કરો: Record output' },
      { id: 'ou-done', type: 'info', path: '/production_output', target: '.ou-card', title: 'Output નોંધાયું ✅',
        text: 'આ <b>Recorded</b> ટૅબ છે. અહીં <b>OUT નંબર, Batch નંબર</b> (<code>BATCH-WS-તારીખ-001</code>), Good/Rework/Scrap અને <b>પ્રતિ યુનિટ ખર્ચ</b> દેખાય છે. <b>Print batch slip</b> થી બેચ-સ્લિપ નીકળે. ભૂલ હોય તો <b>Cancel</b> (જ્યાં સુધી માલ વેચાયો ન હોય).' },
      { id: 'co-link', type: 'click', target: navLink('/costing'), title: 'Costing (નવું)', text: 'બેચની <b>પ્રોડક્ટ કોસ્ટ</b> જોવા ડાબા મેનુમાં <b>Manufacturing</b> હેઠળ <b>Costing</b>.', todo: 'ક્લિક કરો: Costing' },
      { id: 'co-batch', type: 'info', path: '/costing', target: '.cs-table', title: 'Batch cost',
        text: '<b>પહેલા:</b> બેચનો ખર્ચ ફક્ત કાચા માલનો.<br><b>હવે:</b> દરેક બેચની <b>Product cost / unit = કાચો માલ + Fixed cost</b>. ચિપ: <b>Approx</b> (મહિનો હજી ફાઇનલ નથી), <b>Final</b>, અથવા <b>Material only</b> (Fixed cost હજી નક્કી નથી — ડેમોમાં એમ જ છે). ઉપર KG દીઠ કોસ્ટ પણ.' },
      { id: 'co-fixed-tab', type: 'click', path: '/costing', target: '.cs-tabs a[href*="tab=fixed"]', title: 'Fixed cost ટૅબ', text: '<b>Fixed cost</b> ટૅબ ખોલો.', todo: 'ક્લિક કરો: Fixed cost' },
      { id: 'co-fixed', type: 'info', path: '/costing', target: '.cs-box.self-start', title: 'મહિનાનો Fixed cost',
        text: 'પગાર, ભાડું, વીજળી, ઑફિસ ખર્ચ — <b>આખા મહિનાની અંદાજિત રકમ</b> અને <b>કામના દિવસ</b> અહીં લખાય. રોજનો ખર્ચ = રકમ ÷ દિવસ; એ દિવસના <b>કુલ સારા KG</b> પર વહેંચાય અને બેચ પર <b>ફ્રીઝ</b> થઈ જાય. નવી રકમ ફક્ત <b>આગળની તારીખથી</b> લાગે — જૂની બેચ બદલાય નહિ. (ડેમોમાં આપણે કંઈ સેવ નહિ કરીએ.)' },
      { id: 'co-months-tab', type: 'click', path: '/costing', target: '.cs-tabs a[href*="tab=months"]', title: 'Months ટૅબ', text: '<b>Months</b> ટૅબ ખોલો.', todo: 'ક્લિક કરો: Months' },
      { id: 'co-months', type: 'info', path: '/costing', target: '.cs-table', title: 'મહિનો ફાઇનલ કરો',
        text: 'મહિનાના અંતે <b>અસલી Fixed cost</b> લખીને <b>Finalise</b> દબાવો. Final રકમ ÷ મહિનાના કુલ KG = <b>Final રેટ</b>, અને મહિનાની બધી બેચ એક જ વાર <b>Approx → Final</b> થાય. એક મહિનો એક જ વાર ફાઇનલ થાય. સ્ટોરની કિંમત (valuation) હજી ફક્ત કાચા માલની છે.' },
      { id: 'fg-link', type: 'click', target: navLink('/finished_goods'), title: 'Finished goods', text: 'તૈયાર માલનો સ્ટોક.', todo: 'ક્લિક કરો: Finished goods' },
      { id: 'fg-info', type: 'info', path: '/finished_goods', target: '.fg-card', title: 'તૈયાર માલ — કેટેગરી પ્રમાણે',
        text: '<b>પહેલા:</b> દરેક બેચ અલગ લાઇનમાં, લાંબી યાદી.<br><b>હવે:</b> પહેલા <b>કેટેગરી બ્લોક</b> (Solder Wire, Stick ...) — દરેકમાં કુલ જથ્થો (KG / PCS) અને કિંમત.' },
      { id: 'fg-cat', type: 'click', path: '/finished_goods', target: function () { return $$('.fgc').filter(function (c) { return !/\b0 products/.test(c.textContent); })[0] || $('.fgc'); }, title: 'કેટેગરી ખોલો', text: 'કેટેગરી બ્લોક પર ક્લિક કરો — તેના <b>પ્રોડક્ટ</b> ખુલશે. સાથે ચેતવણી: <b>Out of stock</b>, <b>Below minimum</b>, <b>Overstock</b>.', todo: 'ક્લિક કરો: કેટેગરી' },
      { id: 'fg-expand', type: 'click', path: '/finished_goods', target: '.fgp', title: 'પ્રોડક્ટ ખોલો', text: 'પ્રોડક્ટની લાઇન પર ક્લિક કરો — તેની <b>બેચ</b> ખુલશે.', todo: 'ક્લિક કરો: પ્રોડક્ટ' },
      { id: 'fg-batch', type: 'info', path: '/finished_goods', target: '.fg-panel .fg-brow', title: 'બેચ-વાર વિગત',
        text: 'દરેક બેચ: <b>કયા ઓર્ડરનો</b>, કેટલો બચ્યો, પ્રતિ યુનિટ ખર્ચ, કુલ કિંમત, <b>કયા ગોડાઉન અને કયા Rack માં</b>. આગળ <b>Sales</b> માં આ બેચમાંથી જ માલ ગ્રાહકને જશે.' },
      { id: 'fg-scrap', type: 'click', path: '/finished_goods', target: '.fg-tabs a[href*="tab=scrap"]', title: 'Scrap yard', text: 'બીજું ટૅબ <b>Scrap yard</b> ખોલો.', todo: 'ક્લિક કરો: Scrap yard' },
      { id: 'fg-scrap-info', type: 'info', path: '/finished_goods', target: '.fg-card', title: 'Scrap નો સ્ટોક', text: 'Output માં નોંધેલો <b>વેચી શકાય તેવો scrap</b> અહીં સ્ટોક તરીકે આવ્યો (કિંમત શૂન્ય ગણાય). આ ભવિષ્યમાં Sales માં વેચી શકાશે.' },
      { id: 'sc-link', type: 'click', target: navLink('/scrap'), title: 'Scrap / waste', text: 'બધા scrap નો હિસાબ.', todo: 'ક્લિક કરો: Scrap / waste' },
      { id: 'sc-kpi', type: 'info', path: '/scrap', target: '.sc-kpi', title: 'Scrap ના કાર્ડ',
        text: '<b>In scrap yard</b> (સ્ટોકમાં), <b>On the floor</b> (ચાલુ ઓર્ડરનો), <b>Process loss</b> (નોંધ માત્ર) અને <b>Scrap rate %</b> (બેચના વજન સામે).' },
      { id: 'sc-box', type: 'info', path: '/scrap', target: '.sc-box', title: 'ક્યાં સૌથી વધુ બગાડ?',
        text: 'બાર-ચાર્ટ કહે છે <b>કયા પ્રકારનો</b> scrap વધુ છે અને <b>કયું સ્ટેજ</b> સૌથી વધુ બગાડે છે — સુધારા માટે સીધો સંકેત.' },
      { id: 'sc-reg', type: 'info', path: '/scrap', target: '.sc-card', title: 'Scrap register', text: 'દરેક scrap: કયો ઓર્ડર, કયું સ્ટેજ, શું પ્રકાર, કેટલો, અને <b>અત્યારે ક્યાં</b> છે (Floor / Scrap yard / Not stocked).' },
      { id: 'sc-yard', type: 'click', path: '/scrap', target: '.sc-tabs a[href*="tab=yard"]', title: 'Scrap yard ટૅબ', text: '<b>Scrap yard</b> ટૅબ ખોલો.', todo: 'ક્લિક કરો: Scrap yard' },
      { id: 'sc-packbox', type: 'info', path: '/scrap', target: function () { return boxWith('.sc-box', "Pack a day"); }, title: 'દિવસનું Scrap pack (નવું)',
        text: '<b>પહેલા:</b> scrap દરેક ઓર્ડરનો અલગ.<br><b>હવે:</b> એક દિવસનો <b>બધા ઓર્ડરનો scrap એક થેલીમાં</b>, <b>એક barcode</b> સાથે. અહીં દેખાય છે કે કયા દિવસનો કેટલો scrap હજી પેક નથી થયો.' },
      { id: 'sc-pack', type: 'submit', path: '/scrap', target: function () { var b = boxWith('.sc-box', "Pack a day"); return b ? $('form', b) : null; }, retryTo: 'sc-yard', title: 'Pack this day', text: '<b>Pack this day</b> દબાવો.', todo: 'ક્લિક કરો: Pack this day' },
      { id: 'sc-packs', type: 'info', path: '/scrap', target: function () { return boxWith('.sc-box', "Scrap packs"); }, title: 'Pack બની ગયું ✅',
        text: 'Pack નંબર <b>SCP-તારીખ-001</b>. <b>Print label</b> થી થેલી પર ચોંટાડવાનું લેબલ. ખોટું હોય તો <b>Open pack</b> — સ્ટોકમાં કંઈ ફેરફાર થતો નથી.' },
      { id: 'sc-scan', type: 'submit', path: '/scrap', target: 'form[action*="/scrap/scan"]', title: 'Barcode scan', text: 'ઉપરના <b>Scan or type barcode</b> બોક્સમાં barcode scan કરો (અથવા નંબર લખો) — લેબલ ખુલે.', todo: 'barcode નંબર લખો અને Find દબાવો',
        prefill: { label: 'Pack નંબર ભરો', run: function () { var b = boxWith('.sc-box', "Scrap packs"); var no = b && $('.sc-no', b); setVal($('form[action*="/scrap/scan"] input[name=code]'), no ? no.textContent.trim() : ''); return Promise.resolve(); } } },
      { id: 'sc-label', type: 'info', path: /^\/scrap\/pack\/label\/\d+$/, target: '.sheet', title: 'Pack લેબલ',
        text: 'ઉપર <b>barcode</b>, કુલ વજન, તારીખ. નીચે દરેક <b>ઓર્ડર, સ્ટેજ, scrap નો પ્રકાર, ઓપરેટર</b> — scrap ક્યાંથી આવ્યો તે બધું ટ્રેસ થાય.' },
      { id: 'sc-label-back', type: 'click', path: /^\/scrap\/pack\/label\/\d+$/, target: '.toolbar a[href*="/scrap"]', title: 'પાછા', text: '<b>Back</b> દબાવો.', todo: 'ક્લિક કરો: Back' },
      { id: 'cv-link', type: 'click', target: navLink('/consumption_variance'), title: 'Consumption variance', text: 'કાચો માલ <b>આયોજન મુજબ</b> વપરાયો કે નહિ?', todo: 'ક્લિક કરો: Consumption variance' },
      { id: 'cv-view', type: 'click', path: '/consumption_variance', target: inCard('.cv-card', '.cv-view'), title: 'તફાવત જુઓ', text: 'તમારા ઓર્ડરના કાર્ડમાં <b>View details</b>.', todo: 'ક્લિક કરો: View details' },
      { id: 'cv-info', type: 'info', path: '/consumption_variance', target: '#cv-body', title: 'Planned vs Actual',
        text: '<b>તફાવત = Actual − Planned</b>. Planned રેસિપીમાંથી, Actual ખરેખર વપરાયું. <ul><li><b>In short</b> — સાદી ભાષામાં સારાંશ</li><li><b>Used more / less / On plan</b> (±2% સુધી "On plan")</li><li><b>Yield %</b> અને <b>Mass balance</b> — કેટલો માલ ગયો અને કેટલો નીકળ્યો; હિસાબ ન મળે તે KG અહીં દેખાય</li></ul>' },
      { id: 'cv-review', type: 'submit', path: '/consumption_variance', target: '#cv-body form', retryTo: 'cv-view', title: 'Reviewed તરીકે માર્ક કરો',
        text: 'તફાવત જોઈ લીધા પછી તમારું નામ લખીને <b>Mark reviewed</b> દબાવો.', todo: 'ક્લિક કરો: Mark reviewed',
        prefill: { label: 'ડેમો વેલ્યુ ભરો', run: function () { setVal($('#cv-body [name=reviewed_by]'), 'મેનેજર'); setVal($('#cv-body [name=review_note]'), 'ડેમો ટૂર'); return Promise.resolve(); } } },
      { id: 'cv-done', type: 'info', path: '/consumption_variance', target: '.cv-card', title: 'Reviewed ✅', text: 'કાર્ડ પર <b>Reviewed</b> દેખાય છે અને "not reviewed" ગણતરી ઘટી.' },
      { id: 'mp-seed', type: 'action', path: '/production_orders', target: 'main h1', title: 'ડેમો: મોટો ઓર્ડર',
        text: 'Material plan બતાવવા ડેમો માટે <b>1500 KG નો એક મોટો ઓર્ડર</b> કતારમાં મૂકીએ — જેનો માલ સ્ટોકમાં પૂરતો નથી.',
        button: { label: 'ડેમો ઓર્ડર બનાવો', run: function () { return fetch('/tour/shortage_order', { method: 'POST' }).then(function (r) { return r.json(); }).then(function (j) { if (!j.ok) throw new Error(j.message || j.error || 'Request failed'); return j; }); } } },
      { id: 'mp-link', type: 'click', target: navLink('/material_plan'), title: 'Material plan ખોલો', text: '<b>Manufacturing</b> હેઠળ <b>Material plan</b>.', todo: 'ક્લિક કરો: Material plan' },
      { id: 'mp-kpi', type: 'info', path: '/material_plan', target: '.mp-kpi', title: 'Material plan — 30 દિવસ',
        text: '<b>પહેલા:</b> દરેક ઓર્ડરનું અલગ ચેક, અને ફક્ત આજનો સ્ટોક.<br><b>હવે:</b> આખી કતારના <b>આવતા 30 દિવસ</b>નો હિસાબ: સ્ટોર + PO થી આવનાર − કતારના ઓર્ડરની જરૂર. ઉપર ચાર સાદા કાર્ડ: <b>Materials short</b>, <b>Orders affected</b>, <b>Buy now</b>, <b>Chase vendor</b>.' },
      { id: 'mp-orders', type: 'info', path: '/material_plan', target: 'article.mp-card', title: 'Production order પ્રમાણે (નવું)',
        text: 'પહેલો ટૅબ <b>By production order</b>: દરેક ઓર્ડર માટે કયો માલ <b>કેટલો જોઈએ</b>, <b>કેટલો ઓછો</b> છે, ક્યારથી, અને શું કરવાનું (<b>Place PO before …</b> / ઘરમાં બનાવો). કમી વાળા ઓર્ડર ઉપર.' },
      { id: 'mp-tab-all', type: 'click', path: '/material_plan', target: '.mp-tabs a[href*="view=all"]', title: 'All materials ટૅબ', text: 'હવે દરેક <b>માલનો કુલ</b> હિસાબ જોવા <b>All materials</b>.', todo: 'ક્લિક કરો: All materials' },
      { id: 'mp-card', type: 'info', path: '/material_plan', target: 'article.mp-card', title: 'દરેક માલનું કાર્ડ',
        text: 'સ્ટોરમાં કેટલો, 30 દિવસમાં કેટલો જોઈએ, PO થી કેટલો આવે, 30 દિવસ પછી કેટલો બચે. <b>કમી</b> હોય તો <b>કઈ તારીખથી, કેટલી</b>, અને <b>"Place PO before …"</b> — vendor ના lead time મુજબ.' },
      { id: 'mp-days', type: 'click', path: '/material_plan', target: 'article.mp-card details.mp-det summary', title: 'Day-by-day', text: '<b>Day-by-day</b> ખોલો.', todo: 'ક્લિક કરો: Day-by-day' },
      { id: 'mp-days-info', type: 'info', path: '/material_plan', target: 'article.mp-card details.mp-det table', title: 'તારીખ પ્રમાણે હિસાબ',
        text: 'ક્યારે માલ આવે છે (PO), કયો ઓર્ડર ક્યારે વાપરે છે, અને <b>બેલેન્સ ક્યારે માઇનસ</b> થાય છે — લાલ રંગમાં.' },
      { id: 'mp-tab-po', type: 'click', path: '/material_plan', when: function () { return !!$('.mp-tabs a[href*="view=po"]'); }, target: '.mp-tabs a[href*="view=po"]', title: 'Create purchase orders ટૅબ', text: 'PO બનાવવા માટે ત્રીજો ટૅબ <b>Create purchase orders</b>.', todo: 'ક્લિક કરો: Create purchase orders' },
      { id: 'mp-sugg', type: 'info', path: '/material_plan', when: function () { return !!$('form[action*="create_po"]'); }, target: 'form[action*="create_po"]', title: 'Suggested purchase orders',
        text: '<b>પહેલા:</b> દરેક માલનો PO અલગ હાથે.<br><b>હવે:</b> કમી વાળા બધા માલ <b>vendor પ્રમાણે ભેગા</b> — કતારના ઘણા ઓર્ડરનો માલ <b>એક જ PO</b> માં. જથ્થો બદલી શકાય. ભાવ, ટેક્સ, યુનિટ તે માલના છેલ્લા PO માંથી.' },
      { id: 'mp-create', type: 'submit', path: '/material_plan', when: function () { return !!$('form[action*="create_po"]'); }, target: 'form[action*="create_po"]', title: 'Draft PO બનાવો', text: '<b>Create draft PO</b> દબાવો.', todo: 'ક્લિક કરો: Create draft PO' },
      { id: 'mp-created', type: 'info', path: '/material_plan', when: function () { return !!(infoCache && infoCache.ok); }, target: 'main h1', title: 'Draft PO બન્યો ✅',
        text: 'PO <b>Draft</b> માં બન્યો. Purchase orders પેજ પર ભાવ તપાસીને, vendor નું બિલ જોડીને <b>Confirm</b> કરવાનો. Draft ગણતરીમાં આવતો નથી — Confirm પછી જ માલ "આવનાર" ગણાય.' },
      { id: 'po-final', type: 'click', target: navLink('/production_orders'), title: 'છેલ્લું: Production order', text: 'ઓર્ડર હવે કતારમાં નથી — <b>Completed</b> ટૅબમાં છે.', todo: 'ક્લિક કરો: Production order' },
      { id: 'po-final-tab', type: 'click', path: '/production_orders', target: '.po-tabs a[href*="tab=completed"]', title: 'Completed ટૅબ', text: 'આ ટૅબ ખોલો.', todo: 'ક્લિક કરો: Completed' },
      { id: 'end', type: 'info', path: '/production_orders', target: function () { return orderCard('.po-card'); }, title: 'અભિનંદન! 🎉 ટૂર પૂરી',
        text: 'આખું ચક્ર જોયું, સાથે ક્લાયન્ટના બધા ફેરફારો: <b>Production Line, Rack, Wire Drawing 1-3, Lab QC + TC, ફક્ત-scrap લખવાનું, Scrap pack + barcode, Tally જેવો તૈયાર માલ, 30 દિવસનો Material plan અને Draft PO</b>.<br>ઓર્ડર <b>Completed</b> છે અને તેનો <b>Batch નંબર, ખર્ચ</b> અહીં દેખાય છે.<br><br>આગળ આવશે: <b>Sales</b> (Quotation → Order → Delivery → Invoice), Login / Roles અને ખર્ચ ગુપ્ત રાખવું.' }
    ]
  });

  // ---------------------------------------------------------------- prefill / action helpers
  // ---- Procurement demo prefills (PO -> GRN -> QC -> Bill). Sab asli forms bharte hain; submit user / player karta hai.
  var stamp = String(Date.now()).slice(-6);            // demo ke naam (challan, lot, bill no) alag-alag rakhne ke liye
  function todayStr() {
    var d = new Date();
    return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);
  }
  function waitFor(fn, ms) {
    return new Promise(function (res) {
      var t0 = Date.now();
      (function t() {
        var v = null; try { v = fn(); } catch (e) { v = null; }
        if (v) return res(v);
        if (Date.now() - t0 > ms) return res(null);
        setTimeout(t, 120);
      })();
    });
  }
  function demoRate(item) { return item.unit === 'KG' ? 100 : 400; }     // KG material ka rate 100, baaki 400 (demo)

  function prefillPO() {
    return getInfo().then(function (info) {
      if (!info.ok) throw new Error(info.message);
      if (!info.vendor_id) throw new Error('No active vendor found. Add a vendor first.');
      var form = $('#po-form');
      var d = $('#po-date', form); setVal(d, d.max || todayStr());
      setVal($('#po-vendor', form), String(info.vendor_id));
      setVal($('#po-warehouse', form), String(info.store_warehouse_id));
      var rows = $$('#po-line-list tr.po-line-row');
      while (rows.length < info.product.recipe.length) { $('#btn-add-line').click(); rows = $$('#po-line-list tr.po-line-row'); }
      info.product.recipe.forEach(function (item, i) {
        var row = rows[i];
        setVal($('.line-material', row), String(item.rm_id));         // unit + GST material se aapoaap aate hain
        var unit = $('.line-unit', row), tax = $('.line-tax', row);
        if (!unit.value && unit.options.length > 1) setVal(unit, unit.options[1].value);
        if (!tax.value && tax.options.length > 1) setVal(tax, tax.options[1].value);
        setVal($('.line-qty', row), String(Math.ceil(item.ratio * 5)));   // 500 KG ke order jitna (ratio % x 5)
        setVal($('.line-rate', row), String(demoRate(item)));
      });
      setVal($('#po-remarks', form), 'Demo tour');
    });
  }

  function prefillConfirmPO() {
    // Vendor bill ki nakli (chhoti) PDF file banake file input me daalo — asli upload jaisa hi jaata hai
    var win = ctx.win;
    var pdf = '%PDF-1.1\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 120]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF';
    var dt = new win.DataTransfer();
    dt.items.add(new win.File([pdf], 'demo-vendor-bill.pdf', { type: 'application/pdf' }));
    var input = $('#confirm-po-file');
    input.files = dt.files;
    input.dispatchEvent(new win.Event('change', { bubbles: true }));
    setVal($('#confirm-po-inv-no'), 'VB-' + stamp);
    setVal($('#confirm-po-inv-date'), todayStr());
    return Promise.resolve();
  }

  function prefillGRN() {
    // "Receive goods" dabane ke baad PO ki lines server se aati hain — pehle unka intezaar
    return waitFor(function () { return $$('#grn-form .line-recv').length > 0; }, 8000).then(function (ok) {
      if (!ok) throw new Error('GRN lines did not load.');
      var form = $('#grn-form');
      var d = $('#grn-date', form); if (!d.value) setVal(d, d.max || todayStr());
      var batches = $$('.line-batch', form);
      $$('.line-recv', form).forEach(function (inp, i) {
        var left = (parseFloat(inp.getAttribute('data-poqty')) || 0) - (parseFloat(inp.getAttribute('data-prev')) || 0);
        if (left <= 0) return;                                        // is item ka maal pehle aa chuka — line khaali chhodo
        setVal(inp, String(left));                                    // poora baaki maal aaya
        setVal(batches[i], 'DEMO-LOT-' + stamp + '-' + (i + 1));
      });
      $$('.line-rack', form).forEach(function (sel) { if (sel.options.length > 1) setVal(sel, sel.options[1].value); });   // પહેલો rack
      setVal($('#grn-challan', form), 'DC-' + stamp);
      setVal($('#grn-transporter', form), 'Demo Transport');
      setVal($('#grn-vehicle', form), 'GJ-01-AB-1234');
    });
  }

  // QC parameter ki limit ke andar ka ek theek maap (demo me sab test pass)
  function goodFromLimits(min, max) {
    if (min !== null && max !== null) return Math.round((min + max) / 2 * 1000) / 1000;
    if (min !== null) return Math.round((min + Math.max(0.1, Math.abs(min) * 0.002)) * 1000) / 1000;     // sirf Min ho to thoda upar (purity 99.5 -> 99.7)
    if (max !== null) return max > 0 ? max / 2 : max - 1;
    return 1;
  }
  function limitsFromText(std) {
    var m = std.match(/(-?[0-9.]+)\s*to\s*(-?[0-9.]+)/);
    if (m) return [parseFloat(m[1]), parseFloat(m[2])];
    m = std.match(/Min\s+(-?[0-9.]+)/); if (m) return [parseFloat(m[1]), null];
    m = std.match(/Max\s+(-?[0-9.]+)/); if (m) return [null, parseFloat(m[1])];
    return [null, null];
  }

  function prefillQC() {
    // Inspect dabane ke baad lot + uske test server se aate hain — pehle unka intezaar
    return waitFor(function () {
      var recv = $('#qc-recv');
      return recv && /[0-9]/.test(recv.value) && $$('#param-tbody tr').length && !/Select a lot/.test($('#param-tbody').textContent);
    }, 8000).then(function (ok) {
      if (!ok) throw new Error('QC lot did not load.');
      var d = $('#qc-date'); if (!d.value) setVal(d, d.max || todayStr());
      setPerson($('#qc-inspector'));
      var recv = parseFloat($('#qc-recv').value) || 0;
      setVal($('#qc-sample'), '1');
      setVal($('#qc-pass'), String(recv));                              // poora lot pass
      setVal($('#qc-reject'), '0');
      $$('#param-tbody tr').forEach(function (tr) {
        var inp = $('.qc-param-input', tr);
        if (!inp) return;
        if (inp.tagName === 'SELECT') { setVal(inp, 'pass'); return; }
        var lim = limitsFromText((($$('td', tr)[1]) || {}).textContent || '');
        setVal(inp, String(goodFromLimits(lim[0], lim[1])));
      });
    });
  }

  // Demo shortcut: is PO ke baaki lots ka QC (sab test pass). Wahi /inward_qc/add route — sirf typing bachti hai.
  function qcRestDemo() {
    var po = state.vars.po;
    var qcInspectorId = setPerson($('#qc-inspector'));     // demo me jo bhi pehla/login user ho
    var jobs = $$('tr.qc-row').filter(function (r) { return !po || r.textContent.indexOf(po) !== -1; }).map(function (r) {
      var b = $('.btn-inspect-line', r);
      return b ? { grn: b.getAttribute('data-grn-id'), line: parseInt(b.getAttribute('data-line-id'), 10) } : null;
    }).filter(Boolean);
    var chain = Promise.resolve();
    jobs.forEach(function (job) {
      chain = chain.then(function () {
        return fetch('/inward_qc/grn_lines/' + job.grn).then(function (r) { return r.json(); });
      }).then(function (data) {
        var line = data.lines.filter(function (l) { return l.id === job.line; })[0];
        if (!line) return null;
        var fd = new FormData();
        fd.append('inspection_date', todayStr());
        fd.append('inspector_user_id', qcInspectorId);
        fd.append('grn_line_id', String(line.id));
        fd.append('sample_size', '1');
        fd.append('passed_qty', String(line.received_qty));
        fd.append('rejected_qty', '0');
        fd.append('remarks', 'Demo tour');
        line.parameters.forEach(function (p, i) {
          fd.append('param_id_' + i, String(p.id));
          if (p.check_type === 'pass_fail') fd.append('result_' + i, 'pass');
          else fd.append('actual_' + i, String(goodFromLimits(p.min_value, p.max_value)));
        });
        fd.append('qc_action', 'submit');
        return fetch('/inward_qc/add', { method: 'POST', body: fd }).then(function (r) {
          // guard / CSRF ka jawab JSON {success:false,error} hota hai (Phase 0) — use bhi error maano
          if ((r.headers.get('Content-Type') || '').indexOf('json') !== -1) return r.json().then(function (j) { if (j && j.success === false) throw new Error(j.error || 'Request failed'); return ''; });
          return r.text();
        }).then(function (html) {
          // flash message page ke showToast(...) me aata hai; error ho to dikhao
          var m = html.match(/showToast\(("(?:[^"\\]|\\.)*"),\s*"(error|warning)"\)/);
          if (m) throw new Error(JSON.parse(m[1]));
        });
      });
    });
    return chain;
  }

  function prefillBill() {
    // "Create bill" dabane par lines GRN ke data se JS banata hai
    return waitFor(function () { return $$('#pi-line-body tr').length > 0; }, 5000).then(function () {
      setVal($('#pi-vinv'), 'VINV-' + stamp);
      var d = $('#pi-date'); if (!d.value) setVal(d, d.max || todayStr());
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
      var line = $('#mo-line');                                         // lines bani hon to pehli line (us line ki machines tick ho jaati hain)
      if (line && !line.value && line.options.length > 1) setVal(line, line.options[1].value);
    });
  }

  function prefillStageComplete() {
    return sleep(50).then(function () {
      // Good output ab system khud nikaalta hai, demo me sirf scrap bharna hai
      setVal($('#rt-scrap'), '1');
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
      if (!j.ok) throw new Error(j.message || j.error || 'Request failed');
      return j;
    });
  }

  // ---------------------------------------------------------------- awaaz (manual tour me best-effort; browser page badalne ke baad auto-play rok deta hai, isliye 🔊 button bhi hai)
  var voice = { audio: null, key: '' };
  function voiceOn() { try { return localStorage.getItem('erpTourVoice') !== '0'; } catch (e) { return true; } }
  function stopVoice() { if (voice.audio) { try { voice.audio.pause(); } catch (e) { /* ignore */ } voice.audio = null; } }
  function playVoice(id) {
    stopVoice();
    var a = new Audio('/static/audio/gu/' + id + '.mp3');
    voice.audio = a;
    var p = a.play();
    if (p && p.catch) p.catch(function () { /* autoplay blocked — user 🔊 dabayega */ });
  }

  // ---------------------------------------------------------------- state / navigation
  var state = PLAYER ? { vars: {} } : load();
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
    stopVoice();
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
      if (p.hold && !toasts.length) { save(state); return render(); }     // popup cancel hua / bas reload hua - step wahin
      if (err && p.retryTo) {
        var back = indexOfStep(p.retryTo);
        if (back >= 0) { state.si = back; state.notice = 'એન્ટ્રીમાં સમસ્યા: ' + err.msg + ' — ફરી પ્રયત્ન કરો.'; }
        save(state);
        return render();
      }
      if (p.hold) advance();
      var okToast = toasts.filter(function (t) { return t.type === 'success'; });
      if (p.capture) {
        var txt = okToast.map(function (t) { return t.msg; }).join(' ');
        var m = txt.match(new RegExp(p.capture.re));          // capture state me JSON ban ke jaata hai, isliye re string hai
        if (m) state.vars[p.capture.as] = m[0];
      }
      save(state);
      return render();
    }

    if (!stepOn(st)) { advance(); return render(); }          // is waqt ye step lagu nahi (when false) - agle par
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
    if (mode !== 'goto') {
      var speaker = document.createElement('button');
      speaker.type = 'button'; speaker.className = 'tour-btn link'; speaker.style.cssText = 'font-size:16px;padding:0 4px';
      speaker.title = 'અવાજ સાંભળો / બંધ કરો';
      speaker.textContent = voiceOn() ? '🔊' : '🔇';
      speaker.addEventListener('click', function () {
        if (voice.audio && !voice.audio.paused) { stopVoice(); return; }
        try { localStorage.setItem('erpTourVoice', '1'); } catch (e) { /* ignore */ }
        speaker.textContent = '🔊'; playVoice(st.id);
      });
      head.insertBefore(speaker, head.lastChild);
      if (voice.key !== state.ci + ':' + state.si) {
        voice.key = state.ci + ':' + state.si;
        if (voiceOn()) playVoice(st.id); else stopVoice();
      }
    }
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
    state.pending = { retryTo: st.retryTo, capture: st.capture, hold: !!st.confirm };
    state.notice = null;
    // confirm popup wale form (Post bill) me asli submit popup "OK" ke baad aata hai — tab tak step wahin rakho
    if (st.confirm) { save(state); return; }
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
        // confirm popup wale form: autoplay khud "OK" dabata hai
        if (st.confirm) return waitFor(function () { var b = $('.erp-confirm__btn--ok'); return visible(b) ? b : null; }, 4000).then(function (b) { if (b) b.click(); });
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
    box.innerHTML = '<div class="top"><h2>🎓 ડેમો ટૂર (ગુજરાતી)</h2><p>ખરીદીથી લઈને તૈયાર માલ, Scrap અને Variance સુધીનું બધું <b>જાતે કરીને</b> શીખો. દરેક પગલું ગુજરાતીમાં સમજાવેલું છે.</p></div>' +
      '<div class="alert">⚠️ ટૂર <b>સાચી એન્ટ્રીઓ</b> બનાવશે — PO, GRN, QC, બિલ, પ્રોડક્શન ઓર્ડર, માલ આપવો/પાછો, રૂટિંગ, output વગેરે. ટ્રેનિંગ / ડેમો માટે જ ચલાવો.<label><input type="checkbox" id="tour-ok"> હું સમજું છું કે ટૂર સાચી એન્ટ્રીઓ બનાવશે.</label></div>';
    var auto = mk('div', 'tour-ch', box);
    auto.style.cssText += ';background:#EDF3FF;border-color:#BCD2FA';
    auto.innerHTML = '<div class="n">▶</div><div class="t"><b>1-ક્લિક ઓટો ડેમો (ગુજરાતી અવાજ સાથે)</b><span>તમારે કંઈ કરવાનું નથી — ડેમો પોતે બધું ક્લિક કરશે અને ગુજરાતીમાં સમજાવશે. થોભાવી શકાય, ઝડપ બદલી શકાય.</span></div>';
    var autoBtn = btn('શરૂ કરો', 'primary', function () { location.href = '/demo'; });
    auto.appendChild(autoBtn);
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
    note.style.background = '#E6F6F8'; note.style.borderColor = '#B2DDE4'; note.style.color = '#0B7285';
    note.innerHTML = 'સૂચન: <b>"આખો ટૂર"</b> ક્રમમાં ચલાવવો — પછીના ભાગ આગળના ભાગમાં બનેલા ઓર્ડર/સ્ટોક પર આધારિત છે. અલગ ભાગ ચલાવો તો પહેલાં ઓર્ડર બનેલો હોવો જોઈએ.';
  }
  function okBox() { return $('#tour-ok'); }
  function warnBox() { var a = $('.tour-menu .alert'); if (a) { a.style.outline = '3px solid #0B5BEF'; setTimeout(function () { a.style.outline = ''; }, 1200); } }
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
    if (PLAYER) {
      // Demo player: engine nahi, sirf data + helpers (iframe ke document par kaam karne ke liye)
      window.ERP_TOUR_API = {
        chapters: CH,
        resolve: resolveTarget,
        stepOn: stepOn,
        pathOk: pathOk,
        gotoUrl: gotoUrl,
        setContext: function (doc, win) { ctx.doc = doc; ctx.win = win; },
        setVar: function (k, v) { state.vars[k] = v; },
        getVar: function (k) { return state.vars[k]; },
        getInfo: getInfo
      };
      return;
    }
    // Sidebar ka "ડેમો ટૂર" card hata diya (user ka kehna 24 Nov): launcher ab nahi jodte. addLauncher() code rakha hai — dobara chahiye to yahan call wapas.
    // addLauncher();
    if (/[?&]tourauto=1/.test(location.search)) localStorage.setItem(DEV_KEY, '1');
    if (/[?&]tourauto=0/.test(location.search)) localStorage.removeItem(DEV_KEY);
    if (state && state.on) { render(); startTicker(); }
    window.__tour = { state: function () { return state; }, step: step, chapters: CH, resolve: function () { return resolveTarget(step()); }, errors: function () { return window.__tourErrors || []; }, start: start };
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
