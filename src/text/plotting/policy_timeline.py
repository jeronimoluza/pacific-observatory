"""The Policy Timing panel: CSS and script for the v6 dashboard's swimlane.

Kept apart from :mod:`policy_dashboards_v6` so neither file outgrows the repo's
size limit, and because the two charts share nothing but the filter controls.

Both strings are inserted into the dashboard's f-string as values, so braces
here are literal and need no doubling.

The chart draws one lane per taxonomy subcategory, grouped under its category,
against a year axis. Dots are a fixed size: an area-encoded dot answers "how
much coverage" at the cost of overlapping its neighbours, and the question this
panel exists to answer is when a measure appeared, not how loudly.

Under the lanes runs the corpus coverage band -- how many articles that
country's press produced each year. Without it an empty early stretch reads as
"no policy" when it often means "no corpus": the EAP corpus grows from 33k
articles in 2003 to 863k in 2025, so absence of dots is not evidence of absence
of policy until you can see the denominator.
"""

TIMELINE_CSS = """
  .tl-controls { display: flex; gap: 18px; align-items: center; margin: 4px 0 10px; font-size: 13px; color: #555; }
  .tl-controls label { display: flex; gap: 6px; align-items: center; cursor: pointer; }
  .lane-line { stroke: #eceff1; stroke-width: 1; }
  .lane-band { fill: #f7f9fa; }
  .lane-label { font-size: 12px; fill: #555; }
  .lane-head { font-size: 12.5px; font-weight: 700; fill: #263238; }
  .year-line { stroke: #f0f0f0; stroke-width: 1; }
  .year-label { font-size: 12px; fill: #777; }
  .cov-area { fill: #cfd8dc; fill-opacity: .55; }
  .cov-label { font-size: 11px; fill: #90a4ae; }
  .dot { cursor: pointer; stroke: #fff; stroke-width: 1.2; }
  .dot.sel { stroke: #111; stroke-width: 2.4; }
  /* A hollow dot was reported by the press but not verified by an analyst. */
  .dot.disc { stroke-width: 2.2; }
  .tl-key { font-size: 12px; color: #666; display: flex; gap: 14px; align-items: center; }
  .tl-key i { display: inline-block; width: 11px; height: 11px; border-radius: 50%;
              border: 2px solid #607d8b; margin-right: 5px; vertical-align: -1px; }
  .tl-key i.filled { background: #607d8b; }
"""

TIMELINE_JS = """
const timelineSvg = document.getElementById("timeline");
const timelineCard = document.getElementById("timelineCard");
const collapseBox = document.getElementById("tlCollapse");
const discBox = document.getElementById("tlDiscovered");
const tstate = { sel: null, collapsed: false, showDiscovered: true };
const LANE_SEP = " \\u2023 ";

function timelineRows() {
  const allowed = new Set(D.countryGroups[groupSelect.value] || []);
  return filteredRows().filter(r =>
    allowed.has(r.Country) && r.onset_year &&
    (tstate.showDiscovered || r.provenance !== "corpus"));
}

function laneKeyOf(r) {
  return tstate.collapsed ? r.category : r.category + LANE_SEP + r.subcategory;
}

// Lanes follow taxonomy order, not data order, so the same measure sits in the
// same row whatever the filter. Only occupied lanes are drawn.
function buildLanes(rows) {
  const present = new Set(rows.map(laneKeyOf));
  const lanes = [];
  D.categories.forEach(c => {
    if (tstate.collapsed) {
      if (present.has(c)) lanes.push({ key: c, label: D.categoryDisplay[c] || c, category: c, head: false });
      return;
    }
    const subs = (D.taxonomy && D.taxonomy[c]) || [];
    const mine = subs.filter(s => present.has(c + LANE_SEP + s));
    if (!mine.length) return;
    lanes.push({ key: null, label: D.categoryDisplay[c] || c, category: c, head: true });
    mine.forEach(s => lanes.push({ key: c + LANE_SEP + s, label: s, category: c, head: false }));
  });
  return lanes;
}

function coverageSeries() {
  const allowed = D.countryGroups[groupSelect.value] || [];
  const out = {};
  allowed.forEach(country => {
    const series = (D.coverage || {})[country] || {};
    Object.keys(series).forEach(y => { out[y] = (out[y] || 0) + series[y]; });
  });
  return out;
}

function renderTimeline() {
  timelineSvg.innerHTML = "";
  const ns = "http://www.w3.org/2000/svg";
  function el(name, attrs, text, parent) {
    const node = document.createElementNS(ns, name);
    Object.entries(attrs || {}).forEach(([k, v]) => node.setAttribute(k, v));
    if (text !== null && text !== undefined) node.textContent = text;
    (parent || timelineSvg).appendChild(node);
    return node;
  }
  const rows = timelineRows();
  const width = 1180;
  if (!rows.length) {
    timelineSvg.setAttribute("viewBox", "0 0 " + width + " 200");
    el("text", { x: width / 2, y: 100, "text-anchor": "middle", fill: "#777", "font-size": "17" },
       "No dated measures in this view.");
    return;
  }

  const cov = coverageSeries();
  const covYears = Object.keys(cov).map(Number).filter(y => cov[y] > 0);
  const dotYears = rows.map(r => r.onset_year);
  // The axis spans the corpus, not just the dots, so a gap can be read against
  // how much press there was to find a measure in.
  const y0 = Math.min.apply(null, dotYears.concat(covYears));
  const y1 = Math.max.apply(null, dotYears.concat(covYears));

  const lanes = buildLanes(rows);
  const laneH = 24, headH = 26, covH = 46;
  const margin = { top: 18, right: 30, bottom: 52, left: tstate.collapsed ? 230 : 290 };
  let yCursor = margin.top;
  lanes.forEach(l => { l.y = yCursor + (l.head ? headH : laneH) / 2; yCursor += l.head ? headH : laneH; });
  const plotBottom = yCursor;
  const height = plotBottom + covH + margin.bottom;
  const plotW = width - margin.left - margin.right;
  timelineSvg.setAttribute("viewBox", "0 0 " + width + " " + height);

  const xOf = y => margin.left + (y1 === y0 ? plotW / 2 : (y - y0) / (y1 - y0) * plotW);
  const laneAt = {};
  lanes.forEach(l => { if (l.key) laneAt[l.key] = l.y; });

  const span = y1 - y0;
  const step = span > 24 ? 4 : (span > 12 ? 3 : (span > 6 ? 2 : 1));
  for (let y = y0; y <= y1; y += step) {
    el("line", { x1: xOf(y), y1: margin.top - 4, x2: xOf(y), y2: plotBottom + covH, class: "year-line" });
    el("text", { x: xOf(y), y: plotBottom + covH + 22, "text-anchor": "middle", class: "year-label" }, String(y));
  }

  lanes.forEach((l, i) => {
    if (l.head) {
      el("text", { x: 14, y: l.y + 4, class: "lane-head" }, l.label);
      return;
    }
    if (i % 2 === 0) {
      el("rect", { x: margin.left, y: l.y - laneH / 2, width: plotW, height: laneH, class: "lane-band" });
    }
    el("line", { x1: margin.left, y1: l.y + laneH / 2, x2: width - margin.right, y2: l.y + laneH / 2, class: "lane-line" });
    const label = l.label.length > 38 ? l.label.slice(0, 36) + "\\u2026" : l.label;
    const t = el("text", { x: margin.left - 10, y: l.y + 4, "text-anchor": "end", class: "lane-label" }, label);
    el("title", {}, l.label, t);
  });

  // Corpus coverage band. Drawn as a filled step area under the lanes.
  const covMax = Math.max.apply(null, covYears.map(y => cov[y]).concat([1]));
  if (covYears.length) {
    const pts = [];
    for (let y = y0; y <= y1; y++) {
      const v = cov[y] || 0;
      pts.push([xOf(y), plotBottom + covH - (v / covMax) * (covH - 12)]);
    }
    const d = "M" + xOf(y0) + "," + (plotBottom + covH) + " " +
      pts.map(p => "L" + p[0] + "," + p[1]).join(" ") +
      " L" + xOf(y1) + "," + (plotBottom + covH) + " Z";
    el("path", { d: d, class: "cov-area" });
    el("text", { x: margin.left - 10, y: plotBottom + covH - 4, "text-anchor": "end", class: "cov-label" },
       "corpus articles/yr");
    el("text", { x: margin.left + 4, y: plotBottom + 12, class: "cov-label" },
       "peak " + covMax.toLocaleString());
  }

  // Fixed-radius dots. Several measures can share a lane-year cell, so they are
  // fanned deterministically rather than scaled -- size would encode coverage
  // at the cost of hiding neighbours.
  const seen = {};
  rows.slice().sort((a, b) => a.onset_year - b.onset_year || (a.Policy || "").localeCompare(b.Policy || ""))
    .forEach(r => {
      const key = laneKeyOf(r);
      const yy = laneAt[key];
      if (yy === undefined) return;
      const bucket = key + ":" + r.onset_year;
      const i = seen[bucket] = (seen[bucket] || 0) + 1;
      const dx = ((i - 1) % 5 - 2) * 4.5;
      const dy = (Math.floor((i - 1) / 5) % 3 - 1) * 6;
      const disc = r.provenance === "corpus";
      const colour = D.categoryColor[r.category] || "#888";
      const cls = (disc ? "dot disc" : "dot") + (tstate.sel === r ? " sel" : "");
      const dot = el("circle", {
        cx: xOf(r.onset_year) + dx, cy: yy + dy, r: 5,
        fill: disc ? "#ffffff" : colour,
        stroke: disc && tstate.sel !== r ? colour : undefined,
        "fill-opacity": disc ? 1 : 0.85,
        class: cls
      });
      dot.addEventListener("click", () => { tstate.sel = r; renderTimeline(); showMeasure(r); });
      el("title", {}, r.Country + " \\u2014 " + r.Policy + "\\n" +
         (D.categoryDisplay[r.category] || r.category) + " / " + r.subcategory + "\\n" +
         (disc
            ? "found in the news corpus \\u00b7 date basis: " + (r.date_basis || "unknown")
            : "tracker row") +
         "\\n" + (disc ? "dated " : "onset ") + r.onset_year +
         " \\u00b7 " + (r.n_articles || 0) + " article(s)", dot);
    });

  el("line", { x1: margin.left, y1: plotBottom + covH, x2: width - margin.right, y2: plotBottom + covH,
               class: "axis-line", stroke: "#cfcfcf" });
}

function showMeasure(r) {
  const yrs = r.years || {};
  const keys = Object.keys(yrs).sort();
  const peak = Math.max.apply(null, keys.map(k => yrs[k]).concat([1]));
  const spark = keys.map(k =>
    "<span style='display:inline-block;width:14px;vertical-align:bottom;margin-right:1px;background:" +
    (D.categoryColor[r.category] || "#888") + ";opacity:.75;height:" +
    Math.max(2, Math.round(34 * yrs[k] / peak)) + "px' title='" + k + ": " + yrs[k] + "'></span>").join("");
  const prov = r.provenance === "corpus"
    ? "<p style='font-size:12px;color:#b26a00'><strong>Found in the news corpus</strong> &middot; "
      + "date basis: " + (r.date_basis || "unknown")
      + (r.date_confidence ? " (" + r.date_confidence + " confidence)" : "")
      + " &middot; not yet verified against an official source.</p>"
    : "";
  timelineCard.innerHTML =
    "<h2>" + cleanText(r.Policy) + "</h2>" + prov +
    "<p><strong>" + cleanText(r.Country) + "</strong> &middot; " +
    (D.categoryDisplay[r.category] || r.category) + " / " + cleanText(r.subcategory) + "</p>" +
    "<p>" + cleanText(r["Policy Description"]) + "</p>" +
    "<p>Onset year <strong>" + r.onset_year + "</strong> &middot; peak <strong>" + (r.peak_year || "\\u2013") +
    "</strong> &middot; <strong>" + (r.n_articles || 0) + "</strong> matching articles &middot; " +
    "workbook status: <strong>" + (cleanText(r["Active or Proposed Date"]) || "\\u2013") + "</strong></p>" +
    "<div style='margin-top:8px'>" + spark + "</div>" +
    "<p style='font-size:12px;color:#888;margin-top:6px'>Articles per year, " +
    (keys[0] || "") + "\\u2013" + (keys[keys.length - 1] || "") + ".</p>";
}

collapseBox.addEventListener("change", () => {
  tstate.collapsed = collapseBox.checked;
  renderTimeline();
});

if (discBox) {
  discBox.addEventListener("change", () => {
    tstate.showDiscovered = discBox.checked;
    renderTimeline();
  });
}

document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("panel-composition").classList.toggle("hidden", btn.dataset.panel !== "composition");
    document.getElementById("panel-timing").classList.toggle("hidden", btn.dataset.panel !== "timing");
    if (btn.dataset.panel === "timing") renderTimeline();
  });
});
"""
