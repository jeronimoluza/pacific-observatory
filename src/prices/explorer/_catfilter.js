/* Hierarchical COICOP category filter — one tree, mounted wherever a category
   has to be chosen.
   ---------------------------------------------------------------------
   The control it replaces was a <select> whose options faked the tree with
   figure spaces: five levels of COICOP flattened into one scrolling column,
   where "Rice" and "Cereals" and "Food" all read as siblings. The taxonomy is
   the whole point of the corpus, so the picker states it: division, group,
   class, subclass, leaf, each one indented under its parent, each one
   expandable on its own.

   Two things changed after the first version shipped.

   SINGLE SELECT. It drew checkboxes, kept a set of ticked terminals, showed a
   "Filters 3" badge — and then drew ONE category, because every chart it feeds
   draws one category. The extra ticks went into a "2 more picked, drawn one
   category at a time" apology under the panel. A control that accepts input it
   cannot act on is not a filter, it is a trap; the boxes are radios now, the
   badge is gone, and picking a second category replaces the first.

   NO LOCAL COPY OF THE SELECTION. There is no `applied` set here any more, and
   no draft beside it. The tree renders whatever the app says is selected and
   commits through the app; the only state it owns is which branches are open.
   That is what makes a second mount free, and it is what makes it impossible
   for the tree and the chart to disagree.

   NO OVERLAY, NO APPLY. It was a dropdown that covered the chart, with Clear
   and Apply at the bottom to defer a re-render. It is now a panel at the left
   of the chart, always open, committing on click — the same shape and the same
   behaviour as the category panel it replaced on the Compare tab, because it
   IS that panel now. There is nothing to defer: one click is one category, and
   the redraw it triggers is the one the reader asked for. Clear is gone with
   the multi-select: no category is not a state any of these charts has. */
(function () {
"use strict";

if (typeof DATA === "undefined") return;

var TAX = DATA.tax || {}, IDX = DATA.nodeIdx || [], META = DATA.nodeMeta || {};

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

/* The first thing a reader can pick, used only when the app hands back a
   category this tree cannot show — an empty panel is worse than a stand-in. */
function firstLive() {
  var c = ROOTS[0];
  while (c && kids(c).length) c = kids(c)[0];
  return c || null;
}

/* ---------------- markup ---------------- */
var CHEV = '<svg class="cf-ic" viewBox="0 0 16 16" aria-hidden="true" focusable="false">' +
  '<path d="M3.6 6.2 8 10.4l4.4-4.2" fill="none" stroke="currentColor" stroke-width="1.5" ' +
  'stroke-linecap="round" stroke-linejoin="round"/></svg>';

/* ---------------- one mount ----------------
   `get` returns the category the dashboard is actually holding, `set` commits a
   new one. Every mount is otherwise identical, which is the point: the Compare
   tab and the world series now pick a category with the same control, and
   neither of them owns it. */
function mount(id, opts) {
  var root = document.getElementById(id);
  if (!root) return null;

  var openSet = {}, lastWant = null;

  root.className = "cf";
  root.innerHTML =
    '<div class="cf-bar">' +
      '<input type="search" class="cf-search" id="' + id + '-q" ' +
        'placeholder="Search by name" aria-label="Search categories by name" ' +
        'autocomplete="off" spellcheck="false">' +
    '</div>' +
    '<div class="cf-list" id="' + id + '-list" role="radiogroup" ' +
      'aria-label="Category"></div>' +
    '<div class="cf-none" id="' + id + '-none" hidden>Nothing here by that name.</div>' +
    '<div class="cf-sum" id="' + id + '-sum"></div>';

  var elSearch = document.getElementById(id + "-q");
  var elList   = document.getElementById(id + "-list");
  var elNone   = document.getElementById(id + "-none");
  var elSum    = document.getElementById(id + "-sum");

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

  /* A radio, not a checkbox: the affordance has to say "one of these", and the
     browser's own radio-group behaviour — arrow keys, one dot at a time — is
     the behaviour this control wants. The count on the right is the one figure
     the Compare tab's old sibling list carried and this replaces: how many
     countries price anything under the node. */
  function row(c, d, sel, hasKids, open) {
    var n = ((META[c] || {}).countries) || 0;
    return '<div class="cf-row" data-lvl="' + ((TAX[c] || {}).lvl || 1) + '"' +
        ' style="padding-left:' + (11 + d * 17) + 'px">' +
      '<input type="radio" class="cf-cb" name="' + id + '-sel" data-c="' + c +
        '" id="' + id + "-" + c + '"' + (c === sel ? " checked" : "") + '>' +
      '<label class="cf-lab" for="' + id + "-" + c + '">' + esc(title(c)) +
        '<span class="cf-code">' + c + "</span></label>" +
      '<span class="cf-m">' + (n || "—") + "</span>" +
      (hasKids
        ? '<button type="button" class="cf-car' + (open ? " up" : "") + '" data-x="' + c +
          '" aria-expanded="' + (open ? "true" : "false") + '" aria-label="' +
          (open ? "Collapse " : "Expand ") + esc(title(c)) + '">' + CHEV + "</button>"
        : '<span class="cf-car cf-ph" aria-hidden="true"></span>') +
      "</div>";
  }

  /* Repainting is cheap but it is not free of consequences: it destroys the
     element the keyboard is standing on, and this list is a radio group whose
     whole point is that arrow keys walk it. So a paint that would change
     nothing is skipped outright, and one that does change something puts the
     focus back on the row it was on. */
  var lastSig = null;
  function paint(sel) {
    var f = visible(), out = [], shown = 0;
    var sig = sel + "|" + (elSearch.value || "") + "|" +
      Object.keys(openSet).sort().join(",");
    if (sig === lastSig) return;
    var had = document.activeElement;
    var hadId = had && elList.contains(had) ? had.id : null;
    (function walk(list, d) {
      list.forEach(function (c) {
        if (f && !f.vis[c]) return;
        var k = kids(c).filter(function (x) { return !f || f.vis[x]; });
        var open = !!k.length && !!(openSet[c] || (f && f.auto[c]));
        out.push(row(c, d, sel, !!k.length, open));
        shown++;
        if (open) walk(k, d + 1);
      });
    })(ROOTS, 0);
    elList.innerHTML = out.join("");
    elNone.hidden = shown > 0;
    lastSig = sig;
    if (hadId) {
      var back = document.getElementById(hadId);
      if (back) back.focus();
    }
  }

  /* ---------------- commit ----------------
     `set` decides what the dashboard does with the code; all this does is
     remember what was asked for, so `sync` can say so when the dashboard has
     had to draw something else. */
  function commit(c) {
    lastWant = c;
    opts.set(c);
  }

  /* ---------------- the readout ----------------
     The tree no longer names the choice on a button face, so the line under it
     does — and it is the only place that can say "you asked for X and the
     chart is drawing Y", which happens whenever the requested node carries no
     series at the reader's current measure, frequency or window. */
  function sync() {
    var drawn = opts.get();
    if (!drawn || !LIVE[drawn]) {
      /* Not a category this tree can show. Say what is on the canvas anyway
         rather than blanking the line. */
      drawn = drawn || firstLive();
    }
    /* open the path down to the selection, so the panel never sits on a wall
       of collapsed divisions with the choice buried inside it */
    var p = parent(drawn);
    while (p) { openSet[p] = 1; p = parent(p); }
    paint(drawn);
    var msg = "Showing <b>" + esc(title(drawn)) + '</b> <span class="cf-code">' +
      esc(drawn) + "</span>";
    if (lastWant && lastWant !== drawn) {
      msg = "<b>" + esc(title(lastWant)) + "</b> has no series at this setting &mdash; " +
        "showing <b>" + esc(title(drawn)) + '</b> <span class="cf-code">' +
        esc(drawn) + "</span>";
    }
    elSum.innerHTML = msg;
  }

  /* ---------------- events ---------------- */
  elSearch.oninput = function () { sync(); };
  elList.onclick = function (e) {
    var car = e.target.closest ? e.target.closest(".cf-car") : null;
    if (car && car.getAttribute("data-x")) {
      var c = car.getAttribute("data-x");
      if (openSet[c]) delete openSet[c]; else openSet[c] = 1;
      paint(opts.get());
    }
  };
  elList.onchange = function (e) {
    var b = e.target;
    if (!b || !b.classList || !b.classList.contains("cf-cb")) return;
    commit(b.getAttribute("data-c"));
  };

  return {sync: sync};
}

/* ---------------- the mounts ----------------
   The world series keeps the hidden <select> it always had as its state
   carrier, and the walk up the tree with it: the reader may pick a node the
   chart has no series for at the current measure, and the nearest ancestor
   that does have one stands in. Compare has no such list — it draws a bar per
   country and says for itself when a grouping cannot be priced — so it commits
   the code untouched. */
var MOUNTS = [
  mount("catfilter", {
    get: function () {
      var sel = document.getElementById("wtNode");
      return (sel && sel.value) || (window.APP && APP.node && APP.node("world")) || null;
    },
    set: function (c) {
      var sel = document.getElementById("wtNode"), want = c;
      if (sel && sel.options.length) {
        var avail = {};
        Array.prototype.forEach.call(sel.options, function (o) { avail[o.value] = 1; });
        var x = c;
        while (x && !avail[x]) x = parent(x);
        want = x || c;
      }
      if (window.APP && APP.setGNode) APP.setGNode(want);
    }
  }),
  mount("catfilterCmp", {
    get: function () {
      return (window.APP && APP.node && APP.node("cmp")) || null;
    },
    set: function (c) { if (window.APP && APP.pick) APP.pick(c); }
  })
].filter(Boolean);

window.CATFILTER = {
  sync: function () { MOUNTS.forEach(function (m) { m.sync(); }); }
};
})();
