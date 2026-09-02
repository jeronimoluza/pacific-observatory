/* Global price explorer — view layer.
   Every number on screen comes from DATA, pre-aggregated at the only grain a
   unit value is valid at: (country, COICOP node, standard_unit). */
(function () {
"use strict";

var PAL = ["#1f6feb","#e8833a","#2aa36b","#c0392b","#7c5cc4","#0e8f9e","#b8348c","#8a6d3b"];
var UNIT_LABEL = {kg:"per kg", lt:"per litre", unit:"per piece"};
var UNIT_SHORT  = {kg:"kg", lt:"litre", unit:"piece"};
var UNIT_OF     = {kg:"/kg", lt:"/L", unit:"/piece"};

var S = {
  view:"world", mode:"explore", cur:"usd", incModelled:false, measuredOnly:false,
  showFlagged:false, evidence:"solid", region:null, node:"01", unit:null, country:null,
  cmpMode:"abs", fxMode:"both", sortCmp:{k:"val",d:1}, sortCtry:{k:"ratio",d:1},
  multi:[]
};
var charts = {};

/* ---------------- data prep ---------------- */
var C = [];               // cell records
var byNodeUnit = new Map();
var byCountry  = new Map();
var byKey      = new Map();

(function build() {
  var x = DATA.cells, i;
  for (i = 0; i < x.c.length; i++) {
    var cell = {
      ci:x.c[i], ni:x.n[i], ui:x.u[i],
      country:DATA.ctyIdx[x.c[i]], node:DATA.nodeIdx[x.n[i]], unit:DATA.unitIdx[x.u[i]],
      usd:x.usd[i], loc:x.loc[i], cur:x.cur[i] >= 0 ? DATA.curIdx[x.cur[i]] : null,
      obs:x.obs[i], mad:x.mad[i], src:x.src[i], mod:x.mod[i], der:x.der[i],
      mix:x.mix[i], flag:x.flag[i], per:x.per[i]
    };
    C.push(cell);
    push(byNodeUnit, cell.ni + "|" + cell.ui, cell);
    push(byCountry, cell.ci, cell);
    byKey.set(cell.ci + "|" + cell.ni + "|" + cell.ui, cell);
  }
})();
function push(m, k, v) { var a = m.get(k); if (!a) m.set(k, a = []); a.push(v); }

/* children of a COICOP node, in code order */
var KIDS = new Map();
DATA.nodeIdx.forEach(function (code) {
  var p = (DATA.tax[code] || {}).p;
  if (p && DATA.tax[p]) push(KIDS, p, code);
});
KIDS.forEach(function (v) { v.sort(); });
var ROOTS = DATA.nodeIdx.filter(function (c) { return (DATA.tax[c] || {}).lvl === 1; }).sort();

function title(code) { return (DATA.tax[code] || {}).t || code; }
function ancestors(code) {
  var parts = code.split("."), out = [], i;
  for (i = 0; i < parts.length; i++) out.push(parts.slice(0, i + 1).join("."));
  return out;
}

/* ---------------- filters ---------------- */
var EVIDENCE = { any:{obs:0, src:1}, solid:{obs:10, src:1}, corrob:{obs:10, src:2} };
function keep(cell) {
  if (!S.incModelled && cell.mod >= 0.5) return false;
  if (S.measuredOnly && cell.der > 0.2) return false;
  if (!S.showFlagged && cell.flag) return false;
  var e = EVIDENCE[S.evidence] || EVIDENCE.any;
  if (cell.obs < e.obs || cell.src < e.src) return false;
  return true;
}
function cellsFor(ni, ui) { return (byNodeUnit.get(ni + "|" + ui) || []).filter(keep); }

/* value in the currency the user picked; null when unavailable */
function val(cell) { return S.cur === "usd" ? cell.usd : cell.loc; }
function fmtMoney(v, cur) {
  if (v == null || !isFinite(v)) return "—";
  var d = Math.abs(v) >= 100 ? 0 : Math.abs(v) >= 10 ? 1 : Math.abs(v) >= 1 ? 2 : 3;
  var s = v.toLocaleString(undefined, {minimumFractionDigits:d, maximumFractionDigits:d});
  return S.cur === "usd" ? "$" + s : s + (cur ? " " + cur : "");
}
function fmtN(v) { return v == null ? "—" : v.toLocaleString(); }
function pct(v, dp) { if (v == null || !isFinite(v)) return "—";
  return (v >= 0 ? "+" : "") + (v * 100).toFixed(dp == null ? 1 : dp) + "%"; }
function esc(s) { return String(s).replace(/[&<>"]/g, function (c) {
  return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]; }); }
/* a JS literal safe to sit inside a double-quoted HTML attribute */
function arg(v) { return JSON.stringify(v).replace(/"/g, "&quot;"); }

/* dominant unit at a node, restricted to units that survive the filters */
function unitsAt(ni) {
  var out = [];
  DATA.unitIdx.forEach(function (u, ui) {
    var n = cellsFor(ni, ui).length;
    if (n) out.push({ui:ui, u:u, n:n});
  });
  out.sort(function (a, b) { return b.n - a.n; });
  return out;
}
function resolveUnit(ni) {
  var us = unitsAt(ni);
  if (!us.length) return null;
  var hit = us.filter(function (x) { return x.u === S.unit; })[0];
  return hit ? hit.ui : us[0].ui;
}

/* ---------------- chart helper ---------------- */
function chart(id, cfg) {
  if (charts[id]) { charts[id].destroy(); delete charts[id]; }
  var el = document.getElementById(id);
  if (!el) return;
  cfg.options = cfg.options || {};
  cfg.options.responsive = true;
  cfg.options.maintainAspectRatio = false;
  cfg.options.animation = false;
  charts[id] = new Chart(el.getContext("2d"), cfg);
}
function sizeCanvas(id, h) {
  var el = document.getElementById(id);
  if (el) el.parentNode.style.height = h + "px";
}

/* =====================================================================
   1. WORLD
   ===================================================================== */
function levelRows() {
  return DATA.ctyIdx
    .map(function (slug) { return Object.assign({slug:slug}, DATA.cty[slug]); })
    .filter(function (r) { return r.level_ok && r.level != null; })
    .filter(function (r) { return !S.region || r.region === S.region; })
    .sort(function (a, b) { return b.level - a.level; });
}

function renderWorld() {
  var m = DATA.meta;
  var ranked = DATA.ctyIdx.filter(function (s) { return DATA.cty[s].level_ok; }).length;
  document.getElementById("kpis").innerHTML = [
    kpi("Countries", fmtN(m.n_countries), ranked + " comparable enough to rank"),
    kpi("Observations", (m.n_obs / 1e6).toFixed(2) + "M", "trusted unit values"),
    kpi("Food categories", fmtN(Object.keys(DATA.tax).filter(function (c) {
      return DATA.tax[c].lvl === 5; }).length), "COICOP leaves priced"),
    kpi("Retail sources", fmtN(m.n_sources), "shops and catalogues"),
    kpi("Data through", m.through, "latest month with prices")
  ].join("");

  var regions = {};
  DATA.ctyIdx.forEach(function (s) { var r = DATA.cty[s];
    if (r.level_ok) regions[r.region] = (regions[r.region] || 0) + 1; });
  document.getElementById("regionChips").innerHTML = Object.keys(regions).sort()
    .map(function (r) {
      return '<button class="chip' + (S.region === r ? " on" : "") + '" onclick="APP.setRegion(' +
        arg(r) + ')">' + esc(r) +
        '<span class="c">' + regions[r] + "</span></button>";
    }).join("");
  document.getElementById("reg-all").className = "chip" + (S.region ? "" : " on");

  renderRanking();

  /* division + unit composition */
  var divs = {}, units = {};
  C.forEach(function (c) {
    if (!keep(c)) return;
    if (DATA.tax[c.node] && DATA.tax[c.node].lvl === 5) {
      var d = c.node.slice(0, 2);
      divs[d] = (divs[d] || 0) + c.obs;
      units[c.unit] = (units[c.unit] || 0) + c.obs;
    }
  });
  var uk = Object.keys(units).sort(function (a, b) { return units[b] - units[a]; });
  chart("cUnits", {
    type:"bar",
    data:{ labels: uk.map(function (u) { return UNIT_SHORT[u]; }),
      datasets:[{ data: uk.map(function (u) { return units[u]; }),
        backgroundColor: uk.map(function (u, i) { return PAL[i] + "cc"; }),
        borderWidth:0, borderRadius:4 }] },
    options:{ plugins:{ legend:{display:false}, tooltip:{ callbacks:{ label:function (c) {
      return c.parsed.y.toLocaleString() + " observations priced " + UNIT_LABEL[uk[c.dataIndex]]; } } } },
      scales:{ y:{ beginAtZero:true, ticks:{ callback:function (v) {
        return v >= 1e6 ? (v/1e6).toFixed(1)+"M" : v >= 1e3 ? (v/1e3).toFixed(0)+"k" : v; } } } } }
  });
  document.getElementById("unitNote").innerHTML =
    "Divisions present: " + Object.keys(divs).sort().map(function (d) {
      return "<code>" + d + "</code> " + esc(title(d)); }).join(" · ") +
    ". Every price is a <b>unit value</b> — the shelf price divided by the quantity in the pack, " +
    "so a 400&nbsp;g bag and a 2&nbsp;kg bag of the same rice both become a price " +
    "<span class='ub'>per kg</span>. Units are never pooled with each other.";

  var vol = DATA.ctyIdx.map(function (s) { return {n:DATA.cty[s].name, v:DATA.cty[s].obs}; })
    .sort(function (a, b) { return b.v - a.v; }).slice(0, 25);
  chart("cVolume", {
    type:"bar",
    data:{ labels: vol.map(function (r) { return r.n; }),
      datasets:[{ data: vol.map(function (r) { return r.v; }),
        backgroundColor:"#1f6febcc", borderWidth:0, borderRadius:3 }] },
    options:{ indexAxis:"y", plugins:{ legend:{display:false} },
      scales:{ x:{ ticks:{ callback:function (v) {
        return v >= 1e3 ? (v/1e3).toFixed(0)+"k" : v; } } },
        y:{ ticks:{font:{size:10.5}, autoSkip:false}, grid:{display:false} } } }
  });
}
function renderRanking() {
  var rows = levelRows();
  document.getElementById("worldCount").textContent =
    rows.length + " countries ranked · world median = 100";
  if (!rows.length) {
    document.getElementById("rankScale").innerHTML = "";
    document.getElementById("rankList").innerHTML = '<div class="empty">No country in this region is comparable enough to rank.</div>';
    return;
  }
  var lo = Math.min(60, Math.floor(rows[rows.length - 1].level / 10) * 10);
  var hi = Math.max(140, Math.ceil(rows[0].level / 10) * 10);
  var pos = function (v) { return (v - lo) / (hi - lo) * 100; };

  /* scale sits above the scroll area, so it never scrolls out of view */
  var ticks = [], step = (hi - lo) > 200 ? 50 : 20, t;
  for (t = lo; t <= hi + 0.001; t += step) ticks.push(t);
  if (ticks.indexOf(100) < 0) ticks.push(100);
  ticks.sort(function (a, b) { return a - b; });
  document.getElementById("rankScale").innerHTML =
    '<div style="position:absolute;left:236px;right:70px;top:0;bottom:0">' +
    ticks.map(function (v) {
      return '<span class="' + (v === 100 ? "mid" : "") + '" style="left:' + pos(v) + '%">' +
        (v === 100 ? "100 = world median" : v) + '</span><i style="left:' + pos(v) + '%"></i>';
    }).join("") + "</div>";

  document.getElementById("rankList").innerHTML = rows.map(function (r, i) {
    var a = Math.min(r.level, 100), b = Math.max(r.level, 100);
    var up = r.level >= 100;
    return '<div class="rrow' + (r.level_n < 25 ? " thin" : "") + '" onclick="APP.openCountry(' +
      arg(r.slug) + ')" title="' + esc(r.name) + ": " + r.level.toFixed(1) +
      " (world = 100) · " + r.level_n + " matched items · " + r.src + " sources · " +
      r.obs.toLocaleString() + ' observations">' +
      '<div class="n">' + (i + 1) + '</div><div class="nm">' + esc(r.name) + "</div>" +
      '<div class="tr"><div class="zero" style="left:' + pos(100) + '%"></div>' +
      '<div class="f" style="left:' + pos(a) + "%;width:" + (pos(b) - pos(a)) + "%;background:" +
      (up ? "#c0392bcc" : "#2aa36bcc") + '"></div></div>' +
      '<div class="v" style="color:' + (up ? "var(--bad)" : "var(--good)") + '">' +
      r.level.toFixed(0) + "</div></div>";
  }).join("");
}
function kpi(l, v, n) {
  return '<div class="kpi"><div class="l">' + l + '</div><div class="v">' + v +
         '</div><div class="n">' + n + "</div></div>";
}

/* =====================================================================
   shared: hierarchy navigator
   ===================================================================== */
function navigator(crumbId, listId, node, onPick, countFn) {
  var crumb = ancestors(node).map(function (a, i, arr) {
    var last = i === arr.length - 1;
    return last ? '<span class="cur">' + esc(title(a)) + "</span>"
      : '<a onclick="APP.pick(' + arg(a) + ')">' + esc(title(a)) + "</a>";
  }).join(' <span class="sep">›</span> ');
  document.getElementById(crumbId).innerHTML =
    '<a onclick="APP.pick(null)">All food</a> <span class="sep">›</span> ' + crumb;

  var kids = KIDS.get(node) || [];
  var list = (kids.length ? kids : ancestors(node).length > 1
      ? (KIDS.get(DATA.tax[node].p) || []) : ROOTS);
  var isSiblings = !kids.length;
  var html = list.map(function (code) {
    var c = countFn(code);
    var leaf = !(KIDS.get(code) || []).length;
    var dom = (DATA.nodeMeta[code] || {}).dom;
    return '<div class="it' + (code === node ? " on" : "") + '" onclick="APP.pick(' +
      arg(code) + ')">' +
      "<div><div>" + esc(title(code)) +
      (leaf ? ' <span class="leafmark">leaf</span>' : "") + "</div>" +
      '<div class="code">' + code + (dom ? " · " + UNIT_LABEL[dom] : "") + "</div></div>" +
      '<div class="m">' + c + "</div></div>";
  }).join("");
  var hint = isSiblings
    ? '<div class="it" style="cursor:default;background:#f8fafc;color:var(--faint);font-size:11.5px">' +
      "This is a leaf — showing the other items alongside it.</div>"
    : "";
  document.getElementById(listId).innerHTML = hint + html ||
    '<div class="empty">Nothing priced under this node.</div>';
}

/* =====================================================================
   2. COMPARE COUNTRIES
   ===================================================================== */
function renderCompare() {
  var ni = DATA.nodeIdx.indexOf(S.node);
  navigator("cmpCrumb", "cmpNav", S.node, null, function (code) {
    var i = DATA.nodeIdx.indexOf(code);
    if (i < 0) return "—";
    var n = 0;
    DATA.unitIdx.forEach(function (u, ui) { n += cellsFor(i, ui).length; });
    return n + " countries";
  });

  var us = unitsAt(ni);
  var ui = resolveUnit(ni);
  document.getElementById("cmpUnits").innerHTML = us.length ? us.map(function (x) {
    return '<button class="chip' + (x.ui === ui ? " on" : "") + '" onclick="APP.setUnit(' +
      arg(x.u) + ')">' + UNIT_LABEL[x.u] + '<span class="c">' + x.n + "</span></button>";
  }).join("") : '<span class="tiny">no comparable unit at this node</span>';

  document.getElementById("cmp-abs").className = S.cmpMode === "abs" ? "on" : "";
  document.getElementById("cmp-rel").className = S.cmpMode === "rel" ? "on" : "";
  document.getElementById("cmpRelNote").hidden = S.cmpMode !== "rel";

  if (ui == null) {
    document.getElementById("cmpTitle").textContent = title(S.node);
    document.getElementById("cmpSub").textContent = "No comparable unit values at this node.";
    chart("cCompare", {type:"bar", data:{labels:[], datasets:[]}});
    document.getElementById("cmpTbl").innerHTML = "";
    document.getElementById("cmpSamples").innerHTML = "";
    return;
  }
  var unit = DATA.unitIdx[ui];
  var gmed = ((DATA.nodeMeta[S.node] || {}).gmed || {})[unit];

  var rows = cellsFor(ni, ui).map(function (c) {
    var meta = DATA.cty[c.country] || {};
    var v = val(c);
    var rel = (gmed && meta.level) ? (c.usd / gmed) / (meta.level / 100) : null;
    return { c:c, name:meta.name || c.country, region:meta.region,
             val:v, rel:rel, ratio: gmed ? c.usd / gmed : null };
  });
  if (S.cur === "local") rows = rows.filter(function (r) { return r.val != null; });

  var q = (document.getElementById("cmpSearch").value || "").toLowerCase();
  var shown = q ? rows.filter(function (r) { return r.name.toLowerCase().indexOf(q) >= 0; }) : rows;

  var metric = S.cmpMode === "rel" ? "rel" : "val";
  var plot = shown.filter(function (r) { return r[metric] != null; })
                  .sort(function (a, b) { return b[metric] - a[metric]; });

  document.getElementById("cmpTitle").innerHTML = esc(title(S.node)) +
    ' <span class="ub big">' + UNIT_LABEL[unit] + "</span>";
  document.getElementById("cmpSub").innerHTML =
    (S.cmpMode === "rel"
      ? "Relative price — 1.00 means this item costs exactly what the country's overall food basket would predict."
      : "Median " + (S.cur === "usd" ? "US$" : "local-currency") + " price for one " +
        UNIT_SHORT[unit] + (gmed ? ". World median: <b>$" + gmed.toFixed(2) + "</b>" + UNIT_OF[unit] : "")) +
    " · " + plot.length + " countries" +
    (S.cur === "local" ? " · <b>local currencies are not comparable to each other</b>" : "");

  sizeCanvas("cCompare", Math.max(200, plot.length * 17 + 50));
  chart("cCompare", {
    type:"bar",
    data:{ labels: plot.map(function (r) { return r.name; }),
      datasets:[{ data: plot.map(function (r) { return r[metric]; }),
        backgroundColor: plot.map(function (r) {
          if (r.c.flag) return "#c0392bcc";
          if (r.c.mod >= 0.5) return "#7c5cc4cc";
          if (S.cmpMode === "rel") return r.rel >= 1 ? "#e8833acc" : "#0e8f9ecc";
          return r.c.src === 1 ? "#1f6feb66" : "#1f6febcc"; }),
        borderWidth:0, borderRadius:3 }] },
    options:{ indexAxis:"y",
      onClick:function (e, els) { if (els.length) { S.country = plot[els[0].index].c.country; APP.go("trends"); } },
      plugins:{ legend:{display:false}, tooltip:{ callbacks:{ label:function (t) {
        var r = plot[t.dataIndex], c = r.c, out = [];
        out.push(S.cmpMode === "rel" ? "Relative price: " + r.rel.toFixed(2)
          : fmtMoney(r.val, c.cur) + " " + UNIT_LABEL[c.unit]);
        if (S.cmpMode === "abs" && r.ratio) out.push("vs world median: " + pct(r.ratio - 1));
        out.push(c.obs + " observations · " + c.src + " source" + (c.src > 1 ? "s" : ""));
        out.push("dispersion (log MAD): " + (c.mad == null ? "—" : c.mad.toFixed(2)));
        out.push("period: " + c.per);
        if (c.flag) out.push("⚠ outside plausible bounds");
        if (c.mod >= 0.5) out.push("⚠ modelled, not observed retail");
        if (c.mix) out.push("⚠ mixed currencies in cell");
        return out; } } } },
      scales:{ x:{ beginAtZero:true, position:"top", grid:{color:"#eef2f6"},
          title:{display:true, text: S.cmpMode === "rel" ? "Price relative to the country's own food basket (1.00 = as expected)"
            : (S.cur === "usd" ? "US$ " : "Local currency ") + UNIT_LABEL[unit]} },
        y:{ ticks:{font:{size:11}, autoSkip:false}, grid:{display:false} } } }
  });

  /* table */
  var sk = S.sortCmp.k, sd = S.sortCmp.d;
  var tRows = shown.slice().sort(function (a, b) {
    var av, bv;
    if (sk === "name") { av = a.name; bv = b.name; return sd * (av < bv ? -1 : av > bv ? 1 : 0); }
    av = sk === "val" ? a.val : sk === "rel" ? a.rel : sk === "ratio" ? a.ratio : a.c[sk];
    bv = sk === "val" ? b.val : sk === "rel" ? b.rel : sk === "ratio" ? b.ratio : b.c[sk];
    if (av == null) return 1; if (bv == null) return -1;
    return sd * (bv - av);
  });
  var cols = [["name","Country",""],["val","Price","num"],["ratio","vs world","num"],
    ["rel","Relative","num"],["obs","Obs","num"],["src","Src","num"],
    ["mad","Log MAD","num"],["per","Period",""],["flags","Notes",""]];
  document.getElementById("cmpTbl").innerHTML =
    "<thead><tr>" + cols.map(function (c) {
      return '<th class="' + c[2] + '" onclick="APP.sort(\'cmp\',\'' + c[0] + '\')">' + c[1] +
        (sk === c[0] ? (sd === 1 ? " ▼" : " ▲") : "") + "</th>"; }).join("") + "</tr></thead><tbody>" +
    tRows.map(function (r) { var c = r.c;
      return '<tr class="' + (c.flag ? "flagged" : "") + '">' +
        '<td><span class="linkish" onclick="APP.openCountry(' + arg(c.country) + ')">' +
          esc(r.name) + "</span></td>" +
        '<td class="num">' + fmtMoney(r.val, c.cur) + "</td>" +
        '<td class="num">' + (r.ratio ? pct(r.ratio - 1, 0) : "—") + "</td>" +
        '<td class="num">' + (r.rel ? r.rel.toFixed(2) : "—") + "</td>" +
        '<td class="num">' + c.obs + "</td>" +
        '<td class="num">' + c.src + "</td>" +
        '<td class="num">' + (c.mad == null ? "—" : c.mad.toFixed(2)) + "</td>" +
        "<td>" + c.per + "</td>" +
        "<td>" + flagPills(c) + "</td></tr>"; }).join("") + "</tbody>";

  /* sample product names behind the selected cell */
  var sam = [];
  cellsFor(ni, ui).slice(0, 4).forEach(function (c) {
    var names = DATA.samples[c.ci + "|" + c.ni + "|" + c.ui];
    if (names) sam.push("<b>" + esc((DATA.cty[c.country] || {}).name || c.country) + "</b>: " +
      names.map(function (n) { return "<code>" + esc(n) + "</code>"; }).join(" "));
  });
  document.getElementById("cmpSamples").innerHTML = sam.length
    ? "<div style='margin-top:6px'><b>What is actually in these cells</b><br>" + sam.join("<br>") + "</div>" : "";
}
function flagPills(c) {
  var p = [];
  if (c.flag) p.push('<span class="pill bad">implausible</span>');
  if (c.mod >= 0.5) p.push('<span class="pill mod">modelled</span>');
  if (c.mix) p.push('<span class="pill warn">mixed FX</span>');
  if (c.der > 0.5) p.push('<span class="pill warn">derived qty</span>');
  if (c.src === 1) p.push('<span class="pill warn">1 source</span>');
  if (!p.length) p.push('<span class="pill ok">clean</span>');
  return p.join(" ");
}

/* =====================================================================
   3. COUNTRY PROFILE
   ===================================================================== */
function renderCountry() {
  var sel = document.getElementById("ctrySel");
  if (sel.options.length !== DATA.ctyIdx.length) {
    sel.innerHTML = DATA.ctyIdx.slice().sort(function (a, b) {
      return DATA.cty[a].name < DATA.cty[b].name ? -1 : 1; })
      .map(function (s) { return '<option value="' + s + '">' + esc(DATA.cty[s].name) + "</option>"; }).join("");
  }
  sel.value = S.country;
  var m = DATA.cty[S.country] || {};
  var ci = DATA.ctyIdx.indexOf(S.country);

  document.getElementById("ctryKpis").innerHTML = [
    kpi("Price level", m.level_ok ? m.level.toFixed(0) : "n/a",
        m.level_ok ? "world median = 100 · " + m.level_n + " matched items" : "not comparable enough to rank"),
    kpi("Observations", fmtN(m.obs), m.leaves + " food categories"),
    kpi("Sources", fmtN(m.src), m.retail_src + " retail" +
        (m.src > m.retail_src ? ", " + (m.src - m.retail_src) + " modelled" : "")),
    kpi("Currency", (m.cur || []).join(", ") || "—",
        (m.cur || []).length > 1 ? "multi-currency market" : "single currency"),
    kpi("Latest data", m.last || "—", "most recent month")
  ].join("");

  var warn = [];
  if (!m.level_ok) warn.push("This country is <b>held out of the world ranking</b>: too few matched items, " +
    "a single source, or too many implausible cells (" + ((m.defect || 0) * 100).toFixed(0) + "% flagged).");
  if (m.retail_src === 0) warn.push("Every observation here comes from a <b>modelled cost-of-living aggregator</b>, " +
    "not from an observed shelf price.");
  else if (m.src === 1) warn.push("All prices come from a <b>single source</b> — not statistically comparable to " +
    "a country covered by many retailers.");
  if ((m.cur || []).length > 1) warn.push("Prices here are quoted in <b>" + (m.cur || []).join(" and ") +
    "</b>. Local-currency figures use each cell's dominant currency; only the US$ view is comparable across cells.");
  document.getElementById("ctryWarn").innerHTML = warn.length
    ? '<div class="warnbox">' + warn.join("<br>") + "</div>" : "";

  var mineAll = (byCountry.get(ci) || []).filter(keep);
  navigator("ctryCrumb", "ctryNav", S.node, null, function (code) {
    var pre = code + ".";
    var n = mineAll.filter(function (c) {
      return DATA.tax[c.node] && DATA.tax[c.node].lvl === 5 &&
             (c.node === code || c.node.indexOf(pre) === 0); }).length;
    return n ? n + " item" + (n > 1 ? "s" : "") : "—";
  });

  /* all leaf cells for this country under the selected node */
  var prefix = S.node + ".";
  var mine = mineAll.filter(function (c) {
    return (c.node === S.node || c.node.indexOf(prefix) === 0) &&
           DATA.tax[c.node] && DATA.tax[c.node].lvl === 5;
  }).map(function (c) {
    var g = ((DATA.nodeMeta[c.node] || {}).gmed || {})[c.unit];
    return { c:c, name:title(c.node), ratio: g ? c.usd / g : null, gmed:g, val:val(c) };
  });

  var top = mine.filter(function (r) { return r.ratio != null; })
    .sort(function (a, b) { return b.ratio - a.ratio; });
  var show = top.length > 30 ? top.slice(0, 15).concat(top.slice(-15)) : top;
  document.getElementById("ctryChartTitle").innerHTML =
    esc(m.name || "") + " — dearest and cheapest under " + esc(title(S.node)) + ", versus the world";
  sizeCanvas("cCountry", Math.max(200, show.length * 18 + 50));
  chart("cCountry", {
    type:"bar",
    data:{ labels: show.map(function (r) { return r.name + " (" + UNIT_SHORT[r.c.unit] + ")"; }),
      datasets:[{ data: show.map(function (r) { return (r.ratio - 1) * 100; }),
        backgroundColor: show.map(function (r) { return r.ratio >= 1 ? "#c0392bcc" : "#2aa36bcc"; }),
        borderWidth:0, borderRadius:3 }] },
    options:{ indexAxis:"y",
      onClick:function (e, els) { if (els.length) { S.node = show[els[0].index].c.node;
        S.unit = show[els[0].index].c.unit; APP.render(); } },
      plugins:{ legend:{display:false}, tooltip:{ callbacks:{ label:function (t) {
        var r = show[t.dataIndex];
        return [ fmtMoney(r.val, r.c.cur) + " " + UNIT_LABEL[r.c.unit],
                 "world median: $" + r.gmed.toFixed(2) + UNIT_OF[r.c.unit],
                 pct(r.ratio - 1) + " vs world",
                 r.c.obs + " observations" ]; } } } },
      scales:{ x:{ grid:{color:"#eef2f6"}, position:"top",
          title:{display:true, text:"% above (red) or below (green) the world median for the same item and unit"} },
        y:{ ticks:{font:{size:11}, autoSkip:false}, grid:{display:false} } } }
  });

  var q = (document.getElementById("ctrySearch").value || "").toLowerCase();
  var tRows = (q ? mine.filter(function (r) { return r.name.toLowerCase().indexOf(q) >= 0; }) : mine);
  var sk = S.sortCtry.k, sd = S.sortCtry.d;
  tRows = tRows.slice().sort(function (a, b) {
    if (sk === "name") return sd * (a.name < b.name ? -1 : a.name > b.name ? 1 : 0);
    var av = sk === "ratio" ? a.ratio : sk === "val" ? a.val : a.c[sk];
    var bv = sk === "ratio" ? b.ratio : sk === "val" ? b.val : b.c[sk];
    if (av == null) return 1; if (bv == null) return -1;
    return sd * (bv - av);
  });
  var cols = [["name","Item",""],["unit","Unit",""],["val","Price","num"],
    ["ratio","vs world","num"],["obs","Obs","num"],["src","Src","num"],
    ["mad","Log MAD","num"],["per","Period",""],["flags","Notes",""]];
  document.getElementById("ctryTbl").innerHTML =
    "<thead><tr>" + cols.map(function (c) {
      return '<th class="' + c[2] + '" onclick="APP.sort(\'ctry\',\'' + c[0] + '\')">' + c[1] +
        (sk === c[0] ? (sd === 1 ? " ▼" : " ▲") : "") + "</th>"; }).join("") + "</tr></thead><tbody>" +
    (tRows.length ? tRows.map(function (r) { var c = r.c;
      return '<tr class="' + (c.flag ? "flagged" : "") + '">' +
        '<td><span class="linkish" onclick="APP.openNode(' + arg(c.node) + ',' +
          arg(c.unit) + ')">' + esc(r.name) + "</span></td>" +
        '<td><span class="ub">' + UNIT_LABEL[c.unit] + "</span></td>" +
        '<td class="num">' + fmtMoney(r.val, c.cur) + "</td>" +
        '<td class="num">' + (r.ratio ? pct(r.ratio - 1, 0) : "—") + "</td>" +
        '<td class="num">' + c.obs + "</td>" +
        '<td class="num">' + c.src + "</td>" +
        '<td class="num">' + (c.mad == null ? "—" : c.mad.toFixed(2)) + "</td>" +
        "<td>" + c.per + "</td><td>" + flagPills(c) + "</td></tr>"; }).join("")
      : '<tr><td colspan="9" class="empty">Nothing priced here under the current filters.</td></tr>') +
    "</tbody>";
}

/* =====================================================================
   4. TRENDS & FX
   ===================================================================== */
function seriesFor(ci, ni, ui) { return DATA.series[ci + "|" + ni + "|" + ui] || null; }
/* Sparse months must read as gaps, not as evenly-spaced steps. */
function monthGrid(periods) {
  var a = periods[0].split("-"), b = periods[periods.length - 1].split("-");
  var y = +a[0], mo = +a[1], ey = +b[0], em = +b[1], out = [];
  while (y < ey || (y === ey && mo <= em)) {
    out.push(y + "-" + (mo < 10 ? "0" + mo : mo));
    if (++mo > 12) { mo = 1; y++; }
    if (out.length > 400) break;
  }
  return out;
}
/* A segment that bridges empty months is drawn dashed: it is interpolation,
   not measurement, and over this corpus most months are empty. */
var GAP_SEG = { borderDash:function (ctx) {
  return (ctx.p0.skip || ctx.p1.skip || ctx.p1DataIndex - ctx.p0DataIndex > 1) ? [5, 5] : undefined; } };
function onGrid(grid, periods, values) {
  var m = {}; periods.forEach(function (p, i) { m[p] = values[i]; });
  return grid.map(function (g) { return m[g] == null ? null : m[g]; });
}
function fxOf(slug) {
  var f = DATA.fx[slug] || {p:[], r:[]}, m = {};
  f.p.forEach(function (pp, i) { m[pp] = f.r[i]; });
  return m;
}
/* The series behind the trend chart.
   Leaf node  -> the median unit value itself, in both currencies.
   Aggregate  -> the chained matched-item index, whose local counterpart follows
                 from P_local = P_usd x FX, so no currency mixing sneaks in. */
function trendSeries(ci, ni, ui) {
  var code = DATA.nodeIdx[ni], isLeaf = (DATA.tax[code] || {}).lvl === 5;
  if (isLeaf) {
    var s = seriesFor(ci, ni, ui);
    return s ? {p:s.p, usd:s.usd, loc:s.loc, n:s.n, kind:"median", leaves:null} : null;
  }
  var ch = DATA.chain[ci + "|" + ni + "|" + ui];
  if (!ch) return null;
  var fxm = fxOf(DATA.ctyIdx[ci]), fx0 = null;
  ch.p.forEach(function (pp) { if (fx0 == null && fxm[pp] > 0) fx0 = fxm[pp]; });
  var loc = ch.p.map(function (pp, i) {
    var r = fxm[pp];
    return (fx0 && r > 0) ? ch.idx[i] * (r / fx0) : null; });
  return {p:ch.p, usd:ch.idx, loc:loc, n:ch.k, kind:"index", leaves:ch.k};
}

function renderTrends() {
  var csel = document.getElementById("trCtry");
  if (csel.options.length !== DATA.ctyIdx.length) {
    csel.innerHTML = DATA.ctyIdx.slice().sort(function (a, b) {
      return DATA.cty[a].name < DATA.cty[b].name ? -1 : 1; })
      .map(function (s) { return '<option value="' + s + '">' + esc(DATA.cty[s].name) + "</option>"; }).join("");
  }
  csel.value = S.country;
  var ci = DATA.ctyIdx.indexOf(S.country);

  /* only nodes this country actually has a series for */
  var opts = [];
  DATA.nodeIdx.forEach(function (code, ni) {
    for (var ui = 0; ui < DATA.unitIdx.length; ui++) {
      if (trendSeries(ci, ni, ui)) { opts.push(code); return; }
    }
  });
  var nsel = document.getElementById("trNode");
  nsel.innerHTML = opts.length ? opts.map(function (code) {
    return '<option value="' + code + '">' + esc(title(code)) + " · " + code + "</option>"; }).join("")
    : '<option value="">no series for this country</option>';
  if (opts.indexOf(S.node) < 0 && opts.length) {
    var best = opts[0], bn = -1;
    opts.forEach(function (code) {
      var nn = DATA.nodeIdx.indexOf(code);
      for (var uu = 0; uu < DATA.unitIdx.length; uu++) {
        var ss = trendSeries(ci, nn, uu);
        /* prefer a leaf: no chain drift to accumulate */
        if (ss) { var score = ss.p.length + (ss.kind === "median" ? 1000 : 0);
          if (score > bn) { bn = score; best = code; } }
      }
    });
    S.node = best;
  }
  nsel.value = S.node;

  var ni = DATA.nodeIdx.indexOf(S.node);
  var avail = [];
  DATA.unitIdx.forEach(function (u, ui) { if (trendSeries(ci, ni, ui)) avail.push({u:u, ui:ui}); });
  var ui = (avail.filter(function (x) { return x.u === S.unit; })[0] || avail[0] || {}).ui;
  document.getElementById("trUnits").innerHTML = avail.map(function (x) {
    return '<button class="chip' + (x.ui === ui ? " on" : "") + '" onclick="APP.setUnit(' +
      arg(x.u) + ')">' + UNIT_LABEL[x.u] + "</button>"; }).join("");
  document.getElementById("tr-both").className = S.fxMode === "both" ? "on" : "";
  document.getElementById("tr-nofx").className = S.fxMode === "nofx" ? "on" : "";

  var s = ui == null ? null : trendSeries(ci, ni, ui);
  if (!s) {
    document.getElementById("trWarn").innerHTML =
      '<div class="warnbox">No repeated monthly observations for this combination. ' +
      'A price series needs at least ' + 3 + ' months each with ' + DATA.meta.min_cell_obs +
      '+ observations.</div>';
    chart("cTrend", {type:"line", data:{labels:[], datasets:[]}});
    document.getElementById("trDeco").innerHTML = "";
    chart("cTrendMulti", {type:"line", data:{labels:[], datasets:[]}});
    document.getElementById("trMulti").innerHTML = "";
    return;
  }

  var fxMap = fxOf(S.country);
  var isIdx = s.kind === "index";
  document.getElementById("trKind").innerHTML = isIdx
    ? '<span class="pill ok">matched-item index</span> composition held fixed &mdash; only ' +
      'items priced in both months are linked, so this moves when prices move, not when the ' +
      'scrape changes shape'
    : '<span class="pill ok">median unit value</span> the actual median price of one ' +
      UNIT_SHORT[DATA.unitIdx[ui]] + ", indexed to its first month";

  var base = {usd:null, loc:null, fx:null};
  for (var i = 0; i < s.p.length; i++) {
    if (base.usd == null && s.usd[i] > 0) base.usd = s.usd[i];
    if (base.loc == null && s.loc[i] > 0) base.loc = s.loc[i];
    if (base.fx == null && fxMap[s.p[i]] > 0) base.fx = fxMap[s.p[i]];
  }
  var idxUsd = s.usd.map(function (v) { return base.usd && v > 0 ? v / base.usd * 100 : null; });
  var idxLoc = s.loc.map(function (v) { return base.loc && v > 0 ? v / base.loc * 100 : null; });
  var idxFx  = s.p.map(function (p) { var r = fxMap[p];
    return base.fx && r > 0 ? r / base.fx * 100 : null; });

  var grid = monthGrid(s.p);
  var ds = [];
  ds.push({label:"Local currency price", data:onGrid(grid, s.p, idxLoc), borderColor:PAL[2],
           backgroundColor:PAL[2] + "22", borderWidth:2.4, tension:.2, pointRadius:2.5,
           spanGaps:true, segment:GAP_SEG});
  if (S.fxMode === "both") {
    ds.push({label:"US$ price", data:onGrid(grid, s.p, idxUsd), borderColor:PAL[0],
             backgroundColor:PAL[0] + "22", borderWidth:2.4, tension:.2, pointRadius:2.5,
             spanGaps:true, segment:GAP_SEG});
    ds.push({label:"Exchange rate (local per US$)", data:onGrid(grid, s.p, idxFx), borderColor:PAL[1],
             borderWidth:1.8, borderDash:[3,3], tension:.2, pointRadius:0, spanGaps:true});
  }
  ds.push({label: isIdx ? "Items linked" : "Observations", type:"bar", yAxisID:"y2",
           data:onGrid(grid, s.p, s.n), backgroundColor:"#8c9aa833", borderWidth:0, order:99});

  var gaps = grid.length - s.p.length;
  var warn = [];
  if (s.p.length < 6) warn.push("Only <b>" + s.p.length + " months</b> of data — read the direction, not the slope.");
  if (gaps > s.p.length) warn.push("<b>" + gaps + " of " + grid.length +
    "</b> months in this window have no data at all; the line jumps across them.");
  warn.push("Across the whole corpus <b>" + (DATA.qa.history.share_last_12m * 100).toFixed(0) +
    "%</b> of trusted observations fall in the last 12 months, so anything before that rests on " +
    "sparse archive backfill.");
  document.getElementById("trWarn").innerHTML = '<div class="warnbox">' + warn.join("<br>") + "</div>";

  chart("cTrend", {
    type:"line", data:{labels:grid, datasets:ds},
    options:{ interaction:{mode:"index", intersect:false},
      plugins:{ legend:{position:"top", labels:{usePointStyle:true, padding:16, boxWidth:8}},
        tooltip:{ callbacks:{ afterBody:function (items) {
          var k = items[0].dataIndex;
          return isIdx
            ? ["", s.n[k] + " items linked this month"]
            : ["", "US$ " + (s.usd[k] != null ? "$" + s.usd[k].toFixed(2) : "—") +
                 UNIT_OF[DATA.unitIdx[ui]],
               "local " + (s.loc[k] != null ? s.loc[k].toFixed(2) : "—"),
               s.n[k] + " observations"]; } } } },
      scales:{ y:{ title:{display:true, text:"Index, first period with data = 100"}, grid:{color:"#eef2f6"} },
        y2:{ position:"right", beginAtZero:true, grid:{display:false},
             title:{display:true, text: isIdx ? "items linked" : "observations",
                    font:{size:10}, color:"#8c9aa8"},
             ticks:{font:{size:10}, color:"#8c9aa8"},
             /* keep the support bars in the bottom fifth, out of the lines' way */
             afterDataLimits:function (a) { a.max = a.max * 5; } },
        x:{ grid:{display:false}, ticks:{maxRotation:0, autoSkip:true, maxTicksLimit:14} } } }
  });

  /* decomposition over the window */
  var last = {usd:null, loc:null, fx:null};
  for (var j = s.p.length - 1; j >= 0; j--) {
    if (last.usd == null && s.usd[j] > 0) last.usd = s.usd[j];
    if (last.loc == null && s.loc[j] > 0) last.loc = s.loc[j];
    if (last.fx == null && fxMap[s.p[j]] > 0) last.fx = fxMap[s.p[j]];
  }
  var dUsd = base.usd && last.usd ? last.usd / base.usd - 1 : null;
  var dLoc = base.loc && last.loc ? last.loc / base.loc - 1 : null;
  var dFx  = base.fx && last.fx ? last.fx / base.fx - 1 : null;
  var lnUsd = dUsd == null ? null : Math.log(1 + dUsd);
  var lnLoc = dLoc == null ? null : Math.log(1 + dLoc);
  var lnFxC = (lnUsd != null && lnLoc != null) ? lnUsd - lnLoc : null;
  document.getElementById("trDeco").innerHTML = [
    box("US$ price", pct(dUsd), dUsd),
    box("Local price (FX removed)", pct(dLoc), dLoc),
    box("Exchange rate, local per US$", pct(dFx), dFx),
    '<div class="b"><div class="l">' + s.p[0] + " → " + s.p[s.p.length - 1] + '</div>' +
      '<div class="v" style="font-size:14px;font-weight:600;line-height:1.45">' +
      (lnFxC == null ? "FX split unavailable"
        : "Of the US$ move, <b>" + (lnLoc * 100).toFixed(1) + "</b> log-points came from local prices and <b>" +
          (lnFxC * 100).toFixed(1) + "</b> from the currency.") + "</div></div>"
  ].join("");

  /* multi-country overlay */
  var peers = [];
  DATA.ctyIdx.forEach(function (slug, k) {
    var ss = trendSeries(k, ni, ui);
    if (ss && ss.p.length >= 3) peers.push({slug:slug, name:DATA.cty[slug].name, s:ss, n:ss.p.length});
  });
  peers.sort(function (a, b) { return b.n - a.n; });
  if (!S.multi.length) S.multi = peers.slice(0, 5).map(function (p) { return p.slug; });
  S.multi = S.multi.filter(function (sl) {
    return peers.some(function (p) { return p.slug === sl; }); });
  document.getElementById("trMulti").innerHTML = peers.slice(0, 16).map(function (p) {
    return '<button class="chip' + (S.multi.indexOf(p.slug) >= 0 ? " on" : "") + '" onclick="APP.toggleMulti(' +
      arg(p.slug) + ')">' + esc(p.name) + '<span class="c">' + p.n + "m</span></button>"; }).join("");

  var months = [];
  S.multi.forEach(function (sl) { var p = peers.filter(function (x) { return x.slug === sl; })[0];
    if (p) { months.push(p.s.p[0]); months.push(p.s.p[p.s.p.length - 1]); } });
  months.sort();
  var labels = months.length ? monthGrid([months[0], months[months.length - 1]]) : [];
  var mds = S.multi.map(function (sl, i) {
    var p = peers.filter(function (x) { return x.slug === sl; })[0];
    if (!p) return null;
    var arr = S.cur === "usd" ? p.s.usd : p.s.loc, b = null, map = {};
    p.s.p.forEach(function (m, k) { if (b == null && arr[k] > 0) b = arr[k];
      map[m] = arr[k] > 0 && b ? arr[k] / b * 100 : null; });
    return { label:p.name, data:labels.map(function (m) { return map[m] == null ? null : map[m]; }),
      borderColor:PAL[i % PAL.length], borderWidth:2, tension:.2, pointRadius:2,
      spanGaps:true, segment:GAP_SEG };
  }).filter(Boolean);
  chart("cTrendMulti", {
    type:"line", data:{labels:labels, datasets:mds},
    options:{ interaction:{mode:"index", intersect:false},
      plugins:{ legend:{position:"top", labels:{usePointStyle:true, padding:14, boxWidth:8}} },
      scales:{ y:{ title:{display:true, text:"Index, each country's own first period = 100"}, grid:{color:"#eef2f6"} },
        x:{ grid:{display:false}, ticks:{maxRotation:0, autoSkip:true, maxTicksLimit:14} } } }
  });
}
function box(l, v, sign) {
  return '<div class="b ' + (sign == null ? "" : sign >= 0 ? "pos" : "neg") + '"><div class="l">' +
    l + '</div><div class="v">' + v + "</div></div>";
}

/* =====================================================================
   5. DATA QUALITY
   ===================================================================== */
function renderQuality() {
  var q = DATA.qa, ks = Object.keys(q.status).sort(function (a, b) { return q.status[b] - q.status[a]; });
  var LABEL = { trusted:"Trusted — all gates passed",
    review_uv_outlier:"Rejected: unit value is an outlier in its own cell",
    review_missing_qty:"Rejected: quantity could not be parsed from the name",
    review_uv_category:"Rejected: category where a unit value is not meaningful",
    review_basis:"Rejected: pricing basis implausible",
    review_zero_price:"Rejected: price was zero or negative",
    review_fx:"Rejected: no usable exchange rate" };
  chart("cQa", {
    type:"bar",
    data:{ labels: ks.map(function (k) { return LABEL[k] || k; }),
      datasets:[{ data: ks.map(function (k) { return q.status[k]; }),
        backgroundColor: ks.map(function (k) { return k === "trusted" ? "#2aa36bcc" : "#c0392b88"; }),
        borderWidth:0, borderRadius:3 }] },
    options:{ indexAxis:"y", plugins:{legend:{display:false}},
      scales:{ x:{ ticks:{ callback:function (v) {
        return v >= 1e6 ? (v/1e6).toFixed(1)+"M" : v >= 1e3 ? (v/1e3).toFixed(0)+"k" : v; } } },
        y:{ ticks:{font:{size:11}, autoSkip:false}, grid:{display:false} } } }
  });
  var tot = Object.keys(q.status).reduce(function (a, k) { return a + q.status[k]; }, 0);
  document.getElementById("qaNotes").innerHTML =
    '<div class="explain"><b>' + (q.status.trusted / tot * 100).toFixed(1) + "%</b> of " +
    (tot / 1e6).toFixed(2) + "M built observations are trusted. Gates are evaluated in " +
    "<b>first-failing-gate</b> order, so this chart understates how often each individual gate " +
    "would fail on its own.</div>" +
    '<div class="warnbox">Excluded from this dashboard entirely: <b>' + fmtN(q.item_basis_rows) +
    "</b> trusted rows whose quantity never parsed (basis <code>item</code>) — that is a parse-failure " +
    "bucket, not a fourth unit, and pooling it with kg or litre would be meaningless.</div>" +
    "<div class='samples'><b>Quantity provenance</b> (trusted rows): " +
    Object.keys(q.mass_source).map(function (k) {
      return esc(k) + " " + fmtN(q.mass_source[k]); }).join(" · ") +
    ". <code>derived_typical</code> rows infer a pack mass from the leaf's own measured rows " +
    "and run systematically high; the <i>Measured only</i> filter removes them.<br>" +
    "<b>Modelled sources</b> (" + q.modelled_sources.join(", ") + "): " + fmtN(q.modelled_rows) +
    " rows are cost-of-living survey averages, not observed shelf prices. Off by default.</div>";

  /* leaf only: a parent node inherits its single child's bad value and would
     otherwise pad this list with the same defect twice */
  var flagged = C.filter(function (c) {
      return c.flag && DATA.tax[c.node] && DATA.tax[c.node].lvl === 5; })
    .sort(function (a, b) { return b.usd - a.usd; }).slice(0, 200);
  document.getElementById("flagTbl").innerHTML =
    "<thead><tr><th>Country</th><th>Item</th><th>Unit</th><th class='num'>US$</th>" +
    "<th class='num'>Obs</th><th>Source count</th><th>Period</th></tr></thead><tbody>" +
    flagged.map(function (c) {
      return "<tr class='flagged'><td>" + esc((DATA.cty[c.country] || {}).name || c.country) + "</td><td>" +
        esc(title(c.node)) + "</td><td><span class='ub'>" + UNIT_LABEL[c.unit] + "</span></td>" +
        "<td class='num'>" + c.usd.toLocaleString(undefined, {maximumFractionDigits:2}) + "</td>" +
        "<td class='num'>" + c.obs + "</td><td>" + c.src + "</td><td>" + c.per + "</td></tr>"; }).join("") +
    "</tbody>";

  var held = DATA.ctyIdx.map(function (s) { return Object.assign({slug:s}, DATA.cty[s]); })
    .filter(function (r) { return !r.level_ok; })
    .sort(function (a, b) { return b.obs - a.obs; });
  document.getElementById("heldTbl").innerHTML =
    "<thead><tr><th>Country</th><th class='num'>Matched items</th><th class='num'>Sources</th>" +
    "<th class='num'>Retail sources</th><th class='num'>Flagged cells</th><th class='num'>Obs</th>" +
    "<th>Why held out</th></tr></thead><tbody>" +
    held.map(function (r) {
      var why = [];
      if ((r.level_n || 0) < DATA.qa.min_basket_leaves) why.push("fewer than " + DATA.qa.min_basket_leaves + " matched items");
      if (r.retail_src === 0) why.push("modelled sources only");
      else if (r.src < 2) why.push("single source");
      if ((r.defect || 0) >= 0.2) why.push("≥20% implausible cells");
      return "<tr><td>" + esc(r.name) + "</td><td class='num'>" + (r.level_n || 0) + "</td>" +
        "<td class='num'>" + r.src + "</td><td class='num'>" + r.retail_src + "</td>" +
        "<td class='num'>" + ((r.defect || 0) * 100).toFixed(0) + "%</td>" +
        "<td class='num'>" + fmtN(r.obs) + "</td><td>" + (why.join("; ") || "—") + "</td></tr>"; }).join("") +
    "</tbody>";

  var b = DATA.qa.plausible_bounds || {};
  document.getElementById("methodology").innerHTML =
    "<div class='samples' style='font-size:13px;line-height:1.8'>" +
    "<b>A unit value is not a price.</b> It is the shelf price divided by the quantity in the pack " +
    "(<code>amount_value × multiplier</code>), so packs of different sizes become comparable. " +
    "The valid grain is <b>(country, COICOP node, unit)</b>. Values are never pooled across units: " +
    "rice sold by mass and rice sold by the piece are two different numbers.<br>" +
    "<b>Local currency.</b> Each cell's local figure uses that cell's dominant currency, because " +
    "country is not a reliable proxy for currency — several markets quote in two currencies side by side. " +
    "Cells where the dominant currency covers under 90% of rows are marked <span class='pill warn'>mixed FX</span>.<br>" +
    "<b>Reliability.</b> Use <b>log MAD</b> (within-cell dispersion) and the observation and source counts. " +
    "Classifier confidence is deliberately not shown: it sits near 0.94 almost everywhere and " +
    "discriminates nothing.<br>" +
    "<b>Plausibility bounds.</b> Relative outlier gates are blind to systematic error, so an absolute " +
    "screen is applied: " + Object.keys(b).map(function (u) {
      return "<code>" + UNIT_LABEL[u] + " $" + b[u][0] + "–$" + b[u][1] + "</code>"; }).join(", ") +
    ". Cells outside are flagged, never silently dropped.<br>" +
    "<b>What this is not.</b> There are no expenditure weights here, so the price level is not a " +
    "cost-of-living or CPI index. Coverage differs across countries for reasons of sourcing and " +
    "classifier language coverage, not because markets differ.<br>" +
    "<b>Scope.</b> COICOP divisions 01 and 02 only — food, non-alcoholic beverages, alcohol and tobacco. " +
    "Nothing else in the consumption basket is priced here.</div>";
}

/* =====================================================================
   controller
   ===================================================================== */
var APP = {
  set:function (k, v) { S[k] = v; if (k === "country") S.multi = []; this.render(); },
  setRegion:function (r) { S.region = r; this.render(); },
  setUnit:function (u) { S.unit = u; this.render(); },
  setMode:function (m) { S.mode = m;
    document.body.className = "mode-" + m;
    document.getElementById("m-explore").className = m === "explore" ? "on" : "";
    document.getElementById("m-analyst").className = m === "analyst" ? "on" : "";
    if (m !== "analyst" && S.view === "quality") return this.go("world");
    this.render(); },
  go:function (v) { S.view = v;
    ["world","compare","country","trends","quality"].forEach(function (x) {
      document.getElementById("v-" + x).hidden = x !== v;
      document.getElementById("t-" + x).className =
        (x === "quality" ? "analyst-only" : "") + (x === v ? " on" : ""); });
    this.render(); },
  pick:function (code) { S.node = code || "01"; S.unit = null; this.render(); },
  openCountry:function (slug) { S.country = slug; S.multi = []; this.go("country"); },
  openNode:function (code, unit) { S.node = code; S.unit = unit; this.go("compare"); },
  toggleMulti:function (slug) { var i = S.multi.indexOf(slug);
    if (i >= 0) S.multi.splice(i, 1); else S.multi.push(slug); this.render(); },
  sort:function (which, k) {
    var t = which === "cmp" ? S.sortCmp : S.sortCtry;
    if (t.k === k) t.d = -t.d; else { t.k = k; t.d = 1; }
    this.render(); },
  render:function () {
    ["cur-usd","cur-local"].forEach(function (id) {
      document.getElementById(id).className = id === "cur-" + S.cur ? "on" : ""; });
    document.getElementById("mod-0").className = S.incModelled ? "" : "on";
    document.getElementById("mod-1").className = S.incModelled ? "on" : "";
    document.getElementById("der-0").className = S.measuredOnly ? "" : "on";
    document.getElementById("der-1").className = S.measuredOnly ? "on" : "";
    ["any","solid","corrob"].forEach(function (k) {
      document.getElementById("ev-" + k).className = S.evidence === k ? "on" : ""; });
    document.getElementById("flg-0").className = S.showFlagged ? "" : "on";
    document.getElementById("flg-1").className = S.showFlagged ? "on" : "";
    if (S.view === "world") renderWorld();
    else if (S.view === "compare") renderCompare();
    else if (S.view === "country") renderCountry();
    else if (S.view === "trends") renderTrends();
    else if (S.view === "quality") renderQuality();
  }
};
window.APP = APP;

/* boot */
(function () {
  var m = DATA.meta;
  document.getElementById("scope").innerHTML =
    "COICOP divisions " + m.divisions.join(" and ") + " — food, beverages, alcohol, tobacco · " +
    m.n_countries + " countries · " + m.n_sources + " sources · data through " + m.through;
  document.getElementById("minleaves").textContent = DATA.qa.min_basket_leaves;
  document.getElementById("foot").innerHTML =
    "Generated " + m.generated + " · " + m.n_obs.toLocaleString() +
    " trusted unit values · cells need " + m.min_cell_obs + "+ observations";
  /* default country = the one with the deepest series */
  var best = null, bestN = -1;
  Object.keys(DATA.series).forEach(function (k) {
    var n = DATA.series[k].p.length;
    if (n > bestN) { bestN = n; best = DATA.ctyIdx[+k.split("|")[0]]; } });
  S.country = best || DATA.ctyIdx[0];
  APP.render();
})();
})();
