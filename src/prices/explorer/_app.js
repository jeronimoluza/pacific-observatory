/* Global price explorer — view layer.
   Every number on screen comes from DATA, pre-aggregated at the only grain a
   unit value is valid at: (country, COICOP node, standard_unit). */
(function () {
"use strict";

/* Validated categorical order (lightness band, chroma, CVD, normal-vision and
   contrast all pass on the paper ground). Six slots, assigned by entity and never
   cycled by rank, so filtering a place out never repaints the ones that remain. */
var PAL  = ["#1c6fbe","#a83f8c","#cf5a2b","#0f8f6e","#a67c10","#4a4fb5"];
var INK  = "#1b211f", RULE = "#e7e4dc", FAINT = "#787d7a", DIM = "#5c625f";
var CHEAP = "#17627d", DEAR = "#b5442e";
var UNIT_LABEL = {kg:"per kg", lt:"per litre", unit:"per piece"};
var UNIT_SHORT  = {kg:"kg", lt:"litre", unit:"piece"};
var UNIT_OF     = {kg:"/kg", lt:"/L", unit:"/piece"};

var S = {
  view:"world", mode:"explore", cur:"usd", incModelled:false, measuredOnly:false,
  showFlagged:false, evidence:"solid", region:null, node:"01", unit:null, country:null,
  cmpMode:"abs", fxMode:"both", sortCmp:{k:"val",d:1}, sortCtry:{k:"ratio",d:1},
  multi:[], hregion:null, hsort:{k:null, d:1}, hmode:"usd",
  /* world time series: what to compare, at what category, unit, measure and window.
     gsel null means "whatever the default is here" — an explicit list only appears
     once the reader has actually chosen, so a category with thin coverage can never
     silently strike a place off the list for good. */
  gmode:"region", gsel:null, gnode:"01", gunit:0, gmeasure:"level",
  gfreq:"Q", gsmooth:0, gwin:36
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

/* The payload's leaf flag is computed over the whole COICOP code set, which is
   the definition the price level and the chained index use server-side. An older
   payload does not carry it, and every leaf-grain view then silently renders
   blank — so fall back to "no children among the nodes actually priced". */
var TAX_HAS_LEAF = DATA.nodeIdx.some(function (c) { return (DATA.tax[c] || {}).leaf; });
function isLeaf(code) {
  var t = DATA.tax[code];
  if (!t) return false;
  return TAX_HAS_LEAF ? !!t.leaf : !(KIDS.get(code) || []).length;
}
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
function median(a) {
  if (!a.length) return null;
  var x = a.slice().sort(function (p, q) { return p - q; }), h = x.length >> 1;
  return x.length % 2 ? x[h] : (x[h - 1] + x[h]) / 2;
}
/* Subtracting two strings gives NaN, and a NaN comparator leaves the order
   undefined — so text sorts as text and numbers as numbers, declared per column.
   Blanks always sink, whichever direction is active. */
function sortRows(rows, get, kind, dir) {
  return rows.slice().sort(function (a, b) {
    var av = get(a), bv = get(b);
    var an = av == null || av !== av || av === "", bn = bv == null || bv !== bv || bv === "";
    if (an || bn) return an && bn ? 0 : an ? 1 : -1;
    if (kind === "text") { av = String(av); bv = String(bv);
      return dir * (av < bv ? -1 : av > bv ? 1 : 0); }
    return dir * (bv - av);
  });
}
/* a pressed control has to say so to a screen reader too, not just look pressed */
function seg(id, on) {
  var e = document.getElementById(id);
  if (!e) return;
  e.className = on ? "on" : "";
  e.setAttribute("aria-pressed", on ? "true" : "false");
}
/* severity rank, so the Notes column sorts by how worrying a cell is */
function flagRank(c) {
  return (c.flag ? 8 : 0) + (c.mod >= 0.5 ? 4 : 0) + (c.mix ? 2 : 0) +
         (c.der > 0.5 ? 1 : 0) + (c.src === 1 ? 0.5 : 0);
}

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
  renderWorldTrends();
  var regions = {};
  DATA.ctyIdx.forEach(function (s) { var r = DATA.cty[s];
    if (r.level_ok) regions[r.region] = (regions[r.region] || 0) + 1; });
  document.getElementById("regionChips").innerHTML = Object.keys(regions).sort()
    .map(function (r) {
      return '<button class="chip' + (S.region === r ? " on" : "") + '" aria-pressed="' +
        (S.region === r) + '" onclick="APP.setRegion(' + arg(r) + ')">' + esc(r) +
        '<span class="c">' + regions[r] + "</span></button>";
    }).join("");
  document.getElementById("reg-all").className = "chip" + (S.region ? "" : " on");
  document.getElementById("reg-all").setAttribute("aria-pressed", S.region ? "false" : "true");

  renderRanking();

  /* division + unit composition */
  var divs = {}, units = {};
  C.forEach(function (c) {
    if (!keep(c)) return;
    if (isLeaf(c.node)) {
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
        backgroundColor: uk.map(function (u, i) { return PAL[i % PAL.length]; }),
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
        backgroundColor:PAL[0], borderWidth:0, borderRadius:3 }] },
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
      var lab = v === 100 ? "100 = world median"
        : Math.abs(v - 100) < (hi - lo) * 0.09 ? "" : v;
      return '<span class="' + (v === 100 ? "mid" : "") + '" style="left:' + pos(v) + '%">' +
        lab + '</span><i style="left:' + pos(v) + '%"></i>';
    }).join("") + "</div>";
  document.getElementById("rankDatum").innerHTML =
    '<div style="position:absolute;left:236px;right:70px;top:0;bottom:0">' +
    '<i style="left:' + pos(100) + '%"></i></div>';

  document.getElementById("rankList").innerHTML = rows.map(function (r, i) {
    var a = Math.min(r.level, 100), b = Math.max(r.level, 100);
    var up = r.level >= 100;
    return '<div class="rrow' +
      '" tabindex="0" role="button" data-act="1" onclick="APP.openCountry(' +
      arg(r.slug) + ')" title="' + esc(r.name) + ": " + r.level.toFixed(1) +
      " (world = 100) · " + r.level_n + " matched items · " + r.src + " sources · " +
      r.obs.toLocaleString() + ' observations">' +
      '<div class="n">' + (i + 1) + '</div><div class="nm">' + esc(r.name) + "</div>" +
      '<div class="tr">' +
      '<div class="f" style="left:' + pos(a) + "%;width:" + (pos(b) - pos(a)) + "%;background:" +
      (up ? DEAR : CHEAP) + '"></div></div>' +
      '<div class="v" style="color:' + (up ? DEAR : CHEAP) + '">' +
      r.level.toFixed(0) + "</div></div>";
  }).join("");

  /* Every bar is drawn at full strength. The item count behind each one is
     still in its hover title, which is where a reader who wants it looks. */
  document.getElementById("rankLegend").innerHTML =
    '<span><i class="sw" style="background:' + DEAR + '"></i>above the world median</span>' +
    '<span><i class="sw" style="background:' + CHEAP + '"></i>below it</span>';
}
/* ---------------------------------------------------------------------
   World time series — one category compared across regions, subregions
   or countries. The level is the period effect of a two-way fixed-effects
   fit (see aggregate side), so the line moves with prices rather than
   with whichever items the scrape happened to catch that period.
   --------------------------------------------------------------------- */
var GEOS_BY_KIND = {};
Object.keys(DATA.geos).forEach(function (g) {
  var k = DATA.geos[g].kind;
  (GEOS_BY_KIND[k] = GEOS_BY_KIND[k] || []).push(g);
});
/* Six validated slots for a list that can hold 190 places, so a slot is *held*
   rather than derived: a place keeps the colour it was given until it leaves the
   chart, and dropping one never repaints the others. Modulo on a global index
   would have handed two selected countries the same hue. */
var SLOT = {};
function assignSlots(drawn) {
  Object.keys(SLOT).forEach(function (g) {
    if (drawn.indexOf(g) < 0) delete SLOT[g]; });
  var used = {};
  Object.keys(SLOT).forEach(function (g) { used[SLOT[g]] = 1; });
  drawn.forEach(function (g) {
    if (g === "W" || SLOT[g] != null) return;
    for (var i = 0; i < PAL.length; i++) if (!used[i]) { SLOT[g] = i; used[i] = 1; return; }
  });
}
function geoColor(g) { return g === "W" ? INK : (SLOT[g] == null ? FAINT : PAL[SLOT[g]]); }
var GEO_INDEX = {}, LAST_P = {};
Object.keys(DATA.gseries).forEach(function (key) {
  var a = key.split("|"), g = DATA.geos[a[1]], s = DATA.gseries[key];
  if (!g) return;
  var f = GEO_INDEX[a[0]] = GEO_INDEX[a[0]] || {};
  var k = f[g.kind] = f[g.kind] || {};
  (k[a[2]] = k[a[2]] || {})[a[3]] = 1;
  var last = s.p[s.p.length - 1];
  if (!LAST_P[a[0]] || last > LAST_P[a[0]]) LAST_P[a[0]] = last;
});
var DRAWN = [];
function gser(gk, ni, ui) {
  return DATA.gseries[S.gfreq + "|" + gk + "|" + ni + "|" + ui] || null;
}

/* period arithmetic, quarters and months alike */
function pnum(p) {
  var a = p.indexOf("Q") > 0 ? p.split("Q") : p.split("-");
  return p.indexOf("Q") > 0 ? +a[0] * 4 + (+a[1] - 1) : +a[0] * 12 + (+a[1] - 1);
}
function pstr(n, f) {
  if (f === "Q") return Math.floor(n / 4) + "Q" + (n % 4 + 1);
  var y = Math.floor(n / 12), m = n % 12 + 1;
  return y + "-" + (m < 10 ? "0" : "") + m;
}
function pgrid(lo, hi, f) {
  var a = pnum(lo), b = pnum(hi), out = [];
  for (var i = a; i <= b && out.length < 500; i++) out.push(pstr(i, f));
  return out;
}
function winFrom() {
  var f = S.gfreq, last = LAST_P[f];
  if (!S.gwin || !last) return "0";
  var back = f === "Q" ? Math.ceil(S.gwin / 3) : S.gwin;
  return pstr(pnum(last) - (back - 1), f);
}
/* trailing geometric mean — prices compound, so smooth in logs */
function smooth(pts, w) {
  if (!w || w < 2) return pts;
  return pts.map(function (v, i) {
    /* a smoothed point only where a real one stands — otherwise the average
       carries a stale value across a gap and the dashed break disappears */
    if (v == null) return null;
    var acc = 0, n = 0;
    for (var j = Math.max(0, i - w + 1); j <= i; j++) {
      if (pts[j] != null) { acc += Math.log(pts[j]); n++; }
    }
    return Math.exp(acc / n);
  });
}

/* The headline reading was removed from the markup; the chart below carries
   the same story with its own axis. Kept as a no-op so the several call sites
   that still hand it a number do not each need a guard. */
function readout() {}
function renderWorldTrends() {
  var f = S.gfreq, kind = S.gmode;
  if (!GEO_INDEX[f]) { S.gfreq = f = "M"; }
  var byNode = (GEO_INDEX[f] || {})[kind] || {};
  var nodes = Object.keys(byNode).map(function (n) { return DATA.nodeIdx[+n]; })
    .filter(Boolean).sort();
  var word = f === "Q" ? "quarter" : "month";
  document.getElementById("ws-2").textContent = "2 " + word + "s";
  document.getElementById("ws-3").textContent = "3 " + word + "s";
  ["Q","M"].forEach(function (x) {
    document.getElementById("wf-" + x).className = f === x ? "on" : ""; });
  [0,2,3].forEach(function (x) {
    document.getElementById("ws-" + x).className = S.gsmooth === x ? "on" : ""; });
  ["level","index"].forEach(function (m) {
    document.getElementById("wv-" + m).className = S.gmeasure === m ? "on" : ""; });
  [36,60,0].forEach(function (w) {
    document.getElementById("ww-" + w).className = S.gwin === w ? "on" : ""; });
  ["region","subregion","country"].forEach(function (m) {
    document.getElementById("wm-" + m).className = kind === m ? "on" : ""; });

  var chartId = "cWorldTrend";
  function nothing(msg) {
    document.getElementById("wtChips").innerHTML = "";
    readout(null, "", "", "");
    document.getElementById("wtWarn").innerHTML = '<div class="warnbox">' + msg + "</div>";
    chart(chartId, {type:"line", data:{labels:[], datasets:[]}});
    document.getElementById("wtNote").innerHTML = "";
  }
  if (!nodes.length) return nothing("Nothing repeats often enough at this level to draw a line.");
  if (nodes.indexOf(S.gnode) < 0) S.gnode = nodes.indexOf("01") >= 0 ? "01" : nodes[0];
  var ni = DATA.nodeIdx.indexOf(S.gnode);

  var sel = document.getElementById("wtNode");
  sel.innerHTML = nodes.map(function (c) {
    var lvl = (DATA.tax[c] || {}).lvl || 1;
    return '<option value="' + c + '">' + new Array(lvl).join("   ") +
      esc(title(c)) + " · " + c + "</option>"; }).join("");
  sel.value = S.gnode;

  var units = Object.keys(byNode[ni] || {}).map(Number).sort();
  if (units.indexOf(S.gunit) < 0) S.gunit = units[0];
  var ui = S.gunit, unitCode = DATA.unitIdx[ui];
  document.getElementById("wtUnits").innerHTML = units.map(function (u) {
    return '<button class="chip' + (u === ui ? " on" : "") + '" onclick="APP.setGUnit(' + u +
      ')">' + UNIT_LABEL[DATA.unitIdx[u]] + "</button>"; }).join("");

  /* candidate geographies — World is always offered as the yardstick */
  var from = winFrom(), cands = [];
  ["W"].concat(GEOS_BY_KIND[kind] || []).forEach(function (g) {
    var s = gser(g, ni, ui);
    if (!s) return;
    var n = 0;
    s.p.forEach(function (p, i) {
      if (p >= from && (S.gmeasure === "index" ? s.idx[i] : s.lvl[i]) != null) n++; });
    if (n) cands.push({g:g, t:DATA.geos[g].t, n:n, s:s});
  });
  if (!cands.length) return nothing(
    "No " + (S.gmeasure === "index" ? "matched-item chain" : "series") +
    " here in this window. Try a broader category, a wider window" +
    (f === "Q" ? ", monthly periods" : "") + ", or the other measure.");
  cands.sort(function (a, b) { return b.n - a.n || (a.t < b.t ? -1 : 1); });

  var avail = {};
  cands.forEach(function (c) { avail[c.g] = c; });

  /* What the reader picked and what can be drawn today are different things.
     Holding them apart means a thin category *parks* a place instead of striking
     it off, so it comes back the moment the category or window can carry it. */
  function defaults() {
    var d = cands.filter(function (c) { return c.g !== "W"; })
      .slice(0, PAL.length).map(function (c) { return c.g; })
      .sort(function (a, b) { return DATA.geos[a].t < DATA.geos[b].t ? -1 : 1; });
    if (avail.W) d.unshift("W");
    return d;
  }
  var drawn = S.gsel ? S.gsel.filter(function (g) { return avail[g]; }) : defaults();
  if (!drawn.length) drawn = defaults();
  var parked = S.gsel ? S.gsel.filter(function (g) { return !avail[g]; }) : [];
  assignSlots(drawn);
  DRAWN = drawn;

  var atCap = drawn.filter(function (g) { return g !== "W"; }).length >= PAL.length;
  document.getElementById("wtChips").innerHTML =
    (kind === "country" ? cands.slice(0, 18) : cands).map(function (c) {
      var on = drawn.indexOf(c.g) >= 0, full = !on && c.g !== "W" && atCap;
      return '<button class="chip ser' + (on ? " on" : "") + '" aria-pressed="' + on + '"' +
        (full ? ' disabled title="Six lines is the limit — switch one off first"' : "") +
        ' style="border-left-color:' + (on ? geoColor(c.g) : "var(--rule)") +
        '" onclick="APP.toggleGeo(' + arg(c.g) + ')">' + esc(c.t) +
        '<span class="c">' + c.n + "</span></button>"; }).join("") +
    parked.map(function (g) {
      return '<button class="chip ser" style="opacity:.32" title="Still selected, but ' +
        esc(title(S.gnode)) + ' has no series here — it returns when you change category" ' +
        'onclick="APP.toggleGeo(' + arg(g) + ')">' +
        esc((DATA.geos[g] || {}).t || g) + "</button>"; }).join("");
  /* the add-a-place picker was one of the analyst controls and is gone */

  var isLevel = S.gmeasure === "level";
  var lo = null, hi = null;
  drawn.forEach(function (g) {
    avail[g].s.p.forEach(function (p, i) {
      if (p < from || (isLevel ? avail[g].s.lvl[i] : avail[g].s.idx[i]) == null) return;
      if (lo == null || p < lo) lo = p;
      if (hi == null || p > hi) hi = p; }); });
  if (lo == null) return nothing("Nothing to draw for the places selected.");
  var grid = pgrid(lo, hi, f);

  /* the index rebases every line at the first period they can all share */
  var baseP = null;
  if (!isLevel) {
    drawn.forEach(function (g) {
      var s = avail[g].s, first = null;
      s.p.forEach(function (p, i) {
        if (first == null && p >= from && s.idx[i] != null) first = p; });
      if (first && (baseP == null || first > baseP)) baseP = first; });
  }

  var ds = [], thin = [], sup = {};
  drawn.forEach(function (g, k) {
    var c = avail[g], s = c.s, vals = {}, base = null;
    /* rebase on the shared period, then plot the whole window either side of
       it — clipping to the base would throw away history a line really has */
    s.p.forEach(function (p, i) {
      if (base == null && p >= from && s.idx[i] != null &&
          (baseP == null || p >= baseP)) base = s.idx[i]; });
    s.p.forEach(function (p, i) {
      if (p < from) return;
      if (isLevel) { if (s.lvl[i] != null) vals[p] = s.lvl[i]; return; }
      if (s.idx[i] != null && base) vals[p] = s.idx[i] / base * 100;
    });
    var pts = smooth(grid.map(function (p) {
      return vals[p] == null ? null : vals[p]; }), S.gsmooth);
    if (pts.filter(function (v) { return v != null; }).length < 2) thin.push(c.t);
    sup[g] = {t:c.t, s:s};
    ds.push({ label:c.t, data:pts,
      borderColor: geoColor(g),
      borderWidth: g === "W" ? 2.8 : 2.2,
      borderDash: g === "W" ? [6,3] : undefined,
      tension:.2, pointRadius:2.8, spanGaps:true, segment:GAP_SEG });
  });

  /* Only caveats that change how you read what is on screen right now. How the
     measure is built belongs in the note behind the heading, not in a standing
     wall of text above the chart. */
  var warn = [];
  if (!isLevel) warn.push("Only items priced in <b>two consecutive " + word + "s</b> in the " +
    "same country are linked — the strictest reading, and the thinnest.");
  if (S.gsmooth) warn.push("Showing a <b>" + S.gsmooth + "-" + word +
    " trailing average</b>: turning points lag by about half that.");
  if (thin.length) warn.push("Too few " + word + "s to draw: <b>" +
    thin.slice(0, 6).map(esc).join(", ") +
    (thin.length > 6 ? " and " + (thin.length - 6) + " more" : "") + "</b>.");
  warn.push("<b>" + (DATA.qa.history.share_last_12m * 100).toFixed(0) +
    "%</b> of trusted observations fall in the last 12 months, so earlier periods are " +
    "thinner than they look.");
  document.getElementById("wtWarn").innerHTML = '<div class="warnbox">' + warn.join("<br>") + "</div>";

  chart(chartId, {
    type:"line", data:{labels:grid, datasets:ds},
    options:{ interaction:{mode:"index", intersect:false},
      plugins:{ legend:{display:false},
        tooltip:{ callbacks:{
          label:function (it) {
            var v = it.parsed.y;
            return v == null ? null : it.dataset.label + ": " +
              (isLevel ? "$" + v.toFixed(2) + UNIT_OF[unitCode] : v.toFixed(1)); },
          afterBody:function (items) {
            var p = grid[items[0].dataIndex], out = [""];
            drawn.forEach(function (g) {
              var s = sup[g].s, i = s.p.indexOf(p);
              if (i < 0 || !s.k[i]) return;
              out.push(sup[g].t + ": " + s.c[i] + (s.c[i] === 1 ? " country · " : " countries · ") +
                s.k[i] + " item cells"); });
            return out.length > 1 ? out : []; } } } },
      scales:{ y:{ grid:{color:RULE},
          title:{display:true, text: isLevel ? "US$ per " + UNIT_SHORT[unitCode]
            : "Index, " + (baseP || lo) + " = 100"} },
        x:{ grid:{display:false}, ticks:{maxRotation:0, autoSkip:true, maxTicksLimit:14} } } }
  });

  /* read the lead line off what is actually drawn, not off the raw series —
     the window and the smoothing both change what the number should say */
  var lp = ds.length ? ds[0].data : [], first = null, last = null, lastP = null;
  lp.forEach(function (v, i) {
    if (v == null) return;
    if (first == null) first = v;
    last = v; lastP = grid[i];
  });
  if (last == null) readout(null, "", "", "");
  else {
    var leadT = ds[0].label;
    readout(isLevel ? "$" + last.toFixed(2) : last.toFixed(1),
      isLevel ? " US$ per " + UNIT_SHORT[unitCode] : " index",
      (isLevel ? "Average across the items priced per " + UNIT_SHORT[unitCode] + " in "
               : "Matched-item index for ") +
      esc(title(S.gnode)) + " &middot; " + esc(leadT) + " &middot; " + lastP,
      first && first !== last
        ? (function () {
            var d = (last / first - 1) * 100;
            return '<span class="' + (d >= 0 ? "up" : "dn") + '">' +
              (d >= 0 ? "\u25b2 " : "\u25bc ") + Math.abs(d).toFixed(1) + "%</span> since " +
              grid.find(function (p, i) { return lp[i] != null; }); })()
        : "");
  }

  var lead = avail[drawn[0]], li = lead ? lead.s.p.length - 1 : -1;
  document.getElementById("wtNote").innerHTML =
    "Always in US$ here — the local-currency and exchange-rate split lives in " +
    '<span class="linkish" onclick="APP.go(\'trends\')">Currency effects</span>. ' +
    (li >= 0 ? "Latest support: " + esc(lead.t) + " · " + lead.s.c[li] +
      (lead.s.c[li] === 1 ? " country · " : " countries · ") + fmtN(lead.s.k[li]) +
      " item cells in " + lead.s.p[li] + ". " : "") +
    "Dashed segments bridge periods with no data at all.";
}

function kpi(l, v, n) {
  return '<div class="kpi"><div class="l">' + l + '</div><div class="v">' + v +
         '</div><div class="n">' + n + "</div></div>";
}

/* =====================================================================
   shared: hierarchy navigator
   ===================================================================== */
function navigator(crumbId, listId, node, onPick, countFn) {
  /* COICOP has no node above a division, so the top of this tree is genuinely a
     choice between two — 01 food and drink, 02 alcohol and tobacco. One "all"
     crumb had to resolve to one of them, which is how division 02 became
     unreachable from here. */
  var path = ancestors(node);
  var sw = ROOTS.map(function (r) {
    return '<button class="chip' + (r === path[0] ? " on" : "") + '" onclick="APP.pick(' +
      arg(r) + ')">' + esc(proseTitle(r)) + "</button>"; }).join(" ");
  var crumb = path.slice(1).map(function (a, i, arr) {
    var last = i === arr.length - 1;
    return last ? '<span class="cur">' + esc(title(a)) + "</span>"
      : '<a onclick="APP.pick(' + arg(a) + ')">' + esc(title(a)) + "</a>";
  }).join(' <span class="sep">›</span> ');
  document.getElementById(crumbId).innerHTML =
    sw + (crumb ? ' <span class="sep">›</span> ' + crumb : "");

  var kids = KIDS.get(node) || [];
  var list = (kids.length ? kids : ancestors(node).length > 1
      ? (KIDS.get(DATA.tax[node].p) || []) : ROOTS);
  var isSiblings = !kids.length;
  var html = list.map(function (code) {
    var c = countFn(code);
    var leaf = isLeaf(code);
    var dom = (DATA.nodeMeta[code] || {}).dom;
    return '<div class="it' + (code === node ? " on" : "") +
      '" tabindex="0" role="button" data-act="1" onclick="APP.pick(' + arg(code) + ')">' +
      "<div><div>" + esc(title(code)) +
      (leaf ? ' <span class="leafmark">leaf</span>' : "") + "</div>" +
      '<div class="code">' + code + (dom ? " · " + UNIT_LABEL[dom] : "") + "</div></div>" +
      '<div class="m">' + c + "</div></div>";
  }).join("");
  var hint = isSiblings
    ? '<div class="it" style="cursor:default;color:var(--faint);font-size:11.5px">' +
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
    /* one country can hold a cell in kg AND litre AND piece, so summing cells
       across units counted several hundred more "countries" than exist */
    var seen = {};
    DATA.unitIdx.forEach(function (u, ui) {
      cellsFor(i, ui).forEach(function (c) { seen[c.ci] = 1; }); });
    var n = Object.keys(seen).length;
    return n ? n + " countr" + (n === 1 ? "y" : "ies") : "—";
  });

  var us = unitsAt(ni);
  var ui = resolveUnit(ni);
  document.getElementById("cmpUnits").innerHTML = us.length ? us.map(function (x) {
    return '<button class="chip' + (x.ui === ui ? " on" : "") + '" onclick="APP.setUnit(' +
      arg(x.u) + ')">' + UNIT_LABEL[x.u] + '<span class="c">' + x.n + "</span></button>";
  }).join("") : '<span class="tiny">no comparable unit at this node</span>';

  seg("cmp-abs", S.cmpMode === "abs");
  seg("cmp-rel", S.cmpMode === "rel");

  if (ui == null) {
    document.getElementById("cmpTitle").textContent = title(S.node);
    document.getElementById("cmpSub").textContent = "No comparable unit values at this node.";
    chart("cCompare", {type:"bar", data:{labels:[], datasets:[]}});
    document.getElementById("cmpTbl").innerHTML = "";
    return;
  }
  var unit = DATA.unitIdx[ui];
  var gmed = ((DATA.nodeMeta[S.node] || {}).gmed || {})[unit];

  var rows = cellsFor(ni, ui).map(function (c) {
    var meta = DATA.cty[c.country] || {};
    var v = val(c);
    var rel = (gmed && meta.level) ? (c.usd / gmed) / (meta.level / 100) : null;
    return { c:c, name:meta.name || c.country, region:meta.region,
             val:v, usd:c.usd, rel:rel, ratio: gmed ? c.usd / gmed : null };
  });
  var q = (document.getElementById("cmpSearch").value || "").toLowerCase();
  var shown = q ? rows.filter(function (r) { return r.name.toLowerCase().indexOf(q) >= 0; }) : rows;

  /* Two hundred currencies cannot be ranked against each other, so the
     cross-country bars stay in US$ whatever the currency switch says. The local
     figures are still there in the table, where no ordering claims they compare. */
  var metric = S.cmpMode === "rel" ? "rel" : "usd";
  var plot = shown.filter(function (r) { return r[metric] != null; })
                  .sort(function (a, b) { return b[metric] - a[metric]; });
  document.getElementById("cmpWarn").innerHTML = S.cur === "local"
    ? '<div class="warnbox">Prices in <b>local currency</b> cannot be ranked against each ' +
      "other, so these bars stay in <b>US$</b>. The local figures are in the table below.</div>"
    : "";

  document.getElementById("cmpTitle").innerHTML = esc(title(S.node)) +
    ' <span class="ub big">' + UNIT_LABEL[unit] + "</span>";
  document.getElementById("cmpSub").innerHTML =
    (S.cmpMode === "rel"
      ? "Relative price — 1.00 means this item costs exactly what the country's overall basket would predict."
      : "Median US$ price for one " + UNIT_SHORT[unit] +
        (gmed ? ". World median: <b>$" + gmed.toFixed(2) + "</b>" + UNIT_OF[unit] : "")) +
    " · " + plot.length + " countries";

  sizeCanvas("cCompare", Math.max(200, plot.length * 17 + 50));
  chart("cCompare", {
    type:"bar",
    data:{ labels: plot.map(function (r) { return r.name; }),
      datasets:[{ data: plot.map(function (r) { return r[metric]; }),
        backgroundColor: plot.map(function (r) {
          if (r.c.flag) return DEAR;
          if (r.c.mod >= 0.5) return PAL[5];
          if (S.cmpMode === "rel") return r.rel >= 1 ? DEAR : CHEAP;
          return r.c.src === 1 ? PAL[0] + "66" : PAL[0]; }),
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
      scales:{ x:{ beginAtZero:true, position:"top", grid:{color:RULE},
          title:{display:true, text: S.cmpMode === "rel" ? "Price relative to the country's own basket (1.00 = as expected)"
            : "US$ " + UNIT_LABEL[unit]} },
        y:{ ticks:{font:{size:11}, autoSkip:false}, grid:{display:false} } } }
  });

  /* four different things were being said with colour and none of them was labelled */
  var seen = {};
  plot.forEach(function (r) {
    if (r.c.flag) seen.flag = 1;
    else if (r.c.mod >= 0.5) seen.mod = 1;
    else if (S.cmpMode === "rel") seen[r.rel >= 1 ? "dear" : "cheap"] = 1;
    else seen[r.c.src === 1 ? "one" : "many"] = 1; });
  function sw(col, txt) { return '<span><i class="sw" style="background:' + col + '"></i>' + txt + "</span>"; }
  var leg = [];
  if (seen.many) leg.push(sw(PAL[0], "two or more sources"));
  if (seen.one) leg.push(sw(PAL[0] + "66", "a single source"));
  if (seen.dear) leg.push(sw(DEAR, "dear for this country's basket"));
  if (seen.cheap) leg.push(sw(CHEAP, "cheap for it"));
  if (seen.mod) leg.push(sw(PAL[5], "modelled, not an observed shelf price"));
  if (seen.flag) leg.push(sw(DEAR, "outside plausible bounds"));
  document.getElementById("cmpLegend").innerHTML = leg.join("");

  /* table — each column declares its own type so the comparator never subtracts text */
  var CMP_COLS = {
    name:  {label:"Country",  cls:"",    kind:"text", get:function (r) { return r.name; }},
    val:   {label:"Price",    cls:"num", kind:"num",  get:function (r) { return r.val; }},
    ratio: {label:"vs world", cls:"num", kind:"num",  get:function (r) { return r.ratio; }},
    rel:   {label:"Relative", cls:"num", kind:"num",  get:function (r) { return r.rel; }},
    obs:   {label:"Obs",      cls:"num", kind:"num",  get:function (r) { return r.c.obs; }},
    src:   {label:"Src",      cls:"num", kind:"num",  get:function (r) { return r.c.src; }},
    mad:   {label:"Log MAD",  cls:"num", kind:"num",  get:function (r) { return r.c.mad; }},
    per:   {label:"Period",   cls:"",    kind:"text", get:function (r) { return r.c.per; }},
    flags: {label:"Notes",    cls:"",    kind:"num",  get:function (r) { return flagRank(r.c); }}
  };
  var order = ["name","val","ratio","rel","obs","src","mad","per","flags"];
  var sk = CMP_COLS[S.sortCmp.k] ? S.sortCmp.k : "val", sd = S.sortCmp.d;
  var tRows = sortRows(shown, CMP_COLS[sk].get, CMP_COLS[sk].kind, sd);
  document.getElementById("cmpTbl").innerHTML =
    "<thead><tr>" + order.map(function (k) { var c = CMP_COLS[k];
      return '<th class="' + c.cls + '" aria-sort="' + (sk === k ? (sd === 1 ? "descending" : "ascending") : "none") +
        '" onclick="APP.sort(\'cmp\',\'' + k + '\')">' + c.label +
        (sk === k ? (sd === 1 ? " ▼" : " ▲") : "") + "</th>"; }).join("") + "</tr></thead><tbody>" +
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
  setHtmlIfPresent("cmpSamples", sam.length
    ? "<div style='margin-top:6px'><b>What is actually in these cells</b><br>" + sam.join("<br>") + "</div>" : "");
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
    kpi("Observations", fmtN(m.obs), m.leaves + " categories priced"),
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
      return isLeaf(c.node) && (c.node === code || c.node.indexOf(pre) === 0); }).length;
    return n ? n + " item" + (n > 1 ? "s" : "") : "—";
  });

  /* all leaf cells for this country under the selected node */
  var prefix = S.node + ".";
  var mine = mineAll.filter(function (c) {
    return (c.node === S.node || c.node.indexOf(prefix) === 0) && isLeaf(c.node);
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
        backgroundColor: show.map(function (r) { return r.ratio >= 1 ? DEAR : CHEAP; }),
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
      scales:{ x:{ grid:{color:RULE}, position:"top",
          title:{display:true, text:"% above or below the world median for the same item and unit"} },
        y:{ ticks:{font:{size:11}, autoSkip:false}, grid:{display:false} } } }
  });

  var q = (document.getElementById("ctrySearch").value || "").toLowerCase();
  var tRows = (q ? mine.filter(function (r) { return r.name.toLowerCase().indexOf(q) >= 0; }) : mine);
  var CT_COLS = {
    name:  {label:"Item",     cls:"",    kind:"text", get:function (r) { return r.name; }},
    unit:  {label:"Unit",     cls:"",    kind:"text", get:function (r) { return UNIT_LABEL[r.c.unit]; }},
    val:   {label:"Price",    cls:"num", kind:"num",  get:function (r) { return r.val; }},
    ratio: {label:"vs world", cls:"num", kind:"num",  get:function (r) { return r.ratio; }},
    obs:   {label:"Obs",      cls:"num", kind:"num",  get:function (r) { return r.c.obs; }},
    src:   {label:"Src",      cls:"num", kind:"num",  get:function (r) { return r.c.src; }},
    mad:   {label:"Log MAD",  cls:"num", kind:"num",  get:function (r) { return r.c.mad; }},
    per:   {label:"Period",   cls:"",    kind:"text", get:function (r) { return r.c.per; }},
    flags: {label:"Notes",    cls:"",    kind:"num",  get:function (r) { return flagRank(r.c); }}
  };
  var cOrder = ["name","unit","val","ratio","obs","src","mad","per","flags"];
  var sk = CT_COLS[S.sortCtry.k] ? S.sortCtry.k : "ratio", sd = S.sortCtry.d;
  tRows = sortRows(tRows, CT_COLS[sk].get, CT_COLS[sk].kind, sd);
  document.getElementById("ctryTbl").innerHTML =
    "<thead><tr>" + cOrder.map(function (k) { var c = CT_COLS[k];
      return '<th class="' + c.cls + '" aria-sort="' + (sk === k ? (sd === 1 ? "descending" : "ascending") : "none") +
        '" onclick="APP.sort(\'ctry\',\'' + k + '\')">' + c.label +
        (sk === k ? (sd === 1 ? " ▼" : " ▲") : "") + "</th>"; }).join("") + "</tr></thead><tbody>" +
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
  var code = DATA.nodeIdx[ni], terminal = isLeaf(code);
  if (terminal) {
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
  seg("tr-both", S.fxMode === "both");
  seg("tr-nofx", S.fxMode === "nofx");

  var s = ui == null ? null : trendSeries(ci, ni, ui);
  if (!s) {
    document.getElementById("trWarn").innerHTML =
      '<div class="warnbox">No repeated monthly observations for this combination. ' +
      'A price series needs at least ' + 3 + ' months each with ' + DATA.meta.min_cell_obs +
      '+ observations.</div>';
    chart("cTrend", {type:"line", data:{labels:[], datasets:[]}});
    document.getElementById("trDeco").innerHTML = "";
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
  ds.push({label: (isIdx ? "Items" : "Observations") + " behind each point", type:"bar", yAxisID:"y2",
           data:onGrid(grid, s.p, s.n), backgroundColor:"#b9b5aa55", borderWidth:0, order:99});

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
          /* dataIndex points into the dense month grid, but every series array is
             sparse — most months have no observation at all. Map the label back to
             the series before reading anything off it. */
          var k = s.p.indexOf(grid[items[0].dataIndex]);
          if (k < 0) return ["", "no observation this month — the line is bridging a gap"];
          return isIdx
            ? ["", s.n[k] + " items linked this month"]
            : ["", "US$ " + (s.usd[k] != null ? s.usd[k].toFixed(2) : "—") +
                 UNIT_OF[DATA.unitIdx[ui]],
               "local " + (s.loc[k] != null ? s.loc[k].toFixed(2) : "—"),
               s.n[k] + " observations"]; } } } },
      scales:{ y:{ title:{display:true, text:"Index, first period with data = 100"}, grid:{color:RULE} },
        y2:{ display:false, beginAtZero:true,
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

}
function box(l, v, sign) {
  return '<div class="b ' + (sign == null ? "" : sign >= 0 ? "pos" : "neg") + '"><div class="l">' +
    l + '</div><div class="v">' + v + "</div></div>";
}

/* =====================================================================
   5. PATTERNS — what carries one country's gap, and where gaps cluster
   =====================================================================
   Both views read the same quantity: ln(country price / world median) for the
   same COICOP leaf in the same unit. The waterfall takes one country's gap
   apart by category group; the heatmap lays every country's groups side by side. */
var HM_MIN_LEAVES = 3, HM_MID = "#e5e2d9", HM_FULL = Math.log(2);

function classOf(code) {
  var a = ancestors(code), c = a[2] || a[a.length - 1];
  return DATA.tax[c] ? c : null;
}
/* Column headers need a hard width; a sentence does not. Same trimming, but
   prose keeps whole words rather than an ellipsis mid-name. */
function proseTitle(code) {
  return title(code).split(",")[0].split(" and ")[0].replace(/ n\.e\.c\.$/, "");
}
function shortTitle(code) {
  var t = proseTitle(code);
  return t.length > 15 ? t.slice(0, 14) + "…" : t;
}
/* every matched leaf gap this country has, tagged with its category group */
function gapsFor(ci) {
  var out = [];
  (byCountry.get(ci) || []).filter(keep).forEach(function (c) {
    if (!isLeaf(c.node) || !(c.usd > 0)) return;
    var g = ((DATA.nodeMeta[c.node] || {}).gmed || {})[c.unit];
    if (!(g > 0)) return;
    var cls = classOf(c.node);
    if (cls) out.push({cls:cls, r:Math.log(c.usd / g)});
  });
  return out;
}
function groupGaps(gaps) {
  var by = {};
  gaps.forEach(function (g) { (by[g.cls] = by[g.cls] || []).push(g.r); });
  return by;
}
function fillCountries(id) {
  var sel = document.getElementById(id);
  if (sel.options.length !== DATA.ctyIdx.length) {
    sel.innerHTML = DATA.ctyIdx.slice().sort(function (a, b) {
      return DATA.cty[a].name < DATA.cty[b].name ? -1 : 1; })
      .map(function (s) { return '<option value="' + s + '">' + esc(DATA.cty[s].name) + "</option>"; }).join("");
  }
  sel.value = S.country;
}
function hexMix(a, b, t) {
  var o = "#", i, v;
  for (i = 0; i < 3; i++) {
    v = Math.round(parseInt(a.substr(1 + i * 2, 2), 16) +
        (parseInt(b.substr(1 + i * 2, 2), 16) - parseInt(a.substr(1 + i * 2, 2), 16)) * t);
    o += (v < 16 ? "0" : "") + v.toString(16);
  }
  return o;
}
/* diverging: one hue each side of a neutral midpoint, clipped at +/-100% so a
   single extreme cell cannot wash the rest of the table out */
function heatT(r) { return Math.pow(Math.min(1, Math.abs(r) / HM_FULL), 0.8); }
function heatColor(r) { return hexMix(HM_MID, r >= 0 ? DEAR : CHEAP, heatT(r)); }

function renderPatterns() { fillCountries("wfCtry"); renderWaterfall(); renderHeatmap(); }

function renderWaterfall() {
  var slug = S.country, m = DATA.cty[slug] || {}, ci = DATA.ctyIdx.indexOf(slug);
  var gaps = gapsFor(ci);
  document.getElementById("wfSub").innerHTML = esc(m.name || slug) +
    " &mdash; each group's share of its distance from the world median.";
  if (gaps.length < 6) {
    document.getElementById("wfWarn").innerHTML = '<div class="warnbox">' +
      esc(m.name || slug) + " has only <b>" + gaps.length + "</b> item" +
      (gaps.length === 1 ? "" : "s") + " that can be matched against the world median. " +
      "There is nothing here to decompose &mdash; loosen <b>Evidence</b> or pick another " +
      "country.</div>";
    chart("cWaterfall", {type:"bar", data:{labels:[], datasets:[]}});
    document.getElementById("wfLegend").innerHTML = "";
    document.getElementById("wfNote").innerHTML = "";
    return;
  }
  document.getElementById("wfWarn").innerHTML = "";

  var by = groupGaps(gaps), N = gaps.length;
  var all = Object.keys(by).map(function (cls) {
    var a = by[cls], mean = a.reduce(function (p, q) { return p + q; }, 0) / a.length;
    return {cls:cls, n:a.length, mean:mean, contrib:(a.length / N) * mean};
  });
  var total = all.reduce(function (p, g) { return p + g.contrib; }, 0);

  /* Twenty labelled bars is a list, not an explanation. Keep the ten that move
     the total most and fold the tail into one bar, so nothing is dropped from
     the arithmetic and the reader still gets a story. */
  var WF_MAX = 10;
  var groups = all.slice().sort(function (a, b) {
    return Math.abs(b.contrib) - Math.abs(a.contrib); });
  var tail = groups.slice(WF_MAX);
  groups = groups.slice(0, WF_MAX);
  if (tail.length > 1) groups.push({
    cls:null, rest:tail.length,
    n:tail.reduce(function (p, g) { return p + g.n; }, 0),
    contrib:tail.reduce(function (p, g) { return p + g.contrib; }, 0) });
  else groups = groups.concat(tail);
  groups.sort(function (a, b) { return b.contrib - a.contrib; });
  var med = median(gaps.map(function (g) { return g.r; }));

  var labels = [], data = [], colors = [], meta = [], run = 0;
  groups.forEach(function (g) {
    labels.push(g.cls ? shortTitle(g.cls) : g.rest + " smaller groups");
    data.push([run * 100, (run + g.contrib) * 100]);
    colors.push(g.contrib >= 0 ? DEAR : CHEAP);
    meta.push(g);
    run += g.contrib;
  });
  labels.push("Overall gap");
  data.push([0, total * 100]);
  colors.push(INK);
  meta.push(null);

  chart("cWaterfall", {
    type:"bar",
    data:{ labels:labels, datasets:[{ data:data, backgroundColor:colors,
      borderWidth:0, borderRadius:2, borderSkipped:false }] },
    options:{ plugins:{ legend:{display:false}, tooltip:{ callbacks:{
      title:function (it) { var g = meta[it[0].dataIndex];
        return !g ? "Everything together"
          : g.cls ? title(g.cls)
          : "The " + g.rest + " remaining groups, combined"; },
      label:function (it) {
        var g = meta[it.dataIndex];
        if (!g) return ["Mean gap vs the world: " + (total * 100).toFixed(1) + " log %",
                        "That is a price level of " + (Math.exp(total) * 100).toFixed(0) +
                        " on a world median of 100"];
        var out = ["Contributes " + (g.contrib >= 0 ? "+" : "") +
          (g.contrib * 100).toFixed(1) + " log % of the gap"];
        if (g.cls) out.push("This group alone runs " + (g.mean >= 0 ? "+" : "") +
          ((Math.exp(g.mean) - 1) * 100).toFixed(0) + "% vs the world");
        out.push(g.n + " matched item" + (g.n === 1 ? "" : "s") + " of " + N +
          " (" + (g.n / N * 100).toFixed(0) + "% of the weight)");
        return out; } } } },
      scales:{ y:{ grid:{color:RULE},
          title:{display:true, text:"Contribution to the gap (log %, these add up)"} },
        x:{ grid:{display:false}, ticks:{maxRotation:52, minRotation:35, font:{size:10.5}} } } }
  });

  document.getElementById("wfLegend").innerHTML =
    '<span><i class="sw" style="background:' + DEAR + '"></i>pushes prices above the world</span>' +
    '<span><i class="sw" style="background:' + CHEAP + '"></i>pulls them below</span>' +
    '<span><i class="sw" style="background:' + INK + '"></i>the two together</span>';

  function nm(g) { return "<b>" + esc(g.cls ? proseTitle(g.cls).toLowerCase()
    : g.rest + " smaller groups") + "</b>"; }
  var up = groups.filter(function (g) { return g.contrib > 0; }).slice(0, 3);
  var dn = groups.filter(function (g) { return g.contrib < 0; }).slice(-3).reverse();
  document.getElementById("wfNote").innerHTML =
    "<b>" + esc(m.name || slug) + "</b> sits <b>" +
    (Math.exp(total) * 100).toFixed(0) + "</b> against a world median of 100 on this " +
    "decomposition" +
    (up.length ? ", carried mostly by " + up.map(nm).join(", ") : "") +
    (dn.length ? ", and held down by " + dn.map(nm).join(", ") : "") + ". " +
    "Built on " + N + " matched items across " + all.length + " category groups. " +
    "The headline price level on the World tab is <b>" +
    (m.level_ok ? m.level.toFixed(0) : (Math.exp(med) * 100).toFixed(0)) +
    "</b>: it uses the <i>median</i> gap, which resists outliers but cannot be split into parts, " +
    "so the two numbers differ when a country's gaps are lopsided.";
}

/* Category down the side, country across the top -- the same orientation as
   the dashboard's heat table, so the two can be read side by side.

   Two readings of the same cell. USD is the plain unit value a shopper would
   recognise and is what the dashboard shows, so it leads. Index is the gap
   from the world median for the same items, which is the only one of the two
   that is comparable ACROSS rows: a kilo of tea and a kilo of rice are not
   the same kind of number, but "38% dearer than the world" and "12% dearer"
   are. Each row carries one unit, chosen as the unit most of that group's
   prices are quoted in, so a column never mixes kilos with litres. */
function classCellsFor(ci) {
  var out = {};
  (byCountry.get(ci) || []).filter(keep).forEach(function (c) {
    if (!isLeaf(c.node) || !(c.usd > 0)) return;
    var cls = classOf(c.node);
    if (!cls) return;
    var g = ((DATA.nodeMeta[c.node] || {}).gmed || {})[c.unit];
    (out[cls] = out[cls] || []).push({
      unit: c.unit, usd: c.usd, r: g > 0 ? Math.log(c.usd / g) : null});
  });
  return out;
}

/* Some spans only exist in one copy of the prose; writing to a missing one
   used to throw and abort the rest of boot. */
function setTextIfPresent(id, v) {
  var el = document.getElementById(id);
  if (el) el.textContent = v;
}
function setHtmlIfPresent(id, v) {
  var el = document.getElementById(id);
  if (el) el.innerHTML = v;
}

function renderHeatmap() {
  var usdMode = S.hmode !== "index";
  var rowN = {}, byCty = {}, unitVotes = {};

  DATA.ctyIdx.forEach(function (slug, ci) {
    var meta = DATA.cty[slug];
    if (!meta.level_ok) return;                 /* only countries the ranking trusts */
    var per = classCellsFor(ci);
    byCty[slug] = {slug:slug, name:meta.name, region:meta.region,
                   level:meta.level, per:per};
    Object.keys(per).forEach(function (cls) {
      per[cls].forEach(function (x) {
        unitVotes[cls] = unitVotes[cls] || {};
        unitVotes[cls][x.unit] = (unitVotes[cls][x.unit] || 0) + 1; });
    });
  });

  /* one unit per row: whichever the group's prices are mostly quoted in */
  var rowUnit = {};
  Object.keys(unitVotes).forEach(function (cls) {
    rowUnit[cls] = Object.keys(unitVotes[cls]).sort(function (p, q) {
      return unitVotes[cls][q] - unitVotes[cls][p]; })[0];
  });

  /* collapse each (country, group) to one figure, on the row's unit */
  Object.keys(byCty).forEach(function (slug) {
    var c = byCty[slug], cells = {};
    Object.keys(c.per).forEach(function (cls) {
      var u = rowUnit[cls];
      var same = c.per[cls].filter(function (x) { return x.unit === u; });
      if (same.length < HM_MIN_LEAVES) return;
      var gaps = same.map(function (x) { return x.r; })
                     .filter(function (v) { return v != null; });
      cells[cls] = {usd:median(same.map(function (x) { return x.usd; })),
                    r:gaps.length ? median(gaps) : null,
                    n:same.length};
      rowN[cls] = (rowN[cls] || 0) + 1;
    });
    c.cells = cells;
  });

  var all = Object.keys(byCty).map(function (s) { return byCty[s]; })
    .filter(function (c) { return Object.keys(c.cells).length; });

  var regions = {};
  all.forEach(function (r) { regions[r.region] = (regions[r.region] || 0) + 1; });
  document.getElementById("hmRegions").innerHTML = Object.keys(regions).sort()
    .map(function (r) {
      var on = S.hregion === r;
      return '<button class="chip' + (on ? " on" : "") + '" aria-pressed="' + on +
        '" onclick="APP.setHRegion(' + arg(r) + ')">' + esc(r) +
        '<span class="c">' + regions[r] + "</span></button>"; }).join("");
  document.getElementById("hreg-all").className = "chip" + (S.hregion ? "" : " on");
  document.getElementById("hreg-all").setAttribute("aria-pressed", S.hregion ? "false" : "true");

  var rows = Object.keys(rowN).filter(function (c) { return rowN[c] >= 15; })
    .sort(function (a2, b2) { return rowN[b2] - rowN[a2]; }).slice(0, 11).sort();
  var shown = all.filter(function (r) { return !S.hregion || r.region === S.hregion; });

  if (!rows.length || !shown.length) {
    document.getElementById("hmTbl").innerHTML =
      '<tbody><tr><td class="empty">Not enough matched items to build a grid under these ' +
      "filters.</td></tr></tbody>";
    document.getElementById("hmRamp").innerHTML = "";
    return;
  }

  /* Countries are the columns now, so the sort key picks a ROW to order them
     by; clicking a row label sorts across it. Default is the price level, the
     same order the table opened in before. */
  var sk = S.hsort.k, sd = S.hsort.d;
  shown = sk && rows.indexOf(sk) >= 0
    ? sortRows(shown, function (r) {
        var c = r.cells[sk];
        return c ? (usdMode ? c.usd : c.r) : null; }, "num", sd)
    : sortRows(shown, function (r) { return r.level; }, "num", sd);

  var head = '<thead><tr><th class="ctry">Category</th>' +
    shown.map(function (r) {
      return '<th class="ctyh" title="' + esc(r.name) + " · price level " +
        r.level.toFixed(0) + '" tabindex="0" role="button" data-act="1" onclick="APP.openCountry(' +
        arg(r.slug) + ')">' + esc(r.name) + "</th>"; }).join("") + "</tr></thead>";

  var body = "<tbody>" + rows.map(function (cls) {
    var u = rowUnit[cls];
    var vals = shown.map(function (r) { return r.cells[cls]; })
      .filter(Boolean).map(function (c) { return usdMode ? c.usd : c.r; });
    var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
    var tr = '<tr><td class="ctry" title="' + esc(title(cls)) + " · " + rowN[cls] +
      ' countries" tabindex="0" role="button" data-act="1" onclick="APP.hsort(' + arg(cls) +
      ')">' + esc(shortTitle(cls)) +
      '<span class="ru">' + esc(usdMode ? "US$/" + u : "vs world") + "</span>" +
      (sk === cls ? (sd === 1 ? " ▼" : " ▲") : "") + "</td>";
    return tr + shown.map(function (r) {
      var cell = r.cells[cls];
      if (!cell) return '<td class="na" title="' + esc(r.name) + " · " + esc(title(cls)) +
        ': fewer than ' + HM_MIN_LEAVES + ' matched items"></td>';
      var lab, bg, t;
      if (usdMode) {
        lab = cell.usd >= 100 ? cell.usd.toFixed(0) : cell.usd.toFixed(2);
        t = hi > lo ? (cell.usd - lo) / (hi - lo) : 0.5;
        bg = hexMix(HM_MID, t >= 0.5 ? DEAR : CHEAP, Math.pow(Math.abs(t - 0.5) * 2, 0.8));
      } else {
        if (cell.r == null) return '<td class="na" title="' + esc(r.name) +
          ': no world median for these items"></td>';
        var v = (Math.exp(cell.r) - 1) * 100;
        lab = Math.abs(v) >= 999 ? (v > 0 ? "+999" : "-999")
          : (v >= 0 ? "+" : "") + v.toFixed(0);
        t = heatT(cell.r);
        bg = heatColor(cell.r);
      }
      return '<td class="c" style="background:' + bg + ";color:" +
        (t > 0.55 || t < 0.05 ? "#1b211f" : "#1b211f") + '" title="' + esc(r.name) + " · " +
        esc(title(cls)) + ": " + (usdMode
          ? "US$" + cell.usd.toFixed(2) + " per " + u
          : lab + "% vs the world median") +
        ", over " + cell.n + ' matched items">' + lab + "</td>"; }).join("") + "</tr>"; }).join("") +
    "</tbody>";
  document.getElementById("hmTbl").innerHTML = head + body;

  document.getElementById("hmSub").innerHTML = usdMode
    ? "Median US dollars per unit, by category group. Each row is quoted in one unit; "
      + "colour runs cheapest to dearest <b>within</b> the row."
    : "Each category group against the world median for the same items. "
      + "Red is dearer than the world, blue cheaper.";
  document.getElementById("hm-usd").className = "chip" + (usdMode ? " on" : "");
  document.getElementById("hm-idx").className = "chip" + (usdMode ? "" : " on");

  var cut = Object.keys(rowN).filter(function (c) { return rows.indexOf(c) < 0; })
    .sort(function (a2, b2) { return rowN[b2] - rowN[a2]; });
  var stops = [-1, -0.6, -0.3, 0, 0.3, 0.6, 1];
  document.getElementById("hmRamp").innerHTML =
    '<span class="lab">' + (usdMode ? "cheapest in the row" : "cheaper than the world") + "</span>" +
    stops.map(function (t) { return '<i style="background:' +
      hexMix(HM_MID, t >= 0 ? DEAR : CHEAP, Math.pow(Math.abs(t), 0.8)) + '"></i>'; }).join("") +
    '<span class="lab">' + (usdMode ? "dearest" : "dearer") + "</span>" +
    '<span class="lab" style="margin-left:14px">' +
    (usdMode ? "" : "full colour at &plusmn;100% &middot; ") +
    'hatched: fewer than ' + HM_MIN_LEAVES + ' matched items &middot; ' + rows.length +
    " groups &times; " + shown.length + " countries" +
    (cut.length ? " &middot; " + cut.length + " groups too thinly covered to show, " +
       "widest of them " + esc(proseTitle(cut[0])) + " at " + rowN[cut[0]] + " countries" : "") +
    "</span>";
}


/* =====================================================================
   controller
   ===================================================================== */
var searchT = null;
var VIEWS = ["world","compare","country","patterns","trends"];
var APP = {
  set:function (k, v) { S[k] = v; if (k === "country") S.multi = []; this.render(); },
  /* the search box fires on every keystroke; a full re-render per character is
     wasted work on a table this wide */
  searchLater:function () { clearTimeout(searchT);
    searchT = setTimeout(function () { APP.render(); }, 180); },
  about:function (open) {
    document.getElementById("drawer").classList.toggle("open", open);
    document.getElementById("scrim").classList.toggle("open", open);
    document.getElementById("aboutBtn").setAttribute("aria-expanded", open ? "true" : "false");
    (open ? document.querySelector("#drawer .x") : document.getElementById("aboutBtn")).focus();
  },
  info:function (k) {
    var pane = document.getElementById("i-" + k), b = document.getElementById("b-" + k);
    var open = !pane.classList.contains("open");
    pane.classList.toggle("open", open);
    b.setAttribute("aria-expanded", open ? "true" : "false");
  },
  setHRegion:function (r) { S.hregion = r; this.render(); },
  setHMode:function (m) { S.hmode = m; this.render(); },
  hsort:function (k) {
    if (S.hsort.k === k) S.hsort.d = -S.hsort.d;
    else S.hsort = {k:k, d:1};
    this.render(); },
  setRegion:function (r) { S.region = r; this.render(); },
  setUnit:function (u) { S.unit = u; this.render(); },
  go:function (v) { S.view = v;
    VIEWS.forEach(function (x) {
      var tab = document.getElementById("t-" + x);
      document.getElementById("v-" + x).hidden = x !== v;
      tab.className = x === v ? "on" : "";
      tab.setAttribute("aria-selected", x === v ? "true" : "false"); });
    this.render(); },
  pick:function (code) { S.node = code || "01"; S.unit = null; this.render(); },
  openCountry:function (slug) { S.country = slug; S.multi = []; this.go("country"); },
  openNode:function (code, unit) { S.node = code; S.unit = unit; this.go("compare"); },
  setGeoMode:function (m) { S.gmode = m; S.gsel = null; this.render(); },
  setGNode:function (c) { S.gnode = c; this.render(); },
  setGUnit:function (u) { S.gunit = u; this.render(); },
  setGMeasure:function (m) { S.gmeasure = m; this.render(); },
  setGWin:function (w) { S.gwin = w; this.render(); },
  setGFreq:function (f) { S.gfreq = f; this.render(); },
  setGSmooth:function (w) { S.gsmooth = w; this.render(); },
  /* the first toggle turns the default set into an explicit one, so nothing the
     reader picked can be dropped behind their back later */
  toggleGeo:function (g) {
    if (!S.gsel) S.gsel = DRAWN.slice();
    var i = S.gsel.indexOf(g);
    if (i >= 0) { if (DRAWN.length > 1) S.gsel.splice(i, 1); } else S.gsel.push(g);
    this.render(); },
  addGeo:function (g) {
    if (!S.gsel) S.gsel = DRAWN.slice();
    if (g && S.gsel.indexOf(g) < 0) S.gsel.push(g);
    this.render(); },
  toggleMulti:function (slug) { var i = S.multi.indexOf(slug);
    if (i >= 0) S.multi.splice(i, 1); else S.multi.push(slug); this.render(); },
  sort:function (which, k) {
    var t = which === "cmp" ? S.sortCmp : S.sortCtry;
    if (t.k === k) t.d = -t.d; else { t.k = k; t.d = 1; }
    this.render(); },
  render:function () {
    seg("cur-usd", S.cur === "usd");
    seg("cur-local", S.cur === "local");
    seg("mod-0", !S.incModelled); seg("mod-1", S.incModelled);
    seg("der-0", !S.measuredOnly); seg("der-1", S.measuredOnly);
    seg("flg-0", !S.showFlagged); seg("flg-1", S.showFlagged);
    ["any","solid","corrob"].forEach(function (k) { seg("ev-" + k, S.evidence === k); });

    /* A control that cannot change what is on screen reads as broken. Each group
       declares the views it acts on, and the strip disappears when none apply. */
    var strip = document.getElementById("ctlstrip"), live = 0;
    Array.prototype.forEach.call(strip.querySelectorAll(".grp"), function (g) {
      var ok = g.getAttribute("data-views").split(" ").indexOf(S.view) >= 0;
      g.hidden = !ok;
      if (ok) live++;
    });
    strip.hidden = !live;

    if (S.view === "world") renderWorld();
    else if (S.view === "compare") renderCompare();
    else if (S.view === "country") renderCountry();
    else if (S.view === "patterns") renderPatterns();
    else if (S.view === "trends") renderTrends();
  }
};
document.addEventListener("keydown", function (e) {
  if (e.key === "Escape") return APP.about(false);
  if ((e.key === "Enter" || e.key === " ") && e.target && e.target.dataset &&
      e.target.dataset.act) { e.preventDefault(); e.target.click(); }
});
window.APP = APP;

/* boot */
(function () {
  var m = DATA.meta;
  document.getElementById("scope").innerHTML =
    "COICOP divisions " + m.divisions.join(" and ") + " — food, beverages, alcohol and tobacco, " +
    "priced per kilogram, litre or piece";
  setTextIfPresent("minleaves", DATA.qa.min_basket_leaves);
  setTextIfPresent("wtPairs", m.geo_min_pairs);
  setTextIfPresent("hmMinLeaves", HM_MIN_LEAVES);

  /* the corpus counts belong with the method that produced them, not above the
     reading — they are provenance, not the headline */
  var ranked = DATA.ctyIdx.filter(function (s) { return DATA.cty[s].level_ok; }).length;
  var leaves = DATA.nodeIdx.filter(isLeaf).length;
  document.getElementById("aboutFacts").innerHTML = [
    ["Countries", fmtN(m.n_countries)], ["Comparable enough to rank", fmtN(ranked)],
    ["Trusted unit values", (m.n_obs / 1e6).toFixed(2) + "M"], ["Retail sources", fmtN(m.n_sources)],
    ["Categories priced", fmtN(leaves)], ["Data through", m.through]
  ].map(function (r) {
    return '<div><div class="l">' + r[0] + '</div><div class="v">' + r[1] + "</div></div>"; }).join("");
  document.getElementById("aboutFoot").innerHTML =
    "Generated " + m.generated + ". A cell needs " + m.min_cell_obs +
    "+ observations before it is shown at all.";
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
