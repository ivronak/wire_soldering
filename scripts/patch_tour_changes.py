# Ek baar chalane ka patch: demo tour (tour.js) me client ke naye ferfaar (pehle vs ab) ke steps jodta hai.
# Chalane ke baad ye file hata sakte hain; steps ab tour.js me hi hain.  python scripts/patch_tour_changes.py
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "app", "static", "js", "tour.js")
s = io.open(P, encoding="utf-8").read()


def rep(old, new, count=1):
    global s
    assert old in s, "NOT FOUND: " + old[:70]
    s = s.replace(old, new, count)


# ---------------------------------------------------------------- helpers
rep("""  // ---------------------------------------------------------------- chapters (Gujarati)
  var CH = [];
""", """  // Naye features ke steps tabhi jab /tour/info ka flag (lines / racks / scrap_later / wd_split) true ho
  function flag(name) { return function () { return !!(infoCache && infoCache[name]); }; }
  function tableOrTitle() { return $('main table') || $('main h1'); }
  // Material plan / Scrap page ke dabbe (class same hai, isliye likhe hue text se pehchano)
  function boxWith(sel, text) { var b = $$(sel).filter(function (x) { return x.textContent.indexOf(text) !== -1; })[0]; return b || null; }

  // ---------------------------------------------------------------- chapters (Gujarati)
  var CH = [];
""")

# ---------------------------------------------------------------- intro: welcome text + overview step
rep("""      { id: 'howto', type: 'info', title: 'ટૂર કેવી રીતે વાપરવી',""", """      { id: 'ch-overview', type: 'info', title: 'ક્લાયન્ટના ફેરફારો: પહેલા અને હવે',
        text: '<ul><li><b>Production Line</b> — પહેલા ફક્ત મશીનો; હવે Line 1 / Line 2, દરેકની પોતાની મશીનો અને રોજની ક્ષમતા</li><li><b>Packing material</b> — recipe માં સ્પૂલ, સ્લીવ, બોક્સ</li><li><b>30 દિવસનો Material plan</b> — PO ક્યાં સુધીમાં નાખવો તે અગાઉથી</li><li><b>Flux અને Melting અલગ</b>, <b>Lab QC + TC</b> વગર આગળ નહિ</li><li><b>Scrap</b> — ફક્ત scrap લખવાનું, barcode, દિવસનું પેક</li><li><b>Rack</b> અને <b>Tally જેવો તૈયાર માલ</b> (ઓછા / વધુ સ્ટોકની ચેતવણી)</li></ul>આખી ટૂરમાં દરેક પેજ પર આ ફેરફાર <b>જાતે ચલાવીને</b> બતાવીશું.' },
      { id: 'howto', type: 'info', title: 'ટૂર કેવી રીતે વાપરવી',""")

# ---------------------------------------------------------------- new chapter: masters (procure se pehle)
MASTERS = """  CH.push({
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

"""
rep("""  CH.push({
    id: 'procure',""", MASTERS + """  CH.push({
    id: 'procure',""")

# ---------------------------------------------------------------- GRN rack
rep("""      { id: 'pr-grn-post', type: 'submit',""", """      { id: 'pr-grn-rack', type: 'info', path: '/grns', target: '#grn-form .line-rack', title: 'Rack (નવું)',
        text: '<b>પહેલા:</b> માલ ફક્ત ગોડાઉનમાં આવતો.<br><b>હવે:</b> દરેક લાઇનમાં <b>Rack</b> ચૂંટાય — QC પાસ પછી માલ તે ગોડાઉનના કયા રેકમાં મૂકવો. ફરજિયાત નથી.' },
      { id: 'pr-grn-post', type: 'submit',""")
rep("""      setVal($('#grn-challan', form), 'DC-' + stamp);""", """      $$('.line-rack', form).forEach(function (sel) { if (sel.options.length > 1) setVal(sel, sel.options[1].value); });   // પહેલો rack
      setVal($('#grn-challan', form), 'DC-' + stamp);""")

# ---------------------------------------------------------------- Stock: rack column
rep("""      { id: 'st-hist', type: 'click',""", """      { id: 'st-rack', type: 'info', path: '/inventory/stock', target: function () { var r = $('.lot-row'); return r ? r.children[4] : null; }, title: 'Rack કૉલમ (નવું)',
        text: '<b>પહેલા:</b> લોટ મળતો, પણ ક્યાં પડ્યો તે નહિ.<br><b>હવે:</b> દરેક લોટની સામે <b>Rack</b> લખેલો દેખાય છે, અને તેનાથી શોધી પણ શકાય.' },
      { id: 'st-hist', type: 'click',""")

# ---------------------------------------------------------------- Production order: line
rep("<b>૨.</b> કેટલું બનાવવું (Quantity).<br>", "<b>૨.</b> કેટલું બનાવવું (Quantity).<br><b>૩.</b> <b>Production line</b> ચૂંટો (નવું!).<br>")
rep("""      { id: 'po-plan', type: 'info',""", """      { id: 'po-line', type: 'info', path: '/production_orders', target: '#mo-line', when: flag('lines'), title: 'Production line — ઓર્ડર બનાવતાં જ',
        text: '<b>પહેલા:</b> લાઇન ફક્ત Start વખતે ચૂંટાતી, અને પ્લાનરમાં બધી લાઇનની મશીનો સાથે ટિક થતી — એટલે સમય ખોટો (અડધો) દેખાતો.<br><b>હવે:</b> ઓર્ડર બનાવતાં જ <b>લાઇન ચૂંટો</b> — ફક્ત તે લાઇનની મશીનો ટિક, બીજી લાઇનની ઝાંખી (disabled). ઓર્ડર પછી <b>Reschedule</b> માં બીજી લાઇનમાં પણ ખસેડી શકાય.' },
      { id: 'po-plan', type: 'info',""")

# ---------------------------------------------------------------- Start: line pre-chosen
rep("જ્યારે <b>Production lines</b> બનેલી હોય, ત્યારે ઓર્ડર કઈ લાઇનમાં ચલાવવો તે અહીં ચૂંટવાનું.", "ઓર્ડર બનાવતાં ચૂંટેલી <b>Production line</b> અહીં પહેલેથી ચૂંટાયેલી છે (બીજી લાઇનો ઝાંખી).")
rep("""var r = $('#start-form input[name=line_id]'); if (r)""", """var r = $('#start-form input[name=line_id]:checked') || $('#start-form input[name=line_id]:not(:disabled)'); if (r)""")

# ---------------------------------------------------------------- Routing: wire drawing 3 stages, scrap later, shortcut text
rep("""      { id: 'rt-start', type: 'click',""", """      { id: 'rt-wd', type: 'info', path: '/routing', target: inCard('.rt-card', '.rt-pipe'), when: flag('wd_split'), title: 'Wire Drawing — 3 સ્ટેજ',
        text: '<b>પહેલા:</b> Wire Drawing એક સ્ટેજ (8 સ્ટેજ).<br><b>હવે:</b> પાઇપલાઇનમાં <b>Wire Drawing 1 → 2 → 3</b> (કુલ 10 સ્ટેજ). ત્રણ મશીન એક લાઇનમાં, એક પછી એક પાસ — દરેકનો ઓપરેટર અને scrap અલગ નોંધાય.' },
      { id: 'rt-start', type: 'click',""")
rep("'બાકીના 7 સ્ટેજ પણ", "'બાકીના બધા સ્ટેજ પણ")
rep("""      { id: 'rt-alldone', type: 'info',""", """      { id: 'rt-scraplater', type: 'info', when: flag('scrap_later'), title: 'Melting નો scrap — પછીથી લખાય',
        text: '<b>પહેલા:</b> દરેક સ્ટેજમાં આવેલો-ગયેલો બંને લખવો પડતો.<br><b>હવે:</b> ફક્ત <b>scrap</b> લખવાનો; Good output આપમેળે (આવેલો − scrap). Melting નો scrap (dross / slag) ભઠ્ઠી ખાલી થયા પછી, એટલે <b>Ingot Casting પૂરું કરતી વખતે</b> લખાય — ફોર્મમાં અલગ ખાનું આવે, અને Melting નો output અને Casting નો input આપમેળે સુધરે.' },
      { id: 'rt-alldone', type: 'info',""")

# ---------------------------------------------------------------- Output: rack
rep("""prefill: { label: 'ડેમો વેલ્યુ ભરો', run: function () { setVal($('#ou-by'), 'સુરેશભાઈ'); return Promise.resolve(); } } },""",
    """prefill: { label: 'ડેમો વેલ્યુ ભરો', run: function () { setVal($('#ou-by'), 'સુરેશભાઈ'); var rk = $('#ou-rack'); if (rk && rk.options.length > 1) setVal(rk, rk.options[1].value); return Promise.resolve(); } } },
      { id: 'ou-rack', type: 'info', path: '/production_output', target: '#ou-rack', title: 'Rack (નવું)',
        text: '<b>પહેલા:</b> તૈયાર માલ ફક્ત ગોડાઉનમાં જતો.<br><b>હવે:</b> <b>Rack</b> ચૂંટો — Good માલ FG ગોડાઉનના કયા રેકમાં મૂક્યો. એટલે તૈયાર માલ પણ હંમેશા શોધી શકાય.' },""")

# ---------------------------------------------------------------- Finished goods: Tally view
rep("'દરેક <b>બેચ</b> એક ઓર્ડરનો Good માલ છે: કેટલો બચ્યો, <b>પ્રતિ યુનિટ ખર્ચ</b>, કુલ કિંમત અને કયા ગોડાઉનમાં. આગળ <b>Sales</b> માં આ બેચમાંથી જ માલ ગ્રાહકને જશે.'",
    "'<b>પહેલા:</b> દરેક બેચ અલગ લાઇનમાં, લાંબી યાદી.<br><b>હવે (Tally જેવું):</b> <b>પ્રોડક્ટ દીઠ એક લાઇન</b> — કુલ જથ્થો અને કિંમત. સાથે ચેતવણી: <b>Out of stock</b>, <b>Below minimum</b>, <b>Overstock</b>.'")
rep("""      { id: 'fg-scrap', type: 'click',""", """      { id: 'fg-expand', type: 'click', path: '/finished_goods', target: '.fg-group summary', title: 'પ્રોડક્ટ ખોલો', text: 'પ્રોડક્ટની લાઇન પર ક્લિક કરો — તેની <b>બેચ</b> ખુલશે.', todo: 'ક્લિક કરો: પ્રોડક્ટ' },
      { id: 'fg-batch', type: 'info', path: '/finished_goods', target: '.fg-group .fg-row', title: 'બેચ-વાર વિગત',
        text: 'દરેક બેચ: <b>કયા ઓર્ડરનો</b>, કેટલો બચ્યો, પ્રતિ યુનિટ ખર્ચ, કુલ કિંમત, <b>કયા ગોડાઉન અને કયા Rack માં</b>. આગળ <b>Sales</b> માં આ બેચમાંથી જ માલ ગ્રાહકને જશે.' },
      { id: 'fg-scrap', type: 'click',""")

# ---------------------------------------------------------------- Scrap: yard, pack, scan, label
rep("""      { id: 'cv-link', type: 'click',""", """      { id: 'sc-yard', type: 'click', path: '/scrap', target: '.sc-tabs a[href*="tab=yard"]', title: 'Scrap yard ટૅબ', text: '<b>Scrap yard</b> ટૅબ ખોલો.', todo: 'ક્લિક કરો: Scrap yard' },
      { id: 'sc-packbox', type: 'info', path: '/scrap', target: function () { return boxWith('.sc-box', "Pack a day"); }, title: 'દિવસનું Scrap pack (નવું)',
        text: '<b>પહેલા:</b> scrap દરેક ઓર્ડરનો અલગ.<br><b>હવે:</b> એક દિવસનો <b>બધા ઓર્ડરનો scrap એક થેલીમાં</b>, <b>એક barcode</b> સાથે. અહીં દેખાય છે કે કયા દિવસનો કેટલો scrap હજી પેક નથી થયો.' },
      { id: 'sc-pack', type: 'submit', path: '/scrap', target: function () { var b = boxWith('.sc-box', "Pack a day"); return b ? $('form', b) : null; }, retryTo: 'sc-yard', title: 'Pack this day', text: '<b>Pack this day</b> દબાવો.', todo: 'ક્લિક કરો: Pack this day' },
      { id: 'sc-packs', type: 'info', path: '/scrap', target: function () { return boxWith('.sc-box', "Scrap packs"); }, title: 'Pack બની ગયું ✅',
        text: 'Pack નંબર <b>SCP-તારીખ-001</b>. <b>Print label</b> થી થેલી પર ચોંટાડવાનું લેબલ. ખોટું હોય તો <b>Open pack</b> — સ્ટોકમાં કંઈ ફેરફાર થતો નથી.' },
      { id: 'sc-scan', type: 'submit', path: '/scrap', target: 'form[action*="/scrap/scan"]', title: 'Barcode scan', text: 'ઉપરના <b>Scan or type barcode</b> બોક્સમાં barcode scan કરો (અથવા નંબર લખો) — લેબલ ખુલે.', todo: 'barcode નંબર લખો અને Find દબાવો',
        prefill: { label: 'Pack નંબર ભરો', run: function () { var b = boxWith('.sc-box', "Scrap packs"); var no = b && $('.sc-no', b); setVal($('form[action*="/scrap/scan"] input[name=code]'), no ? no.textContent.trim() : ''); return Promise.resolve(); } } },
      { id: 'sc-label', type: 'info', path: /^\\/scrap\\/pack\\/label\\/\\d+$/, target: '.sheet', title: 'Pack લેબલ',
        text: 'ઉપર <b>barcode</b>, કુલ વજન, તારીખ. નીચે દરેક <b>ઓર્ડર, સ્ટેજ, scrap નો પ્રકાર, ઓપરેટર</b> — scrap ક્યાંથી આવ્યો તે બધું ટ્રેસ થાય.' },
      { id: 'sc-label-back', type: 'click', path: /^\\/scrap\\/pack\\/label\\/\\d+$/, target: '.toolbar a[href*="/scrap"]', title: 'પાછા', text: '<b>Back</b> દબાવો.', todo: 'ક્લિક કરો: Back' },
      { id: 'cv-link', type: 'click',""")

# ---------------------------------------------------------------- Material plan chapter (variance ke baad, final se pehle)
rep("""      { id: 'po-final', type: 'click',""", """      { id: 'mp-seed', type: 'action', path: '/production_orders', target: 'main h1', title: 'ડેમો: મોટો ઓર્ડર',
        text: 'Material plan બતાવવા ડેમો માટે <b>1500 KG નો એક મોટો ઓર્ડર</b> કતારમાં મૂકીએ — જેનો માલ સ્ટોકમાં પૂરતો નથી.',
        button: { label: 'ડેમો ઓર્ડર બનાવો', run: function () { return fetch('/tour/shortage_order', { method: 'POST' }).then(function (r) { return r.json(); }).then(function (j) { if (!j.ok) throw new Error(j.message); return j; }); } } },
      { id: 'mp-link', type: 'click', target: navLink('/material_plan'), title: 'Material plan ખોલો', text: '<b>Manufacturing</b> હેઠળ <b>Material plan</b>.', todo: 'ક્લિક કરો: Material plan' },
      { id: 'mp-kpi', type: 'info', path: '/material_plan', target: '.mp-kpi', title: 'Material plan — 30 દિવસ',
        text: '<b>પહેલા:</b> દરેક ઓર્ડરનું અલગ ચેક, અને ફક્ત આજનો સ્ટોક.<br><b>હવે:</b> આખી કતારના <b>આવતા 30 દિવસ</b>નો હિસાબ: સ્ટોર + PO થી આવનાર − કતારના ઓર્ડરની જરૂર. ઉપર: <b>Place PO now</b>, <b>soon</b>, <b>lead time નથી</b>, <b>તારીખ વગરનો PO</b>.' },
      { id: 'mp-card', type: 'info', path: '/material_plan', target: 'article.mp-card', title: 'દરેક માલનું કાર્ડ',
        text: 'સ્ટોરમાં કેટલો, 30 દિવસમાં કેટલો જોઈએ, PO થી કેટલો આવે, 30 દિવસ પછી કેટલો બચે. <b>કમી</b> હોય તો <b>કઈ તારીખથી, કેટલી</b>, અને <b>"Place PO before …"</b> — vendor ના lead time મુજબ.' },
      { id: 'mp-days', type: 'click', path: '/material_plan', target: 'article.mp-card details.mp-det summary', title: 'Day-by-day', text: '<b>Day-by-day</b> ખોલો.', todo: 'ક્લિક કરો: Day-by-day' },
      { id: 'mp-days-info', type: 'info', path: '/material_plan', target: 'article.mp-card details.mp-det table', title: 'તારીખ પ્રમાણે હિસાબ',
        text: 'ક્યારે માલ આવે છે (PO), કયો ઓર્ડર ક્યારે વાપરે છે, અને <b>બેલેન્સ ક્યારે માઇનસ</b> થાય છે — લાલ રંગમાં.' },
      { id: 'mp-sugg', type: 'info', path: '/material_plan', when: function () { return !!$('form[action*="create_po"]'); }, target: 'form[action*="create_po"]', title: 'Suggested purchase orders',
        text: '<b>પહેલા:</b> દરેક માલનો PO અલગ હાથે.<br><b>હવે:</b> કમી વાળા બધા માલ <b>vendor પ્રમાણે ભેગા</b> — કતારના ઘણા ઓર્ડરનો માલ <b>એક જ PO</b> માં. જથ્થો બદલી શકાય. ભાવ, ટેક્સ, યુનિટ તે માલના છેલ્લા PO માંથી.' },
      { id: 'mp-create', type: 'submit', path: '/material_plan', when: function () { return !!$('form[action*="create_po"]'); }, target: 'form[action*="create_po"]', title: 'Draft PO બનાવો', text: '<b>Create draft PO</b> દબાવો.', todo: 'ક્લિક કરો: Create draft PO' },
      { id: 'mp-created', type: 'info', path: '/material_plan', when: function () { return !!(infoCache && infoCache.ok); }, target: 'main h1', title: 'Draft PO બન્યો ✅',
        text: 'PO <b>Draft</b> માં બન્યો. Purchase orders પેજ પર ભાવ તપાસીને, vendor નું બિલ જોડીને <b>Confirm</b> કરવાનો. Draft ગણતરીમાં આવતો નથી — Confirm પછી જ માલ "આવનાર" ગણાય.' },
      { id: 'po-final', type: 'click',""")

# ---------------------------------------------------------------- end step text
rep("""text: 'તમે જાતે આખું ચક્ર કર્યું: <b>Purchase order → GRN → QC → Bill → સ્ટોક → Production order → માલ આપવો/પાછો → Start → Routing → Output → તૈયાર માલ → Scrap → Variance</b>.<br>ઓર્ડર <b>Completed</b> છે અને તેનો <b>Batch નંબર, ખર્ચ</b> અહીં દેખાય છે.<br><br>આગળ આવશે: <b>Sales</b> (Quotation → Order → Delivery → Invoice) અને Login/Roles.' }""",
    """text: 'આખું ચક્ર જોયું, સાથે ક્લાયન્ટના બધા ફેરફારો: <b>Production Line, Rack, Wire Drawing 1-3, Lab QC + TC, ફક્ત-scrap લખવાનું, Scrap pack + barcode, Tally જેવો તૈયાર માલ, 30 દિવસનો Material plan અને Draft PO</b>.<br>ઓર્ડર <b>Completed</b> છે અને તેનો <b>Batch નંબર, ખર્ચ</b> અહીં દેખાય છે.<br><br>આગળ આવશે: <b>Sales</b> (Quotation → Order → Delivery → Invoice), Login / Roles અને ખર્ચ ગુપ્ત રાખવું.' }""")

# ---------------------------------------------------------------- prefillOrder: line ચૂંટો
rep("""      setVal($('#mo-qty'), '100');
      setVal($('#mo-remarks'), 'Demo tour');""", """      setVal($('#mo-qty'), '100');
      setVal($('#mo-remarks'), 'Demo tour');
      var line = $('#mo-line');                                         // lines bani hon to pehli line (us line ki machines tick ho jaati hain)
      if (line && !line.value && line.options.length > 1) setVal(line, line.options[1].value);""")

io.open(P, "w", encoding="utf-8", newline="").write(s)
print("tour.js patched")
