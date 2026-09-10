/* Hierarchical COICOP category filter — a checkbox tree, not a flat list.
   ---------------------------------------------------------------------
   The control it replaces was a <select> whose options faked the tree with
   figure spaces: five levels of COICOP flattened into one scrolling column,
   where "Rice" and "Cereals" and "Food" all read as siblings. The taxonomy is
   the whole point of the corpus, so the picker states it: division, group,
   class, subclass, leaf, each one indented under its parent, each one
   expandable on its own.

   The <select> is still in the document, hidden. It stays the state carrier
   the view layer already writes to, so nothing downstream of the picker had
   to be rewired: this file reads which categories the chart can currently
   draw off its options, and commits a choice through APP.setGNode. */
(function () {
"use strict";

if (typeof DATA === "undefined") return;
var root = document.getElementById("catfilter");
if (!root) return;

var TAX = DATA.tax || {}, IDX = DATA.nodeIdx || [], META = DATA.nodeMeta || {};

/* Rice. `_app.js` opens Compare on the same code and says why: it is priced
   almost everywhere, in one unit, and it is the worked example everyone
   reaches for. The two tabs opening on the same item is the point. */
var DEFAULT_CODE = "01.1.1.1.2";

function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
function title(c) { return (TAX[c] || {}).t || c; }
function parent(c) { var p = (TAX[c] || {}).p; return p && TAX[p] ? p : null; }

/* ---------------- the tree ----------------
   Children in code order, which is also taxonomic order. */
var KIDS = {};
IDX.forEach(function (c) {
  var p = parent(c);
  if (p) (KIDS[p] = KIDS[p] || []).push(c);
});
Object.keys(KIDS).forEach(function (k) { KIDS[k].sort(); });

/* Which nodes are real.
   A node is dropped only when NOTHING in the payload stands behind it or any
   of its descendants. `nodeMeta[code].countries` is the number of countries
   holding a cell at that node, counted server-side before any gate the reader
   can touch — evidence threshold, flagged cells, modelled cells, the current
   unit, the series-availability of the chosen measure. Filtering on any of
   those would empty branches that are in fact well covered: rice is priced in
   202 of 209 countries and maize in 181, and both vanish from a tree built out
   of whatever the chart happens to be able to draw this second. */
var LIVE = {};
(function () {
  function live(c) {
    if (LIVE[c] !== undefined) return LIVE[c];
    LIVE[c] = false;                                  /* cycle guard */
    var ok = (((META[c] || {}).countries) || 0) > 0;
    (KIDS[c] || []).forEach(function (k) { if (live(k)) ok = true; });
    return (LIVE[c] = ok);
  }
  IDX.forEach(live);
})();

function kids(c) {
  return (KIDS[c] || []).filter(function (k) { return LIVE[k]; });
}
var ROOTS = IDX.filter(function (c) {
  return LIVE[c] && !parent(c);
}).sort();

/* Terminals of a subtree. Selection is held at the terminals and nowhere else:
   a parent is checked when all of its terminals are, indeterminate when some
   are, and every cascade is then a set operation rather than a tree walk that
   has to keep two representations agreeing with each other. */
var TERM = {};
function terms(c) {
  if (TERM[c]) return TERM[c];
  var k = kids(c), out = [];
  if (!k.length) out = [c];
  else k.forEach(function (x) { out = out.concat(terms(x)); });
  return (TERM[c] = out);
}

/* ---------------- state ----------------
   `applied` is what the dashboard is showing; `draft` is what the reader has
   ticked but not yet committed. Closing the panel any way other than Apply
   throws the draft away. */
var applied = {}, draft = {}, openSet = {}, isOpen = false, lastWant = null;

function copy(o) { var r = {}, k; for (k in o) if (o[k]) r[k] = 1; return r; }
function count(o) { var n = 0, k; for (k in o) if (o[k]) n++; return n; }

/* 0 = none of this subtree, 1 = all of it, 2 = some */
function state(c, set) {
  var t = terms(c), n = 0;
  t.forEach(function (x) { if (set[x]) n++; });
  return n === 0 ? 0 : n === t.length ? 1 : 2;
}
function setSub(c, on, set) {
  terms(c).forEach(function (x) { if (on) set[x] = 1; else delete set[x]; });
}

/* The selection, collapsed onto the shallowest nodes that cover it — every
   child of "Cereals" ticked reads back as "Cereals", not as eight leaves. */
function canonical(set) {
  var out = [];
  (function walk(list) {
    list.forEach(function (c) {
      var st = state(c, set);
      if (st === 1) out.push(c);
      else if (st === 2) walk(kids(c));
    });
  })(ROOTS);
  return out;
}

/* ---------------- markup ---------------- */
var FUNNEL = '<svg class="cf-ic" viewBox="0 0 16 16" aria-hidden="true" focusable="false">' +
  '<path d="M1.6 2.6h12.8L9.4 8.4V13.4L6.6 11.8V8.4z" fill="none" stroke="currentColor" ' +
  'stroke-width="1.3" stroke-linejoin="round"/></svg>';
var CHEV = '<svg class="cf-ic" viewBox="0 0 16 16" aria-hidden="true" focusable="false">' +
  '<path d="M3.6 6.2 8 10.4l4.4-4.2" fill="none" stroke="currentColor" stroke-width="1.5" ' +
  'stroke-linecap="round" stroke-linejoin="round"/></svg>';

root.className = "cf";
root.innerHTML =
  '<div class="cf-bar">' +
    '<input type="search" class="cf-search" id="cfSearch" placeholder="Search by Name" ' +
      'aria-label="Search categories by name" autocomplete="off" spellcheck="false">' +
    '<button type="button" class="cf-btn" id="cfOpen" aria-expanded="false" ' +
      'aria-controls="cfPanel" aria-haspopup="dialog">' + FUNNEL +
      'Filters<span class="cf-n" id="cfN"></span></button>' +
  '</div>' +
  '<div class="cf-sum" id="cfSum"></div>' +
  '<div class="cf-panel" id="cfPanel" role="dialog" aria-label="Filter categories" hidden>' +
    '<div class="cf-head">Filter</div>' +
    '<div class="cf-list" id="cfList"></div>' +
    '<div class="cf-none" id="cfNone" hidden>Nothing here by that name.</div>' +
    '<div class="cf-foot">' +
      '<button type="button" class="cf-clear" id="cfClear">Clear</button>' +
      '<button type="button" class="cf-apply" id="cfApply">Apply</button>' +
    '</div>' +
  '</div>';

var elSearch = document.getElementById("cfSearch");
var elOpen   = document.getElementById("cfOpen");
var elPanel  = document.getElementById("cfPanel");
var elList   = document.getElementById("cfList");
var elNone   = document.getElementById("cfNone");
var elN      = document.getElementById("cfN");
var elSum    = document.getElementById("cfSum");

/* ---------------- the visible rows ----------------
   Searching keeps every ancestor of a match on screen and opens the path down
   to it, so a match is never hidden behind a collapsed parent. A match's own
   subtree stays available but collapsed — searching "Cereals" should not
   dump forty leaves on the reader. */
function visible() {
  var q = (elSearch.value || "").trim().toLowerCase();
  if (!q) return null;
  var vis = {}, auto = {};
  function under(c) { vis[c] = 1; kids(c).forEach(under); }
  IDX.forEach(function (c) {
    if (!LIVE[c]) return;
    if (title(c).toLowerCase().indexOf(q) < 0 && c.indexOf(q) < 0) return;
    under(c);
    var p = parent(c);
    while (p) { vis[p] = 1; auto[p] = 1; p = parent(p); }
  });
  return {vis: vis, auto: auto};
}

function row(c, d, hasKids, open) {
  var st = state(c, draft);
  return '<div class="cf-row" data-lvl="' + ((TAX[c] || {}).lvl || 1) + '"' +
      ' style="padding-left:' + (11 + d * 17) + 'px">' +
    '<input type="checkbox" class="cf-cb" data-c="' + c + '" id="cf-' + c + '"' +
      (st === 1 ? " checked" : "") + '>' +
    '<label class="cf-lab" for="cf-' + c + '">' + esc(title(c)) +
      '<span class="cf-code">' + c + "</span></label>" +
    (hasKids
      ? '<button type="button" class="cf-car' + (open ? " up" : "") + '" data-x="' + c +
        '" aria-expanded="' + (open ? "true" : "false") + '" aria-label="' +
        (open ? "Collapse " : "Expand ") + esc(title(c)) + '">' + CHEV + "</button>"
      : '<span class="cf-car cf-ph" aria-hidden="true"></span>') +
    "</div>";
}

function paint() {
  var f = visible(), out = [], shown = 0;
  (function walk(list, d) {
    list.forEach(function (c) {
      if (f && !f.vis[c]) return;
      var k = kids(c).filter(function (x) { return !f || f.vis[x]; });
      var open = !!k.length && !!(openSet[c] || (f && f.auto[c]));
      out.push(row(c, d, !!k.length, open));
      shown++;
      if (open) walk(k, d + 1);
    });
  })(ROOTS, 0);
  elList.innerHTML = out.join("");
  elNone.hidden = shown > 0;
  /* `indeterminate` is a property, never an attribute — it cannot be written
     into the markup above and has to be stamped on after the fact. */
  Array.prototype.forEach.call(elList.querySelectorAll(".cf-cb"), function (b) {
    b.indeterminate = state(b.getAttribute("data-c"), draft) === 2;
  });
}

/* ---------------- open / close ---------------- */
function open() {
  draft = copy(applied);
  /* open the path down to whatever is already selected, so the panel never
     opens on a wall of collapsed divisions with the choice buried inside */
  canonical(applied).forEach(function (c) {
    var p = parent(c);
    while (p) { openSet[p] = 1; p = parent(p); }
  });
  isOpen = true;
  sync();
}
function close() {
  isOpen = false;
  sync();
}

/* ---------------- commit ----------------
   The chart draws one category at a time, so the committed set is read back
   through its shallowest covering node. Where that node carries no series at
   the reader's current measure, freqency or window, the nearest ancestor that
   does stands in — and the summary line underneath says so out loud rather
   than letting the heading quietly disagree with the tree. */
function commit() {
  var codes = canonical(applied), sel = document.getElementById("wtNode");
  lastWant = codes.length ? codes[0] : null;
  var want = lastWant;
  if (want && sel && sel.options.length) {
    var avail = {};
    Array.prototype.forEach.call(sel.options, function (o) { avail[o.value] = 1; });
    var c = want;
    while (c && !avail[c]) c = parent(c);
    want = c || want;
  }
  if (want && window.APP && APP.setGNode) APP.setGNode(want);
  else sync();
}

/* ---------------- the readout ----------------
   The hidden <select> is the truth about what is on the canvas; this line is
   the only place the reader is told, now that the picker no longer names it. */
function sync() {
  var sel = document.getElementById("wtNode");
  var drawn = sel ? sel.value : "";
  var codes = canonical(applied), n = codes.length;
  elN.textContent = n ? " " + n : "";
  elOpen.className = isOpen ? "cf-btn on" : "cf-btn";
  elOpen.setAttribute("aria-expanded", isOpen ? "true" : "false");
  elPanel.hidden = !isOpen;
  var msg;
  if (!n) {
    msg = "No category picked &mdash; the chart is showing <b>" + esc(title(drawn)) +
      "</b>. Open <b>Filters</b> to choose.";
  } else {
    msg = "Showing <b>" + esc(title(drawn)) + "</b> <span class=\"cf-code\">" +
      esc(drawn) + "</span>";
    if (lastWant && lastWant !== drawn) {
      msg = "<b>" + esc(title(lastWant)) + "</b> has no series at this setting &mdash; " +
        "showing <b>" + esc(title(drawn)) + "</b> <span class=\"cf-code\">" +
        esc(drawn) + "</span>";
    } else if (n > 1) {
      msg += " &middot; " + (n - 1) + " more picked, drawn one category at a time";
    }
  }
  elSum.innerHTML = msg;
  if (isOpen) paint();
}

/* ---------------- events ---------------- */
elOpen.onclick = function () { if (isOpen) close(); else open(); };
elSearch.oninput = function () { if (!isOpen) open(); else paint(); };
document.getElementById("cfClear").onclick = function () { draft = {}; paint(); };
document.getElementById("cfApply").onclick = function () {
  applied = copy(draft); close(); commit();
};
elList.onclick = function (e) {
  var car = e.target.closest ? e.target.closest(".cf-car") : null;
  if (car && car.getAttribute("data-x")) {
    var c = car.getAttribute("data-x");
    if (openSet[c]) delete openSet[c]; else openSet[c] = 1;
    paint();
  }
};
elList.onchange = function (e) {
  var b = e.target;
  if (!b || !b.classList || !b.classList.contains("cf-cb")) return;
  var c = b.getAttribute("data-c");
  setSub(c, state(c, draft) !== 1, draft);
  paint();
};
document.addEventListener("mousedown", function (e) {
  if (isOpen && !root.contains(e.target)) close();
});
document.addEventListener("keydown", function (e) {
  if (e.key === "Escape" && isOpen) close();
});

/* ---------------- boot ----------------
   Rice, unless a regional payload does not carry it, in which case the first
   live terminal stands in — an empty tree on open is worse than a stand-in. */
(function () {
  var d = LIVE[DEFAULT_CODE] ? DEFAULT_CODE : null;
  if (!d && ROOTS.length) d = terms(ROOTS[0])[0];
  if (d) { setSub(d, true, applied); lastWant = canonical(applied)[0] || d; }
  draft = copy(applied);
})();

window.CATFILTER = {
  sync: sync,
  selection: function () { return canonical(applied); },
  count: function () { return count(applied); }
};
})();
