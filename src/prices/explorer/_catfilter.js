/* Hierarchical COICOP category filter — one tree, mounted wherever a category
   has to be chosen.
   ---------------------------------------------------------------------
   The control it replaces was a <select> whose options faked the tree with
   figure spaces: five levels of COICOP flattened into one scrolling column,
   where "Rice" and "Cereals" and "Food" all read as siblings. The taxonomy is
   the whole point of the corpus, so the picker states it: division, group,
   class, subclass, leaf, each one indented under its parent, each one
   expandable on its own.

   Three things changed after the first version shipped.

   A MODE, BECAUSE THE CHARTS DIFFER. It drew checkboxes everywhere, kept a set
   of ticked terminals, showed a "Filters 3" badge — and then drew ONE category
   under the world series and on Compare, because those two charts draw one
   category. The extra ticks went into a "2 more picked, drawn one category at a
   time" apology under the panel. A control that accepts input it cannot act on
   is not a filter, it is a trap. So those two mounts are radios and picking a
   second category replaces the first, while the Country profile's ranking chart
   — which really can draw a union of categories, and always could — keeps the
   checkbox tree with its indeterminate parents. One file, one `opts.multi`
   flag, three mounts; never two copies of a tree widget.

   NO LOCAL COPY OF THE SELECTION. There is no `applied` set here any more, and
   no draft beside it. The tree renders whatever the app says is selected and
   commits through the app; the only state it owns is which branches are open.
   That is what makes a second mount free, and it is what makes it impossible
   for the tree and the chart to disagree.

   NO OVERLAY, NO APPLY, NO FILTERS BUTTON. It was a dropdown behind a funnel
   icon, covering the chart it filtered, with Clear and Apply at the bottom to
   defer a re-render. Every mount is now a panel at the left of what it
   governs, always on screen, with no button to open it and nothing to open —
   the same shape as the category panel it replaced on the Compare tab, because
   it IS that panel now. There is nothing to defer either: see the note on the
   event handlers. Clear survives on the multi mount alone, renamed to what it
   actually does there ("Show all items"), because on that one chart an empty
   selection is a real state and a reader needs a way back to it. */
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

/* ---------------- multi-select arithmetic ----------------
   Only the MULTI mounts use any of this. Selection is held at the TERMINALS of
   the tree and nowhere else: a parent is ticked when all of its terminals are,
   indeterminate when only some are, and every cascade is then a set operation
   rather than a tree walk that has to keep two representations agreeing with
   each other.

   A terminal is a node with no live children. That is the same no-children
   test `isLeaf` makes in the app and it is deliberately NOT "depth 5": nine of
   this taxonomy's 254 leaves stop at depth 4 -- spirits, the two wines, beer,
   cigarettes, cigars and their siblings, which is the whole of division 02 --
   and a depth test would put every one of them beyond reach of this control. */
var TERM = {};
function terms(c) {
  if (TERM[c]) return TERM[c];
  var k = kids(c), out = [];
  if (!k.length) out = [c];
  else k.forEach(function (x) { out = out.concat(terms(x)); });
  return (TERM[c] = out);
}
/* 0 = none of this subtree, 1 = all of it, 2 = some */
function state(c, set) {
  var t = terms(c), n = 0;
  t.forEach(function (x) { if (set[x]) n++; });
  return n === 0 ? 0 : n === t.length ? 1 : 2;
}
function setSub(c, on, set) {
  terms(c).forEach(function (x) { if (on) set[x] = 1; else delete set[x]; });
}
/* The selection collapsed onto the shallowest nodes that cover it — every child
   of "Cereals" ticked reads back as "Cereals", not as eight leaves. This is the
   form the app is handed and the form it hands back. */
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
/* …and the inverse: the app's canonical list back to a terminal set. Round-trip
   through these two rather than caching a set here, so the tree still keeps no
   copy of the selection. */
function expand(codes) {
  var set = {};
  (codes || []).forEach(function (c) {
    if (TAX[c]) terms(c).forEach(function (t) { set[t] = 1; }); });
  return set;
}

/* ---------------- markup ---------------- */
var CHEV = '<svg class="cf-ic" viewBox="0 0 16 16" aria-hidden="true" focusable="false">' +
  '<path d="M3.6 6.2 8 10.4l4.4-4.2" fill="none" stroke="currentColor" stroke-width="1.5" ' +
  'stroke-linecap="round" stroke-linejoin="round"/></svg>';

/* ---------------- one mount ----------------
   `get` returns the category the dashboard is actually holding, `set` commits a
   new one. Every mount is otherwise identical, which is the point: all three
   pickers on this dashboard are now the same control, and none of them owns
   the state it shows.

   `opts.multi` is the only thing that differs between them, and it is about HOW
   MANY nodes may be picked, never about whether the panel is on screen. All
   three are always-visible left-hand panels.

     single (Regional View, Compare) — radios, one node, committed on click.
       No selection is not a state either of those charts has.
     multi  (Country profile)        — checkboxes with the indeterminate
       marker, `get`/`set` speak arrays, and NO selection is a real and useful
       state: it means every item this country prices, which is what that tab
       opens on.

   `opts.count(code)` is what the right-hand figure on a row means. It differs
   per mount because the useful count differs: how many countries price a node
   is the right number under a cross-country chart and a meaningless one on a
   single country's profile, where the question is how many items THIS country
   prices under it. `opts.rev()` lets a mount declare that its counts have gone
   stale (the country changed) so the panel repaints. */
function mount(id, opts) {
  var root = document.getElementById(id);
  if (!root) return null;

  var MULTI = !!opts.multi;
  var openSet = {}, lastWant = null;

  root.className = "cf";
  root.innerHTML =
    '<div class="cf-bar">' +
      '<input type="search" class="cf-search" id="' + id + '-q" ' +
        'placeholder="Search by name" aria-label="Search categories by name" ' +
        'autocomplete="off" spellcheck="false">' +
    '</div>' +
    '<div class="cf-list" id="' + id + '-list" role="' +
      (MULTI ? "group" : "radiogroup") + '" aria-label="Category"></div>' +
    '<div class="cf-none" id="' + id + '-none" hidden>Nothing here by that name.</div>' +
    /* The one button in this control, and only on a multi mount, where it does
       something no tick can do: put the chart back to every item. On a single
       mount "nothing picked" is not a state, so there is nothing to clear and
       no button. */
    (MULTI ? '<div class="cf-foot"><button type="button" class="cf-clear" id="' + id +
      '-clear">Show all items</button></div>' : "") +
    '<div class="cf-sum" id="' + id + '-sum"></div>';

  var elSearch = document.getElementById(id + "-q");
  var elList   = document.getElementById(id + "-list");
  var elNone   = document.getElementById(id + "-none");
  var elSum    = document.getElementById(id + "-sum");
  var elClear  = document.getElementById(id + "-clear");

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

  /* SINGLE: a radio, because the affordance has to say "one of these", and the
     browser's own radio-group behaviour — arrow keys, one dot at a time —
     is exactly the behaviour wanted.
     MULTI: a checkbox, ticked when the whole subtree is in, and stamped
     `indeterminate` after paint when only part of it is, so a half-selected
     parent never looks like an empty one.

     The figure on the right is whatever the mount says is worth counting.
     Default: how many countries price anything under the node. */
  function row(c, d, cur, hasKids, open) {
    var n = opts.count ? opts.count(c) : (((META[c] || {}).countries) || 0);
    var on = MULTI ? state(c, cur) === 1 : c === cur;
    return '<div class="cf-row" data-lvl="' + ((TAX[c] || {}).lvl || 1) + '"' +
        ' style="padding-left:' + (11 + d * 17) + 'px">' +
      '<input type="' + (MULTI ? "checkbox" : "radio") + '" class="cf-cb"' +
        (MULTI ? "" : ' name="' + id + '-sel"') + ' data-c="' + c +
        '" id="' + id + "-" + c + '"' + (on ? " checked" : "") + '>' +
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
  function paint(cur) {
    var f = visible(), out = [], shown = 0;
    var sig = (MULTI ? Object.keys(cur).sort().join(",") : cur) + "|" +
      (elSearch.value || "") + "|" + Object.keys(openSet).sort().join(",") + "|" +
      (opts.rev ? opts.rev() : "");
    if (sig === lastSig) return;
    var had = document.activeElement;
    var hadId = had && elList.contains(had) ? had.id : null;
    (function walk(list, d) {
      list.forEach(function (c) {
        if (f && !f.vis[c]) return;
        var k = kids(c).filter(function (x) { return !f || f.vis[x]; });
        var open = !!k.length && !!(openSet[c] || (f && f.auto[c]));
        out.push(row(c, d, cur, !!k.length, open));
        shown++;
        if (open) walk(k, d + 1);
      });
    })(ROOTS, 0);
    elList.innerHTML = out.join("");
    elNone.hidden = shown > 0;
    lastSig = sig;
    /* `indeterminate` is a property, never an attribute — it cannot be written
       into the markup above and has to be stamped on after the fact. It is the
       whole difference on screen between "all of Cereals" and "some of it". */
    if (MULTI) {
      Array.prototype.forEach.call(elList.querySelectorAll(".cf-cb"), function (b) {
        b.indeterminate = state(b.getAttribute("data-c"), cur) === 2; });
    }
    if (hadId) {
      var back = document.getElementById(hadId);
      if (back) back.focus();
    }
  }

  /* ---------------- the readout ----------------
     The tree does not name the choice on a button face, so the line under it
     does. On a single mount it is also the only place that can say "you asked
     for X and the chart is drawing Y", which happens whenever the requested
     node carries no series at the reader's current measure, frequency or
     window. On a multi mount it names every branch picked, in code order, or
     says out loud that nothing is picked and what that means. */
  function syncMulti() {
    var picked = opts.get() || [];
    var cur = expand(picked);
    picked.forEach(function (c) {
      var p = parent(c);
      while (p) { openSet[p] = 1; p = parent(p); }
    });
    paint(cur);
    if (elClear) elClear.disabled = !picked.length;
    elSum.innerHTML = picked.length
      ? "Showing " + picked.map(function (c) {
          return "<b>" + esc(title(c)) + '</b> <span class="cf-code">' + esc(c) +
            "</span>"; }).join(", ")
      : "<b>All items</b> — nothing picked, so nothing is filtered out.";
  }

  function syncSingle() {
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

  function sync() { if (MULTI) syncMulti(); else syncSingle(); }

  /* ---------------- events ----------------
     Every tick commits immediately, on the multi mount too. There is no Apply.
     An Apply button buys a deferred redraw and pays for it with a panel that
     shows one thing while the chart beside it shows another -- which is the
     exact divergence this rewrite removed by giving the tree no copy of the
     selection, and it is worse in an always-visible panel than it was in an
     overlay, because both halves of the disagreement are on screen at once.
     What it would have bought is not worth it either: a tick is one cascade
     over a memoised terminal list and one Chart.js update of at most 30 bars.
     Ticking three classes redraws three times and every one of those redraws
     is a true picture of what is ticked. */
  elSearch.oninput = function () { sync(); };
  elList.onclick = function (e) {
    var car = e.target.closest ? e.target.closest(".cf-car") : null;
    if (car && car.getAttribute("data-x")) {
      var c = car.getAttribute("data-x");
      if (openSet[c]) delete openSet[c]; else openSet[c] = 1;
      paint(MULTI ? expand(opts.get()) : opts.get());
    }
  };
  elList.onchange = function (e) {
    var b = e.target;
    if (!b || !b.classList || !b.classList.contains("cf-cb")) return;
    var c = b.getAttribute("data-c");
    if (!MULTI) { lastWant = c; opts.set(c); return; }
    /* Ticking a parent takes its whole subtree; unticking it gives the whole
       subtree back. The set is rebuilt from what the app currently holds, so
       two rapid ticks cannot race a stale local copy. */
    var cur = expand(opts.get());
    setSub(c, state(c, cur) !== 1, cur);
    opts.set(canonical(cur));
  };
  if (elClear) elClear.onclick = function () { opts.set([]); };

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
  }),
  /* The Country profile's ranking chart. MULTI, and the only mount where an
     empty selection means something: every item this country prices, which is
     what the tab opens on and what `S.cnodes = []` holds.

     Its counts are this country's items under the node, not the world's
     countries -- the number the two dropdowns this replaces printed beside
     every option ("Cereals - 12 items"), and the only count that answers a
     question anybody has while looking at one country. `rev` is the token those
     counts were computed under, so switching country or moving the evidence
     strip repaints them instead of leaving the previous ones beside the new
     bars. */
  mount("catfilterCtry", {
    multi: true,
    get: function () { return (window.APP && APP.node && APP.node("country")) || []; },
    set: function (codes) { if (window.APP && APP.setCNodes) APP.setCNodes(codes); },
    count: function (c) {
      return (window.APP && APP.ctryItems) ? APP.ctryItems(c) : 0; },
    rev: function () { return (window.APP && APP.ctryRev) ? APP.ctryRev() : ""; }
  })
].filter(Boolean);

window.CATFILTER = {
  sync: function () { MOUNTS.forEach(function (m) { m.sync(); }); }
};
})();
