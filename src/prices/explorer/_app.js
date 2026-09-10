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

/* No `cur` and no `incImputed`.

   CURRENCY was a two-way switch over the whole dashboard, and there is no
   question it answered. A cross-country comparison has no ruler but the
   dollar -- two hundred currencies cannot be ranked against each other -- and
   where the local figure IS meaningful, one country's own shelf or one
   product's own history, both numbers are simply printed. A control whose
   right answer is fixed on one screen and "both" on the other is not a
   control.

   IMPUTED was a toggle defaulting to off, so the default screen was the one
   with holes in it. Fills are labelled everywhere they appear -- hollow
   diamonds on a line, a marker in a table or a grid cell -- which was always
   the real requirement; hiding them by default was never it. */
var S = {
  view:"world", mode:"explore", incModelled:false, measuredOnly:false,
  showFlagged:false, evidence:"solid", region:null, node:OPEN_ON, country:null,
  /* Country profile keeps its own category state: it opens on ALL items and
     the filter narrows it, where Compare opens on one item and drills. The two
     tabs wanted opposite defaults out of one variable, which is why one of them
     was always wrong. `cnode` null means the whole tree. */
  cnode:null, bench:"world",
  sortCmp:{k:"val",d:1}, sortCtry:{k:"ratio",d:1},
  multi:[], hregion:null, hsort:{k:null, d:1},
  /* world time series: what to compare, at what category, unit, measure and window.
     gsel null means "whatever the default is here" — an explicit list only appears
     once the reader has actually chosen, so a category with thin coverage can never
     silently strike a place off the list for good. */
  /* CATFILTER: the world series opens on the same item Compare does, and for
     the reason given at OPEN_ON above -- a division is not a thing anyone buys. */
  gmode:"region", gsel:null, gnode:OPEN_ON, gunit:0, gmeasure:"chg12", gcpi:false,
  gfreq:"Q", gsmooth:0, gwin:36,
  /* Basket weighting: which vector is selected, the raw vector itself, and the
     fixed vector a custom one was seeded FROM -- which is what Reset returns to
     and what each slider's "was" figure is measured against. All three stay
     null on a payload that carries no weight vector at all. */
  wmode:null, w:null, wbase:null
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
      mix:x.mix[i], flag:x.flag[i], per:x.per[i],
      /* Optional and absent today. RT-CAL fills reach the SERIES; the moment
         they reach a cell as well, the build has to say which cells they
         reached or nothing on this screen can mark them. `x.imp` is read as a
         share in 0..1 and defaults to none, so a payload without it behaves
         exactly as it does now. */
      imp:x.imp ? x.imp[i] : 0
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

/* =====================================================================
   WHAT THIS BUILD IS OF
   ---------------------------------------------------------------------
   `prices explorer --region eap` filters the corpus to one region's
   countries before anything is aggregated, so a regional payload carries
   38 EAP countries and nothing else -- while the tab over them said
   "World" and the geo series labelled its own total "World" too. The data
   behind that word was East Asia and the Pacific. That is the complaint
   this block exists to answer.

   Nothing in the payload states its own scope, so it is read off the
   country list: one region present means one region was asked for. A
   genuinely global build carries all six. If the build ever ships
   `meta.region` this becomes a one-liner and should.

   What a regional build DOES still carry of the world is the yardstick:
   `nodeMeta[code].gmed` is the world median, computed before the region
   filter, and `rmed` carries a median for every world region and
   subregion beside it. That is a real global comparison and it is what
   the Global View tab is built from -- not a second copy of these 38
   countries wearing the word "world". */
var BUILD_REGIONS = (function () {
  var seen = {}, out = [];
  DATA.ctyIdx.forEach(function (s) {
    var r = (DATA.cty[s] || {}).region;
    if (r && !seen[r]) { seen[r] = 1; out.push(r); }
  });
  return out.sort();
})();
var IS_REGIONAL = BUILD_REGIONS.length === 1;
var BUILD_REGION = IS_REGIONAL ? BUILD_REGIONS[0] : null;
/* Prose that sends the reader to the first tab has to call it what the tab
   calls itself, or the rename is only half done. */
var HOME_TAB = IS_REGIONAL ? "Regional View" : "Global View";

/* The six World Bank regions, from src/configs/regions.yaml. `rmed` is keyed
   by LABEL and holds regions and subregions in one flat map with nothing to
   tell them apart, so the region names have to be named here; a label that is
   not on this list is a subregion and is left off the global grid. If a rename
   ever empties the intersection the grid falls back to every label it can see,
   which is wrong and visible rather than silently blank. */
var WORLD_REGIONS = ["East Asia & Pacific", "Europe & Central Asia",
  "Latin America & Caribbean",
  "Middle East, North Africa, Afghanistan & Pakistan",
  "South Asia", "Sub-Saharan Africa"];

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
var EVIDENCE = { any:{obs:0, src:1}, thin:{obs:5, src:1}, solid:{obs:10, src:1} };
function keep(cell) {
  if (!S.incModelled && cell.mod >= 0.5) return false;
  if (S.measuredOnly && cell.der > 0.2) return false;
  if (!S.showFlagged && cell.flag) return false;
  var e = EVIDENCE[S.evidence] || EVIDENCE.any;
  if (cell.obs < e.obs || cell.src < e.src) return false;
  return true;
}
function cellsFor(ni, ui) { return (byNodeUnit.get(ni + "|" + ui) || []).filter(keep); }

/* One money formatter per currency, and a third that prints both.
   `fmtBoth` is what a country's own screen uses: the dollar figure is the one
   every other view is denominated in and the local figure is the one somebody
   standing in the shop would recognise, and neither is worth hiding behind a
   switch. Local is dropped silently when the cell has none -- an em dash beside
   a real dollar price says "missing" about a number nobody asked for. */
function fmtNum(v) {
  var d = Math.abs(v) >= 100 ? 0 : Math.abs(v) >= 10 ? 1 : Math.abs(v) >= 1 ? 2 : 3;
  return v.toLocaleString(undefined, {minimumFractionDigits:d, maximumFractionDigits:d});
}
function fmtUsd(v) {
  return (v == null || !isFinite(v)) ? "—" : "$" + fmtNum(v);
}
function fmtLocal(v, cur) {
  return (v == null || !isFinite(v)) ? "" : fmtNum(v) + (cur ? " " + cur : "");
}
function fmtBoth(usd, loc, cur) {
  var l = fmtLocal(loc, cur);
  return fmtUsd(usd) + (l ? ' <span class="tiny">· ' + l + "</span>" : "");
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
   because of it — and the evidence filter defaults to ten observations, which
   removes the thin cells an outlier comes from before the mean sees them.

   The filter does NOT require two sources. A second source corroborates, but a
   single retailer with forty readings is evidence and a rule that discarded it
   cost eighteen countries and 2,486 leaf-country cells for no gain against the
   noise the filter exists to remove. Ten observations was the bar that was
   actually reviewed and accepted; the source count never was. */
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
         (c.der > 0.5 ? 1 : 0) + (c.src === 1 ? 0.5 : 0) + (c.imp > 0 ? 0.25 : 0);
}

/* =====================================================================
   WHAT THE NOTES MEAN
   ---------------------------------------------------------------------
   These pills were the shortest true label for each condition and nothing
   else -- "mixed FX", "derived qty" -- which is fine for whoever wrote the
   build and opaque to everybody else. Each one now carries the sentence it
   needed, on the pill itself and in a key under the table it appears in.

   Every wording below is the condition as the build actually applies it,
   checked against the code that sets it:
     flag  aggregate._cells: the cell's US$ median is outside PLAUSIBLE_USD
           for its unit -- kg 0.20-200, litre 0.05-200, piece 0.005-500.
     mod   the mean of `is_modelled` over the cell's rows; a source counts as
           modelled when it is one of sources.MODELLED_SOURCES, the four
           cost-of-living estimate sites.
     mix   `n_local / n < 0.9`: fewer than nine in ten of the cell's rows were
           priced in the currency the local median is quoted in.
     der   the mean of `is_derived`, which is `mass_source == "derived_typical"`
           -- build/sold_by_item substituted a typical pack size because the
           listing stated none.
     src   distinct sources behind the cell.
   ===================================================================== */
var FLAG_DEFS = [
  ["implausible", "bad",
   "The price per unit falls outside the range any real shelf price for this " +
   "unit could sit in ($0.20&ndash;$200 a kilo, $0.05&ndash;$200 a litre, " +
   "$0.005&ndash;$500 a piece). Almost always a misread pack size rather than " +
   "a real price. These cells are held out of every comparison unless you ask " +
   "for them."],
  ["modelled", "mod",
   "At least half the readings behind this figure come from cost-of-living " +
   "estimate sites rather than from an observed shop listing. Those sites " +
   "publish a modelled figure for a city, not a price someone paid."],
  ["mixed FX", "warn",
   "The listings behind this cell were not all priced in one currency &mdash; " +
   "fewer than nine in ten share the currency the local figure is quoted in. " +
   "The US$ figure is unaffected; the local one describes only the dominant " +
   "currency."],
  ["derived qty", "warn",
   "The listing did not state a pack size, so a typical size for that item was " +
   "used to work out the price per kilo, litre or piece. The price is observed; " +
   "the quantity it is divided by is an assumption."],
  ["1 source", "warn",
   "Every reading comes from a single retailer, so nothing corroborates it. " +
   "One shop's pricing is not a market's."],
  ["imputed", "mod",
   "Some of the months behind this figure were not observed. A model estimated " +
   "them from what the same item did elsewhere, and they are drawn as hollow " +
   "diamonds wherever they appear on a chart."],
  ["clean", "ok",
   "None of the notes above apply: an observed retail price, one currency, a " +
   "stated pack size, more than one source, inside plausible bounds."]
];
var FLAG_NOTE = {};
FLAG_DEFS.forEach(function (d) { FLAG_NOTE[d[0]] = d[2]; });
/* The pill's own tooltip, stripped of the markup the key can afford. */
function flagTitle(k) {
  return (FLAG_NOTE[k] || "").replace(/<[^>]+>/g, "")
    .replace(/&ndash;/g, "-").replace(/&mdash;/g, "-").replace(/&nbsp;/g, " ");
}
function flagKeyHtml() {
  return '<div class="explain"><b>What the notes mean.</b><br>' +
    FLAG_DEFS.map(function (d) {
      return '<span class="pill ' + d[1] + '">' + d[0] + "</span> " + d[2];
    }).join("<br>") + "</div>";
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
   BASKET WEIGHTS
   ---------------------------------------------------------------------
   The price level on the ranking is a weighted sum over COICOP classes:
   one log ratio per class, weighted by what households spend on it. The
   weights are the one input here that is not a fact about this corpus --
   they come from ICP, or from the countries' own CPI returns, or from
   nothing at all -- so they are the input a reader is entitled to
   disagree with, and these controls are how they disagree with it
   without being handed a different dashboard.

   FOUR VECTORS, ONE ARITHMETIC. Equal, World Bank and IMF are fixed and
   ship in the payload; Custom is whatever the sliders say. All four run
   through `bwLevel`, which is the tail of `_basket_levels` re-run on the
   per-class terms the server shipped in `basket.cty`. With the vector at
   `basket.w0` the two must produce the same number -- a browser test
   asserts it -- and if they ever part company the figure on screen is
   the one that is wrong.

   TWO RULES SURVIVE THE MOVE, because they are what the statistic means:

   1. A class the country does not price is an ABSENT TERM, never a zero.
      Its weight is redistributed over the classes the country does
      price, in proportion to theirs. Entering it at zero would say the
      country prices that class at the world median, which is not
      something anyone measured.

   2. `covered` is the share of the UNRENORMALISED vector the country
      actually prices, and the gate on it is re-applied at every change.
      That gate is load-bearing: American Samoa reads 2790 on two leaves
      at 0.18 coverage. Countries therefore enter and leave the ranking
      as the weights move. That is correct, and the count says so out
      loud rather than leaving a reader to notice a name has gone.
   ===================================================================== */
var BW       = DATA.basket || {};
var BW_MODES = BW.modes || {};
var BW_W0    = BW.w0 || {};
var BW_CTY   = BW.cty || {};
var BW_LAB   = BW.lab || {};
var BW_CODES = Object.keys(BW_W0).sort();
var BW_MIN_COV = (BW.gates || {}).min_covered;
/* Per mille, integer. A slider is an integer control and the lightest class in
   the published vector is 0.011 of the basket, so a thousandth is the coarsest
   step that leaves the light classes draggable at all. 400 is the ceiling: a
   bit over twice the heaviest default (meat, 0.179), which is enough headroom
   to make any single class dominate without a track so long that a class at
   0.011 sits on its first pixel. */
var BW_UNIT = 1000, BW_MAX = 400;
/* A payload built before this block existed, or built with no weights table at
   all, carries no vector and no matrix -- and a panel of sliders that cannot
   change anything reads as broken, so it simply does not appear. */
var BW_ON = BW_CODES.length > 0 && Object.keys(BW_CTY).length > 0 &&
  BW_MIN_COV != null && !!BW_MODES[BW.mode0] &&
  DATA.ctyIdx.some(function (s) { return DATA.cty[s].level_gate != null; });
/* The mode order is the order they are offered in: what the taxonomy says, then
   the two institutions, then the reader. Anything the payload does not carry is
   dropped rather than shown dead. */
var BW_ORDER = ["equal", "icp", "imf"].filter(function (k) { return !!BW_MODES[k]; });

/* The published figures, taken aside before anything is recomputed. Reset puts
   these back rather than re-deriving them at `w0`: the two agree to a hundredth
   of an index point, and a published figure should still be exactly the
   published figure once the reader has finished moving things. */
var BW_PUB = {};
if (BW_ON) DATA.ctyIdx.forEach(function (s) {
  var m = DATA.cty[s];
  BW_PUB[s] = {level:m.level, level_n:m.level_n, level_cov:m.level_cov,
               level_ok:m.level_ok};
});

function bwTitle(code) {
  var t = BW_LAB[code] || (DATA.tax[code] || {}).t;
  return t || code;
}
function bwCopy(w) {
  var out = {};
  BW_CODES.forEach(function (c) { out[c] = w[c] || 0; });
  return out;
}
/* Switch to a fixed vector. Custom is always SEEDED from one of these, so a
   reader who starts dragging never starts from nowhere -- and `wbase` is what
   Reset goes back to and what each row's "was" figure is measured against. */
function bwSetMode(k) {
  S.wmode = k; S.wbase = k; S.w = bwCopy(BW_MODES[k].w);
}
function bwDirty() {
  var base = BW_MODES[S.wbase].w;
  return BW_CODES.some(function (c) { return S.w[c] !== (base[c] || 0); });
}
/* Is what is on screen the vector this build published? Only then may the
   ranking go unbadged. */
function bwPublished() { return S.wmode === BW.mode0 && !bwDirty(); }
/* A slider's integer position. An untouched class keeps the payload's own
   float: rounding every default onto the per-mille grid would shift the vector
   by up to half a thousandth per class and put the opening figure a tenth of a
   point off the published one, for nothing. */
function bwPos(c) { return Math.round(S.w[c] * BW_UNIT); }

/* One country's level under weight vector `w`, and the share of that vector it
   is able to price. This is the tail of `_basket_levels`, deliberately line for
   line -- if it drifts, so does the number under the reader's finger. */
function bwLevel(slug, w) {
  var m = BW_CTY[slug];
  if (!m) return null;
  var tot = 0, i, code, wi, sw = 0, acc = 0, k = 0;
  for (i = 0; i < BW_CODES.length; i++) tot += w[BW_CODES[i]] || 0;
  for (code in m) {
    /* Every priced class contributes its leaf count, including one carrying no
       weight: `n_leaves` says how much of this country was matched, which is
       the same statement whatever the weights are. The build sums it the same
       way, over every row of the matrix. */
    k += m[code][1];
    wi = w[code];
    if (!(wi > 0)) continue;
    sw += wi;
    acc += wi * m[code][0];
  }
  if (!(sw > 0) || !(tot > 0)) return null;
  /* `sw / tot` is `covered`: the share of the vector as it stands that this
     country actually prices. `acc / sw` is the weighted mean over the classes
     that exist -- the redistribution of the absent terms, written as a division
     rather than as a second pass over the weights. */
  return {level:Math.exp(acc / sw) * 100, covered:sw / tot, n:k};
}

/* Write the current figures back into `DATA.cty`, which is where every view on
   this dashboard reads a price level from. Recomputing in place rather than at
   each call site is what stops the ranking and the country profile from
   quietly disagreeing once a slider has moved. */
function bwApply() {
  if (!BW_ON) return;
  var pub = bwPublished();
  DATA.ctyIdx.forEach(function (slug) {
    var m = DATA.cty[slug], p = BW_PUB[slug], b;
    if (pub) {
      m.level = p.level; m.level_n = p.level_n;
      m.level_cov = p.level_cov; m.level_ok = p.level_ok;
      return;
    }
    b = bwLevel(slug, S.w);
    /* No row in the matrix at all: the country was never in the basket, and no
       weight vector can put it there. */
    if (!b) { m.level_ok = false; return; }
    m.level = b.level;
    m.level_n = b.n;
    m.level_cov = b.covered;
    /* `level_gate` is the build's verdict on everything EXCEPT coverage --
       matched items, sources, defect share -- every one of which is a property
       of the corpus and cannot move with a weight. Coverage can, and does. */
    m.level_ok = !!m.level_gate && b.covered >= BW_MIN_COV;
  });
}
/* How many countries the PUBLISHED vector ranks, under the region filter now
   in force, so the count on screen is compared against like. */
function bwPubCount() {
  return DATA.ctyIdx.filter(function (s) {
    return BW_PUB[s].level_ok && (!S.region || DATA.cty[s].region === S.region);
  }).length;
}

/* URL state. There is no existing persistence in this app to be consistent
   with -- no hash reader, no query string, no storage -- so this is the first,
   and it stays narrow on purpose: the weighting, and nothing else. Only the
   entries that differ from the seed vector are written, so a link keeps working
   across a build that revises the defaults; encoding positions would not. */
function bwHash() {
  if (bwPublished()) return "";
  var parts = [], base = BW_MODES[S.wbase].w;
  BW_CODES.forEach(function (c) {
    if (S.w[c] !== (base[c] || 0)) parts.push(c + ":" + bwPos(c));
  });
  return "w=" + S.wbase + (parts.length ? "|" + parts.join(",") : "");
}
function bwWriteHash() {
  /* `history.replaceState` is refused on `file://` in some browsers and this
     dashboard is opened from a file at least as often as it is served, so the
     hash is set directly. Written on `change` and never on `input`: a history
     entry per pixel of drag is not state worth keeping. */
  var h = bwHash();
  if ((window.location.hash || "").replace(/^#/, "") === h) return;
  window.location.hash = h;
}
function bwReadHash() {
  var m = /(?:^|[#&])w=([^&]*)/.exec(window.location.hash || "");
  if (!m) return;
  var raw = decodeURIComponent(m[1]), bar = raw.indexOf("|");
  var mode = bar < 0 ? raw : raw.slice(0, bar);
  /* A mode this build does not carry -- an IMF link opened against a payload
     built with no WGT_PT rows -- is ignored rather than half-applied. */
  if (!BW_MODES[mode]) return;
  bwSetMode(mode);
  if (bar < 0) return;
  raw.slice(bar + 1).split(",").forEach(function (kv) {
    var p = kv.split(":"), v;
    if (p.length !== 2 || BW_W0[p[0]] == null) return;
    v = parseInt(p[1], 10);
    if (!isFinite(v) || v < 0 || v > BW_MAX) return;
    S.w[p[0]] = v / BW_UNIT;
  });
  if (bwDirty()) S.wmode = "custom";
}

/* The grid is built ONCE. Rebuilding it on input would destroy the range input
   the reader has hold of and end the drag on the first pixel; everything that
   changes while dragging is text, and `bwSync` writes that. */
function bwBuild() {
  if (!BW_ON) return;
  document.getElementById("wBox").hidden = false;
  var html = "", grp = null;
  BW_CODES.forEach(function (c, i) {
    var g = c.slice(0, c.lastIndexOf("."));
    if (g !== grp) {
      grp = g;
      html += '<div class="wgrp">' + esc(bwTitle(c.slice(0, 2))) +
        ' <span style="opacity:.6">&rsaquo;</span> ' + esc(bwTitle(g)) + "</div>";
    }
    html += '<div class="wrow" id="w-r-' + i + '">' +
      '<span class="lab" title="' + esc(c + " " + bwTitle(c)) + '">' +
        esc(bwTitle(c)) + "</span>" +
      '<input type="range" id="w-i-' + i + '" min="0" max="' + BW_MAX +
        '" step="1" value="' + bwPos(c) + '" aria-label="' + esc(bwTitle(c)) +
        ' weight" oninput="APP.setWeight(' + arg(c) + ',this.value)"' +
        ' onchange="APP.setWeight(' + arg(c) + ',this.value,1)">' +
      '<span class="num" id="w-n-' + i + '"></span></div>';
  });
  document.getElementById("wGrid").innerHTML = html;
}

/* Everything that changes when the vector changes, and nothing that does not. */
function bwSync() {
  if (!BW_ON) return;
  var dirty = bwDirty(), tot = 0, base = BW_MODES[S.wbase].w, bt = 0;
  BW_CODES.forEach(function (c) { tot += S.w[c]; bt += base[c] || 0; });

  document.getElementById("wModes").innerHTML =
    BW_ORDER.map(function (k) {
      return '<button id="wm-' + k + '" class="' + (S.wmode === k ? "on" : "") +
        '" aria-pressed="' + (S.wmode === k) + '" onclick="APP.setWMode(' +
        arg(k) + ')">' + esc(BW_MODES[k].meta.name || k) + "</button>";
    }).join("") +
    '<button id="wm-custom" class="' + (S.wmode === "custom" ? "on" : "") +
    '" aria-pressed="' + (S.wmode === "custom") + '" disabled' +
    ' title="Move any slider below to weight the basket yourself">Custom</button>';

  var badge = document.getElementById("wBadge");
  badge.hidden = bwPublished();
  badge.textContent = (S.wmode === "custom" ? "Your own weights"
    : BW_MODES[S.wmode].meta.name) + " \u2014 not the published ranking";
  document.getElementById("wReset").disabled = !dirty;
  document.getElementById("wReset").textContent =
    "Reset to " + (BW_MODES[S.wbase].meta.name || S.wbase);

  var meta = BW_MODES[S.wmode === "custom" ? S.wbase : S.wmode].meta;
  document.getElementById("wProv").innerHTML =
    "<b>" + esc(meta.label) + ".</b> " + esc(meta.note || "") +
    (S.wmode === "custom"
      ? " You have moved this vector; every share below is shown beside the one " +
        "it started from."
      : "") +
    " Every share below is a share of what this dashboard prices, not of a " +
    "national CPI basket that mostly is not on it." +
    /* The single most useful thing about any of these vectors, and the one a
       reader will otherwise attribute to the prices: a category nothing here
       prices still sits in the denominator of `covered`, so it caps how much of
       the basket ANY country can reach and therefore how many get ranked. Two
       modes can differ in who they rank without differing in a single price. */
    (meta.unpriced > 0.005
      ? " <b>Nothing in this build prices " + Math.round(meta.unpriced * 100) +
        "% of this vector</b>, so no country can cover more than " +
        Math.round((1 - meta.unpriced) * 100) + "% of it — which is why " +
        "the number of countries ranked moves with the weights and not only " +
        "with the prices."
      : "");

  BW_CODES.forEach(function (c, i) {
    var inp = document.getElementById("w-i-" + i);
    if (!inp) return;
    /* Setting the value the input already holds is a no-op and does not
       interrupt a drag; setting a different one is how Reset and the mode
       buttons move the sliders. */
    if (+inp.value !== bwPos(c)) inp.value = bwPos(c);
    var moved = S.w[c] !== (base[c] || 0);
    document.getElementById("w-r-" + i).className = "wrow" + (moved ? " moved" : "");
    document.getElementById("w-n-" + i).innerHTML =
      "<b>" + (S.w[c] / tot * 100).toFixed(1) + "%</b>" +
      (dirty ? '<span class="was">was ' +
        ((base[c] || 0) / bt * 100).toFixed(1) + "%</span>" : "");
  });
}

/* =====================================================================
   1. WORLD
   ===================================================================== */
/* `all` skips the region filter. The region chips count what each region would
   contribute to the ranking, which is a question about the whole list, and the
   list itself is the same rows narrowed. */
function levelRows(all) {
  return DATA.ctyIdx
    .map(function (slug) { return Object.assign({slug:slug}, DATA.cty[slug]); })
    .filter(function (r) { return r.level_ok && r.level != null; })
    .filter(function (r) { return all || !S.region || r.region === S.region; })
    .sort(function (a, b) { return b.level - a.level; });
}

/* The heatmap opens the dashboard, so it is drawn first here — every country
   against every category group, before a control has been touched. The time
   series is the second question and sits under it. The country ranking left
   this tab for Compare, where the other cross-country reading lives. */
function renderWorld() {
  renderHeatmap();
  renderWorldTrends();
  /* Was its own tab. Same tab as the heatmap now, and measured against the
     same world median, so the two read as one argument rather than two. */
  renderVsWorldGrid();

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
  bwSync();
  /* Counted off the rows as they now stand, not off the payload: under a weight
     vector the reader has chosen, a region's count is what THAT vector ranks. */
  var regions = {};
  levelRows(true).forEach(function (r) {
    regions[r.region] = (regions[r.region] || 0) + 1; });
  document.getElementById("regionChips").innerHTML = Object.keys(regions).sort()
    .map(function (r) {
      return '<button class="chip' + (S.region === r ? " on" : "") + '" aria-pressed="' +
        (S.region === r) + '" onclick="APP.setRegion(' + arg(r) + ')">' + esc(r) +
        '<span class="c">' + regions[r] + "</span></button>";
    }).join("");
  document.getElementById("reg-all").className = "chip" + (S.region ? "" : " on");
  document.getElementById("reg-all").setAttribute("aria-pressed", S.region ? "false" : "true");

  var rows = levelRows();
  /* A country is ranked only where the live vector covers enough of the basket
     it would need, so countries enter and leave as the weights move. Saying how
     many, and how that compares with the published vector, is the difference
     between that being visible behaviour and a name quietly going missing. */
  var count = rows.length + " countries ranked · world median = 100";
  if (BW_ON && !bwPublished()) {
    var d = rows.length - bwPubCount();
    count += " · " + (d === 0
      ? "the same countries the published weights rank"
      : (d > 0 ? d + " more" : (-d) + " fewer") + " than the published weights" +
        " — a country is ranked only where these weights cover " +
        Math.round(BW_MIN_COV * 100) + "% of its basket");
  }
  document.getElementById("worldCount").textContent = count;
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
      r.obs.toLocaleString() + " observations" +
      (r.imp > 0 ? " · rests partly on imputed months" : "") + '">' +
      '<div class="n">' + (i + 1) + '</div><div class="nm">' + esc(r.name) +
      (r.imp > 0 ? ' <span class="impm">◇</span>' : "") + "</div>" +
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
    '<span><i class="sw" style="background:' + CHEAP + '"></i>below it</span>' +
    (rows.some(function (r) { return r.imp > 0; })
      ? '<span><span class="impm">◇</span> rests partly on imputed months</span>' : "");
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
/* `build_geo_series` maps EVERY country it is handed to the "W" geo, and a
   regional build hands it one region's countries -- so in a regional payload W
   is the region total wearing the word "World", not the world. It is not merely
   mislabelled, it is a DUPLICATE: all 788 W series in an EAP payload are
   byte-identical to their `R:East Asia & Pacific` twin, so the chart drew one
   line twice under two names and offered it as two comparators.

   One of the pair has to go. W keeps the slot because it is the only anchor the
   country and subregion modes have -- the region geo is only ever offered in
   region mode -- and it is relabelled with the region's own name at boot, which
   is what the numbers are. A GENUINE world comparator is not available to a
   regional build at all: the payload's only world-scope figures are the
   cross-sectional medians `gmed`/`rmed`, and there is no world time series in
   it. Nothing here may be dressed up as one. */
if (IS_REGIONAL) {
  GEOS_BY_KIND.region = (GEOS_BY_KIND.region || []).filter(function (g) {
    return g !== "R:" + BUILD_REGION; });
}
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
/* Periods at which an index LEVEL steps, i.e. where the published series stops
   being the same series. A doubling or a halving inside one month is a change
   of base or a break in the feed far more often than it is a price move: Libya
   rebased all eleven of its published series at 2025-01 (CP01 353.9 -> 102.0)
   and ZMB CP01 carries a one-month decimal error (464.47 -> 4755.04 -> 486.52)
   that reads as +1042% year on year. Differencing across either reports an
   index change as an inflation rate.

   Over the whole IMF table this marks 32 months across 26 of 1,549 series.
   Some of them -- LBN, SDN, ZWE, UKR -- are a currency collapse rather than a
   rebase, and the two are not separable from the levels alone. The response is
   the same either way and is the conservative one: the two ends are not known
   to be the same series, so they are not differenced, and the month is NAMED
   on the chart so a reader can judge it. */
function levelBreaks(map) {
  var ks = Object.keys(map).sort(), step = [], out = {}, i, j, k;
  for (i = 1; i < ks.length; i++) {
    var a = map[ks[i - 1]], b = map[ks[i]];
    step[i] = a > 0 && b > 0 && (b / a < 0.5 || b / a > 2.0);
  }
  /* How LONG the series stays out of band is what separates a defect from an
     economy. One month out and it stays there is a rebase; out and straight
     back is a decimal slip; three or more consecutive months of doubling is a
     currency dying, which is real and must be drawn rather than cut. */
  for (i = 1; i < ks.length; i++) {
    if (!step[i]) continue;
    for (j = i; step[j + 1]; j++) { /* walk the run */ }
    if (j - i + 1 <= 2) for (k = i; k <= j; k++) out[ks[k]] = true;
    i = j;
  }
  return out;
}
/* A change axis that survives a hyperinflation.

   Percent change is not log-scalable: it crosses zero and goes negative. But a
   chart carrying Venezuela and Cambodia at once is carrying +68,000,000% and
   +5%, and on a linear axis every country that is not Venezuela is the zero
   line. The three ways out are a clamp, a broken axis, and a log axis.

   A clamp is the only one that LIES: it draws Venezuela at whatever the clamp
   is and the reader takes that for the value. A broken axis is honest but is a
   lot of custom drawing to say what a log axis says with a tick callback. So:
   a symmetric log, sign(v) * log10(1 + |v|), which is exactly v near zero,
   compresses the tail, keeps the ordering, and keeps small movements legible
   beside enormous ones. The axis is relabelled and a warning is raised, because
   an unannounced log axis is its own kind of lie.

   It is a DISPLAY decision and deliberately not a claim about the number. Some
   of these extremes are redenominations rather than inflation -- a currency
   changing its unit, not its value. Saying which is which is the build's job
   (see `_warn_on_fx_span` / `_warn_on_fx_excursion` in aggregate.py), not the
   axis's. */
var SYMLOG_AT = 1000;   /* engage once something on screen exceeds +1000% */
function symlog(v) {
  return v == null ? null : (v < 0 ? -1 : 1) * Math.log10(1 + Math.abs(v));
}
function symlogInv(t) {
  return (t < 0 ? -1 : 1) * (Math.pow(10, Math.abs(t)) - 1);
}
function pctTick(v) {
  var a = Math.abs(v);
  return (v >= 0 ? "+" : "\u2212") +
    (a >= 1e6 ? (a / 1e6).toPrecision(3).replace(/\.?0+$/, "") + "m"
     : a >= 1e3 ? (a / 1e3).toPrecision(3).replace(/\.?0+$/, "") + "k"
     : a >= 10 ? a.toFixed(0) : a.toFixed(1)) + "%";
}

/* `brk`, when given, collects the periods this call refused to difference
   across, so the reader is told a series was cut rather than left to wonder
   why a line stops. A break is never smoothed over and never dropped in
   silence. */
function pctOver(map, grid, L, brk) {
  var breaks = levelBreaks(map);
  return grid.map(function (p, i) {
    var was = grid[i - L];
    if (was == null) return null;
    var a = map[was], b = map[p];
    if (!(a > 0) || !(b > 0)) return null;
    /* the change from `was` to `p` is only a price change if the index meant
       the same thing at both ends */
    for (var k = i - L + 1; k <= i; k++) {
      if (breaks[grid[k]]) { if (brk) brk[grid[k]] = true; return null; }
    }
    return (b / a - 1) * 100;
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
  var cpiDrawn = [], cpiBreaks = {}, cpiCode = cpiCodeFor(S.gnode);
  var cpiSpecs = (cpiCode ? [[cpiCode, [2,2], 1.8]] : []).concat([["_T", [1,3], 1.4]]);
  if (cpiOn) drawn.forEach(function (g) {
    var slug = g.slice(2), L = lagPeriods(months, f);
    cpiSpecs.forEach(function (spec) {
      var code = spec[0];
      var series = cpiFor(slug, code);
      if (!series) return;
      var pts = smoothPct(
        pctOver(toGrain(series.p, series.v, f), grid, L, cpiBreaks), S.gsmooth);
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
    var brkP = Object.keys(cpiBreaks).sort();
    if (brkP.length) warn.push("The official index <b>changes level</b> at <b>" +
      brkP.map(esc).join(", ") + "</b> — it halves or more than doubles inside a " +
      "single " + word + ", which is a <b>change of base or a break in the feed</b> " +
      "far more often than a price move. The two ends are not known to be the same " +
      "series, so the official line is <b>cut</b> there rather than differenced " +
      "across it and has no points for " + changeLabel(months, word) + " after the " +
      "break. Nothing is dropped quietly: the gap is the break, and the " + word +
      " is named above so you can judge it.");
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
  /* Only a change measure produces a number a log axis can help: a US$ level
     and a based index are already on one scale. The official CPI lines are in
     `ds` too and count towards the peak -- an index that blows up is exactly as
     unreadable beside a calm one as ours would be. */
  var peak = 0;
  if (kindM === "change") ds.forEach(function (d) {
    d.data.forEach(function (v) { if (v != null && Math.abs(v) > peak) peak = Math.abs(v); }); });
  var logY = peak >= SYMLOG_AT;
  if (logY) {
    /* the true value is kept on the dataset, so the tooltip and the lead line
       still read the number rather than its logarithm */
    ds.forEach(function (d) { d.rawData = d.data; d.data = d.data.map(symlog); });
    warn.push("One line on this chart passes <b>" + pctTick(peak) + "</b>, so the " +
      "vertical axis is drawn on a <b>symmetric log scale</b> — equal spacing is an " +
      "equal <b>multiple</b>, not an equal number of points. It is the only way a " +
      "single-digit change and a millionfold one are both readable here. <b>A number " +
      "this size is often a currency redenomination rather than inflation</b>: the " +
      "unit changed, not the price. The build logs every country whose rate moves " +
      "further than any currency should.");
  }
  document.getElementById("wtWarn").innerHTML = '<div class="warnbox">' + warn.join("<br>") + "</div>";

  chart(chartId, {
    type:"line", data:{labels:grid, datasets:ds},
    options:{ interaction:{mode:"index", intersect:false},
      plugins:{ legend:{display:false},
        tooltip:{ callbacks:{
          label:function (it) {
            var v = it.dataset.rawData ? it.dataset.rawData[it.dataIndex] : it.parsed.y;
            return v == null ? null : it.dataset.label + ": " +
              (isLevel ? "$" + v.toFixed(2) + UNIT_OF[unitCode]
                : isIndex ? v.toFixed(1)
                : Math.abs(v) >= 1000 ? pctTick(v)
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
          ticks: logY ? {callback:function (v) { return pctTick(symlogInv(v)); }} : {},
          title:{display:true, text: isLevel ? "US$ per " + UNIT_SHORT[unitCode] + " (fitted)"
            : isIndex ? "Index, " + baseP + " = 100"
            : "% change vs " + changeLabel(months, word) +
              (cpiOn ? ", local currency" : ", US$") +
              (logY ? " — log scale" : "")} },
        x:{ grid:{display:false}, ticks:{maxRotation:0, autoSkip:true, maxTicksLimit:14} } } }
  });

  /* read the lead line off what is actually drawn, not off the raw series —
     the window and the smoothing both change what the number should say */
  var lp = ds.length ? (ds[0].rawData || ds[0].data) : [],
    first = null, last = null, lastP = null;
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
      'thing. They still count in the price <i>changes</i> on the ' + HOME_TAB +
      ' tab.</div>'
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
  /* The external benchmark sits under the ranking and answers the same
     question about the same countries, so it is drawn with it. */
  renderPppBench();

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
    'the <span class="linkish" onclick="APP.go(\'world\')">' + HOME_TAB +
    "</span> tab, which is " +
    "built item by item and then averaged.");
  /* A catch-all leaf holds whatever did not resolve to a named sibling, so one
     country's is not the other's. Ranking them against each other is the figure
     `publish` has withheld since it was written. */
  if (isResidual(S.node)) return cmpNothing(
    "<b>" + esc(title(S.node)) + "</b> is a catch-all category — it holds whatever could " +
    "not be placed on a named item, and what lands in it differs from one country to the " +
    "next. A price per unit for it is not comparable across countries, so none is shown. " +
    'Its price <i>changes</i> are still on the <span class="linkish" ' +
    "onclick=\"APP.go('world')\">" + HOME_TAB + "</span> tab.");
  var unit = DATA.unitIdx[ui];
  var gmed = ((DATA.nodeMeta[S.node] || {}).gmed || {})[unit];

  /* Always US dollars here, with no switch to say otherwise. The bars refused
     to honour a local-currency setting anyway and printed a warnbox saying so,
     which is the worst of both: a control that does nothing and an apology for
     it. Two hundred currencies have no common ruler and cannot be ranked, so
     the reading is one reading. The cell's own local price is still printed
     beside the dollar one in the tooltip, because it is a true fact about that
     country's shelf; it is simply never what the bars are sorted on. */
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
        /* A cell carrying an imputed month is outlined rather than recoloured:
           the fill already says where the reading came from, and this says
           whether every month behind it was actually observed. Same idea as
           the hollow diamond on a line. */
        borderColor: INK,
        borderWidth: plot.map(function (r) { return r.c.imp > 0 ? 1.4 : 0; }),
        borderRadius:3 }] },
    options:{ indexAxis:"y",
      onClick:function (e, els) { if (els.length) { S.country = plot[els[0].index].c.country; APP.go("trends"); } },
      plugins:{ legend:{display:false}, tooltip:{ callbacks:{ label:function (t) {
        var r = plot[t.dataIndex], c = r.c, out = [];
        var loc = fmtLocal(c.loc, c.cur);
        out.push("$" + r.usd.toFixed(2) + " " + UNIT_LABEL[c.unit] +
          (loc ? "  ·  " + loc : ""));
        if (r.ratio) out.push("vs world median: " + pct(r.ratio - 1));
        out.push(c.obs + " observations · " + c.src + " source" + (c.src > 1 ? "s" : ""));
        out.push("dispersion (log MAD): " + (c.mad == null ? "—" : c.mad.toFixed(2)));
        out.push("period: " + c.per);
        if (c.flag) out.push("⚠ outside plausible bounds");
        if (c.mod >= 0.5) out.push("⚠ modelled, not observed retail");
        if (c.mix) out.push("⚠ mixed currencies in cell");
        if (c.imp > 0) out.push("◇ includes imputed months");
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
    else seen[r.c.src === 1 ? "one" : "many"] = 1;
    if (r.c.imp > 0) seen.imp = 1; });
  function sw(col, txt) { return '<span><i class="sw" style="background:' + col + '"></i>' + txt + "</span>"; }
  var leg = [];
  if (seen.many) leg.push(sw(PAL[0], "two or more sources"));
  if (seen.one) leg.push(sw(PAL[0] + "66", "a single source"));
  if (seen.mod) leg.push(sw(PAL[5], "modelled, not an observed shelf price"));
  if (seen.flag) leg.push(sw(DEAR, "outside plausible bounds"));
  if (seen.imp) leg.push('<span><i class="sw" style="background:transparent;border:1.4px solid ' +
    INK + '"></i>outlined: some months behind it are imputed</span>');
  document.getElementById("cmpLegend").innerHTML = leg.join("");

  /* table — each column declares its own type so the comparator never subtracts text */
  var CMP_COLS = {
    name:  {label:"Country",  cls:"",    kind:"text", get:function (r) { return r.name; }},
    /* Sorted on the dollar figure and only ever on it: this column is a
       cross-country ranking, and the local prices beside it are in a different
       currency on every row. */
    val:   {label:"Price",    cls:"num", kind:"num",  get:function (r) { return r.usd; }},
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
        '<td class="num">' + fmtBoth(c.usd, c.loc, c.cur) + "</td>" +
        '<td class="num">' + (r.ratio ? pct(r.ratio - 1, 0) : "—") + "</td>" +
        '<td class="num">' + c.obs + "</td>" +
        '<td class="num">' + c.src + "</td>" +
        '<td class="num">' + (c.mad == null ? "—" : c.mad.toFixed(2)) + "</td>" +
        "<td>" + c.per + "</td>" +
        "<td>" + flagPills(c) + "</td></tr>"; }).join("") + "</tbody>";
  setHtmlIfPresent("cmpFlagKey", flagKeyHtml());

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
/* Every pill carries its own explanation, because the word on it is the
   build's vocabulary and not the reader's. The same sentences are set out in
   full under each table by `flagKeyHtml`. */
function pill(k, cls) {
  return '<span class="pill ' + cls + '" title="' + esc(flagTitle(k)) + '">' +
    k + "</span>";
}
function flagPills(c) {
  var p = [];
  if (c.flag) p.push(pill("implausible", "bad"));
  if (c.mod >= 0.5) p.push(pill("modelled", "mod"));
  if (c.mix) p.push(pill("mixed FX", "warn"));
  if (c.der > 0.5) p.push(pill("derived qty", "warn"));
  if (c.src === 1) p.push(pill("1 source", "warn"));
  if (c.imp > 0) p.push(pill("imputed", "mod"));
  if (!p.length) p.push(pill("clean", "ok"));
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
    return { c:c, name:title(c.node), ratio: g ? c.usd / g : null, gmed:g };
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
    esc(m.name || "") + " — most and least expensive" +
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
        var r = show[t.dataIndex], loc = fmtLocal(r.c.loc, r.c.cur);
        /* Both currencies, because this is one country's own shelf: the dollar
           is what every other view is denominated in and the local figure is
           what somebody standing in the shop would recognise. */
        return [ fmtUsd(r.c.usd) + " " + UNIT_LABEL[r.c.unit] +
                   (loc ? "  ·  " + loc : ""),
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
    /* Sorted on the US$ figure: the local one beside it is in whichever
       currency the cell was quoted in, and a column that sorted 89,000 VND
       above $12 would be sorting the currencies. */
    val:   {label:"Price",    cls:"num", kind:"num",  get:function (r) { return r.c.usd; }},
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
        '<td class="num">' + fmtBoth(c.usd, c.loc, c.cur) + "</td>" +
        '<td class="num">' + (r.ratio ? pct(r.ratio - 1, 0) : "—") + "</td>" +
        '<td class="num">' + c.obs + "</td>" +
        '<td class="num">' + c.src + "</td>" +
        '<td class="num">' + (c.mad == null ? "—" : c.mad.toFixed(2)) + "</td>" +
        "<td>" + c.per + "</td><td>" + flagPills(c) + "</td></tr>"; }).join("")
      : '<tr><td colspan="9" class="empty">Nothing priced here under the current filters.</td></tr>') +
    "</tbody>";
  setHtmlIfPresent("ctryFlagKey", flagKeyHtml());

  renderWaterfall();
}

/* =====================================================================
   4. TRENDS & FX
   ===================================================================== */
/* The series exactly as the payload shipped it, fills included.

   This function used to strip the imputed months out unless a toggle was on,
   which meant the screen a reader landed on was the one with holes in it and
   the fills were something you had to know to ask for. The objection that
   toggle answered -- an imputed point being indistinguishable from a measured
   one -- is answered by the DRAWING instead: a fill is a hollow diamond on a
   line and a marked cell in a table, everywhere it appears. So the filter is
   gone and this is a lookup. */
function seriesFor(ci, ni, ui) {
  return DATA.series[ci + "|" + ni + "|" + ui] || null;
}
var HAS_IMPUTED = (function () {
  var k, ks = Object.keys(DATA.series || {});
  if (DATA.cells.imp) return true;
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
    /* `imp` has to come along. It did not, and the consequence was that the
       hollow-diamond treatment below never fired once: with the old toggle off
       the fills were stripped upstream, and with it on they were dropped here
       — so a filled month was drawn as an ordinary point either way, which is
       the one thing the whole design said it would never do. */
    return s ? {p:s.p, usd:s.usd, loc:s.loc, n:s.n, imp:s.imp,
                kind:"median", leaves:null} : null;
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

  /* Drawn first and unconditionally: it is a statement about the COUNTRY, and
     a category with no series must not take the country's currency split down
     with it. */
  renderFxBars(ci);

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
  /* All three lines, always. The "Remove FX" switch dropped two of them and
     was the same question the US$/local switch asked: which currency am I in.
     Showing the local price, the dollar price and the rate together is what
     makes the answer readable — the gap between the first two IS the third. */
  ds.push({label:"US$ price", data:onGrid(grid, s.p, idxUsd), borderColor:PAL[0],
           backgroundColor:PAL[0] + "22", borderWidth:2.4, tension:.2,
           pointRadius:pointRadius(2.5), pointStyle:pointStyle(),
           pointBackgroundColor:pointFill(PAL[0]), pointBorderColor:PAL[0],
           spanGaps:true, segment:GAP_SEG});
  ds.push({label:"Exchange rate (local per US$)", data:onGrid(grid, s.p, idxFx), borderColor:PAL[1],
           borderWidth:1.8, borderDash:[3,3], tension:.2, pointRadius:0, spanGaps:true});
  ds.push({label: (isIdx ? "Items" : "Observations") + " behind each point", type:"bar", yAxisID:"y2",
           data:onGrid(grid, s.p, s.n), backgroundColor:"#b9b5aa55", borderWidth:0, order:99});

  var gaps = grid.length - s.p.length;
  var warn = [];
  if (anyImp) {
    var nImp = impGrid.reduce(function (a, b) { return a + b; }, 0);
    warn.push("<b>" + nImp + " of " + s.p.length + "</b> points on this line are " +
      "<b>imputed</b> and drawn as hollow diamonds: no price was observed in those " +
      "months and the value is a model estimate of what the item was doing. Filled and " +
      "measured points are always distinguishable on sight; hover any point to see which " +
      "it is.");
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
               "IMPUTED — no price was observed this month, this is a model estimate"]
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

  /* The currency leg of a price move is ONE NUMBER for the whole country.
     What is left is per product, and that split now has a chart of its own
     above this one; all this panel does is state the three readings for the
     item on screen, over the same window that chart uses. */
  var win = countryWindow(ci);
  function at(arr, p) { var i = s.p.indexOf(p); return i >= 0 && arr[i] > 0 ? arr[i] : null; }
  var wb = {usd:at(s.usd, win.lo), loc:at(s.loc, win.lo),
            fx:fxMap[win.lo] > 0 ? fxMap[win.lo] : null};
  var wl = {usd:at(s.usd, win.hi), loc:at(s.loc, win.hi),
            fx:fxMap[win.hi] > 0 ? fxMap[win.hi] : null};
  var dUsd = wb.usd && wl.usd ? wl.usd / wb.usd - 1 : null;
  var dLoc = wb.loc && wl.loc ? wl.loc / wb.loc - 1 : null;
  var dFx  = wb.fx && wl.fx ? wl.fx / wb.fx - 1 : null;
  document.getElementById("trDeco").innerHTML = [
    box("US$ price", pct(dUsd), dUsd),
    box("Local price (FX removed)", pct(dLoc), dLoc),
    box("Exchange rate, local per US$", pct(dFx), dFx),
    '<div class="b"><div class="l">' + (win.lo || "?") + " → " + (win.hi || "?") +
      ' · the same window, and the same exchange rate, for every item here</div>' +
      '<div class="v" style="font-size:14px;font-weight:600;line-height:1.45">' +
      (dUsd != null
        ? "The currency leg is the country’s and is identical for every product; " +
          "only the local-price leg belongs to <b>" + esc(title(S.node)) + "</b>."
        : dFx != null
        ? "<b>" + esc(title(S.node)) + "</b> is not priced in both " + win.lo + " and " +
          win.hi + ", so its own move cannot be split over this window. The exchange rate " +
          "beside this is the country’s and stands."
        : "FX split unavailable") + "</div></div>"
  ].join("");

}

/* =====================================================================
   THE CURRENCY EFFECT IS A SCALAR
   ---------------------------------------------------------------------
   An exchange-rate move shifts every price in the country by the same
   proportion. It is one number, not a property of rice or of beer, and a
   panel that reported a different one per product was reporting the
   arithmetic of its own windows.

   So this chart states it once, as a bar every product shares, and puts
   the product's own move on top of it. In logs the two add exactly:

       d ln P_usd  =  d ln P_local  +  ( - d ln FX )

   where FX is local currency per US dollar. Each bar therefore runs from
   zero to the shared currency leg and then on to that product's total, so
   the segment beyond the shared one is the real price change with the
   currency netted out. Read the second segment across products and the
   currency is gone from the comparison, which is the entire point.

   THE WINDOW IS TWELVE MONTHS to the country's latest data, not its whole
   span. The span was tried and it does not work: over Vietnam's full
   2013-12 to 2026-09 exactly ONE product is priced at both endpoints, and
   Japan, Fiji and Tonga are the same. Over twelve months it is 61, 208, 87
   and 26. A decomposition nobody can see is not the more rigorous one.
   ===================================================================== */
function monthsBack(p, k) {
  var a = p.split("-"), n = +a[0] * 12 + (+a[1] - 1) - k, m = n % 12 + 1;
  return Math.floor(n / 12) + "-" + (m < 10 ? "0" : "") + m;
}
var FX_WIN_MONTHS = 12;
/* The two months every currency split on this tab is measured over: the last
   month this COUNTRY has a published series in, and the same month a year
   before it. One window per country is the whole point — read the endpoints
   off each item and the exchange rate stops being a country-level number. */
function countryWindow(ci) {
  var hi = null, pre = ci + "|";
  Object.keys(DATA.series).forEach(function (k) {
    if (k.indexOf(pre) !== 0) return;
    var ps = DATA.series[k].p;
    if (!ps.length) return;
    if (hi == null || ps[ps.length - 1] > hi) hi = ps[ps.length - 1];
  });
  return {lo:hi == null ? null : monthsBack(hi, FX_WIN_MONTHS), hi:hi};
}
function renderFxBars(ci) {
  var slug = DATA.ctyIdx[ci], m = DATA.cty[slug] || {};
  var fsel = document.getElementById("fxbCtry");
  if (fsel) {
    if (fsel.options.length !== DATA.ctyIdx.length) {
      fsel.innerHTML = DATA.ctyIdx.slice().sort(function (a, b) {
        return DATA.cty[a].name < DATA.cty[b].name ? -1 : 1; })
        .map(function (x) {
          return '<option value="' + x + '">' + esc(DATA.cty[x].name) + "</option>"; })
        .join("");
    }
    fsel.value = slug;
  }
  var win = countryWindow(ci), fxMap = fxOf(slug);
  var warnEl = document.getElementById("fxbWarn");
  function nothing(msg) {
    warnEl.innerHTML = '<div class="warnbox">' + msg + "</div>";
    document.getElementById("fxbLead").innerHTML = "";
    document.getElementById("fxbLegend").innerHTML = "";
    sizeCanvas("cFxBars", 90);
    chart("cFxBars", {type:"bar", data:{labels:[], datasets:[]}});
  }
  if (!win.hi) return nothing("No monthly series for " +
    esc(m.name || slug) + " at all, so there is nothing to split.");
  var r0 = fxMap[win.lo], r1 = fxMap[win.hi];
  if (!(r0 > 0) || !(r1 > 0)) return nothing(
    "No exchange rate for <b>" + esc(m.name || slug) + "</b> in both " + win.lo +
    " and " + win.hi + ", so a US$ move cannot be split into a currency leg and a " +
    "price leg over this window.");
  /* d ln P_usd = d ln P_local − d ln FX, so the CURRENCY's contribution to a
     dollar price is minus the rate's own move: a currency that loses ground
     against the dollar (FX up) pulls dollar prices down. */
  var fxLeg = -Math.log(r1 / r0);

  var rows = [];
  DATA.nodeIdx.forEach(function (code, ni) {
    if (!isLeaf(code) || isResidual(code)) return;
    for (var ui = 0; ui < DATA.unitIdx.length; ui++) {
      var ser = DATA.series[ci + "|" + ni + "|" + ui];
      if (!ser) continue;
      var a = ser.p.indexOf(win.lo), b = ser.p.indexOf(win.hi);
      if (a < 0 || b < 0 || !(ser.usd[a] > 0) || !(ser.usd[b] > 0)) continue;
      rows.push({code:code, name:title(code), unit:DATA.unitIdx[ui],
        total:Math.log(ser.usd[b] / ser.usd[a]),
        imp:!!(ser.imp && (ser.imp[a] || ser.imp[b]))});
      return;
    }
  });
  rows.forEach(function (r) { r.real = r.total - fxLeg; });

  /* The rate is quoted LOCAL PER US DOLLAR, so a rise in it is the local
     currency losing ground and it makes every dollar price smaller. Saying
     which direction which way round is the whole difficulty of this sentence,
     so it names the rate rather than "the currency" and then says what that
     did to a dollar price. */
  var moved = (r1 / r0 - 1) * 100;
  document.getElementById("fxbLead").innerHTML =
    "<b>" + esc(m.name || slug) + "</b> &middot; " + win.lo + " &rarr; " + win.hi +
    ". The exchange rate — local currency per US dollar — moved <b>" +
    (moved >= 0 ? "+" : "") + moved.toFixed(1) + "%</b> over this window, so the " +
    "local currency " + (moved >= 0 ? "bought fewer dollars" : "bought more dollars") +
    " at the end than at the start. On its own that " +
    (fxLeg >= 0 ? "adds <b>+" : "takes <b>") + (fxLeg * 100).toFixed(1) +
    " log points</b> " + (fxLeg >= 0 ? "to" : "off") + " <i>every</i> US$ price in the " +
    "country alike — the shared bar below, identical on every row. Whatever runs " +
    "beyond it is that product's own price move.";

  if (!rows.length) return nothing(
    "No product in <b>" + esc(m.name || slug) + "</b> is priced in both " + win.lo +
    " and " + win.hi + ", so nothing can be split over this window.");
  warnEl.innerHTML = "";

  /* Widest real moves either way, so the chart is the story and not the
     catalogue. Sorted on the REAL leg: the currency leg is the same everywhere,
     so sorting on the total would sort on the real leg with a constant added —
     the point of netting it out is precisely that it does not rank anything. */
  rows.sort(function (a, b) { return b.real - a.real; });
  var FXB_MAX = 24, show = rows;
  if (rows.length > FXB_MAX) show = rows.slice(0, FXB_MAX / 2)
    .concat(rows.slice(-FXB_MAX / 2));

  sizeCanvas("cFxBars", Math.max(220, show.length * 21 + 70));
  chart("cFxBars", {
    type:"bar",
    data:{
      labels: show.map(function (r) {
        return (r.imp ? "◇ " : "") + r.name + " (" + UNIT_SHORT[r.unit] + ")"; }),
      datasets:[
        { label:"Exchange rate — the same for every product",
          data: show.map(function () { return [0, fxLeg * 100]; }),
          backgroundColor:PAL[1], borderWidth:0 },
        { label:"The product's own price change",
          data: show.map(function (r) { return [fxLeg * 100, r.total * 100]; }),
          backgroundColor: show.map(function (r) { return r.real >= 0 ? DEAR : CHEAP; }),
          borderWidth:0 }
      ]},
    options:{ indexAxis:"y",
      onClick:function (e, els) { if (els.length) APP.set("node", show[els[0].index].code); },
      plugins:{ legend:{display:false}, tooltip:{ callbacks:{
        title:function (it) { return show[it[0].dataIndex].name; },
        label:function (it) {
          var r = show[it.dataIndex];
          return [
            "US$ price: " + (r.total >= 0 ? "+" : "") + (r.total * 100).toFixed(1) + " log %",
            "of which the currency: " + (fxLeg >= 0 ? "+" : "") + (fxLeg * 100).toFixed(1) +
              " log %, the same for every product",
            "of which the price itself: " + (r.real >= 0 ? "+" : "") +
              (r.real * 100).toFixed(1) + " log %"
          ].concat(r.imp ? ["one endpoint is an imputed month"] : []); } } } },
      /* The category axis is stacked so the two datasets share one row rather
         than being dodged into two; the value axis is NOT, because each bar
         already carries its own [from, to] and stacking them would add the
         shared leg in twice. */
      scales:{
        x:{ stacked:false, grid:{color:RULE}, position:"top",
            title:{display:true, text:"Change over the 12 months to " + win.hi +
              " (log %, the two parts add up)"} },
        y:{ stacked:true, ticks:{font:{size:11}, autoSkip:false}, grid:{display:false} } } }
  });

  document.getElementById("fxbLegend").innerHTML =
    '<span><i class="sw" style="background:' + PAL[1] + '"></i>the exchange rate, ' +
    "identical on every row</span>" +
    '<span><i class="sw" style="background:' + DEAR + '"></i>the price itself rose</span>' +
    '<span><i class="sw" style="background:' + CHEAP + '"></i>the price itself fell</span>' +
    (rows.length > show.length
      ? "<span>" + rows.length + " products split; the " + show.length +
        " widest real moves are drawn</span>"
      : "<span>" + rows.length + " product" + (rows.length === 1 ? "" : "s") +
        " priced in both months</span>");
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

/* The client-side twin of `sources.ladder_agg`. Fold a set of leaf readings up
   to `toDepth` one COICOP level at a time, so every child of a node counts once
   at its parent however many leaves the taxonomy split it into. A flat mean over
   the leaves of a class hands the class to whichever of its subclasses is
   enumerated most finely, which is a fact about the taxonomy and not about
   prices. Ragged branches are fine: a leaf that terminates above `toDepth`
   simply waits at its own level until the fold reaches it. */
function ladderMean(items, toDepth) {
  var lvl = {}, bucket = {};
  items.forEach(function (x) { (bucket[x.code] = bucket[x.code] || []).push(x.r); });
  var d = 0;
  Object.keys(bucket).forEach(function (c) {
    lvl[c] = mean(bucket[c]);
    d = Math.max(d, c.split(".").length);
  });
  while (d > toDepth) {
    var up = {};
    Object.keys(lvl).forEach(function (c) {
      if (c.split(".").length !== d) return;
      var p = c.slice(0, c.lastIndexOf("."));
      (up[p] = up[p] || []).push(lvl[c]);
      delete lvl[c];
    });
    Object.keys(up).forEach(function (p) { lvl[p] = mean(up[p]); });
    d -= 1;
  }
  var vals = Object.keys(lvl).map(function (c) { return lvl[c]; });
  return vals.length ? mean(vals) : null;
}

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
  /* Each group is split by SIGN before anything is drawn, and this is the fix
     for a real defect: the chart used to draw one net bar per group, so a
     group holding nine items above the world median and fourteen below became
     a single downward bar and the nine were invisible. Over the EAP build that
     was not a corner case -- every one of Vietnam's 18 groups and all 14 of
     Indonesia's came out net-negative, so the chart contained NO upward bar at
     all while the table beside it listed 24 and 7 items priced above the
     world, sorted dearest-first at the top of the screen. The gap really was
     negative; the claim that nothing pushed upward was not.

     `up` and `dn` are the two halves of the same sum, so `up + dn` is exactly
     the contribution the single bar carried before and the bars still add up
     to the total. Nothing about the arithmetic changed -- what changed is that
     both signs reach the canvas. */
  var all = Object.keys(by).map(function (cls) {
    var a = by[cls], up = 0, dn = 0;
    a.forEach(function (r) { if (r > 0) up += r; else dn += r; });
    return {cls:cls, n:a.length, mean:mean(a), up:up / N, dn:dn / N,
            nup:a.filter(function (r) { return r > 0; }).length,
            contrib:(a.length / N) * mean(a)};
  });
  var total = all.reduce(function (p, g) { return p + g.contrib; }, 0);

  /* Twenty labelled bars is a list, not an explanation. Keep the ten that move
     the total most and fold the tail into one bar, so nothing is dropped from
     the arithmetic and the reader still gets a story. The fold carries its own
     up and down halves for the same reason every other bar does. */
  var WF_MAX = 10;
  var groups = all.slice().sort(function (a, b) {
    return Math.abs(b.contrib) - Math.abs(a.contrib); });
  var tail = groups.slice(WF_MAX);
  groups = groups.slice(0, WF_MAX);
  function sum(rows, k) {
    return rows.reduce(function (p, g) { return p + g[k]; }, 0); }
  if (tail.length > 1) groups.push({
    cls:null, rest:tail.length, n:sum(tail, "n"), nup:sum(tail, "nup"),
    up:sum(tail, "up"), dn:sum(tail, "dn"), contrib:sum(tail, "contrib") });
  else groups = groups.concat(tail);
  groups.sort(function (a, b) { return b.contrib - a.contrib; });
  var own = mean(gaps.map(function (g) { return g.r; }));
  var grossUp = sum(all, "up"), grossDn = sum(all, "dn");

  var labels = [], up = [], dn = [], tot = [], colors = [], meta = [], run = 0;
  groups.forEach(function (g) {
    labels.push(g.cls ? shortTitle(g.cls) : g.rest + " smaller groups");
    up.push([run * 100, (run + g.up) * 100]);
    dn.push([(run + g.up) * 100, (run + g.up + g.dn) * 100]);
    tot.push(null);
    colors.push(g.contrib >= 0 ? DEAR : CHEAP);
    meta.push(g);
    run += g.contrib;
  });
  labels.push("Overall gap");
  up.push(null); dn.push(null); tot.push([0, total * 100]);
  colors.push(INK);
  meta.push(null);

  chart("cWaterfall", {
    type:"bar",
    data:{ labels:labels, datasets:[
      { label:"pushed up by items priced above the world", data:up,
        backgroundColor:DEAR, borderWidth:0, borderRadius:2, borderSkipped:false },
      { label:"pulled down by items priced below it", data:dn,
        backgroundColor:CHEAP, borderWidth:0, borderRadius:2, borderSkipped:false },
      { label:"everything together", data:tot,
        backgroundColor:INK, borderWidth:0, borderRadius:2, borderSkipped:false }
    ]},
    /* The category axis is stacked so the three datasets share one column slot
       instead of being dodged into three thin bars; the value axis is NOT,
       because every bar already carries its own [from, to] range. */
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
        var out = ["Net contribution " + (g.contrib >= 0 ? "+" : "") +
          (g.contrib * 100).toFixed(1) + " log % of the gap",
          "  " + g.nup + " item" + (g.nup === 1 ? "" : "s") + " above the world push " +
            "+" + (g.up * 100).toFixed(1),
          "  " + (g.n - g.nup) + " below it pull " + (g.dn * 100).toFixed(1)];
        if (g.cls) out.push("This group alone runs " + (g.mean >= 0 ? "+" : "") +
          ((Math.exp(g.mean) - 1) * 100).toFixed(0) + "% vs the world");
        out.push(g.n + " matched item" + (g.n === 1 ? "" : "s") + " of " + N +
          " (" + (g.n / N * 100).toFixed(0) + "% of the weight)");
        return out; } } } },
      scales:{ y:{ grid:{color:RULE},
          title:{display:true, text:"Contribution to the gap (log %, these add up)"} },
        x:{ stacked:true, grid:{display:false},
            ticks:{maxRotation:52, minRotation:35, font:{size:10.5}} } } }
  });

  document.getElementById("wfLegend").innerHTML =
    '<span><i class="sw" style="background:' + DEAR + '"></i>pushed up by the items ' +
    "priced above the world</span>" +
    '<span><i class="sw" style="background:' + CHEAP + '"></i>pulled down by the ones ' +
    "priced below it</span>" +
    '<span><i class="sw" style="background:' + INK + '"></i>the two together</span>';

  function nm(g) { return "<b>" + esc(g.cls ? proseTitle(g.cls).toLowerCase()
    : g.rest + " smaller groups") + "</b>"; }
  var upG = groups.filter(function (g) { return g.contrib > 0; }).slice(0, 3);
  var dnG = groups.filter(function (g) { return g.contrib < 0; }).slice(-3).reverse();
  var nUp = gaps.filter(function (g) { return g.r > 0; }).length;
  document.getElementById("wfNote").innerHTML =
    "<b>" + esc(m.name || slug) + "</b> sits <b>" +
    (Math.exp(total) * 100).toFixed(0) + "</b> against a world median of 100 on this " +
    "decomposition" +
    (upG.length ? ", carried mostly by " + upG.map(nm).join(", ") : "") +
    (dnG.length ? ", and held down by " + dnG.map(nm).join(", ") : "") + ". " +
    "Built on " + N + " matched items across " + all.length + " category groups. " +
    /* The single sentence that stops the chart being read as "nothing here is
       expensive": every bar is a NET of two pulls, and both are on it. */
    "<b>" + nUp + " of those " + N + "</b> items are priced above the world median and " +
    "together push <b>+" + (grossUp * 100).toFixed(1) + " log %</b>; the other <b>" +
    (N - nUp) + "</b> pull <b>" + (grossDn * 100).toFixed(1) + "</b>. Every bar shows " +
    "both halves, so a group whose net is downward still shows what pushed the other " +
    "way. " +
    /* This used to have to explain that the two figures disagreed because one
       averaged the gaps and the other took their median. They now use the same
       estimator, so what is left to explain is the only difference that
       remains: the published level is built on the eligible basket -- the
       leaves priced almost everywhere -- while this decomposes every matched
       item the country has. */
    "The published price level is <b>" +
    (m.level_ok ? m.level.toFixed(0) : (Math.exp(own) * 100).toFixed(0)) +
    "</b>. Both average the differences, and they part company twice. The " +
    "published level uses only the leaves priced across almost every country, " +
    "where this decomposes everything this country prices; and the level folds " +
    "those leaves up the COICOP tree a level at a time, where these bars weight " +
    "each group by how many matched items it holds. That weighting is what makes " +
    "the bars add up to the total, which is the only thing a decomposition is " +
    "for, so it is kept here and nowhere else.";
}

/* Category down the side, country across the top -- the same orientation as
   the dashboard's heat table, so the two can be read side by side.

   One reading of a cell: the gap from the world median for the same items,
   matched leaf by leaf. The US$-per-unit reading this table used to lead with
   was a median dollars-per-kilo taken ACROSS a whole COICOP class, and there
   is no such quantity -- the members of a class are not the same good, so
   their unit values are not one distribution to take a median of. The gap is
   built per leaf and then averaged UP THE TREE, subclass by subclass, so it
   survives the aggregation the level does not. Each row still carries one unit, chosen as the unit most of
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
      code: c.node, unit: c.unit, imp: c.imp,
      r: g > 0 ? Math.log(c.usd / g) : null});
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
      var usable = same.filter(function (x) { return x.r != null; });
      cells[cls] = {r:ladderMean(usable, cls.split(".").length), n:same.length,
                    imp:same.filter(function (x) { return x.imp > 0; }).length};
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
        arg(r.slug) + ')"><span>' + esc(r.name) + "</span></th>"; }).join("") + "</tr></thead>";

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
      /* Same mark as the hollow diamond on a line, at grid scale: this cell
         rests in part on months a model filled rather than months anyone
         priced. It says WHICH cells, never how much to trust them. */
      return '<td class="c" style="background:' + heatColor(cell.r) + ';color:#1b211f" title="' +
        esc(r.name) + " · " + esc(title(cls)) + ": " + lab + "% vs the world median" +
        ", over " + cell.n + " matched items" +
        (cell.imp ? ", " + cell.imp + " of them carrying imputed months" : "") +
        '">' + lab + (cell.imp ? '<span class="impm">◇</span>' : "") +
        "</td>"; }).join("") + "</tr>"; }).join("") +
    "</tbody>";
  document.getElementById("hmTbl").innerHTML = head + body;

  document.getElementById("hmSub").innerHTML =
    "Each category group against the world median for the same items. " +
    "Red is more expensive than the world, blue cheaper.";

  var cut = Object.keys(rowN).filter(function (c) { return rows.indexOf(c) < 0; })
    .sort(function (a2, b2) { return rowN[b2] - rowN[a2]; });
  var stops = [-1, -0.6, -0.3, 0, 0.3, 0.6, 1];
  document.getElementById("hmRamp").innerHTML =
    '<span class="lab">cheaper than the world</span>' +
    stops.map(function (t) { return '<i style="background:' +
      hexMix(HM_MID, t >= 0 ? DEAR : CHEAP, Math.pow(Math.abs(t), 0.8)) + '"></i>'; }).join("") +
    '<span class="lab">more expensive</span>' +
    '<span class="lab" style="margin-left:14px">' +
    'full colour at &plusmn;100% &middot; ' +
    'hatched: fewer than ' + HM_MIN_LEAVES + ' matched items &middot; ' +
    '<span class="impm">◇</span> rests partly on imputed months &middot; ' + rows.length +
    " groups &times; " + shown.length + " countries" +
    (cut.length ? " &middot; " + cut.length + " groups too thinly covered to show, " +
       "widest of them " + esc(proseTitle(cut[0])) + " at " + rowN[cut[0]] + " countries" : "") +
    "</span>";
}


/* =====================================================================
   AGAINST THE WORLD MEDIAN, ROW BY ROW
   =====================================================================
   Two cards that used to sit on a "Global View" tab of their own, shown only
   in a regional build. They are on the same tab as the heatmap now, in both
   builds, and they answer the heatmap's question one level up: not "where is
   this category expensive" but "how does this whole shelf compare".

   ONE thing changes with the build, and it is who is on the rows.

     global build   the world's six regions, from `nodeMeta[code].rmed[label]`
                    -- a median taken over each region, published only where at
                    least `qa.benchmark.min_countries` of its countries price
                    the item.
     regional build the countries this build carries, from their own cells --
                    the same cells the heatmap above is built from, so the two
                    tables cannot disagree about a country.

   A regional build has no business ranking regions it does not hold; a global
   build has 200 countries and no room for them. Hence the split.

   What does NOT change is the yardstick. Both branches divide by
   `nodeMeta[code].gmed`, the world median for that item in that unit, computed
   over the whole corpus BEFORE any region filter. So "vs the world median" is
   true on every label in either build, and the silent swap
   `aggregate.build_payload` warns about -- a screen saying "vs world" over a
   number that is not -- cannot happen here.

   Gaps are built per LEAF, on a unit both sides price, and only then folded up
   the COICOP tree by `ladderMean`, so a finely split branch cannot outvote its
   neighbours. A median taken across a whole class is not a quantity anyone can
   price, which is why nothing here takes one.
   ===================================================================== */
var GV_MIN_LEAVES = 3, GV_MIN_ROWS = 3;

/* Every world region the payload carries a median for. `rmed` mixes regions
   and subregions in one flat map, so the region list is intersected with
   WORLD_REGIONS; an empty intersection means the labels have been renamed and
   the grid falls back to every label it can see. */
function gvRegions() {
  var seen = {};
  DATA.nodeIdx.forEach(function (code) {
    var rm = (DATA.nodeMeta[code] || {}).rmed || {};
    Object.keys(rm).forEach(function (lab) { seen[lab] = 1; });
  });
  var labs = Object.keys(seen);
  var known = labs.filter(function (l) { return WORLD_REGIONS.indexOf(l) >= 0; });
  return (known.length ? known : labs).sort();
}
/* One region's gap from the world for every leaf it and the world both price,
   on the leaf's own dominant unit. A region median and a world median taken in
   different units are two different quantities, so the unit has to agree
   before the ratio means anything. */
function gvLeafGaps(region) {
  var out = [];
  DATA.nodeIdx.forEach(function (code) {
    if (!isLeaf(code) || isResidual(code)) return;
    var meta = DATA.nodeMeta[code] || {};
    var g = meta.gmed || {}, rm = (meta.rmed || {})[region];
    if (!rm) return;
    var dom = (meta.dom && g[meta.dom] > 0 && rm[meta.dom] > 0) ? meta.dom : null;
    var u = dom || DATA.unitIdx.filter(function (x) {
      return g[x] > 0 && rm[x] > 0; })[0];
    if (!u) return;
    out.push({code:code, cls:classOf(code), unit:u, r:Math.log(rm[u] / g[u])});
  });
  return out;
}

/* The rows, in whichever of the two shapes this build calls for. `gaps` is the
   same list either way -- one entry per leaf, carrying its class, its unit and
   the log ratio to the world median -- so everything below is written once.

   The country branch reads `classCellsFor`, the heatmap's own accessor, rather
   than re-deriving a country median: a second definition of "this country's
   price for this item" is exactly how two tables on one tab start disagreeing.
   It also means the Evidence strip moves this card in a regional build, which
   is the behaviour the heatmap beside it already has. */
function gvRows() {
  if (!IS_REGIONAL) {
    return gvRegions().map(function (R) {
      return {key:R, label:R, mine:R === BUILD_REGION, gaps:gvLeafGaps(R)};
    });
  }
  var out = [];
  DATA.ctyIdx.forEach(function (slug, ci) {
    var meta = DATA.cty[slug];
    if (!meta.level_ok) return;      /* only countries the ranking trusts */
    var per = classCellsFor(ci), gaps = [];
    Object.keys(per).forEach(function (cls) {
      per[cls].forEach(function (x) {
        if (x.r == null) return;
        gaps.push({code:x.code, cls:cls, unit:x.unit, r:x.r});
      });
    });
    if (gaps.length) out.push({key:slug, label:meta.name, mine:false, gaps:gaps});
  });
  return out;
}

function renderVsWorldGrid() {
  var tbl = document.getElementById("gvTbl");
  if (!tbl) return;
  /* What a row IS, in this build's words. Every count and every caption below
     uses it, so the two never drift apart. */
  var ROWWORD = IS_REGIONAL ? "country" : "region";
  var ROWWORDS = IS_REGIONAL ? "countries" : "regions";

  var rowsIn = gvRows();
  var per = {}, rowN = {}, overall = {}, lab = {}, mineOf = {};
  rowsIn.forEach(function (e) {
    lab[e.key] = e.label; mineOf[e.key] = e.mine;
    var by = {};
    e.gaps.forEach(function (x) { if (x.cls) (by[x.cls] = by[x.cls] || []).push(x); });
    var cells = {};
    Object.keys(by).forEach(function (cls) {
      if (by[cls].length < GV_MIN_LEAVES) return;
      cells[cls] = {r:ladderMean(by[cls], cls.split(".").length), n:by[cls].length};
      rowN[cls] = (rowN[cls] || 0) + 1;
    });
    per[e.key] = cells;
    /* The headline figure folds all the way to the division, so a place with
       forty kinds of rice and one kind of beef does not have its number
       decided by rice. Same ladder as the heatmap and the price level. */
    overall[e.key] = e.gaps.length ? {r:ladderMean(e.gaps, 1), n:e.gaps.length} : null;
  });

  var live = rowsIn.map(function (e) { return e.key; })
    .filter(function (k) { return overall[k]; });
  if (!live.length) {
    tbl.innerHTML = '<tbody><tr><td class="empty">This build carries nothing that ' +
      "can be set against the world median here.</td></tr></tbody>";
    setHtmlIfPresent("gvRamp", "");
    setHtmlIfPresent("gvLead", "");
    sizeCanvas("cGlobalBars", 90);
    chart("cGlobalBars", {type:"bar", data:{labels:[], datasets:[]}});
    return;
  }
  /* Most expensive first, which is the order every other ranking here uses. */
  live.sort(function (a, b) { return overall[b].r - overall[a].r; });

  /* A country list is dozens of rows where a region list is six, so the bar
     chart is sized off what it actually holds rather than off the fixed height
     the wrapper declares. The region row height is left exactly where it was so
     a global build draws this card at the size it always would have. */
  sizeCanvas("cGlobalBars",
    Math.max(180, live.length * (IS_REGIONAL ? 22 : 30) + 60));
  chart("cGlobalBars", {
    type:"bar",
    data:{ labels: live.map(function (k) { return lab[k]; }),
      datasets:[{ data: live.map(function (k) {
          return (Math.exp(overall[k].r) - 1) * 100; }),
        backgroundColor: live.map(function (k) {
          return overall[k].r >= 0 ? DEAR : CHEAP; }),
        borderColor: INK,
        borderWidth: live.map(function (k) { return mineOf[k] ? 1.6 : 0; }),
        borderRadius:3 }] },
    options:{ indexAxis:"y",
      plugins:{ legend:{display:false}, tooltip:{ callbacks:{ label:function (t) {
        var k = live[t.dataIndex], o = overall[k];
        return [ (Math.exp(o.r) - 1) * 100 >= 0
                   ? "+" + ((Math.exp(o.r) - 1) * 100).toFixed(0) + "% vs the world median"
                   : ((Math.exp(o.r) - 1) * 100).toFixed(0) + "% vs the world median",
                 o.n + " items matched against the world",
                 mineOf[k] ? "the region this dashboard is built from" : "" ]
          .filter(Boolean); } } } },
      scales:{ x:{ grid:{color:RULE}, position:"top",
          title:{display:true,
            text:"% above or below the world median, same items and same units"} },
        y:{ ticks:{font:{size:11.5}, autoSkip:false}, grid:{display:false} } } }
  });

  var rows = Object.keys(rowN)
    .filter(function (c) { return rowN[c] >= GV_MIN_ROWS; }).sort();
  var head = '<thead><tr><th class="ctry">Category</th>' +
    live.map(function (k) {
      return '<th class="ctyh' + (mineOf[k] ? " mine" : "") + '" title="' + esc(lab[k]) +
        (mineOf[k] ? " — the region this dashboard is built from" : "") +
        '"><span>' + esc(lab[k]) + "</span></th>"; }).join("") + "</tr></thead>";
  function cellHtml(k, cls) {
    var c = per[k][cls];
    if (!c || c.r == null) return '<td class="na" title="' + esc(lab[k]) + " · " +
      esc(title(cls)) + ': fewer than ' + GV_MIN_LEAVES + ' matched items"></td>';
    var v = (Math.exp(c.r) - 1) * 100;
    var l = Math.abs(v) >= 999 ? (v > 0 ? "+999" : "-999")
      : (v >= 0 ? "+" : "") + v.toFixed(0);
    return '<td class="c' + (mineOf[k] ? " mine" : "") + '" style="background:' +
      heatColor(c.r) + ';color:#1b211f" title="' + esc(lab[k]) + " · " + esc(title(cls)) +
      ": " + l + "% vs the world median, over " + c.n + ' matched items">' +
      l + "</td>";
  }
  var span = live.length + 1, seen = {};
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
  var body = "<tbody>" +
    '<tr class="gvall"><td class="ctry">Everything priced</td>' +
    live.map(function (k) {
      var o = overall[k], v = (Math.exp(o.r) - 1) * 100;
      var l = (v >= 0 ? "+" : "") + v.toFixed(0);
      return '<td class="c' + (mineOf[k] ? " mine" : "") + '" style="background:' +
        heatColor(o.r) + ';color:#1b211f" title="' + esc(lab[k]) + ": " + l +
        "% vs the world median, over " + o.n + ' matched items">' + l + "</td>";
    }).join("") + "</tr>" +
    rows.map(function (cls) {
      return band(cls) + '<tr><td class="ctry ind" title="' + esc(title(cls)) + '">' +
        esc(proseTitle(cls)) + '<span class="ru">vs world</span></td>' +
        live.map(function (k) { return cellHtml(k, cls); }).join("") + "</tr>";
    }).join("") + "</tbody>";
  tbl.innerHTML = head + body;

  var stops = [-1, -0.6, -0.3, 0, 0.3, 0.6, 1];
  setHtmlIfPresent("gvRamp",
    '<span class="lab">cheaper than the world</span>' +
    stops.map(function (t) { return '<i style="background:' +
      hexMix(HM_MID, t >= 0 ? DEAR : CHEAP, Math.pow(Math.abs(t), 0.8)) + '"></i>'; }).join("") +
    '<span class="lab">more expensive</span>' +
    '<span class="lab" style="margin-left:14px">full colour at &plusmn;100% &middot; ' +
    "hatched: fewer than " + GV_MIN_LEAVES + " matched items &middot; " + rows.length +
    " groups &times; " + live.length + " " + ROWWORDS + "</span>");

  if (!IS_REGIONAL) {
    /* This card was only ever drawn in a regional build, on a tab a global
       build hid, so its lead could say "before this build was narrowed to
       <region>" unconditionally -- and in a global build BUILD_REGION is null,
       which rendered that as "narrowed to a region" about a build that was
       never narrowed at all. Now that the card is on a tab both builds show,
       the clause is written where it is true and left out where it is not. */
    setHtmlIfPresent("gvLead",
      "Every world region against the <b>world median for the same items in the same " +
      "units</b> &mdash; the identical yardstick every other figure in this dashboard " +
      "is measured against, taken over the whole corpus. " +
      "A region is priced by whichever retailers the corpus reaches inside it, so read " +
      "this as what the collected shelves say, not as a sample of the region. Where " +
      "fewer than " + benchMinCountries() + " countries in a region price an item, no " +
      "regional median is published for it and the cell is left hatched rather than " +
      "estimated.");
    return;
  }
  /* The regional lead says the same thing about countries, and then says where
     the region as a whole stands -- which no row carries any more, and which is
     the one figure a reader of a regional dashboard came for. It comes from
     `rmed`, the region's own published median, so it is the region measured
     against the world and not an average of the bars above it. */
  var ro = gvLeafGaps(BUILD_REGION);
  var rr = ro.length ? ladderMean(ro, 1) : null;
  setHtmlIfPresent("gvLead",
    "Every " + esc(BUILD_REGION) + " country against the <b>world median for the same " +
    "items in the same units</b> &mdash; the identical yardstick every other figure in " +
    "this dashboard is measured against, and one that was computed over the whole " +
    "corpus before this build was narrowed to " + esc(BUILD_REGION) + ". " +
    (rr != null
      ? "<b>" + esc(BUILD_REGION) + "</b> as a whole reads <b>" +
        ((Math.exp(rr) - 1) * 100 >= 0 ? "+" : "") +
        ((Math.exp(rr) - 1) * 100).toFixed(0) + "%</b> against the world, on " +
        ro.length + " matched items. "
      : "") +
    "A country is priced by whichever retailers the corpus reaches inside it, so read " +
    "this as what the collected shelves say, not as a sample of the country. A group " +
    "with fewer than " + GV_MIN_LEAVES + " matched items is left hatched rather than " +
    "estimated, and a group no " + ROWWORD + " prices " + GV_MIN_ROWS +
    " times over is left off entirely.");
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
  /* Null under IS_REGIONAL: see the boot block that hides the chip groups. */
  setHRegion:function (r) { S.hregion = IS_REGIONAL ? null : r; this.render(); },
  hsort:function (k) {
    if (S.hsort.k === k) S.hsort.d = -S.hsort.d;
    else S.hsort = {k:k, d:1};
    this.render(); },
  setRegion:function (r) { S.region = IS_REGIONAL ? null : r; this.render(); },
  weightPanel:function () {
    var pane = document.getElementById("wPanel"), b = document.getElementById("wToggle");
    var open = pane.hidden;
    pane.hidden = !open;
    b.className = "chip" + (open ? " on" : "");
    b.setAttribute("aria-expanded", open ? "true" : "false");
    b.textContent = (open ? "Hide" : "Show") + " the weights";
  },
  setWMode:function (k) {
    if (!BW_MODES[k]) return;
    bwSetMode(k); bwApply(); bwWriteHash(); this.render();
  },
  /* `commit` is set from `onchange` and never from `oninput`. The recompute has
     to be live -- a slider whose number arrives on release is a slider nobody
     can aim -- but a full re-render redraws two charts and a two-hundred-row
     table, and a history entry per pixel of drag is not state worth keeping.
     So dragging repaints the ranking alone, and letting go does the rest. */
  setWeight:function (code, v, commit) {
    if (!BW_ON || S.w[code] == null) return;
    S.w[code] = (+v) / BW_UNIT;
    /* Moving anything while a fixed vector is selected makes it the reader's
       own, seeded from where they were rather than from nowhere. */
    if (bwDirty()) S.wmode = "custom"; else S.wmode = S.wbase;
    bwApply();
    renderRanking();
    if (commit) { bwWriteHash(); this.render(); }
  },
  resetWeights:function () {
    if (!BW_ON) return;
    bwSetMode(S.wbase); bwApply(); bwWriteHash(); this.render();
  },
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
    seg("mod-0", !S.incModelled); seg("mod-1", S.incModelled);
    seg("der-0", !S.measuredOnly); seg("der-1", S.measuredOnly);
    seg("flg-0", !S.showFlagged); seg("flg-1", S.showFlagged);
    ["any","thin","solid"].forEach(function (k) { seg("ev-" + k, S.evidence === k); });

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
    /* CATFILTER: the category tree reads the picker the views just rebuilt. */
    if (window.CATFILTER) window.CATFILTER.sync();
  }
};
document.addEventListener("keydown", function (e) {
  if (e.key === "Escape") return APP.about(false);
  if ((e.key === "Enter" || e.key === " ") && e.target && e.target.dataset &&
      e.target.dataset.act) { e.preventDefault(); e.target.click(); }
});
window.APP = APP;

/* =====================================================================
   AN EXTERNAL PRICE LEVEL — a benchmark, never a correction
   =====================================================================
   The ranking above divides every country by the world median of OUR OWN
   corpus, so nothing in this file can say whether it is right: the scale is
   self-referential. What settles it is somebody else's price level over the
   same countries, built from somebody else's prices. The World Bank's ICP
   sends enumerators to price a common specification in each economy and
   publishes a food, beverage, alcohol and tobacco price level on the SAME
   world = 100 base this dashboard uses; the WDI publishes a whole-economy one.

   Neither is blended into our number and neither corrects it — this is the
   relationship the official CPI has with our change series one tab over: two
   independent measurements on one pair of axes, and the reader judges.

   The 45-degree line is the claim. A country sitting on it reads the same in
   both. Distance from it, in logs, is the disagreement; the ten widest are
   named underneath rather than left to be hunted for on the canvas.

   Both axes are LOGARITHMIC because both numbers are ratios: 50 is as far
   below 100 as 200 is above it, and a linear axis says otherwise. */
var PPP = DATA.ppp || {}, PPPMETA = DATA.pppMeta || {};
var PPP_ON = Object.keys(PPP).length > 0;
/* Which benchmark, and whether the countries our own gate rejects are drawn.
   Local to this card rather than in `S`: `S` is the shared, URL-shaped state
   every view reads, and neither of these is a question about the corpus. */
var PPPSEL = "icp", PPP_UNGATED = true;
var PPP_BENCH = {
  icp:  {v:"icp", y:"icpYear", lab:"ICP food &amp; tobacco",
         ax:"ICP price level — food, beverages, alcohol, tobacco (world = 100)",
         note:"has the same scope and the same base as ours"},
  wdi:  {v:"wdi", y:"wdiYear", lab:"WDI whole economy",
         ax:"WDI price level — whole economy (world = 100)",
         note:"prices rent, health and services too, so poor countries " +
              "read lower on it than they do on food alone"},
  hfce: {v:"wdiHfce", y:"wdiHfceYear", lab:"WDI household consumption",
         ax:"WDI price level — household final consumption (world = 100)",
         note:"covers household consumption rather than the whole of GDP, "
              + "still far wider than food"}
};

/* The vector the ranking is CURRENTLY drawn under — the reader's if they have
   moved a slider, the published one otherwise. Handing it to the benchmark too
   is what keeps the comparison honest: re-weighting our basket and leaving
   theirs fixed would turn a difference of method into a difference of price. */
function pppWeights() {
  if (typeof BW_ON !== "undefined" && BW_ON && S.w) return S.w;
  return (DATA.basket && DATA.basket.w0) || null;
}

/* The ICP benchmark, re-aggregated on the client under `w`. At the published
   vector this reproduces the server's `icp` figure exactly, which is what
   makes it safe to recompute at all; `e.icp` is the fallback for a payload
   built before the class matrix existed. */
function pppIcpLevel(slug, w) {
  var e = PPP[slug];
  if (!e) return null;
  var nodeOf = PPPMETA.nodeOf || {}, num = 0, den = 0, code, node, cell;
  if (e.cls && w) {
    for (code in w) {
      if (!Object.prototype.hasOwnProperty.call(w, code)) continue;
      node = nodeOf[code];
      cell = node && e.cls[node];
      if (!cell || !(cell[0] > 0)) continue;
      num += w[code] * Math.log(cell[0] / 100);
      den += w[code];
    }
    if (den > 0) return Math.exp(num / den) * 100;
  }
  return e.icp != null ? e.icp : null;
}

function pppBenchOf(slug, w) {
  var spec = PPP_BENCH[PPPSEL], e = PPP[slug];
  if (!e) return null;
  var v = PPPSEL === "icp" ? pppIcpLevel(slug, w) : e[spec.v];
  if (v == null || !(v > 0)) return null;
  return {v:v, y:e[spec.y] || null};
}

/* One row per country that has BOTH numbers. The region chips above filter
   this list too — the reader has narrowed the ranking and the chart under it
   has to answer the same question. */
function pppRows() {
  var w = pppWeights();
  return DATA.ctyIdx.map(function (slug) {
    var m = DATA.cty[slug];
    if (m.level == null || !(m.level > 0)) return null;
    if (S.region && m.region !== S.region) return null;
    var b = pppBenchOf(slug, w);
    if (!b) return null;
    return {slug:slug, name:m.name, iso3:m.iso3, region:m.region,
            ours:m.level, bench:b.v, year:b.y, ok:!!m.level_ok,
            n:m.level_n, src:m.src,
            gap:Math.log(m.level / b.v)};
  }).filter(function (r) { return !!r; });
}

/* Average ranks, so a tie does not hand one of the tied values a rank the
   other does not get and bias the rank correlation. */
function pppRanks(v) {
  var idx = v.map(function (x, i) { return i; })
    .sort(function (a, b) { return v[a] - v[b]; });
  var out = new Array(v.length), i = 0, j, r;
  while (i < idx.length) {
    j = i;
    while (j + 1 < idx.length && v[idx[j + 1]] === v[idx[i]]) j++;
    r = (i + j) / 2 + 1;
    for (var k = i; k <= j; k++) out[idx[k]] = r;
    i = j + 1;
  }
  return out;
}
function pppPearson(x, y) {
  var n = x.length, i, mx = 0, my = 0, sxy = 0, sxx = 0, syy = 0, dx, dy;
  if (n < 3) return null;
  for (i = 0; i < n; i++) { mx += x[i]; my += y[i]; }
  mx /= n; my /= n;
  for (i = 0; i < n; i++) {
    dx = x[i] - mx; dy = y[i] - my;
    sxy += dx * dy; sxx += dx * dx; syy += dy * dy;
  }
  if (!(sxx > 0) || !(syy > 0)) return null;
  return {r:sxy / Math.sqrt(sxx * syy), slope:sxy / sxx,
          intercept:my - (sxy / sxx) * mx, n:n,
          sdx:Math.sqrt(sxx / n), sdy:Math.sqrt(syy / n)};
}
/* Everything on LOGS. Both figures are ratios to a world median, so the thing
   that is linear in them is the log, and a slope of 1 there means "one per
   cent dearer on theirs is one per cent dearer on ours" — which is the claim
   being tested. A slope below 1 says our spread is COMPRESSED against theirs. */
function pppStats(rows) {
  if (rows.length < 3) return null;
  var x = rows.map(function (r) { return Math.log(r.bench); });
  var y = rows.map(function (r) { return Math.log(r.ours); });
  var fit = pppPearson(x, y);
  if (!fit) return null;
  var rho = pppPearson(pppRanks(x), pppRanks(y));
  fit.rho = rho ? rho.r : null;
  /* The RATIO OF SPREADS, which is the question the slope only looks like it
     answers. A regression of ours on theirs is pulled below 1 by any error in
     THEIR figure, so a slope of 0.7 is not evidence that our range is narrow;
     the two standard deviations side by side are. */
  fit.disp = fit.sdx > 0 ? fit.sdy / fit.sdx : null;
  return fit;
}

function pppFmtGap(g) {
  var pct = (Math.exp(g) - 1) * 100;
  return (pct >= 0 ? "+" : "") + pct.toFixed(0) + "%";
}

function renderPppBench() {
  var card = document.getElementById("pppCard");
  if (!card) return;
  if (!PPP_ON) { card.hidden = true; return; }
  card.hidden = false;

  var avail = Object.keys(PPP_BENCH).filter(function (k) {
    var spec = PPP_BENCH[k];
    return DATA.ctyIdx.some(function (s) {
      return PPP[s] && PPP[s][spec.v] != null; });
  });
  if (avail.indexOf(PPPSEL) < 0) PPPSEL = avail[0];
  document.getElementById("pppChips").innerHTML = avail.map(function (k) {
    return '<button class="chip' + (PPPSEL === k ? " on" : "") + '" aria-pressed="' +
      (PPPSEL === k) + '" onclick="APP.setPppBench(' + arg(k) + ')">' +
      PPP_BENCH[k].lab + "</button>"; }).join("") +
    '<button class="chip' + (PPP_UNGATED ? " on" : "") + '" aria-pressed="' +
    PPP_UNGATED + '" title="Countries our own gate holds out of the ranking. ' +
    'One of them landing far off the line is evidence the gate is working." ' +
    'onclick="APP.togglePppUngated()">Show the countries we hold out</button>';

  var spec = PPP_BENCH[PPPSEL];
  var all = pppRows();
  var gated = all.filter(function (r) { return r.ok; });
  var held  = all.filter(function (r) { return !r.ok; });
  var shown = PPP_UNGATED ? all : gated;
  var st = pppStats(gated);

  if (shown.length < 3) {
    /* The message goes in the caption, not into the table: a <div> inside a
       <table> is not markup a browser keeps where it was put. */
    document.getElementById("pppStat").innerHTML =
      "Too few countries here carry both a price level and a benchmark to " +
      "compare them" +
      (S.region ? " in " + esc(S.region) + "." : ".");
    document.getElementById("pppOut").innerHTML = "";
    if (charts.cPpp) { charts.cPpp.destroy(); delete charts.cPpp; }
    document.getElementById("pppLegend").innerHTML = "";
    return;
  }

  var vals = [], i;
  for (i = 0; i < shown.length; i++) { vals.push(shown[i].bench, shown[i].ours); }
  var lo = Math.min.apply(null, vals) / 1.15, hi = Math.max.apply(null, vals) * 1.15;

  /* The ten widest disagreements, among the countries we actually publish.
     They are labelled on the canvas AND listed, because a name written next to
     a dot is findable and a name in a row is readable, and this card exists to
     be argued with. */
  var worst = gated.slice().sort(function (a, b) {
    return Math.abs(b.gap) - Math.abs(a.gap); }).slice(0, 10);
  var flagged = {};
  worst.slice(0, 8).forEach(function (r) { flagged[r.slug] = true; });

  var pt = function (r) {
    return {x:r.bench, y:r.ours, row:r}; };
  var ds = [{
    type:"line", label:"same price level in both",
    data:[{x:lo, y:lo}, {x:hi, y:hi}],
    borderColor:DIM, borderDash:[6, 5], borderWidth:1.4,
    pointRadius:0, fill:false, order:9
  }];
  if (st) {
    var fx = [], k;
    for (k = 0; k <= 24; k++) {
      var xv = lo * Math.pow(hi / lo, k / 24);
      fx.push({x:xv, y:Math.exp(st.intercept + st.slope * Math.log(xv))});
    }
    ds.push({type:"line", label:"line of best fit", data:fx,
      borderColor:PAL[0], borderDash:[2, 3], borderWidth:1.6,
      pointRadius:0, fill:false, order:8});
  }
  if (PPP_UNGATED && held.length) {
    ds.push({label:"held out of the ranking", data:held.map(pt),
      backgroundColor:"transparent", borderColor:FAINT, borderWidth:1.1,
      pointRadius:3.2, pointHoverRadius:5.5, order:2});
  }
  ds.push({label:"ranked", data:gated.map(pt),
    backgroundColor:"rgba(28,111,190,.72)", borderColor:"transparent",
    pointRadius:4, pointHoverRadius:6.5, order:1});

  var nice = [5,10,15,20,30,40,50,60,70,80,100,125,150,200,250,300,400,500,700,1000,1500,2000,3000,5000];
  var axis = function (title) {
    return {
      type:"logarithmic", min:lo, max:hi,
      title:{display:true, text:title, color:DIM, font:{size:11.5}},
      grid:{color:RULE},
      afterBuildTicks:function (a) {
        a.ticks = nice.filter(function (v) { return v >= a.min && v <= a.max; })
          .map(function (v) { return {value:v}; });
      },
      ticks:{color:FAINT, font:{size:10.5},
        callback:function (v) { return v; }}
    };
  };

  chart("cPpp", {
    type:"scatter",
    data:{datasets:ds},
    options:{
      parsing:false,
      plugins:{
        legend:{display:false},
        tooltip:{callbacks:{label:function (c) {
          var r = c.raw && c.raw.row;
          if (!r) return c.dataset.label;
          return [r.name + (r.ok ? "" : "  (held out of the ranking)"),
                  "ours " + r.ours.toFixed(0) + "  ·  benchmark " +
                  r.bench.toFixed(0) + (r.year ? " (" + r.year + ")" : ""),
                  "we read " + pppFmtGap(r.gap) + " against it  ·  " +
                  r.n + " matched items"];
        }}}
      },
      scales:{x:axis(spec.ax), y:axis("Our matched-basket price level (world = 100)")}
    },
    /* Chart.js ships no label plugin and nothing may be fetched, so the eight
       widest disagreements are written onto the canvas here. Only eight: a
       name against every dot is a smear, and the rest of the list is a table. */
    plugins:[{
      id:"pppLabels",
      afterDatasetsDraw:function (c) {
        var ctx = c.ctx, placed = [];
        ctx.save();
        ctx.font = "600 10.5px system-ui, -apple-system, sans-serif";
        ctx.fillStyle = INK;
        ctx.textAlign = "left";
        c.data.datasets.forEach(function (d, di) {
          var meta = c.getDatasetMeta(di);
          if (d.type === "line") return;
          d.data.forEach(function (p, pi) {
            if (!p.row || !flagged[p.row.slug]) return;
            var el = meta.data[pi];
            if (!el) return;
            var above = p.row.gap > 0;
            var x = el.x + 6, y = el.y + (above ? -4 : 5);
            /* Two names on top of each other is worse than one name missing:
               Kuwait and Qatar sit within a few pixels and the pair read as a
               single smear. A label that cannot find clear air is dropped, and
               the country is still in the table underneath. */
            var clash = placed.some(function (q) {
              return Math.abs(q[0] - x) < 46 && Math.abs(q[1] - y) < 13; });
            if (clash) return;
            placed.push([x, y]);
            ctx.textBaseline = above ? "bottom" : "top";
            ctx.fillText(p.row.name, x, y);
          });
        });
        ctx.restore();
      }
    }]
  });

  var stat = st
    ? "<b>" + st.n + " countries</b> carry both figures. Correlation of the logs " +
      "<b>r&nbsp;=&nbsp;" + st.r.toFixed(2) + "</b>" +
      (st.rho != null ? ", rank correlation <b>&rho;&nbsp;=&nbsp;" +
        st.rho.toFixed(2) + "</b>" : "") +
      ". Our spread is <b>" + (st.disp != null ? st.disp.toFixed(2) : "?") +
      "&times;</b> the benchmark's" +
      (st.disp != null
        ? (st.disp > 1.08
           ? " &mdash; we place the expensive and the cheap FURTHER apart than it does. "
           : st.disp < 0.93
           ? " &mdash; we place the expensive and the cheap closer together than it does. "
           : " &mdash; the two ranges are about the same width. ")
        : ". ") +
      "The line of best fit has slope <b>" + st.slope.toFixed(2) + "</b>, which sits " +
      "below the ratio of spreads because a regression is pulled toward flat by the " +
      "error in whichever figure is on the horizontal axis &mdash; it is not evidence " +
      "on its own about whose range is wider."
    : "Too few countries to fit a line.";
  document.getElementById("pppStat").innerHTML = stat +
    " The benchmark " + spec.note + ".";

  var yrs = {};
  gated.forEach(function (r) { if (r.year) yrs[r.year] = (yrs[r.year] || 0) + 1; });
  var yk = Object.keys(yrs).sort();
  document.getElementById("pppLegend").innerHTML =
    '<span><i class="sw" style="background:rgba(28,111,190,.72)"></i>ranked here</span>' +
    (PPP_UNGATED && held.length
      ? '<span><i class="sw" style="background:transparent;border:1px solid ' + FAINT +
        '"></i>held out of our ranking (' + held.length + ")</span>" : "") +
    '<span><i class="sw" style="background:' + DIM + '"></i>the two agree</span>' +
    (st ? '<span><i class="sw" style="background:' + PAL[0] + '"></i>line of best fit</span>' : "") +
    (yk.length ? '<span>benchmark vintage: ' + yk.map(function (y) {
      return y + " (" + yrs[y] + ")"; }).join(", ") + "</span>" : "");

  document.getElementById("pppOut").innerHTML = !worst.length ? "" :
    "<thead><tr><th>Widest disagreement</th><th class='num'>Ours</th>" +
    "<th class='num'>Benchmark</th><th class='num'>Vintage</th>" +
    "<th class='num'>Gap</th><th class='num'>Items</th><th class='num'>Sources</th>" +
    "</tr></thead><tbody>" +
    worst.map(function (r) {
      return '<tr tabindex="0" role="button" data-act="1" onclick="APP.openCountry(' +
        arg(r.slug) + ')"><td>' + esc(r.name) + "</td>" +
        '<td class="num">' + r.ours.toFixed(0) + "</td>" +
        '<td class="num">' + r.bench.toFixed(0) + "</td>" +
        '<td class="num">' + (r.year || "&mdash;") + "</td>" +
        '<td class="num" style="color:' + (r.gap > 0 ? DEAR : CHEAP) + '">' +
        pppFmtGap(r.gap) + "</td>" +
        '<td class="num">' + r.n + "</td>" +
        '<td class="num">' + r.src + "</td></tr>"; }).join("") + "</tbody>";
}

APP.setPppBench = function (k) { PPPSEL = k; renderPppBench(); };
APP.togglePppUngated = function () { PPP_UNGATED = !PPP_UNGATED; renderPppBench(); };


/* boot */
(function () {
  var m = DATA.meta;
  /* The masthead says what this build is OF before it says what it measures.
     "Global Retail Prices" over 38 EAP countries was the same misreading the
     tab labels carried, one line higher up. */
  document.getElementById("scope").innerHTML =
    (IS_REGIONAL ? "<b>" + esc(BUILD_REGION) + "</b> · " + m.n_countries +
       " countries · " : m.n_countries + " countries · ") +
    "COICOP divisions " + m.divisions.join(" and ") + " — food, beverages, alcohol and tobacco, " +
    "priced per kilogram, litre or piece";

  /* ONE tab for the scope of the build, named after that scope: "Global View"
     over the world, "Regional View" over one region. There used to be a second
     "Global View" tab beside the regional one -- two tabs both claiming to be
     the world, in front of a reader who had asked for a region. Its two cards
     moved into this tab and it is gone. */
  setTextIfPresent("t-world", IS_REGIONAL ? "Regional View" : "Global View");

  /* Those two cards name WHO is on their rows, and that is the one thing the
     build's scope changes about them: the world's regions globally, this
     build's own countries regionally. The yardstick they divide by is the world
     median in both, so no label here may stop saying "world". */
  if (IS_REGIONAL) {
    setTextIfPresent("gvTitle", "How " + BUILD_REGION + " prices the same basket");
    setTextIfPresent("gvSub", "Every " + BUILD_REGION +
      " country against the world median, item by item.");
    setHtmlIfPresent("gvHelp",
      "Every figure here is one country's median price for an item set against the " +
      "<b>world median for the same item in the same unit</b> &mdash; 1&nbsp;kg of rice " +
      "against 1&nbsp;kg of rice &mdash; and those item-by-item differences are then " +
      "folded up the category tree, so a finely split branch cannot outvote its " +
      "neighbours. Red is more expensive than the world, blue cheaper. The world " +
      "median is computed over the whole corpus, before this build was narrowed to " +
      esc(BUILD_REGION) + ".");
    setTextIfPresent("gvGridTitle", "Country by category group");
    setTextIfPresent("gvGridSub", "Each category group in each " + BUILD_REGION +
      " country, against the world median for the same items.");
  }

  /* A regional build is already scoped to one region, so a region filter is a
     control with exactly one setting -- "All regions", which over this payload
     IS the region. It read as an offer to narrow further that could not narrow
     anything. Both chip groups go, in every tab that carries one. The state
     they write stays null, which is what every reader of S.region/S.hregion
     already treats as "no region filter"; the setters refuse a non-null value
     under IS_REGIONAL so a hidden control cannot strand a stale filter. */
  if (IS_REGIONAL) {
    ["regionFilter", "hmRegionFilter"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.hidden = true;
    });
  }
  /* `build_geo_series` labels the total over whatever countries it was handed
     "World". In a regional build that total is the region, so it is named after
     the region -- plainly, because with the duplicate region chip dropped above
     this IS the region's line and there is nothing to tell it apart from. */
  if (IS_REGIONAL && DATA.geos.W) DATA.geos.W.t = BUILD_REGION;
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
    /* The old promise was "no missing month is ever filled in", stated flatly.
       It is still true when no fills are loaded, and still shown then. What it
       must never do is survive into a payload that HAS fills — the reader would
       be told nothing is filled while hollow diamonds are drawn in front of
       them. The objection that promise was defending against was never that
       imputation is wrong; it was that an imputed value would be
       indistinguishable from a measured one. That is what the marking answers,
       which is why the marking is unconditional and the old toggle is not here
       any more. */
    (HAS_IMPUTED
      ? "<b>Months with no observed price are filled in, and every filled month is " +
        "marked.</b> Some of these gaps are collection artefacts rather than quiet " +
        "markets, so they are estimated from what the same item did elsewhere — and " +
        "then drawn as a hollow diamond on a line, or a ◇ beside a figure in a table " +
        "or a grid, wherever one stands behind what you are reading. Filled and " +
        "measured values are never interchangeable on screen. "
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
    " trusted unit values · cells need " + m.min_cell_obs + "+ observations" +
    /* The gate is now "enough observations OR at least one fill", so the old
       flat claim understated what is on screen the moment fills are loaded. */
    (HAS_IMPUTED ? " or a marked estimate" : "");
  /* The weighting comes up before the first render, so nothing is ever drawn
     under the published vector and then redrawn under the reader's. */
  if (BW_ON) {
    bwSetMode(DATA.basket.mode0);
    bwReadHash();
    bwApply();
    bwBuild();
  }

  /* The default country was "whichever slug has the longest series", which in
     the EAP build is Brunei Darussalam on 165 periods -- a country of 450,000
     people opening a dashboard about the region. Depth of series is a fact
     about the scrape, not about what a reader wants to see first, so a named
     country leads and the heuristic stays only as the fallback that keeps an
     arbitrary payload booting. */
  var PREFER = ["indonesia", "china", "india"];
  var best = PREFER.filter(function (c) { return DATA.ctyIdx.indexOf(c) >= 0; })[0];
  if (!best) {
    var bestN = -1;
    Object.keys(DATA.series).forEach(function (k) {
      var n = DATA.series[k].p.length;
      if (n > bestN) { bestN = n; best = DATA.ctyIdx[+k.split("|")[0]]; } });
  }
  S.country = best || DATA.ctyIdx[0];
  APP.render();
})();
})();
