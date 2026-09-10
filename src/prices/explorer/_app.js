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

/* Compare opens on one named item, not on a division. `01` is a grouping, and
   the grouping branch of renderCompare draws nothing at all — so the tab that
   exists to rank countries used to open on an explanation of why it could not.
   Rice is the item to open on: it is priced almost everywhere, in one unit,
   and it is the worked example everyone reaches for. */
var OPEN_ON = "01.1.1.1.2";
/* The base month is pinned rather than negotiated, matching the policy
   dashboard, so a reader moving between the two is reading one index rather
   than two that happen to share a shape. */
var INDEX_BASE = {M:"2024-01", Q:"2024Q1"};

var S = {
  view:"world", mode:"explore", cur:"usd", incModelled:false, measuredOnly:false,
  incImputed:false,
  showFlagged:false, evidence:"corrob", region:null, node:OPEN_ON, country:null,
  /* Country profile keeps its own category state: it opens on ALL items and
     the filter narrows it, where Compare opens on one item and drills. The two
     tabs wanted opposite defaults out of one variable, which is why one of them
     was always wrong. `cnode` null means the whole tree. */
  cnode:null, bench:"world",
  fxMode:"both", sortCmp:{k:"val",d:1}, sortCtry:{k:"ratio",d:1},
  multi:[], hregion:null, hsort:{k:null, d:1},
  /* world time series: what to compare, at what category, unit, measure and window.
     gsel null means "whatever the default is here" — an explicit list only appears
     once the reader has actually chosen, so a category with thin coverage can never
     silently strike a place off the list for good. */
  gmode:"region", gsel:null, gnode:"01", gunit:0, gmeasure:"chg12", gcpi:false,
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

/* The taxonomy's catch-all leaves — "... n.e.c." and titles that open with
   "Other". A LEVEL for one is not a quantity: its members share no common good,
   so a dollars-per-kilo of "other bakery products" prices croissants in one
   country against flatbread in another. A CHANGE for one is fine — the same
   catch-all in the same country month over month is a basket of its own — so
   these are held out of the level views only, and the chain keeps them. */
var RESIDUAL = {};
(DATA.residual || []).forEach(function (c) { RESIDUAL[c] = 1; });
function isResidual(code) { return !!RESIDUAL[code]; }
function notResidual(code) { return !RESIDUAL[code]; }
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
/* One estimator, everywhere a gap is summarised: the mean of the differences.
   The heatmap took a median and the ranking took a median while the waterfall
   took a mean, so two cells on the same screen answered the same question
   differently and the app had to say so in a footnote. A mean is also the only
   one of the two that decomposes — the waterfall's bars add up to its total
   because of it — and the evidence filter now defaults to two sources, which
   removes the thin cells an outlier comes from before the mean sees them. */
function mean(a) {
  if (!a.length) return null;
  return a.reduce(function (p, q) { return p + q; }, 0) / a.length;
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
/* The unit is a LABEL now, not a control. `nodeMeta[node].dom` is the unit most
   of a node's observations are quoted in, and it is the only unit drawn, so a
   bar means the same thing before and after any other click on the page.

   `dom` is worked out globally, over every country at once, and that is the
   accepted cost of making it authoritative: a leaf that is dominant-kg
   worldwide now drops the countries that only price it by the piece, where the
   old chip could still reach them. It is stated on screen rather than absorbed
   — `unitNote` below names the units left out at the node on display. */
function domUnit(code) {
  var d = (DATA.nodeMeta[code] || {}).dom;
  var i = DATA.unitIdx.indexOf(d);
  return i >= 0 ? i : null;
}
/* `dom` is counted over every trusted OBSERVATION at the node; a cell has to
   clear MIN_CELL_OBS and then the evidence filter on top of it. So the
   dominant unit can end up with no surviving cell at all while another unit
   still has several, and picking it regardless would put a confident heading
   over an empty chart. Where that happens the unit with the most surviving
   cells is drawn instead and `unitLabelHtml` names what was left out — the
   same rule the World and Currency-effects charts already apply to their own
   series. It is still a label, not a control: nothing here is clickable. */
function resolveUnit(ni) {
  var dom = domUnit(DATA.nodeIdx[ni]);
  if (dom != null && cellsFor(ni, dom).length) return dom;
  var us = unitsAt(ni);
  return us.length ? us[0].ui : dom;
}
/* The read-only counterpart of the old chip row. It carries the count so the
   label still says how much is behind it, and it names what the dominant unit
   is costing when a node is priced in more than one. */
function unitLabelHtml(ni) {
  var ui = resolveUnit(ni);
  if (ui == null) return '<span class="tiny">no unit of measure at this node</span>';
  var us = unitsAt(ni), here = us.filter(function (x) { return x.ui === ui; })[0];
  var other = us.filter(function (x) { return x.ui !== ui; });
  return '<span class="ub big">' + UNIT_LABEL[DATA.unitIdx[ui]] + "</span>" +
    (here ? ' <span class="tiny">' + here.n + " cells</span>" : "") +
    (other.length ? ' <span class="tiny">&middot; ' +
      other.map(function (x) { return x.n + " priced " + UNIT_LABEL[x.u]; }).join(", ") +
      " not shown: a chart cannot mix them</span>" : "");
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

/* The heatmap opens the dashboard, so it is drawn first here — every country
   against every category group, before a control has been touched. The time
   series is the second question and sits under it. The country ranking left
   this tab for Compare, where the other cross-country reading lives. */
function renderWorld() {
  renderHeatmap();
  renderWorldTrends();

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
var GEO_DASH = [undefined, [7,4], [2,3], [11,4,2,4]];
var MAX_SLOTS = PAL.length * GEO_DASH.length;
var SLOT = {};
function assignSlots(drawn) {
  Object.keys(SLOT).forEach(function (g) {
    if (drawn.indexOf(g) < 0) delete SLOT[g]; });
  var used = {};
  Object.keys(SLOT).forEach(function (g) { used[SLOT[g]] = 1; });
  drawn.forEach(function (g) {
    if (g === "W" || SLOT[g] != null) return;
    for (var i = 0; i < MAX_SLOTS; i++) if (!used[i]) { SLOT[g] = i; used[i] = 1; return; }
  });
}
/* Hue cycles first and dash second, so the six validated hues are exhausted as
   solid lines before any of them is reused with a different stroke. */
function geoColor(g) {
  return g === "W" ? INK
    : (SLOT[g] == null ? FAINT : PAL[SLOT[g] % PAL.length]);
}
function geoDash(g) {
  if (g === "W") return [6,3];
  return SLOT[g] == null ? undefined
    : GEO_DASH[Math.floor(SLOT[g] / PAL.length)];
}
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

/* ---- what the World chart is measuring -----------------------------------
   Three families, and only one of them needs a base period.

   A change ("what has it done since a year ago") is two observations of the
   same items and stops there — nothing accumulates, and no month's own noise
   sets the level of the whole line. That is why it leads.

   The base-100 chain is still here for anyone who wants the cumulated series,
   but it is read against a period that was one thin draw, which is exactly the
   reading that was hard to defend.

   A level is a US$ figure and exists only at a leaf; see the node filter. */
function changeLabel(months, word) {
  return months === 1 ? "the previous " + word
    : months === 12 ? "a year earlier" : (months / 12) + " years earlier";
}
function changeMonths() {
  return S.gmeasure.indexOf("chg") === 0 ? +S.gmeasure.slice(3) : null;
}
/* the payload keys each horizon by MONTHS; the shortest a quarter can carry
   is three, so "previous period" is 1 month or 3 depending on the grain */
function horizonKey(months, f) {
  return String(months === 1 && f === "Q" ? 3 : months);
}
/* How far apart two observations may sit and still be linked by the chain.
   Published by the build so this reading cannot drift from the constant that
   produced it; the fallback is for a payload built before it was. */
function gapMonths(f) {
  var g = DATA.qa.link_gap_months || {};
  return g[f] != null ? g[f] : (f === "Q" ? 1 : 3);
}
function measureKind() {
  return S.gmeasure === "level" ? "level"
    : S.gmeasure === "index" ? "index" : "change";
}
function gvalue(s, i, months, f) {
  if (S.gmeasure === "level") return s.lvl[i];
  if (S.gmeasure === "index") return s.idx[i];
  var c = s.chg && s.chg[horizonKey(months, f)];
  return c ? c.v[i] : null;
}
/* ---- official CPI overlay ------------------------------------------------
   An official CPI is a LOCAL-CURRENCY index and every series this dashboard
   builds is in US dollars, so laying one over the other unconverted would put
   the exchange rate inside the comparison — the exact misreading the Currency
   effects tab exists to prevent.

   The fix is the FX identity the Trends tab already uses, P_local = P_usd x FX,
   in its change form:  d ln P_local = d ln P_usd + d ln FX. Applied to OUR
   line, not to the official one: the published index is the thing being
   benchmarked against and must not be the thing that moves.

   It does not generalise. A region or the world spans many currencies and has
   no exchange rate to apply, so the overlay is country-mode only and switches
   the whole chart into local terms while it is on, rather than drawing one
   converted line among unconverted ones. */
function lagPeriods(months, f) {
  return f === "Q" ? (months === 1 ? 1 : months / 3) : months;
}
/* monthly values collapsed onto the chart's own period grain */
function toGrain(ps, vs, f) {
  var acc = {}, out = {};
  ps.forEach(function (p, i) {
    if (vs[i] == null) return;
    var k = f === "M" ? p
      : p.slice(0, 4) + "Q" + (Math.floor((+p.slice(5, 7) - 1) / 3) + 1);
    (acc[k] = acc[k] || []).push(vs[i]);
  });
  Object.keys(acc).forEach(function (k) {
    out[k] = acc[k].reduce(function (a, b) { return a + b; }, 0) / acc[k].length; });
  return out;
}
function pctOver(map, grid, L) {
  return grid.map(function (p, i) {
    var was = grid[i - L];
    if (was == null) return null;
    var a = map[was], b = map[p];
    return (a > 0 && b > 0) ? (b / a - 1) * 100 : null;
  });
}
/* the COICOP division on screen, as the IMF names it — so the official line
   beside our food series is the official FOOD series, not the headline */
function cpiCodeFor(node) {
  var code = "CP" + String(node).split(".")[0];
  return (DATA.cpiMeta && DATA.cpiMeta.labels && DATA.cpiMeta.labels[code]) ? code : null;
}
function cpiFor(slug, code) {
  var c = (DATA.cpi || {})[slug];
  return c && c[code] ? c[code] : null;
}
/* the overlay only means something where one country meets one currency */
function cpiPossible(kind) {
  return kind === "country" && measureKind() === "change" &&
    !!DATA.cpi && Object.keys(DATA.cpi).length > 0;
}

/* how many item cells stand behind the point actually being read */
function gsupport(s, i, months, f) {
  if (S.gmeasure === "level" || S.gmeasure === "index") return s.k[i];
  var c = s.chg && s.chg[horizonKey(months, f)];
  return c ? c.k[i] : 0;
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

/* trailing arithmetic mean, for a series that is already a rate of change:
   a percentage change can be negative, so it has no logarithm to average */
function smoothPct(pts, w) {
  if (!w || w < 2) return pts;
  return pts.map(function (v, i) {
    if (v == null) return null;
    var acc = 0, n = 0;
    for (var j = Math.max(0, i - w + 1); j <= i; j++) {
      if (pts[j] != null) { acc += pts[j]; n++; }
    }
    return acc / n;
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
  var allNodes = Object.keys(byNode).map(function (n) { return DATA.nodeIdx[+n]; })
    .filter(Boolean).sort();
  /* A level is a US$-per-unit figure, so the level measure offers only
     categories where such a figure exists: a single leaf, and not a catch-all
     one. Every change measure keeps the whole tree — a group compared with its
     own past is a basket, and a basket has a perfectly good growth rate. */
  var levelOnly = S.gmeasure === "level", months = changeMonths();
  var nodes = levelOnly
    ? allNodes.filter(function (c) { return isLeaf(c) && notResidual(c); })
    : allNodes;
  var droppedForLevel = allNodes.length - nodes.length;
  var word = f === "Q" ? "quarter" : "month";
  document.getElementById("ws-2").textContent = "2 " + word + "s";
  document.getElementById("ws-3").textContent = "3 " + word + "s";
  ["Q","M"].forEach(function (x) {
    document.getElementById("wf-" + x).className = f === x ? "on" : ""; });
  [0,2,3].forEach(function (x) {
    document.getElementById("ws-" + x).className = S.gsmooth === x ? "on" : ""; });
  ["level","index","chg1","chg12","chg24","chg36"].forEach(function (m) {
    document.getElementById("wv-" + m).className = S.gmeasure === m ? "on" : ""; });
  document.getElementById("wv-chg1-word").textContent = word;
  [36,60,0].forEach(function (w) {
    document.getElementById("ww-" + w).className = S.gwin === w ? "on" : ""; });
  ["region","subregion","country"].forEach(function (m) {
    document.getElementById("wm-" + m).className = kind === m ? "on" : ""; });
  var cpiOK = cpiPossible(kind), cpiOn = cpiOK && S.gcpi;
  var cpiBtn = document.getElementById("wv-cpi");
  cpiBtn.disabled = !cpiOK;
  cpiBtn.className = cpiOn ? "on" : "";
  cpiBtn.setAttribute("aria-pressed", cpiOn ? "true" : "false");
  cpiBtn.title = cpiOK
    ? "Switch the chart into local-currency terms and draw the official index beside it"
    : "An official CPI is a local-currency index, so it can only be set against " +
      "one country at a time, on a price change. Pick Countries and a change measure.";

  var chartId = "cWorldTrend";
  function nothing(msg) {
    document.getElementById("wtChips").innerHTML = "";
    readout(null, "", "", "");
    document.getElementById("wtWarn").innerHTML = '<div class="warnbox">' + msg + "</div>";
    chart(chartId, {type:"line", data:{labels:[], datasets:[]}});
    document.getElementById("wtNote").innerHTML = "";
  }
  if (!nodes.length) return nothing(levelOnly
    ? "No single item here has a deep enough series to price in US$ per unit. " +
      "A price level only means something for one item; try a change measure, " +
      "which works for any grouping."
    : "Nothing repeats often enough at this level to draw a line.");
  if (nodes.indexOf(S.gnode) < 0) S.gnode = nodes.indexOf("01") >= 0 ? "01" : nodes[0];
  var ni = DATA.nodeIdx.indexOf(S.gnode);

  /* The level measure is a US$-per-unit figure, so it is offered only where one
     exists. Disabling it beats silently swapping the category out from under
     the reader, which is what the "not in the list" fallback above would do. */
  var levelOK = isLeaf(S.gnode) && notResidual(S.gnode);
  var lvlBtn = document.getElementById("wv-level");
  lvlBtn.disabled = !levelOK;
  lvlBtn.title = levelOK ? ""
    : "A price per unit only means something for a single named item. " +
      title(S.gnode) + " is a grouping — pick one item to price it in US$.";

  var sel = document.getElementById("wtNode");
  sel.innerHTML = nodes.map(function (c) {
    var lvl = (DATA.tax[c] || {}).lvl || 1;
    return '<option value="' + c + '">' + new Array(lvl).join("   ") +
      esc(title(c)) + " · " + c + "</option>"; }).join("");
  sel.value = S.gnode;

  /* The unit is read off the node, not off the reader. `dom` is what the node
     is mostly priced in; where the geo series has nothing at that unit there is
     no chart to draw at it, so the first unit that does carry a series is used
     and the label says which — the alternative is a blank chart under a
     confident heading. */
  var units = Object.keys(byNode[ni] || {}).map(Number).sort();
  var dom = domUnit(S.gnode);
  S.gunit = units.indexOf(dom) >= 0 ? dom : units[0];
  var ui = S.gunit, unitCode = DATA.unitIdx[ui];
  document.getElementById("wtUnits").innerHTML =
    '<span class="ub big">' + UNIT_LABEL[unitCode] + "</span>" +
    (units.length > 1
      ? ' <span class="tiny">also priced ' + units
          .filter(function (u) { return u !== ui; })
          .map(function (u) { return UNIT_LABEL[DATA.unitIdx[u]]; }).join(", ") +
        ", not drawn: one line cannot hold two units</span>"
      : "");

  /* candidate geographies — World is always offered as the yardstick */
  var from = winFrom(), cands = [];
  ["W"].concat(GEOS_BY_KIND[kind] || []).forEach(function (g) {
    var s = gser(g, ni, ui);
    if (!s) return;
    var n = 0;
    s.p.forEach(function (p, i) {
      if (p >= from && gvalue(s, i, months, f) != null) n++; });
    if (n) cands.push({g:g, t:DATA.geos[g].t, n:n, s:s});
  });
  if (!cands.length) return nothing(
    "No " + (measureKind() === "change"
      ? "item priced both now and " + changeLabel(months, word)
      : measureKind() === "index" ? "matched-item chain" : "series") +
    " here in this window. Try a broader category, a wider window" +
    (f === "Q" ? ", monthly periods" : "") + ", a shorter horizon, or another measure.");
  cands.sort(function (a, b) { return b.n - a.n || (a.t < b.t ? -1 : 1); });

  var avail = {};
  cands.forEach(function (c) { avail[c.g] = c; });

  /* What the reader picked and what can be drawn today are different things.
     Holding them apart means a thin category *parks* a place instead of striking
     it off, so it comes back the moment the category or window can carry it. */
  var cap = kind === "country" ? PAL.length : MAX_SLOTS;
  function defaults() {
    var d = cands.filter(function (c) { return c.g !== "W"; })
      .slice(0, cap).map(function (c) { return c.g; })
      .sort(function (a, b) { return DATA.geos[a].t < DATA.geos[b].t ? -1 : 1; });
    if (avail.W) d.unshift("W");
    return d;
  }
  var drawn = S.gsel ? S.gsel.filter(function (g) { return avail[g]; }) : defaults();
  if (!drawn.length) drawn = defaults();
  /* The world has no exchange rate, so it cannot come along into local terms.
     Dropping it is better than drawing it in a currency it does not have. */
  if (cpiOn) drawn = drawn.filter(function (g) { return g !== "W"; });
  if (cpiOn && !drawn.length) drawn = cands.filter(function (c) { return c.g !== "W"; })
    .slice(0, 1).map(function (c) { return c.g; });
  if (!drawn.length) drawn = defaults();
  var parked = S.gsel ? S.gsel.filter(function (g) { return !avail[g]; }) : [];
  assignSlots(drawn);
  DRAWN = drawn;

  var atCap = drawn.filter(function (g) { return g !== "W"; }).length >= cap;
  /* Countries are capped at eighteen chips, but the World yardstick is drawn by
     default and must keep its own chip whatever the cap: without one it was on
     the chart with no way to switch it off. */
  var chips = kind === "country"
    ? cands.filter(function (c) { return c.g === "W"; })
        .concat(cands.filter(function (c) { return c.g !== "W"; }).slice(0, 18))
    : cands;
  document.getElementById("wtChips").innerHTML =
    chips.map(function (c) {
      var on = drawn.indexOf(c.g) >= 0, full = !on && c.g !== "W" && atCap;
      /* the world has no exchange rate, so while the chart is in local terms
         its chip is dead rather than clickable-but-ignored */
      var noFx = cpiOn && c.g === "W";
      return '<button class="chip ser' + (on ? " on" : "") + '" aria-pressed="' + on + '"' +
        (noFx ? ' disabled title="The world spans many currencies, so it has no rate to ' +
          'convert at — turn the official-CPI benchmark off to bring it back"' :
         full ? ' disabled title="' + cap + ' lines is the limit — switch one off first"' : "") +
        ' style="border-left-color:' + (on ? geoColor(c.g) : "var(--rule)") +
        '" onclick="APP.toggleGeo(' + arg(c.g) + ')">' + esc(c.t) +
        '<span class="c">' + c.n + "</span></button>"; }).join("") +
    parked.map(function (g) {
      return '<button class="chip ser" style="opacity:.32" title="Still selected, but ' +
        esc(title(S.gnode)) + ' has no series here — it returns when you change category" ' +
        'onclick="APP.toggleGeo(' + arg(g) + ')">' +
        esc((DATA.geos[g] || {}).t || g) + "</button>"; }).join("");
  /* the add-a-place picker was one of the analyst controls and is gone */

  var kindM = measureKind(), isLevel = kindM === "level", isIndex = kindM === "index";
  var lo = null, hi = null;
  drawn.forEach(function (g) {
    avail[g].s.p.forEach(function (p, i) {
      if (p < from || gvalue(avail[g].s, i, months, f) == null) return;
      if (lo == null || p < lo) lo = p;
      if (hi == null || p > hi) hi = p; }); });
  if (lo == null) return nothing("Nothing to draw for the places selected.");
  var grid = pgrid(lo, hi, f);

  /* Only the base-100 chain needs a base, and the base is now FIXED at
     2024-01. This deliberately gives up what the previous base bought: that
     one rebased every line on the latest period they could all share, so no
     line was ever indexed off a month it had no reading in.

     A pinned base brings that problem back, and the warnbox below says so. It
     is taken on purpose — the policy dashboard is based on 2024-01, and two
     dashboards whose indices are based on different months cannot be read
     against each other at all, which is a worse failure than a thin base.

     A line with no observation in the base month is NOT quietly rebased onto
     its nearest neighbour. It is dropped and named. */
  var baseP = isIndex ? INDEX_BASE[f] : null;

  var ds = [], thin = [], unbased = [], sup = {};
  drawn.forEach(function (g, k) {
    var c = avail[g], s = c.s, vals = {}, base = null;
    /* exactly the base period, never the first period at or after it: a line
       that starts in 2024-03 has no 2024-01 reading, and indexing it off March
       would put a different question on the same axis */
    if (isIndex) {
      var bi = s.p.indexOf(baseP);
      base = bi >= 0 && s.idx[bi] > 0 ? s.idx[bi] : null;
      if (base == null) unbased.push(c.t);
    }
    s.p.forEach(function (p, i) {
      if (p < from) return;
      var v = gvalue(s, i, months, f);
      if (v == null) return;
      if (isIndex) { if (base) vals[p] = v / base * 100; return; }
      vals[p] = v;
    });
    /* A change is already a ratio of two logs; smoothing it is a moving
       average of a rate, not of a price, so it is averaged arithmetically
       rather than in logs (a negative change has no logarithm). */
    var raw = grid.map(function (p) { return vals[p] == null ? null : vals[p]; });
    /* d ln P_local = d ln P_usd + d ln FX, applied before any smoothing:
       a trailing average of converted points is not the conversion of a
       trailing average once the rate has moved inside the window. */
    if (cpiOn) {
      var fxg = toGrain(DATA.fx[g.slice(2)] ? DATA.fx[g.slice(2)].p : [],
                        DATA.fx[g.slice(2)] ? DATA.fx[g.slice(2)].r : [], f);
      var L = lagPeriods(months, f);
      raw = raw.map(function (v, i) {
        var was = grid[i - L];
        if (v == null || was == null) return null;
        var r0 = fxg[was], r1 = fxg[grid[i]];
        if (!(r0 > 0) || !(r1 > 0)) return null;
        return (Math.exp(Math.log(1 + v / 100) + Math.log(r1 / r0)) - 1) * 100;
      });
    }
    var pts = kindM === "change" ? smoothPct(raw, S.gsmooth) : smooth(raw, S.gsmooth);
    if (pts.filter(function (v) { return v != null; }).length < 2) thin.push(c.t);
    sup[g] = {t:c.t, s:s};
    ds.push({ label:c.t, data:pts,
      borderColor: geoColor(g),
      borderWidth: g === "W" ? 2.8 : 2.2,
      borderDash: geoDash(g),
      tension:.2, pointRadius:2.8, spanGaps:true, segment:GAP_SEG });
  });

  /* The official index, exactly as published — headline, and the division the
     category on screen sits in. Same colour as the country it belongs to, so
     the pairing is readable without a legend; dotted, because it is somebody
     else's measurement rather than ours. */
  var cpiDrawn = [], cpiCode = cpiCodeFor(S.gnode);
  var cpiSpecs = (cpiCode ? [[cpiCode, [2,2], 1.8]] : []).concat([["_T", [1,3], 1.4]]);
  if (cpiOn) drawn.forEach(function (g) {
    var slug = g.slice(2), L = lagPeriods(months, f);
    cpiSpecs.forEach(function (spec) {
      var code = spec[0];
      var series = cpiFor(slug, code);
      if (!series) return;
      var pts = smoothPct(
        pctOver(toGrain(series.p, series.v, f), grid, L), S.gsmooth);
      if (!pts.filter(function (v) { return v != null; }).length) return;
      cpiDrawn.push(code);
      ds.push({
        label: (DATA.geos[g] || {}).t + " — official " +
          (code === "_T" ? "CPI, all items" : "CPI, " +
            DATA.cpiMeta.labels[code].toLowerCase()),
        data: pts, borderColor: geoColor(g), borderWidth: spec[2],
        borderDash: spec[1], tension:.2, pointRadius:0, spanGaps:true });
    });
  });

  /* Only caveats that change how you read what is on screen right now. How the
     measure is built belongs in the note behind the heading, not in a standing
     wall of text above the chart. */
  var warn = [];
  if (droppedForLevel) warn.push("<b>" + droppedForLevel + "</b> categor" +
    (droppedForLevel === 1 ? "y is" : "ies are") + " missing from this list: a US$ level " +
    "needs a single, named item, so groupings and catch-all “other…” items " +
    "are offered on the change measures only. <b>The two measures do not cover the " +
    "same categories.</b>");
  if (kindM === "change") warn.push("Each point averages the price change of every item " +
    "priced <b>both in that " + word + " and " + changeLabel(months, word) + "</b>, in the " +
    "same country — items priced in only one of the two are left out entirely, so the " +
    "line answers “what did the same shopping do”, not “what is on the shelf now”.");
  if (isIndex) {
    warn.push("Only items priced in <b>two consecutive " + word + "s</b> in the " +
      "same country are linked — the strictest reading, and the thinnest. The whole line " +
      "hangs off the base " + word + ", <b>" + baseP + "</b>, which is itself one thin " +
      "reading — pinned there so this index and the policy dashboard's share one base.");
    /* Failing loudly is the whole point of pinning the base: a line with no
       reading in the base month simply cannot be indexed, and vanishing without
       a word is exactly what the previous shared-base rule existed to prevent. */
    if (unbased.length) warn.push("<b>" + unbased.length + "</b> of the places selected " +
      "ha" + (unbased.length === 1 ? "s" : "ve") + " <b>no reading in " + baseP + "</b> and " +
      "cannot be indexed against it: <b>" + unbased.slice(0, 6).map(esc).join(", ") +
      (unbased.length > 6 ? " and " + (unbased.length - 6) + " more" : "") + "</b>. " +
      "They are missing from the chart, not flat on it. A price change measure needs no " +
      "base and still covers them.");
    /* Disclosure, not a fix: a link is allowed to span a gap, and the whole
       move is booked onto the later period. Nothing is interpolated, so the
       alternative would be to drop the link, not to invent the missing month. */
    var gap = gapMonths(f);
    if (gap > 1) warn.push("A link may span up to <b>" + gap + " " + word + "s</b>, and the " +
      "entire move is booked onto the later one — so a " + gap + "-" + word + " rise can " +
      "appear as a single " + word + "'s. <b>Nothing is interpolated</b>: an empty " + word +
      " stays empty rather than being filled in.");
  }
  if (isLevel) warn.push("This level is <b>fitted, not observed</b>: " +
    esc(DATA.qa.fitted_level || "a two-way fixed-effects model on log price") +
    ", whose period effect is the level with the item mix held fixed. It uses every item " +
    "that recurs at all, not only items that recur in consecutive periods — which is why " +
    "it exists — but it is a model output, and a point can stand where no single shop was " +
    "observed that " + word + ".");
  if (cpiOn) {
    warn.push("Comparing with an official CPI means comparing in the currency it is " +
      "published in, so <b>our lines are converted to local currency</b> here " +
      "(d ln P<sub>local</sub> = d ln P<sub>US$</sub> + d ln FX) and the official index " +
      "is drawn exactly as published. The world line is dropped: it spans many " +
      "currencies and has no rate to convert at.");
    warn.push("Ours is a <b>matched-item retail</b> change over the items we scrape; " +
      "the official index is an <b>expenditure-weighted</b> national basket over a much " +
      "wider range of outlets. They should move together, not coincide — a gap is a " +
      "question to ask, not an error to correct.");
    if (!cpiDrawn.length) warn.push("<b>No official CPI</b> is published for the " +
      "countries on screen at this horizon.");
    else if (cpiCode && cpiDrawn.indexOf(cpiCode) < 0) warn.push(
      "No official <b>" + esc(DATA.cpiMeta.labels[cpiCode].toLowerCase()) + "</b> index " +
      "for these countries — only the all-items headline is drawn.");
  }
  if (kindM === "change") warn.push("Nothing here is interpolated or modelled: each point is " +
    "two observations of the same item, exactly " + (months === 1 ? "one " + word : months +
    " months") + " apart. A " + word + " with no match simply has no point.");
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
              (isLevel ? "$" + v.toFixed(2) + UNIT_OF[unitCode]
                : isIndex ? v.toFixed(1)
                : (v >= 0 ? "+" : "") + v.toFixed(1) + "%"); },
          afterBody:function (items) {
            var p = grid[items[0].dataIndex], out = [""];
            drawn.forEach(function (g) {
              var s = sup[g].s, i = s.p.indexOf(p);
              var n = i < 0 ? 0 : gsupport(s, i, months, f);
              if (!n) return;
              out.push(sup[g].t + ": " + s.c[i] + (s.c[i] === 1 ? " country · " : " countries · ") +
                n + " item cells"); });
            return out.length > 1 ? out : []; } } } },
      scales:{ y:{ grid:{color:RULE},
          title:{display:true, text: isLevel ? "US$ per " + UNIT_SHORT[unitCode] + " (fitted)"
            : isIndex ? "Index, " + baseP + " = 100"
            : "% change vs " + changeLabel(months, word) +
              (cpiOn ? ", local currency" : ", US$")} },
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
      isLevel ? " US$ per " + UNIT_SHORT[unitCode] : isIndex ? " index" : "%",
      (isLevel ? "Average across the items priced per " + UNIT_SHORT[unitCode] + " in "
               : isIndex ? "Matched-item index for " : "Change vs " +
                 changeLabel(months, word) + " for ") +
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
  var leadN = li >= 0 ? gsupport(lead.s, li, months, f) : 0;
  document.getElementById("wtNote").innerHTML =
    "Always in US$ here — the local-currency and exchange-rate split lives in " +
    '<span class="linkish" onclick="APP.go(\'trends\')">Currency effects</span>. ' +
    (li >= 0 && leadN ? "Latest support: " + esc(lead.t) + " · " + lead.s.c[li] +
      (lead.s.c[li] === 1 ? " country · " : " countries · ") + fmtN(leadN) +
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

  /* Both callers of this navigator are LEVEL views, so the catch-all leaves
     are not offered here at all rather than offered and then blanked. They are
     still reachable wherever a change is what is being read. */
  var kids = (KIDS.get(node) || []).filter(notResidual);
  var list = (kids.length ? kids : ancestors(node).length > 1
      ? (KIDS.get(DATA.tax[node].p) || []).filter(notResidual) : ROOTS);
  var hidden = (KIDS.get(node) || []).filter(isResidual).length;
  /* read off the UNFILTERED children: a node whose every child is a catch-all
     is still a node, and must not claim to be a leaf */
  var isSiblings = !(KIDS.get(node) || []).length;
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
  var foot = hidden
    ? '<div class="it" style="cursor:default;color:var(--faint);font-size:11.5px">' +
      hidden + ' catch-all item' + (hidden === 1 ? "" : "s") + ' ("other …", ' +
      '"n.e.c.") hidden: a price per kilo needs the items in it to be the same ' +
      'thing. They still count in the price <i>changes</i> on the World tab.</div>'
    : "";
  document.getElementById(listId).innerHTML = (hint + html + foot) ||
    '<div class="empty">Nothing priced under this node.</div>';
}

/* =====================================================================
   2. COMPARE COUNTRIES
   ===================================================================== */
function renderCompare() {
  /* The whole-basket ranking moved to this tab with its markup, so its renderer
     has to follow it or the card sits empty under a heading. It is drawn FIRST,
     and before every early return below: the ranking answers a question about
     countries and knows nothing about the item selected on the left, so a node
     that cannot be ranked must not take the country ranking down with it. */
  renderRanking();

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

  var ui = resolveUnit(ni);
  document.getElementById("cmpUnits").innerHTML = unitLabelHtml(ni);

  /* Nothing to rank: clear the chart and the table rather than leaving the last
     node's numbers standing under the new node's heading. */
  function cmpNothing(sub) {
    document.getElementById("cmpTitle").innerHTML = esc(title(S.node));
    document.getElementById("cmpSub").innerHTML = sub;
    document.getElementById("cmpWarn").innerHTML = "";
    document.getElementById("cmpLegend").innerHTML = "";
    sizeCanvas("cCompare", 0);
    chart("cCompare", {type:"bar", data:{labels:[], datasets:[]}});
    document.getElementById("cmpTbl").innerHTML = "";
    setHtmlIfPresent("cmpSamples", "");
  }
  if (ui == null) return cmpNothing("No comparable unit values at this node.");
  /* A price in levels is only a price at a leaf. "US$4.10 per kilo of cereals"
     divides one country's mix of rice, bread and pasta by another country's,
     and the ratio moves with whichever items each happened to price -- there is
     no such quantity to compare. The reader is sent down to an item instead of
     being handed a number that looks like one. */
  if (!isLeaf(S.node)) return cmpNothing(
    "<b>" + esc(title(S.node)) + "</b> is a grouping, not an item, and a price per " +
    UNIT_SHORT[DATA.unitIdx[ui]] + " for a grouping is not a quantity — one country's " +
    "mix of the items inside it is not another's. <b>Pick an item on the left</b> to " +
    "compare countries; to compare the grouping itself, use a price <i>change</i> on " +
    'the <span class="linkish" onclick="APP.go(\'world\')">World</span> tab, which is ' +
    "built item by item and then averaged.");
  /* A catch-all leaf holds whatever did not resolve to a named sibling, so one
     country's is not the other's. Ranking them against each other is the figure
     `publish` has withheld since it was written. */
  if (isResidual(S.node)) return cmpNothing(
    "<b>" + esc(title(S.node)) + "</b> is a catch-all category — it holds whatever could " +
    "not be placed on a named item, and what lands in it differs from one country to the " +
    "next. A price per unit for it is not comparable across countries, so none is shown. " +
    'Its price <i>changes</i> are still on the <span class="linkish" ' +
    "onclick=\"APP.go('world')\">World</span> tab.");
  var unit = DATA.unitIdx[ui];
  var gmed = ((DATA.nodeMeta[S.node] || {}).gmed || {})[unit];

  /* Always US dollars here, with no switch to say otherwise. The bars refused
     to honour a local-currency setting anyway and printed a warnbox saying so,
     which is the worst of both: a control that does nothing and an apology for
     it. Two hundred currencies have no common ruler and cannot be ranked, so
     the reading is one reading. `val()` and `S.cur` are not consulted. */
  var rows = cellsFor(ni, ui).map(function (c) {
    var meta = DATA.cty[c.country] || {};
    return { c:c, name:meta.name || c.country, region:meta.region,
             usd:c.usd, ratio: gmed ? c.usd / gmed : null };
  });
  var q = (document.getElementById("cmpSearch").value || "").toLowerCase();
  var shown = q ? rows.filter(function (r) { return r.name.toLowerCase().indexOf(q) >= 0; }) : rows;

  var plot = shown.filter(function (r) { return r.usd != null; })
                  .sort(function (a, b) { return b.usd - a.usd; });
  document.getElementById("cmpWarn").innerHTML = "";

  document.getElementById("cmpTitle").innerHTML = esc(title(S.node)) +
    ' <span class="ub big">' + UNIT_LABEL[unit] + "</span>";
  document.getElementById("cmpSub").innerHTML =
    "Median US$ price for one " + UNIT_SHORT[unit] +
    (gmed ? ". World median: <b>$" + gmed.toFixed(2) + "</b>" + UNIT_OF[unit] : "") +
    " · " + plot.length + " countries";

  sizeCanvas("cCompare", Math.max(200, plot.length * 17 + 50));
  chart("cCompare", {
    type:"bar",
    data:{ labels: plot.map(function (r) { return r.name; }),
      datasets:[{ data: plot.map(function (r) { return r.usd; }),
        backgroundColor: plot.map(function (r) {
          if (r.c.flag) return DEAR;
          if (r.c.mod >= 0.5) return PAL[5];
          return r.c.src === 1 ? PAL[0] + "66" : PAL[0]; }),
        borderWidth:0, borderRadius:3 }] },
    options:{ indexAxis:"y",
      onClick:function (e, els) { if (els.length) { S.country = plot[els[0].index].c.country; APP.go("trends"); } },
      plugins:{ legend:{display:false}, tooltip:{ callbacks:{ label:function (t) {
        var r = plot[t.dataIndex], c = r.c, out = [];
        out.push("$" + r.usd.toFixed(2) + " " + UNIT_LABEL[c.unit]);
        if (r.ratio) out.push("vs world median: " + pct(r.ratio - 1));
        out.push(c.obs + " observations · " + c.src + " source" + (c.src > 1 ? "s" : ""));
        out.push("dispersion (log MAD): " + (c.mad == null ? "—" : c.mad.toFixed(2)));
        out.push("period: " + c.per);
        if (c.flag) out.push("⚠ outside plausible bounds");
        if (c.mod >= 0.5) out.push("⚠ modelled, not observed retail");
        if (c.mix) out.push("⚠ mixed currencies in cell");
        return out; } } } },
      scales:{ x:{ beginAtZero:true, position:"top", grid:{color:RULE},
          title:{display:true, text:"US$ " + UNIT_LABEL[unit]} },
        y:{ ticks:{font:{size:11}, autoSkip:false}, grid:{display:false} } } }
  });

  /* three different things were being said with colour and none of them was labelled */
  var seen = {};
  plot.forEach(function (r) {
    if (r.c.flag) seen.flag = 1;
    else if (r.c.mod >= 0.5) seen.mod = 1;
    else seen[r.c.src === 1 ? "one" : "many"] = 1; });
  function sw(col, txt) { return '<span><i class="sw" style="background:' + col + '"></i>' + txt + "</span>"; }
  var leg = [];
  if (seen.many) leg.push(sw(PAL[0], "two or more sources"));
  if (seen.one) leg.push(sw(PAL[0] + "66", "a single source"));
  if (seen.mod) leg.push(sw(PAL[5], "modelled, not an observed shelf price"));
  if (seen.flag) leg.push(sw(DEAR, "outside plausible bounds"));
  document.getElementById("cmpLegend").innerHTML = leg.join("");

  /* table — each column declares its own type so the comparator never subtracts text */
  var CMP_COLS = {
    name:  {label:"Country",  cls:"",    kind:"text", get:function (r) { return r.name; }},
    val:   {label:"Price US$",cls:"num", kind:"num",  get:function (r) { return r.usd; }},
    ratio: {label:"vs world", cls:"num", kind:"num",  get:function (r) { return r.ratio; }},
    obs:   {label:"Obs",      cls:"num", kind:"num",  get:function (r) { return r.c.obs; }},
    src:   {label:"Src",      cls:"num", kind:"num",  get:function (r) { return r.c.src; }},
    mad:   {label:"Log MAD",  cls:"num", kind:"num",  get:function (r) { return r.c.mad; }},
    per:   {label:"Period",   cls:"",    kind:"text", get:function (r) { return r.c.per; }},
    flags: {label:"Notes",    cls:"",    kind:"num",  get:function (r) { return flagRank(r.c); }}
  };
  var order = ["name","val","ratio","obs","src","mad","per","flags"];
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
        '<td class="num">$' + r.usd.toFixed(2) + "</td>" +
        '<td class="num">' + (r.ratio ? pct(r.ratio - 1, 0) : "—") + "</td>" +
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
   =====================================================================
   The yardstick is selectable HERE and nowhere else.

   `gmed` is the world median and stays the default reading on every screen in
   this dashboard. `rmed` is a second set of medians — one per region, one per
   subregion — shipped ALONGSIDE it and never instead of it. The build's rule
   is that a "vs world" figure keeps its global yardstick, and this does not
   break it: what that rule forbids is the SILENT swap, a screen still saying
   "vs world" over a number that is not. So every label moves with the
   selector — chart title, axis, column heading, tooltips — and the world is
   what the page opens on.

   The waterfall below stays on the world median whatever this is set to. It is
   the decomposition the country ranking is built from, and a decomposition
   whose parts and whose total answered to different yardsticks would add up to
   nothing. */
function benchName() {
  var m = DATA.cty[S.country] || {};
  return S.bench === "region" ? (m.region || "its region")
    : S.bench === "subregion" ? (m.subregion || "its subregion")
    : "the world";
}
function benchMinCountries() {
  return ((DATA.qa || {}).benchmark || {}).min_countries || 3;
}
function benchMed(code, unit) {
  var meta = DATA.nodeMeta[code] || {};
  if (S.bench === "world") return (meta.gmed || {})[unit];
  return ((meta.rmed || {})[benchName()] || {})[unit];
}

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

  /* Division and class, never an item. The category navigator used to sit here
     and scoped this chart down to a single leaf, which drew exactly one bar --
     "the ranked chart of one thing". These two selects narrow the basket and
     stop: "All items" is the default and every level below a class is out of
     reach on purpose. Drilling to an item is what Compare is for. */
  var mineAll = (byCountry.get(ci) || []).filter(keep);
  function underCount(code) {
    var pre = code + ".";
    return mineAll.filter(function (c) {
      return isLeaf(c.node) && notResidual(c.node) &&
        (c.node === code || c.node.indexOf(pre) === 0); }).length;
  }
  var div = S.cnode ? ancestors(S.cnode)[0] : null;
  var dsel = document.getElementById("ctryDiv");
  dsel.innerHTML = '<option value="">All items</option>' +
    ROOTS.map(function (r) {
      return '<option value="' + r + '">' + esc(proseTitle(r)) + " · " +
        underCount(r) + " items</option>"; }).join("");
  dsel.value = div || "";
  /* Classes are the level-3 nodes under the chosen division -- the same grain
     the heatmap's rows use, so the two read as one vocabulary. */
  var classes = div
    ? DATA.nodeIdx.filter(function (c) {
        return (DATA.tax[c] || {}).lvl === 3 && ancestors(c)[0] === div; })
    : [];
  var csel = document.getElementById("ctryCls");
  csel.innerHTML = '<option value="' + (div || "") + '">All classes</option>' +
    classes.map(function (c) {
      return '<option value="' + c + '">' + esc(proseTitle(c)) + " · " +
        underCount(c) + " items</option>"; }).join("");
  csel.value = S.cnode || div || "";
  csel.disabled = !div;

  ["world", "region", "subregion"].forEach(function (b) {
    seg("bm-" + b, S.bench === b); });

  /* all leaf cells for this country under the selected filter */
  var scope = S.cnode, prefix = scope ? scope + "." : null;
  var mine = mineAll.filter(function (c) {
    return (!scope || c.node === scope || c.node.indexOf(prefix) === 0) &&
      isLeaf(c.node) && notResidual(c.node);
  }).map(function (c) {
    var g = benchMed(c.node, c.unit);
    return { c:c, name:title(c.node), ratio: g ? c.usd / g : null, gmed:g, val:val(c) };
  });

  /* A yardstick that does not exist for an item drops the item, and a chart
     that quietly loses half its bars when a control is touched is the failure
     this whole selector has to avoid. So the count is said out loud. */
  var noBench = mine.filter(function (r) { return r.ratio == null; }).length;
  document.getElementById("ctryBenchWarn").innerHTML =
    S.bench !== "world" && noBench
      ? '<div class="warnbox"><b>' + noBench + "</b> item" + (noBench === 1 ? " has" : "s have") +
        " no " + esc(benchName()) + " median and " + (noBench === 1 ? "is" : "are") +
        " missing from this chart: fewer than " + benchMinCountries() + " countries in " +
        esc(benchName()) + " price " + (noBench === 1 ? "it" : "them") + ". They are still " +
        "there against <b>the world</b>.</div>"
      : "";

  var top = mine.filter(function (r) { return r.ratio != null; })
    .sort(function (a, b) { return b.ratio - a.ratio; });
  var show = top.length > 30 ? top.slice(0, 15).concat(top.slice(-15)) : top;
  document.getElementById("ctryChartTitle").innerHTML =
    esc(m.name || "") + " — dearest and cheapest" +
    (scope ? " under " + esc(proseTitle(scope)) : " across every item priced") +
    ", versus " + esc(benchName());
  setHtmlIfPresent("ctryChartSub",
    "Ratio of this country's unit value to the <b>" + esc(benchName()) +
    "</b> median for the same item and unit. " + top.length + " items.");
  sizeCanvas("cCountry", Math.max(200, show.length * 18 + 50));
  chart("cCountry", {
    type:"bar",
    data:{ labels: show.map(function (r) { return r.name + " (" + UNIT_SHORT[r.c.unit] + ")"; }),
      datasets:[{ data: show.map(function (r) { return (r.ratio - 1) * 100; }),
        backgroundColor: show.map(function (r) { return r.ratio >= 1 ? DEAR : CHEAP; }),
        borderWidth:0, borderRadius:3 }] },
    options:{ indexAxis:"y",
      onClick:function (e, els) { if (els.length) APP.openNode(show[els[0].index].c.node); },
      plugins:{ legend:{display:false}, tooltip:{ callbacks:{ label:function (t) {
        var r = show[t.dataIndex];
        return [ fmtMoney(r.val, r.c.cur) + " " + UNIT_LABEL[r.c.unit],
                 benchName() + " median: $" + r.gmed.toFixed(2) + UNIT_OF[r.c.unit],
                 pct(r.ratio - 1) + " vs " + benchName(),
                 r.c.obs + " observations" ]; } } } },
      scales:{ x:{ grid:{color:RULE}, position:"top",
          title:{display:true, text:"% above or below the " + benchName() +
            " median for the same item and unit"} },
        y:{ ticks:{font:{size:11}, autoSkip:false}, grid:{display:false} } } }
  });

  var q = (document.getElementById("ctrySearch").value || "").toLowerCase();
  var tRows = (q ? mine.filter(function (r) { return r.name.toLowerCase().indexOf(q) >= 0; }) : mine);
  var CT_COLS = {
    name:  {label:"Item",     cls:"",    kind:"text", get:function (r) { return r.name; }},
    unit:  {label:"Unit",     cls:"",    kind:"text", get:function (r) { return UNIT_LABEL[r.c.unit]; }},
    val:   {label:"Price",    cls:"num", kind:"num",  get:function (r) { return r.val; }},
    /* the heading follows the yardstick: a column that says "vs world" over a
       regional ratio is exactly the silent substitution this must never be */
    ratio: {label:"vs " + benchName(), cls:"num", kind:"num",
                                       get:function (r) { return r.ratio; }},
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
        '<td><span class="linkish" onclick="APP.openNode(' + arg(c.node) + ')">' +
          esc(r.name) + "</span></td>" +
        '<td><span class="ub">' + UNIT_LABEL[c.unit] + "</span></td>" +
        '<td class="num">' + fmtMoney(r.val, c.cur) + "</td>" +
        '<td class="num">' + (r.ratio ? pct(r.ratio - 1, 0) : "—") + "</td>" +
        '<td class="num">' + c.obs + "</td>" +
        '<td class="num">' + c.src + "</td>" +
        '<td class="num">' + (c.mad == null ? "—" : c.mad.toFixed(2)) + "</td>" +
        "<td>" + c.per + "</td><td>" + flagPills(c) + "</td></tr>"; }).join("")
      : '<tr><td colspan="9" class="empty">Nothing priced here under the current filters.</td></tr>') +
    "</tbody>";

  renderWaterfall();
}

/* =====================================================================
   4. TRENDS & FX
   ===================================================================== */
/* Every trend reads its series through here, which is why the imputed filter
   lives here and nowhere else. With the toggle off the returned object is the
   one the payload shipped, untouched — a series carrying no fill has no `imp`
   array at all, so the common case does no work and behaves exactly as it did
   before RT-CAL existed. */
function seriesFor(ci, ni, ui) {
  var s = DATA.series[ci + "|" + ni + "|" + ui] || null;
  if (!s || !s.imp) return s;
  if (S.incImputed) return s;
  var out = {p:[], usd:[], loc:[], n:[], imp:[], pr:[]}, i;
  for (i = 0; i < s.p.length; i++) {
    if (s.imp[i]) continue;
    out.p.push(s.p[i]); out.usd.push(s.usd[i]); out.loc.push(s.loc[i]);
    out.n.push(s.n[i]); out.imp.push(0); out.pr.push(null);
  }
  return out.p.length ? out : null;
}
var HAS_IMPUTED = (function () {
  var k, ks = Object.keys(DATA.series || {});
  for (k = 0; k < ks.length; k++) if (DATA.series[ks[k]].imp) return true;
  return false;
})();
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
  /* Read-only, off the node's dominant unit, as on the other two tabs. Where
     the country has no series at that unit the first one it does have is drawn
     rather than nothing, and the label says which. */
  var dom = domUnit(S.node);
  var ui = (avail.filter(function (x) { return x.ui === dom; })[0] || avail[0] || {}).ui;
  document.getElementById("trUnits").innerHTML = ui == null ? "" :
    '<span class="ub big">' + UNIT_LABEL[DATA.unitIdx[ui]] + "</span>" +
    (avail.length > 1
      ? ' <span class="tiny">also priced ' + avail
          .filter(function (x) { return x.ui !== ui; })
          .map(function (x) { return UNIT_LABEL[x.u]; }).join(", ") + ", not drawn</span>"
      : "");
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
  /* An imputed point must be unmistakable at a glance, not only in the tooltip:
     a hollow diamond against a filled dot. The arrays are aligned to the DENSE
     grid, not to the sparse series, because that is what Chart.js indexes. */
  var impGrid = grid.map(function (m) {
    var k = s.p.indexOf(m);
    return k >= 0 && s.imp && s.imp[k] ? 1 : 0;
  });
  var anyImp = impGrid.indexOf(1) >= 0;
  function pointStyle() { return impGrid.map(function (v) { return v ? "rectRot" : "circle"; }); }
  function pointRadius(r) { return impGrid.map(function (v) { return v ? r + 2.5 : r; }); }
  function pointFill(col) { return impGrid.map(function (v) { return v ? "#ffffff" : col; }); }
  var ds = [];
  ds.push({label:"Local currency price", data:onGrid(grid, s.p, idxLoc), borderColor:PAL[2],
           backgroundColor:PAL[2] + "22", borderWidth:2.4, tension:.2,
           pointRadius:pointRadius(2.5), pointStyle:pointStyle(),
           pointBackgroundColor:pointFill(PAL[2]), pointBorderColor:PAL[2],
           spanGaps:true, segment:GAP_SEG});
  if (S.fxMode === "both") {
    ds.push({label:"US$ price", data:onGrid(grid, s.p, idxUsd), borderColor:PAL[0],
             backgroundColor:PAL[0] + "22", borderWidth:2.4, tension:.2,
             pointRadius:pointRadius(2.5), pointStyle:pointStyle(),
             pointBackgroundColor:pointFill(PAL[0]), pointBorderColor:PAL[0],
             spanGaps:true, segment:GAP_SEG});
    ds.push({label:"Exchange rate (local per US$)", data:onGrid(grid, s.p, idxFx), borderColor:PAL[1],
             borderWidth:1.8, borderDash:[3,3], tension:.2, pointRadius:0, spanGaps:true});
  }
  ds.push({label: (isIdx ? "Items" : "Observations") + " behind each point", type:"bar", yAxisID:"y2",
           data:onGrid(grid, s.p, s.n), backgroundColor:"#b9b5aa55", borderWidth:0, order:99});

  var gaps = grid.length - s.p.length;
  var warn = [];
  if (anyImp) {
    var nImp = impGrid.reduce(function (a, b) { return a + b; }, 0);
    warn.push("<b>" + nImp + " of " + s.p.length + "</b> points on this line are " +
      "<b>imputed</b>, drawn as hollow diamonds: no price was observed those months and " +
      "the value is a model estimate. Each carries its own probability of landing within " +
      "25% of the truth — hover to read it. Turn them off to see only measured prices.");
  }
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
            : s.imp && s.imp[k]
            ? ["", "US$ " + (s.usd[k] != null ? s.usd[k].toFixed(2) : "—") +
                 UNIT_OF[DATA.unitIdx[ui]],
               "IMPUTED — no price was observed this month",
               s.pr && s.pr[k] != null
                 ? Math.round(s.pr[k] * 100) + "% chance it is within 25% of the truth"
                 : "modelled estimate"]
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

  /* Decomposition over the COUNTRY's window, not over this item's.

     The exchange-rate effect is a country-level scalar: one currency, one move
     over one span of months. This panel nonetheless reported a different one
     for every product, and the cause was never a per-product FX effect. It was
     that `base` and `last` were each series' OWN first and last month with
     data, so two items were measured over two different windows and therefore
     saw two different currency moves. The identity was always right; the
     window was the defect.

     So the window is pinned per country and all three legs read its two
     endpoints. The currency figure is then one number whatever is on screen.

     An item not priced in one of those two months cannot be split over the
     common window, and says so. It does NOT quietly fall back to its own
     window — that fallback is what produced the per-product spread. */
  var win = countryWindow(ci);
  function at(arr, p) { var i = s.p.indexOf(p); return i >= 0 && arr[i] > 0 ? arr[i] : null; }
  var wb = {usd:at(s.usd, win.lo), loc:at(s.loc, win.lo),
            fx:fxMap[win.lo] > 0 ? fxMap[win.lo] : null};
  var wl = {usd:at(s.usd, win.hi), loc:at(s.loc, win.hi),
            fx:fxMap[win.hi] > 0 ? fxMap[win.hi] : null};
  var dUsd = wb.usd && wl.usd ? wl.usd / wb.usd - 1 : null;
  var dLoc = wb.loc && wl.loc ? wl.loc / wb.loc - 1 : null;
  var dFx  = wb.fx && wl.fx ? wl.fx / wb.fx - 1 : null;
  var lnUsd = dUsd == null ? null : Math.log(1 + dUsd);
  var lnLoc = dLoc == null ? null : Math.log(1 + dLoc);
  var lnFxC = (lnUsd != null && lnLoc != null) ? lnUsd - lnLoc : null;
  document.getElementById("trDeco").innerHTML = [
    box("US$ price", pct(dUsd), dUsd),
    box("Local price (FX removed)", pct(dLoc), dLoc),
    box("Exchange rate, local per US$", pct(dFx), dFx),
    '<div class="b"><div class="l">' + (win.lo || "?") + " → " + (win.hi || "?") +
      ' · the same window for every item here</div>' +
      '<div class="v" style="font-size:14px;font-weight:600;line-height:1.45">' +
      (lnFxC != null
        ? "Of the US$ move, <b>" + (lnLoc * 100).toFixed(1) + "</b> log-points came from local " +
          "prices and <b>" + (lnFxC * 100).toFixed(1) + "</b> from the currency — and the " +
          "currency leg is the country’s, not this item’s."
        : dFx != null
        ? "<b>" + esc(title(S.node)) + "</b> is not priced in both " + win.lo + " and " +
          win.hi + ", so its own move cannot be split over this window. The exchange rate " +
          "beside this is the country’s and stands."
        : "FX split unavailable") + "</div></div>"
  ].join("");

}
/* The window every currency split is measured over: the first and last month
   this COUNTRY has a published series in, whichever item that series belongs
   to. One window per country is the whole point — read the endpoints off the
   item and the exchange rate stops being a country-level number. */
function countryWindow(ci) {
  var lo = null, hi = null, pre = ci + "|";
  Object.keys(DATA.series).forEach(function (k) {
    if (k.indexOf(pre) !== 0) return;
    var ps = DATA.series[k].p;
    if (!ps.length) return;
    if (lo == null || ps[0] < lo) lo = ps[0];
    if (hi == null || ps[ps.length - 1] > hi) hi = ps[ps.length - 1];
  });
  return {lo:lo, hi:hi};
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
var HM_MIN_COUNTRIES = 6;

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
    if (!isLeaf(c.node) || isResidual(c.node) || !(c.usd > 0)) return;
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
    var a = by[cls], mu = mean(a);
    return {cls:cls, n:a.length, mean:mu, contrib:(a.length / N) * mu};
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
  var own = mean(gaps.map(function (g) { return g.r; }));

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
    /* This used to have to explain that the two figures disagreed because one
       averaged the gaps and the other took their median. They now use the same
       estimator, so what is left to explain is the only difference that
       remains: the published level is built on the eligible basket -- the
       leaves priced almost everywhere -- while this decomposes every matched
       item the country has. */
    "The published price level is <b>" +
    (m.level_ok ? m.level.toFixed(0) : (Math.exp(own) * 100).toFixed(0)) +
    "</b>. Both average the differences; they part company on which items count, " +
    "because the published level uses only the leaves priced across almost every " +
    "country and this decomposes everything this country prices.";
}

/* Category down the side, country across the top -- the same orientation as
   the dashboard's heat table, so the two can be read side by side.

   One reading of a cell: the gap from the world median for the same items,
   matched leaf by leaf. The US$-per-unit reading this table used to lead with
   was a median dollars-per-kilo taken ACROSS a whole COICOP class, and there
   is no such quantity -- the members of a class are not the same good, so
   their unit values are not one distribution to take a median of. The gap is
   built per leaf and only then averaged, so it survives the aggregation the
   level does not. Each row still carries one unit, chosen as the unit most of
   that group's prices are quoted in, so a column never mixes kilos with
   litres. */
function classCellsFor(ci) {
  var out = {};
  (byCountry.get(ci) || []).filter(keep).forEach(function (c) {
    if (!isLeaf(c.node) || isResidual(c.node) || !(c.usd > 0)) return;
    var cls = classOf(c.node);
    if (!cls) return;
    var g = ((DATA.nodeMeta[c.node] || {}).gmed || {})[c.unit];
    (out[cls] = out[cls] || []).push({
      unit: c.unit, r: g > 0 ? Math.log(c.usd / g) : null});
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
      cells[cls] = {r:mean(gaps), n:same.length};
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

  var rows = Object.keys(rowN)
    .filter(function (c) { return rowN[c] >= HM_MIN_COUNTRIES; }).sort();
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
        return c ? c.r : null; }, "num", sd)
    : sortRows(shown, function (r) { return r.level; }, "num", sd);

  var head = '<thead><tr><th class="ctry">Category</th>' +
    shown.map(function (r) {
      return '<th class="ctyh" title="' + esc(r.name) + " · price level " +
        r.level.toFixed(0) + '" tabindex="0" role="button" data-act="1" onclick="APP.openCountry(' +
        arg(r.slug) + ')">' + esc(r.name) + "</th>"; }).join("") + "</tr></thead>";

  var span = shown.length + 1, seen = {};
  function band(cls) {
    var a2 = ancestors(cls), out = "";
    [0, 1].forEach(function (d) {
      var code = a2[d];
      if (!code || seen[code] || !DATA.tax[code]) return;
      seen[code] = 1;
      out += '<tr class="hmg l' + (d + 1) + '"><td colspan="' + span + '"><span>' +
        esc(title(code)) + "</span></td></tr>";
    });
    return out;
  }
  var body = "<tbody>" + rows.map(function (cls) {
    var tr = band(cls) + '<tr><td class="ctry ind" title="' + esc(title(cls)) + " · " +
      rowN[cls] +
      ' countries" tabindex="0" role="button" data-act="1" onclick="APP.hsort(' + arg(cls) +
      ')">' + esc(proseTitle(cls)) +
      '<span class="ru">vs world</span>' +
      (sk === cls ? (sd === 1 ? " ▼" : " ▲") : "") + "</td>";
    return tr + shown.map(function (r) {
      var cell = r.cells[cls];
      if (!cell) return '<td class="na" title="' + esc(r.name) + " · " + esc(title(cls)) +
        ': fewer than ' + HM_MIN_LEAVES + ' matched items"></td>';
      if (cell.r == null) return '<td class="na" title="' + esc(r.name) +
        ': no world median for these items"></td>';
      var v = (Math.exp(cell.r) - 1) * 100;
      var lab = Math.abs(v) >= 999 ? (v > 0 ? "+999" : "-999")
        : (v >= 0 ? "+" : "") + v.toFixed(0);
      return '<td class="c" style="background:' + heatColor(cell.r) + ';color:#1b211f" title="' +
        esc(r.name) + " · " + esc(title(cls)) + ": " + lab + "% vs the world median" +
        ", over " + cell.n + ' matched items">' + lab + "</td>"; }).join("") + "</tr>"; }).join("") +
    "</tbody>";
  document.getElementById("hmTbl").innerHTML = head + body;

  document.getElementById("hmSub").innerHTML =
    "Each category group against the world median for the same items. " +
    "Red is dearer than the world, blue cheaper.";

  var cut = Object.keys(rowN).filter(function (c) { return rows.indexOf(c) < 0; })
    .sort(function (a2, b2) { return rowN[b2] - rowN[a2]; });
  var stops = [-1, -0.6, -0.3, 0, 0.3, 0.6, 1];
  document.getElementById("hmRamp").innerHTML =
    '<span class="lab">cheaper than the world</span>' +
    stops.map(function (t) { return '<i style="background:' +
      hexMix(HM_MID, t >= 0 ? DEAR : CHEAP, Math.pow(Math.abs(t), 0.8)) + '"></i>'; }).join("") +
    '<span class="lab">dearer</span>' +
    '<span class="lab" style="margin-left:14px">' +
    'full colour at &plusmn;100% &middot; ' +
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
var VIEWS = ["world","compare","country","trends"];
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
  hsort:function (k) {
    if (S.hsort.k === k) S.hsort.d = -S.hsort.d;
    else S.hsort = {k:k, d:1};
    this.render(); },
  setRegion:function (r) { S.region = r; this.render(); },
  /* Division and class come out of the same control: picking a division clears
     the class under it, picking a class carries its own division. Empty is
     "All items", which is what this tab opens on. */
  setCNode:function (code) { S.cnode = code || null; this.render(); },
  setBench:function (b) { S.bench = b; this.render(); },
  go:function (v) { S.view = v;
    VIEWS.forEach(function (x) {
      var tab = document.getElementById("t-" + x);
      document.getElementById("v-" + x).hidden = x !== v;
      tab.className = x === v ? "on" : "";
      tab.setAttribute("aria-selected", x === v ? "true" : "false"); });
    this.render(); },
  /* Falling back to `01` is what opened Compare on a division, and a division
     draws no bars at all — so the fallback is the item the tab opens on. */
  pick:function (code) { S.node = code || OPEN_ON; this.render(); },
  openCountry:function (slug) { S.country = slug; S.multi = []; this.go("country"); },
  openNode:function (code) { S.node = code; this.go("compare"); },
  setGeoMode:function (m) { S.gmode = m; S.gsel = null; this.render(); },
  setGNode:function (c) { S.gnode = c; this.render(); },
  setGMeasure:function (m) { S.gmeasure = m; this.render(); },
  toggleCPI:function () { S.gcpi = !S.gcpi; this.render(); },
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
    seg("imp-0", !S.incImputed); seg("imp-1", S.incImputed);
    /* A payload built without RT-CAL carries no fills at all, and a control that
       cannot change anything reads as broken -- so the strip only exists when
       there is something behind it. */
    var impSeg = document.getElementById("impSeg");
    if (impSeg) impSeg.hidden = !HAS_IMPUTED;
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
  /* The basket rule in the build's own words, so the ranking states the
     missing-price policy rather than leaving the reader to infer it. */
  setTextIfPresent("leafshare",
    Math.round((DATA.qa.min_basket_leaf_share || 0.75) * 100) + "%");

  /* Compare opens on one item. If the corpus does not carry it — a regional
     build with no rice, or a taxonomy revision that moved the code — the next
     named leaf stands in, because opening on a grouping opens on nothing. */
  if (DATA.nodeIdx.indexOf(OPEN_ON) < 0 || !isLeaf(OPEN_ON) || isResidual(OPEN_ON)) {
    S.node = DATA.nodeIdx.filter(function (c) {
      return isLeaf(c) && notResidual(c); })[0] || DATA.nodeIdx[0] || "01";
  }

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
    "+ observations before it is shown at all. " +
    /* The old promise was "no missing month is ever filled in", stated flatly. It is
       still true when no fills are loaded, and still shown then. What it must never do
       is survive into a payload that HAS fills -- the reader would be told nothing is
       filled while hollow diamonds are drawn in front of them. Same objection, same
       answer as the QA panel: the gap stays a gap until asked for. */
    (HAS_IMPUTED
      ? "<b>Filled months are shown only if you ask for them.</b> Some of these gaps are " +
        "collection artefacts rather than quiet markets, so a gap stays a gap until you " +
        "turn on “Add imputed” — and then a filled month is drawn as a hollow diamond " +
        "carrying the calibrated probability that it lands within 25% of the observed " +
        "median. Filled months reach these curves and nothing else: not the base-100 " +
        "chain, not the changes, not the basket, not the category counts. "
      : "<b>No missing month is ever filled in.</b> " +
        "Some of these gaps are collection artefacts rather than quiet markets, and an " +
        "imputed price would be indistinguishable on screen from a measured one — so a " +
        "gap stays a gap. ") +
    "The two places that come closest are said out loud where they are used: the base-100 " +
    "chain may link across up to " + gapMonths("M") + " months and books the whole move onto " +
    "the later one, and the US$ price level is a fitted model output rather than an observed " +
    "median.";
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
