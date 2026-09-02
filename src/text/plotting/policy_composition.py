"""The Policy Composition panel: script for the v6 dashboard's stacked bars.

Split out of :mod:`policy_dashboards_v6` alongside the timeline panel so the
renderer stays inside the repo's file-size limit. The string is inserted into
the dashboard's f-string as a value, so its braces are literal.
"""

COMPOSITION_JS = """
const chartTitle = document.getElementById("chartTitle");
const subtitle = document.getElementById("subtitle");
const svg = document.getElementById("chart");
const tooltip = document.getElementById("tooltip");
const legend = document.getElementById("legend");
const detailCard = document.getElementById("detailCard");

function initControls() {
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
  [groupSelect, subcategorySelect, statusSelect, titleInput].forEach(el => el.addEventListener("input", render));
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

function cleanText(s) { return (s || "").toString().replace(/\\s+/g, " ").trim(); }
function wrapCountryLabel(name) {
  if (D.displayName && D.displayName[name]) return D.displayName[name].split("\\n");
  if (name.length <= 12) return [name];
  const c = name.indexOf(", ");
  if (c > 0) return [name.slice(0, c + 1), name.slice(c + 2)];
  const mid = Math.ceil(name.length / 2);
  const sp = name.lastIndexOf(" ", mid + 6);
  if (sp > 2 && sp < name.length - 2) return [name.slice(0, sp), name.slice(sp + 1)];
  return [name];
}
function isActive(r) { return cleanText(r["Active or Proposed Date"]).toLowerCase().startsWith("active"); }
function isProposed(r) { return cleanText(r["Active or Proposed Date"]).toLowerCase().startsWith("proposed"); }

function filteredRows() {
  const cat = categorySelect.value;
  const sub = subcategorySelect.value;
  const status = statusSelect.value;
  return D.policies.filter(r => {
    if (cat !== "all" && r.category !== cat) return false;
    if (sub !== "all" && r.subcategory !== sub) return false;
    if (status === "active" && !isActive(r)) return false;
    if (status === "proposed" && !isProposed(r)) return false;
    return true;
  });
}

function visibleCountries(rows) {
  const group = D.countryGroups[groupSelect.value] || [];
  const allowed = new Set(group);
  const totals = new Map();
  rows.forEach(r => { if (!allowed.has(r.Country)) return; totals.set(r.Country, (totals.get(r.Country) || 0) + 1); });
  return group.filter(c => totals.has(c)).sort((a, b) => {
    const diff = (totals.get(b) || 0) - (totals.get(a) || 0);
    return diff !== 0 ? diff : a.localeCompare(b);
  });
}

function aggregate(rows, countries) {
  const byCountry = new Map();
  countries.forEach(c => byCountry.set(c, new Map()));
  rows.forEach(r => {
    if (!byCountry.has(r.Country)) return;
    const cmap = byCountry.get(r.Country);
    if (!cmap.has(r.category)) cmap.set(r.category, new Map());
    const smap = cmap.get(r.category);
    const key = r.subcategory || "(unspecified)";
    if (!smap.has(key)) smap.set(key, []);
    smap.get(key).push(r);
  });
  return byCountry;
}

function niceMax(v) { if (v <= 0) return 1; const head = v <= 1 ? 1 : 2; return Math.ceil(v) + head; }
function yTicks(max) {
  const top = niceMax(max);
  if (top <= 10) return Array.from({length: top + 1}, (_, i) => i);
  const step = Math.ceil(top / 8);
  const t = [];
  for (let v = 0; v <= top; v += step) t.push(v);
  if (t[t.length - 1] !== top) t.push(top);
  return t;
}

function escapeHTML(s) { return cleanText(s).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#039;"}[ch])); }
function truncate(s, n) { s = cleanText(s); return s.length > n ? s.slice(0, n - 1) + "…" : s; }
function titleCase(s) { return cleanText(s).replace(/\\b([a-z])/g, m => m.toUpperCase()); }

function tooltipHTML(country, cat, sub, policies) {
  const items = policies.map(r => `
    <li><strong>${escapeHTML(titleCase(r.Policy))}</strong>: ${escapeHTML(r["Policy Description"])}
      <br><span class="meta">${escapeHTML(r["Active or Proposed Date"])} · ${escapeHTML(r.Source)}</span>
    </li>`).join("");
  const catDisp = D.categoryDisplay[cat] || cat;
  return `<h3>${escapeHTML(country)}</h3><h4>${escapeHTML(catDisp)}</h4><h5>${escapeHTML(titleCase(sub))}</h5>` +
         `<p class="meta">${policies.length} polic${policies.length === 1 ? "y" : "ies"} in this segment</p><ul>${items}</ul>`;
}

function showTooltip(e, html) { tooltip.innerHTML = html; tooltip.style.display = "block"; moveTooltip(e); }
function moveTooltip(e) {
  const pad = 16;
  const rect = tooltip.getBoundingClientRect();
  let left = e.clientX + 14, top = e.clientY + 14;
  if (left + rect.width + pad > window.innerWidth) left = e.clientX - rect.width - 14;
  if (top + rect.height + pad > window.innerHeight) top = e.clientY - rect.height - 14;
  tooltip.style.left = Math.max(pad, left) + "px"; tooltip.style.top = Math.max(pad, top) + "px";
}
function hideTooltip() { tooltip.style.display = "none"; }

function pinDetails(country, cat, sub, policies) {
  const catDisp = D.categoryDisplay[cat] || cat;
  detailCard.innerHTML = `<h2>${escapeHTML(country)} — ${escapeHTML(catDisp)} / ${escapeHTML(titleCase(sub))}</h2>` +
    `<p>Clicked segment; policy details are pinned below.</p><div class="policy-list">` +
    policies.map(r => `<div class="policy-card" style="border-left-color:${D.categoryColor[cat] || "#999"}">` +
      `<div class="policy-title">${escapeHTML(titleCase(r.Policy))}</div>` +
      `<div class="policy-desc">${escapeHTML(r["Policy Description"])}</div>` +
      `<div class="policy-foot">${escapeHTML(r["Active or Proposed Date"])} · ${escapeHTML(r.Source)}</div></div>`).join("") + "</div>";
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

function render() {
  chartTitle.textContent = titleInput.value || "";
  const rows = filteredRows();
  const countries = visibleCountries(rows);
  const byCountry = aggregate(rows, countries);

  const totals = countries.map(c => {
    let t = 0;
    const cmap = byCountry.get(c);
    if (!cmap) return 0;
    cmap.forEach(smap => smap.forEach(arr => { t += arr.length; }));
    return t;
  });
  const maxTotal = Math.max(0, ...totals);
  const ticks = yTicks(maxTotal);
  const yMax = ticks[ticks.length - 1];

  const activeCats = new Set();
  byCountry.forEach(cmap => cmap.forEach((_, cat) => activeCats.add(cat)));

  document.getElementById("kpiPolicies").textContent = rows.filter(r => countries.includes(r.Country)).length;
  document.getElementById("kpiCountries").textContent = countries.length;
  document.getElementById("kpiCats").textContent = activeCats.size;
  document.getElementById("kpiMax").textContent = maxTotal;
  subtitle.textContent = `${groupSelect.value} · ${categorySelect.options[categorySelect.selectedIndex].text} · ${subcategorySelect.options[subcategorySelect.selectedIndex].text} · ${statusSelect.options[statusSelect.selectedIndex].text}`;

  drawLegend(activeCats);

  const countryCount = Math.max(countries.length, 1);
  const width = Math.max(920, countryCount * 82 + 130);
  const height = 600;
  const margin = {top: 20, right: 26, bottom: 80, left: 42};
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;
  const barSlot = plotW / countryCount;
  const barW = Math.min(48, barSlot * 0.48);
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("width", width); svg.setAttribute("height", height);
  svg.innerHTML = "";
  const ns = "http://www.w3.org/2000/svg";
  function el(name, attrs = {}, text = null) {
    const node = document.createElementNS(ns, name);
    Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
    if (text !== null) node.textContent = text;
    svg.appendChild(node);
    return node;
  }
  function yScale(v) { return margin.top + plotH - (v / yMax) * plotH; }
  ticks.forEach(t => {
    const y = yScale(t);
    el("line", {x1: margin.left, y1: y, x2: margin.left + plotW, y2: y, class: "axis-line", stroke: t === 0 ? "#cfcfcf" : "#d9d9d9", "stroke-width": t === 0 ? 1.4 : 1.2});
    el("text", {x: margin.left - 18, y: y + 5, "text-anchor": "end", fill: "#666", "font-size": "15"}, t);
  });

  countries.forEach((country, i) => {
    const xCenter = margin.left + i * barSlot + barSlot / 2;
    const x = xCenter - barW / 2;
    let cumulative = 0;
    const cmap = byCountry.get(country) || new Map();
    D.categories.forEach(cat => {
      const smap = cmap.get(cat);
      if (!smap) return;
      const subs = Array.from(smap.keys()).sort();
      subs.forEach(sub => {
        const policies = smap.get(sub) || [];
        const value = policies.length;
        if (value <= 0) return;
        const y1 = yScale(cumulative + value);
        const y0 = yScale(cumulative);
        const rect = el("rect", {x: x, y: y1, width: barW, height: Math.max(1, y0 - y1), fill: D.categoryColor[cat] || "#999", class: "bar-segment", "data-country": country, "data-category": cat, "data-subcategory": sub});
        const tip = tooltipHTML(country, cat, sub, policies);
        rect.addEventListener("mouseenter", e => showTooltip(e, tip));
        rect.addEventListener("mousemove", moveTooltip);
        rect.addEventListener("mouseleave", hideTooltip);
        rect.addEventListener("click", () => pinDetails(country, cat, sub, policies));
        cumulative += value;
      });
    });
    const text = document.createElementNS(ns, "text");
    text.setAttribute("x", xCenter);
    text.setAttribute("y", margin.top + plotH + 22);
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("fill", "#666");
    text.setAttribute("font-size", "13");
    const lines = wrapCountryLabel(country);
    lines.forEach((line, idx) => {
      const tsp = document.createElementNS(ns, "tspan");
      tsp.setAttribute("x", xCenter);
      tsp.setAttribute("dy", idx === 0 ? 0 : 15);
      tsp.textContent = line;
      text.appendChild(tsp);
    });
    svg.appendChild(text);
  });
  el("line", {x1: margin.left, y1: margin.top, x2: margin.left, y2: margin.top + plotH, class: "axis-line"});
  el("line", {x1: margin.left, y1: margin.top + plotH, x2: margin.left + plotW, y2: margin.top + plotH, class: "axis-line"});
  if (countries.length === 0) { el("text", {x: width / 2, y: height / 2, "text-anchor": "middle", fill: "#777", "font-size": "18"}, "No rows match the current filters."); }
}
"""
