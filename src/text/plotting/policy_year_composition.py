"""The single Policy panel: composition stacked by year instead of by country.

Replaces the v6 dashboard's two panels. "Policy Timing" answered *when* and
"Policy Composition" answered *what*, and neither answered them together: the
timing swimlane spent its width on empty pre-corpus years and could only say
"a measure exists here", while the composition bars had no time axis at all.

This draws one stacked bar per year -- height is the number of distinct
measures, colour is the v6 Category, each segment inside a category is one
Subcategory -- so the reader gets the count, the mix and the date from one
mark. The x domain runs from the oldest measure in view, not from the corpus
start, because a decade of empty years is width spent saying nothing.

Both strings are inserted into the dashboard f-string as values, so braces
here are literal and need no doubling.
"""

YEAR_CSS = """
  .yc-controls { display: flex; gap: 18px; align-items: center; margin: 4px 0 10px; font-size: 13px; color: #555; }
  .yc-controls label { display: flex; gap: 6px; align-items: center; cursor: pointer; }
  .panel-split { display: flex; gap: 18px; align-items: flex-start; margin-top: 6px; }
  .chart-col { flex: 1 1 auto; min-width: 0; }
  .chart-col svg { min-width: 0; margin: 0; }
  .chart-frame { display: flex; align-items: flex-start; width: 100%; }
  .chart-frame .chart-wrap { flex: 1 1 auto; min-width: 0; }
  #chartAxis { flex: 0 0 auto; }
  .detail-col { flex: 0 0 340px; position: sticky; top: 12px; max-height: 640px; overflow-y: auto; }
  .detail-col .detail-card { margin: 0; }
  .detail-col .policy-list { grid-template-columns: 1fr; }
  .year-tick { font-size: 13px; fill: #666; }
  .axis-title { font-size: 12px; fill: #8a8a8a; letter-spacing: .02em; }
  @media (max-width: 900px) {
    .panel-split { flex-direction: column; }
    .detail-col { flex: 1 1 auto; width: 100%; position: static; max-height: none; }
  }
"""

YEAR_JS = """
const chartTitle = document.getElementById("chartTitle");
const subtitle = document.getElementById("subtitle");
const svg = document.getElementById("chart");
const legend = document.getElementById("legend");
const detailCard = document.getElementById("detailCard");
const chartScroll = document.getElementById("chartScroll");
const axisSvg = document.getElementById("chartAxis");
const discBox = document.getElementById("ycDiscovered");
const sqrtBox = document.getElementById("ycSqrt");
const ystate = { showDiscovered: true, sqrt: false, sig: "", pinned: null };

function cleanText(s) { return (s || "").toString().replace(/\\s+/g, " ").trim(); }
function escapeHTML(s) { return cleanText(s).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#039;"}[ch])); }
function titleCase(s) { return cleanText(s).replace(/\\b([a-z])/g, m => m.toUpperCase()); }
function isActive(r) { return cleanText(r["Active or Proposed Date"]).toLowerCase().startsWith("active"); }
function isProposed(r) { return cleanText(r["Active or Proposed Date"]).toLowerCase().startsWith("proposed"); }

function initControls() {
  Object.keys(D.subregionGroups || {}).forEach(name => {
    const opt = document.createElement("option");
    opt.value = name; opt.textContent = name;
    subregionSelect.appendChild(opt);
  });
  Object.keys(D.countryGroups).forEach((name, index) => {
    const opt = document.createElement("option");
    opt.value = name; opt.textContent = name;
    if (index === 0) opt.selected = true;
    groupSelect.appendChild(opt);
  });
  const allCat = document.createElement("option");
  allCat.value = "all"; allCat.textContent = "All policy categories";
  categorySelect.appendChild(allCat);
  D.categories.forEach(cat => {
    const opt = document.createElement("option");
    opt.value = cat; opt.textContent = D.categoryDisplay[cat] || cat;
    categorySelect.appendChild(opt);
  });
  refreshSubcategoryOptions();
  categorySelect.addEventListener("input", () => { refreshSubcategoryOptions(); render(); });
  [subregionSelect, groupSelect, subcategorySelect, statusSelect].forEach(el => el.addEventListener("input", render));
  if (discBox) discBox.addEventListener("change", () => {
    ystate.showDiscovered = discBox.checked; render();
  });
  if (sqrtBox) sqrtBox.addEventListener("change", () => {
    ystate.sqrt = sqrtBox.checked; render();
  });
}

function refreshSubcategoryOptions() {
  subcategorySelect.innerHTML = "";
  const cat = categorySelect.value;
  const allSub = document.createElement("option");
  allSub.value = "all"; allSub.textContent = "All policy subcategories";
  subcategorySelect.appendChild(allSub);
  let subs = [];
  if (cat === "all") {
    const seen = new Set();
    D.categories.forEach(c => (D.subcatsByCategory[c] || []).forEach(s => seen.add(s)));
    subs = Array.from(seen).sort();
  } else {
    subs = D.subcatsByCategory[cat] || [];
  }
  subs.forEach(s => {
    const opt = document.createElement("option");
    opt.value = s; opt.textContent = s;
    subcategorySelect.appendChild(opt);
  });
}

// The country dropdown still scopes the view; it just no longer sets the axis.
// Subregion and country view stack: a country must satisfy both.
function filteredRows() {
  const cat = categorySelect.value;
  const sub = subcategorySelect.value;
  const status = statusSelect.value;
  const allowed = new Set(D.countryGroups[groupSelect.value] || []);
  const inSub = subregionSelect.value === "all"
    ? null
    : new Set((D.subregionGroups || {})[subregionSelect.value] || []);
  return D.policies.filter(r => {
    if (!allowed.has(r.Country)) return false;
    if (inSub && !inSub.has(r.Country)) return false;
    if (cat !== "all" && r.category !== cat) return false;
    if (sub !== "all" && r.subcategory !== sub) return false;
    if (status === "active" && !isActive(r)) return false;
    if (status === "proposed" && !isProposed(r)) return false;
    if (!ystate.showDiscovered && r.provenance === "corpus") return false;
    return true;
  });
}

function niceMax(v) { if (v <= 0) return 1; const head = v <= 1 ? 1 : 2; return Math.ceil(v) + head; }
const SQRT_STOPS = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000];
function yTicks(max) {
  const top = niceMax(max);
  if (ystate.sqrt) {
    // Square-root spacing bunches the low stops together; drop any that would
    // land within 5% of the axis of the one below it.
    const t = [0];
    SQRT_STOPS.concat([top]).forEach(v => {
      if (v > top) return;
      const last = t[t.length - 1];
      if (Math.sqrt(v / top) - Math.sqrt(last / top) >= 0.05) t.push(v);
    });
    if (t[t.length - 1] !== top) {
      if (t.length > 1 && Math.sqrt(top / top) - Math.sqrt(t[t.length - 1] / top) < 0.05) t.pop();
      t.push(top);
    }
    return t;
  }
  if (top <= 10) return Array.from({length: top + 1}, (_, i) => i);
  const step = Math.ceil(top / 8);
  const t = [];
  for (let v = 0; v <= top; v += step) t.push(v);
  if (t[t.length - 1] !== top) t.push(top);
  return t;
}

function pinDetails(year, cat, sub, policies) {
  const catDisp = D.categoryDisplay[cat] || cat;
  ystate.pinned = { year: year, cat: cat, sub: sub };
  detailCard.innerHTML = `<h2>${year} — ${escapeHTML(catDisp)}</h2>` +
    `<p>${escapeHTML(titleCase(sub))} · ${policies.length} measure${policies.length === 1 ? "" : "s"}</p>` +
    `<div class="policy-list">` +
    policies.map(r => `<div class="policy-card" style="border-left-color:${D.categoryColor[cat] || "#999"}">` +
      `<div class="policy-title">${escapeHTML(r.Country)} — ${escapeHTML(titleCase(r.Policy))}</div>` +
      `<div class="policy-desc">${escapeHTML(r["Policy Description"])}</div>` +
      `<div class="policy-foot">${escapeHTML(r["Active or Proposed Date"])}` +
      `${r.Source ? " · " + escapeHTML(r.Source) : ""}</div></div>`).join("") + "</div>";
}

function drawLegend(activeCats) {
  legend.innerHTML = "";
  D.categories.forEach(c => {
    if (!activeCats.has(c)) return;
    const item = document.createElement("div");
    item.className = "legend-item";
    item.innerHTML = `<span class="legend-swatch" style="background:${D.categoryColor[c] || "#999"}"></span><span>${escapeHTML(D.categoryDisplay[c] || c)}</span>`;
    legend.appendChild(item);
  });
}

// Rows fall into (year, category, subcategory) cells. Years with no measure are
// still drawn, so a quiet stretch reads as quiet rather than being closed up.
function aggregate(rows, years) {
  const byYear = new Map();
  years.forEach(y => byYear.set(y, new Map()));
  rows.forEach(r => {
    const cmap = byYear.get(r.onset_year);
    if (!cmap) return;
    if (!cmap.has(r.category)) cmap.set(r.category, new Map());
    const smap = cmap.get(r.category);
    const key = r.subcategory || "(unspecified)";
    if (!smap.has(key)) smap.set(key, []);
    smap.get(key).push(r);
  });
  return byYear;
}

function render() {
  chartTitle.textContent = CHART_TITLE || "";
  const scope = filteredRows();
  const rows = scope.filter(r => r.onset_year);
  const undated = scope.length - rows.length;

  const countries = new Set(rows.map(r => r.Country));
  const activeCats = new Set(rows.map(r => r.category));

  const years = [];
  if (rows.length) {
    const ys = rows.map(r => r.onset_year);
    const lo = Math.min.apply(null, ys), hi = Math.max.apply(null, ys);
    for (let y = lo; y <= hi; y++) years.push(y);
  }
  const byYear = aggregate(rows, years);

  const totals = years.map(y => {
    let t = 0;
    (byYear.get(y) || new Map()).forEach(smap => smap.forEach(arr => { t += arr.length; }));
    return t;
  });
  const maxTotal = Math.max(0, ...totals);
  const ticks = yTicks(maxTotal);
  const yMax = ticks[ticks.length - 1];

  document.getElementById("kpiPolicies").textContent = rows.length;
  document.getElementById("kpiCountries").textContent = countries.size;
  document.getElementById("kpiCats").textContent = activeCats.size;
  document.getElementById("kpiMax").textContent = maxTotal;
  subtitle.textContent =
    (subregionSelect.value === "all" ? "" : `${subregionSelect.value} · `) +
    `${groupSelect.value} · ${categorySelect.options[categorySelect.selectedIndex].text}` +
    ` · ${subcategorySelect.options[subcategorySelect.selectedIndex].text}` +
    ` · ${statusSelect.options[statusSelect.selectedIndex].text}` +
    (years.length ? ` · ${years[0]}\\u2013${years[years.length - 1]}` : "") +
    (undated ? ` · ${undated} undated row${undated === 1 ? "" : "s"} not shown` : "");

  drawLegend(activeCats);

  const slot = 52;
  const height = 560;
  const axisW = 62;
  const margin = {top: 20, right: 26, bottom: 54, left: 8};
  const plotW = Math.max(320, years.length * slot);
  const width = margin.left + plotW + margin.right;
  const plotH = height - margin.top - margin.bottom;
  const barW = Math.min(34, slot * 0.62);

  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("width", width); svg.setAttribute("height", height);
  svg.innerHTML = "";
  if (axisSvg) axisSvg.innerHTML = "";
  const ns = "http://www.w3.org/2000/svg";
  function pen(target) {
    return function (name, attrs = {}, text = null) {
      const node = document.createElementNS(ns, name);
      Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
      if (text !== null) node.textContent = text;
      target.appendChild(node);
      return node;
    };
  }
  const el = pen(svg);
  const ax = pen(axisSvg || svg);

  if (!years.length) {
    if (axisSvg) { axisSvg.setAttribute("width", 0); axisSvg.setAttribute("height", 0); }
    el("text", {x: width / 2, y: height / 2, "text-anchor": "middle", fill: "#777", "font-size": "18"},
       "No dated measures match the current filters.");
    return;
  }

  if (axisSvg) {
    axisSvg.setAttribute("width", axisW);
    axisSvg.setAttribute("height", height);
    axisSvg.setAttribute("viewBox", `0 0 ${axisW} ${height}`);
  }

  // A tracker refreshed for currently-active measures piles hundreds of rows
  // into the newest year, and on a linear axis every earlier year collapses to
  // a line one pixel tall. The square-root option trades exact proportionality
  // for being able to see the years the chart exists to show.
  function yScale(v) {
    const f = ystate.sqrt ? Math.sqrt(Math.max(0, v) / yMax) : v / yMax;
    return margin.top + plotH - f * plotH;
  }
  ticks.forEach(t => {
    const y = yScale(t);
    el("line", {x1: 0, y1: y, x2: width, y2: y, class: "axis-line",
                stroke: t === 0 ? "#cfcfcf" : "#d9d9d9", "stroke-width": t === 0 ? 1.4 : 1.2});
    ax("line", {x1: axisW - 5, y1: y, x2: axisW, y2: y, class: "axis-line",
                stroke: t === 0 ? "#cfcfcf" : "#d9d9d9"});
    ax("text", {x: axisW - 10, y: y + 5, "text-anchor": "end", fill: "#666", "font-size": "14"}, t);
  });
  ax("text", {x: 0, y: 0, class: "axis-title", "text-anchor": "middle",
              transform: `translate(13, ${margin.top + plotH / 2}) rotate(-90)`},
     "distinct policies" + (ystate.sqrt ? " (\u221a scale)" : ""));
  ax("line", {x1: axisW, y1: margin.top, x2: axisW, y2: margin.top + plotH, class: "axis-line"});

  // A dense axis (2007-2026 is 20 slots) needs every label; a filtered view can
  // be narrower still. Only thin the labels when the slots get tight.
  const labelStep = slot >= 46 ? 1 : (slot >= 28 ? 2 : 5);
  years.forEach((year, i) => {
    const xCenter = margin.left + i * slot + slot / 2;
    const x = xCenter - barW / 2;
    let cumulative = 0;
    const cmap = byYear.get(year) || new Map();
    D.categories.forEach(cat => {
      const smap = cmap.get(cat);
      if (!smap) return;
      Array.from(smap.keys()).sort().forEach(sub => {
        const policies = smap.get(sub) || [];
        if (!policies.length) return;
        const y1 = yScale(cumulative + policies.length);
        const y0 = yScale(cumulative);
        const rect = el("rect", {x: x, y: y1, width: barW, height: Math.max(1, y0 - y1),
                                 fill: D.categoryColor[cat] || "#999", class: "bar-segment",
                                 "data-year": year, "data-category": cat, "data-subcategory": sub});
        rect.addEventListener("click", () => pinDetails(year, cat, sub, policies));
        cumulative += policies.length;
      });
    });
    if (i % labelStep === 0 || i === years.length - 1) {
      el("text", {x: xCenter, y: margin.top + plotH + 22, "text-anchor": "middle", class: "year-tick"},
         String(year));
    }
  });

  el("line", {x1: 0, y1: margin.top + plotH, x2: width, y2: margin.top + plotH, class: "axis-line"});

  // The newest year is the one being tracked, so the view opens on it and older
  // years are reached by scrolling left. Clicking a segment re-renders, and must
  // not yank the reader back to the right edge, so the offset is only reset when
  // the axis itself changed.
  if (chartScroll) {
    const sig = years[0] + ":" + years[years.length - 1] + ":" + width;
    if (sig !== ystate.sig) {
      ystate.sig = sig;
      chartScroll.scrollLeft = chartScroll.scrollWidth;
    }
  }
}
"""
