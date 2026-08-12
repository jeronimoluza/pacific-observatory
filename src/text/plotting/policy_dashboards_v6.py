"""v6-taxonomy renderer for the Fuel Crisis Policy addon.

Dispatched from ``policy_dashboards.generate_region`` when the workbook
exposes the closed (Category, Subcategory) pair instead of the legacy
8-value ``Label`` axis.

Bars are colored by the 6 v6 Categories; each stacked segment is a unique
(country, category, subcategory) tuple. A cascading subcategory filter
sits next to the category filter.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


CATEGORY_DISPLAY: Dict[str, str] = {
    "agriculture": "Agriculture",
    "energy": "Energy",
    "firm liquidity and financial support": "Firm liquidity & financial support",
    "fiscal measures": "Fiscal measures",
    "regulatory and trade facilitation reforms": "Regulatory & trade facilitation reforms",
    "social protection": "Social protection",
}

CATEGORY_COLOR: Dict[str, str] = {
    "agriculture": "#9bbb59",
    "energy": "#4f81bd",
    "firm liquidity and financial support": "#8064a2",
    "fiscal measures": "#f79646",
    "regulatory and trade facilitation reforms": "#4bacc6",
    "social protection": "#c0504d",
}


def _norm_cat(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip().lower()


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def has_v6_columns(rows: List[Dict[str, str]]) -> bool:
    """Return True if at least one row carries a non-empty Category value."""
    return any(_clean(r.get("Category", "")) for r in rows)


def build_v6_dashboard_data(
    rows: List[Dict[str, str]],
    region_cfg: Dict[str, Any],
    xlsx_path: Path,
    sheet_name: str,
    excluded_count: int,
    country_groups: Dict[str, List[str]],
    display_names: Dict[str, str],
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Shape the dashboard payload for the v6 renderer.

    ``country_groups`` and ``display_names`` are passed in so that the host
    module owns the region carve-out logic (PICs, regional groups, etc.).
    """
    policies: List[Dict[str, str]] = []
    blank_cat = 0
    for row in rows:
        cat = _norm_cat(row.get("Category"))
        if not cat:
            blank_cat += 1
            continue
        policies.append(
            {
                "Country": _clean(row.get("Country")),
                "Policy": _clean(row.get("Policy")),
                "Policy Description": _clean(row.get("Policy Description")),
                "Active or Proposed Date": _clean(row.get("Active or Proposed Date")),
                "Source": _clean(row.get("Source")),
                "category": cat,
                "category_display": CATEGORY_DISPLAY.get(cat, cat),
                "subcategory": _clean(row.get("Subcategory")),
            }
        )

    present = {p["category"] for p in policies}
    categories_order = [c for c in CATEGORY_DISPLAY if c in present]
    unknown = sorted(present - set(CATEGORY_DISPLAY))
    if unknown:
        # Surface as a build-time warning; still render so user can spot it.
        print(
            f"  WARN: v6 categories outside closed enum will appear unstyled: {unknown}"
        )
        categories_order += unknown

    subcats_by_category: Dict[str, List[str]] = {}
    for cat in categories_order:
        subs = sorted(
            {
                p["subcategory"]
                for p in policies
                if p["category"] == cat and p["subcategory"]
            }
        )
        subcats_by_category[cat] = subs

    # Filter country_groups down to countries actually present in the v6-filtered
    # row set so the dropdown does not list empty buckets.
    present_countries = {p["Country"] for p in policies}
    filtered_groups: Dict[str, List[str]] = {}
    for name, members in country_groups.items():
        kept = [m for m in members if m in present_countries]
        if kept:
            filtered_groups[name] = kept

    metadata = {
        "generated_on": dt.date.today().isoformat(),
        "source_file": xlsx_path.name,
        "source_sheet": sheet_name,
        "row_count": len(rows) + excluded_count,
        "country_count": len(present_countries),
        "dashboard_version": "policy_dashboards_v6",
        "region": region_cfg.get("display_name", region_cfg.get("key", "Region")),
        "included_rows": len(policies),
    }
    if excluded_count:
        metadata["excluded_rows"] = excluded_count
    if blank_cat:
        metadata["blank_category_rows_dropped"] = blank_cat
    if region_cfg.get("exclude_countries"):
        metadata["excluded_countries"] = region_cfg.get("exclude_countries")

    data = {
        "policies": policies,
        "categories": categories_order,
        "categoryDisplay": {c: CATEGORY_DISPLAY.get(c, c) for c in categories_order},
        "categoryColor": {
            c: CATEGORY_COLOR.get(c, "#999999") for c in categories_order
        },
        "subcatsByCategory": subcats_by_category,
        "countryGroups": filtered_groups,
        "displayName": {
            c: display_names[c] for c in present_countries if c in display_names
        },
        "metadata": metadata,
    }
    colors = {c: CATEGORY_COLOR.get(c, "#999999") for c in categories_order}
    return data, colors


def make_v6_html(
    data: Dict[str, Any],
    chart_title: str,
    page_title: str = "Fuel Crisis Policy Dashboard",
    chart_aria_subject: str = "fuel-crisis",
) -> str:
    data_json = json.dumps(data, ensure_ascii=False, indent=2)
    safe_title = json.dumps(chart_title, ensure_ascii=False)

    return f"""<!doctype html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
<title>{page_title}</title>
<style>
  html, body {{ margin: 0; padding: 0; background: #f5f6f8; font-family: Calibri, Arial, Helvetica, sans-serif; color: #555; }}
  .page {{ max-width: 1180px; margin: 24px auto; padding: 0 16px 32px; }}
  .dashboard {{ background: #fff; border: 1px solid #d0d0d0; box-shadow: 0 1px 4px rgba(0,0,0,0.08); padding: 20px 24px 28px; }}
  .controls {{ display: grid; grid-template-columns: minmax(180px, 1fr) minmax(180px, 1.1fr) minmax(180px, 1.2fr) minmax(140px, .8fr) minmax(180px, 1fr); gap: 12px; align-items: end; margin-bottom: 14px; }}
  .control-group label {{ display: block; font-size: 12px; color: #666; margin-bottom: 4px; text-transform: uppercase; letter-spacing: .03em; }}
  select, input[type=\"text\"] {{ width: 100%; box-sizing: border-box; border: 1px solid #cfcfcf; border-radius: 4px; padding: 7px 8px; font-size: 14px; background: #fff; color: #333; }}
  .kpis {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-bottom: 4px; }}
  .kpi {{ border: 1px solid #e2e2e2; border-radius: 6px; padding: 8px 10px; background: #fbfbfb; }}
  .kpi .value {{ font-size: 24px; line-height: 1.1; color: #444; }}
  .kpi .label {{ font-size: 12px; color: #777; }}
  .chart-title {{ text-align: center; font-size: 25px; font-weight: 400; margin: 18px 0 0; color: #555; }}
  .chart-subtitle {{ text-align: center; font-size: 12px; color: #888; margin: 4px 0 10px; }}
  .chart-wrap {{ position: relative; width: 100%; overflow-x: auto; padding-bottom: 4px; }}
  svg {{ display: block; margin: 0 auto; background: #fff; min-width: 900px; }}
  .axis text {{ font-size: 15px; fill: #666; }}
  .grid line {{ stroke: #d9d9d9; stroke-width: 1.2; }}
  .axis-line {{ stroke: #cfcfcf; stroke-width: 1.2; }}
  .bar-segment {{ cursor: help; shape-rendering: crispEdges; stroke: #fff; stroke-width: 0.5px; }}
  .bar-segment:hover {{ filter: brightness(0.94); stroke: #333; stroke-width: 1px; }}
  .legend {{ display: flex; flex-wrap: wrap; justify-content: center; align-items: center; gap: 12px 20px; max-width: 900px; margin: 8px auto 0; font-size: 15px; color: #666; }}
  .legend-item {{ display: flex; align-items: center; gap: 5px; white-space: nowrap; }}
  .legend-swatch {{ width: 10px; height: 10px; display: inline-block; }}
  .tooltip {{ position: fixed; z-index: 20; pointer-events: none; display: none; width: min(440px, calc(100vw - 32px)); background: rgba(255,255,255,0.98); color: #333; border: 1px solid #bdbdbd; border-radius: 6px; box-shadow: 0 4px 18px rgba(0,0,0,0.18); padding: 10px 12px; font-size: 13px; line-height: 1.35; }}
  .tooltip h3 {{ font-size: 15px; margin: 0 0 4px; color: #333; }}
  .tooltip h4 {{ font-size: 13px; margin: 0 0 2px; color: #555; font-weight: 600; }}
  .tooltip h5 {{ font-size: 12px; margin: 0 0 7px; color: #666; font-weight: 500; font-style: italic; }}
  .tooltip .meta {{ margin: 0 0 7px; color: #666; font-size: 12px; }}
  .tooltip ul {{ margin: 6px 0 0 18px; padding: 0; }}
  .tooltip li {{ margin: 0 0 6px; }}
  .tooltip strong {{ color: #333; }}
  .detail-panel {{ margin-top: 20px; display: grid; grid-template-columns: 1fr; gap: 10px; }}
  .detail-card {{ border: 1px solid #e2e2e2; border-radius: 6px; background: #fff; padding: 12px 14px; }}
  .detail-card h2 {{ font-size: 17px; font-weight: 600; margin: 0 0 8px; color: #444; }}
  .detail-card p {{ margin: 4px 0; font-size: 13px; color: #666; }}
  .policy-list {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 8px; margin-top: 8px; }}
  .policy-card {{ border-left: 5px solid #ccc; background: #fafafa; padding: 8px 10px; min-height: 72px; }}
  .policy-card .policy-title {{ font-weight: 600; color: #333; font-size: 13px; }}
  .policy-card .policy-desc {{ color: #666; font-size: 12px; margin-top: 3px; }}
  .policy-card .policy-foot {{ color: #888; font-size: 11px; margin-top: 5px; }}
  .note {{ margin-top: 14px; font-size: 12px; color: #777; }}
  @media (max-width: 820px) {{ .controls {{ grid-template-columns: 1fr 1fr; }} .kpis {{ grid-template-columns: 1fr 1fr; }} }}
  @media (max-width: 540px) {{ .controls, .kpis {{ grid-template-columns: 1fr; }} .dashboard {{ padding: 14px; }} }}
</style>
</head>
<body>
<div class=\"page\">
  <div class=\"dashboard\">
    <div class=\"controls\">
      <div class=\"control-group\"><label for=\"groupSelect\">Country view</label><select id=\"groupSelect\"></select></div>
      <div class=\"control-group\"><label for=\"categorySelect\">Policy category</label><select id=\"categorySelect\"></select></div>
      <div class=\"control-group\"><label for=\"subcategorySelect\">Policy subcategory</label><select id=\"subcategorySelect\"></select></div>
      <div class=\"control-group\"><label for=\"statusSelect\">Status</label><select id=\"statusSelect\"><option value=\"all\">Active and proposed</option><option value=\"active\">Active only</option><option value=\"proposed\">Proposed only</option></select></div>
      <div class=\"control-group\"><label for=\"titleInput\">Chart title</label><input id=\"titleInput\" type=\"text\" value={safe_title} /></div>
    </div>
    <div class=\"kpis\">
      <div class=\"kpi\"><div class=\"value\" id=\"kpiPolicies\">0</div><div class=\"label\">Policies in current view</div></div>
      <div class=\"kpi\"><div class=\"value\" id=\"kpiCountries\">0</div><div class=\"label\">Countries/economies shown</div></div>
      <div class=\"kpi\"><div class=\"value\" id=\"kpiCats\">0</div><div class=\"label\">Policy categories present</div></div>
      <div class=\"kpi\"><div class=\"value\" id=\"kpiMax\">0</div><div class=\"label\">Largest country total</div></div>
    </div>
    <h1 id=\"chartTitle\" class=\"chart-title\"></h1>
    <div class=\"chart-subtitle\" id=\"subtitle\"></div>
    <div class=\"chart-wrap\">
      <svg id=\"chart\" aria-label=\"Stacked bar chart of {chart_aria_subject} policy responses by country, category and subcategory\"></svg>
      <div id=\"tooltip\" class=\"tooltip\"></div>
    </div>
    <div id=\"legend\" class=\"legend\"></div>
    <div class=\"detail-panel\"><div class=\"detail-card\" id=\"detailCard\"><h2>Policy details</h2><p>Hover over a shaded bar segment to see an info tip. Click a segment to pin its policy details here.</p></div></div>
    <div class=\"note\">Note: bar color encodes policy category; each stacked segment within a category is a distinct policy subcategory. Subcategory filter cascades off the category selection.</div>
  </div>
</div>
<script>
const D = {data_json};
const state = {{ pinned: null }};

const groupSelect = document.getElementById(\"groupSelect\");
const categorySelect = document.getElementById(\"categorySelect\");
const subcategorySelect = document.getElementById(\"subcategorySelect\");
const statusSelect = document.getElementById(\"statusSelect\");
const titleInput = document.getElementById(\"titleInput\");
const chartTitle = document.getElementById(\"chartTitle\");
const subtitle = document.getElementById(\"subtitle\");
const svg = document.getElementById(\"chart\");
const tooltip = document.getElementById(\"tooltip\");
const legend = document.getElementById(\"legend\");
const detailCard = document.getElementById(\"detailCard\");

function initControls() {{
  Object.keys(D.countryGroups).forEach((name, index) => {{
    const opt = document.createElement(\"option\");
    opt.value = name; opt.textContent = name;
    if (index === 0) opt.selected = true;
    groupSelect.appendChild(opt);
  }});
  const allCat = document.createElement(\"option\");
  allCat.value = \"all\"; allCat.textContent = \"All policy categories\";
  categorySelect.appendChild(allCat);
  D.categories.forEach(cat => {{
    const opt = document.createElement(\"option\");
    opt.value = cat; opt.textContent = D.categoryDisplay[cat] || cat;
    categorySelect.appendChild(opt);
  }});
  refreshSubcategoryOptions();
  categorySelect.addEventListener(\"input\", () => {{ refreshSubcategoryOptions(); render(); }});
  [groupSelect, subcategorySelect, statusSelect, titleInput].forEach(el => el.addEventListener(\"input\", render));
}}

function refreshSubcategoryOptions() {{
  subcategorySelect.innerHTML = \"\";
  const cat = categorySelect.value;
  const allSub = document.createElement(\"option\");
  allSub.value = \"all\"; allSub.textContent = \"All policy subcategories\";
  subcategorySelect.appendChild(allSub);
  let subs = [];
  if (cat === \"all\") {{
    const seen = new Set();
    D.categories.forEach(c => (D.subcatsByCategory[c] || []).forEach(s => seen.add(s)));
    subs = Array.from(seen).sort();
  }} else {{
    subs = D.subcatsByCategory[cat] || [];
  }}
  subs.forEach(s => {{
    const opt = document.createElement(\"option\");
    opt.value = s; opt.textContent = s;
    subcategorySelect.appendChild(opt);
  }});
}}

function cleanText(s) {{ return (s || \"\").toString().replace(/\\s+/g, \" \").trim(); }}
function wrapCountryLabel(name) {{
  if (D.displayName && D.displayName[name]) return D.displayName[name].split(\"\\n\");
  if (name.length <= 12) return [name];
  const c = name.indexOf(\", \");
  if (c > 0) return [name.slice(0, c + 1), name.slice(c + 2)];
  const mid = Math.ceil(name.length / 2);
  const sp = name.lastIndexOf(\" \", mid + 6);
  if (sp > 2 && sp < name.length - 2) return [name.slice(0, sp), name.slice(sp + 1)];
  return [name];
}}
function isActive(r) {{ return cleanText(r[\"Active or Proposed Date\"]).toLowerCase().startsWith(\"active\"); }}
function isProposed(r) {{ return cleanText(r[\"Active or Proposed Date\"]).toLowerCase().startsWith(\"proposed\"); }}

function filteredRows() {{
  const cat = categorySelect.value;
  const sub = subcategorySelect.value;
  const status = statusSelect.value;
  return D.policies.filter(r => {{
    if (cat !== \"all\" && r.category !== cat) return false;
    if (sub !== \"all\" && r.subcategory !== sub) return false;
    if (status === \"active\" && !isActive(r)) return false;
    if (status === \"proposed\" && !isProposed(r)) return false;
    return true;
  }});
}}

function visibleCountries(rows) {{
  const group = D.countryGroups[groupSelect.value] || [];
  const allowed = new Set(group);
  const totals = new Map();
  rows.forEach(r => {{ if (!allowed.has(r.Country)) return; totals.set(r.Country, (totals.get(r.Country) || 0) + 1); }});
  return group.filter(c => totals.has(c)).sort((a, b) => {{
    const diff = (totals.get(b) || 0) - (totals.get(a) || 0);
    return diff !== 0 ? diff : a.localeCompare(b);
  }});
}}

function aggregate(rows, countries) {{
  const byCountry = new Map();
  countries.forEach(c => byCountry.set(c, new Map()));
  rows.forEach(r => {{
    if (!byCountry.has(r.Country)) return;
    const cmap = byCountry.get(r.Country);
    if (!cmap.has(r.category)) cmap.set(r.category, new Map());
    const smap = cmap.get(r.category);
    const key = r.subcategory || \"(unspecified)\";
    if (!smap.has(key)) smap.set(key, []);
    smap.get(key).push(r);
  }});
  return byCountry;
}}

function niceMax(v) {{ if (v <= 0) return 1; const head = v <= 1 ? 1 : 2; return Math.ceil(v) + head; }}
function yTicks(max) {{
  const top = niceMax(max);
  if (top <= 10) return Array.from({{length: top + 1}}, (_, i) => i);
  const step = Math.ceil(top / 8);
  const t = [];
  for (let v = 0; v <= top; v += step) t.push(v);
  if (t[t.length - 1] !== top) t.push(top);
  return t;
}}

function escapeHTML(s) {{ return cleanText(s).replace(/[&<>\"']/g, ch => ({{\"&\":\"&amp;\",\"<\":\"&lt;\",\">\":\"&gt;\",\"\\\"\":\"&quot;\",\"'\":\"&#039;\"}}[ch])); }}
function truncate(s, n) {{ s = cleanText(s); return s.length > n ? s.slice(0, n - 1) + \"…\" : s; }}
function titleCase(s) {{ return cleanText(s).replace(/\\b([a-z])/g, m => m.toUpperCase()); }}

function tooltipHTML(country, cat, sub, policies) {{
  const items = policies.map(r => `
    <li><strong>${{escapeHTML(titleCase(r.Policy))}}</strong>: ${{escapeHTML(r[\"Policy Description\"])}}
      <br><span class=\"meta\">${{escapeHTML(r[\"Active or Proposed Date\"])}} · ${{escapeHTML(r.Source)}}</span>
    </li>`).join(\"\");
  const catDisp = D.categoryDisplay[cat] || cat;
  return `<h3>${{escapeHTML(country)}}</h3><h4>${{escapeHTML(catDisp)}}</h4><h5>${{escapeHTML(titleCase(sub))}}</h5>` +
         `<p class=\"meta\">${{policies.length}} polic${{policies.length === 1 ? \"y\" : \"ies\"}} in this segment</p><ul>${{items}}</ul>`;
}}

function showTooltip(e, html) {{ tooltip.innerHTML = html; tooltip.style.display = \"block\"; moveTooltip(e); }}
function moveTooltip(e) {{
  const pad = 16;
  const rect = tooltip.getBoundingClientRect();
  let left = e.clientX + 14, top = e.clientY + 14;
  if (left + rect.width + pad > window.innerWidth) left = e.clientX - rect.width - 14;
  if (top + rect.height + pad > window.innerHeight) top = e.clientY - rect.height - 14;
  tooltip.style.left = Math.max(pad, left) + \"px\"; tooltip.style.top = Math.max(pad, top) + \"px\";
}}
function hideTooltip() {{ tooltip.style.display = \"none\"; }}

function pinDetails(country, cat, sub, policies) {{
  const catDisp = D.categoryDisplay[cat] || cat;
  detailCard.innerHTML = `<h2>${{escapeHTML(country)}} — ${{escapeHTML(catDisp)}} / ${{escapeHTML(titleCase(sub))}}</h2>` +
    `<p>Clicked segment; policy details are pinned below.</p><div class=\"policy-list\">` +
    policies.map(r => `<div class=\"policy-card\" style=\"border-left-color:${{D.categoryColor[cat] || \"#999\"}}\">` +
      `<div class=\"policy-title\">${{escapeHTML(titleCase(r.Policy))}}</div>` +
      `<div class=\"policy-desc\">${{escapeHTML(r[\"Policy Description\"])}}</div>` +
      `<div class=\"policy-foot\">${{escapeHTML(r[\"Active or Proposed Date\"])}} · ${{escapeHTML(r.Source)}}</div></div>`).join(\"\") + \"</div>\";
}}

function drawLegend(activeCats) {{
  legend.innerHTML = \"\";
  D.categories.forEach(c => {{
    if (!activeCats.has(c)) return;
    const item = document.createElement(\"div\");
    item.className = \"legend-item\";
    item.innerHTML = `<span class=\"legend-swatch\" style=\"background:${{D.categoryColor[c] || \"#999\"}}\"></span><span>${{escapeHTML(D.categoryDisplay[c] || c)}}</span>`;
    legend.appendChild(item);
  }});
}}

function render() {{
  chartTitle.textContent = titleInput.value || \"\";
  const rows = filteredRows();
  const countries = visibleCountries(rows);
  const byCountry = aggregate(rows, countries);

  const totals = countries.map(c => {{
    let t = 0;
    const cmap = byCountry.get(c);
    if (!cmap) return 0;
    cmap.forEach(smap => smap.forEach(arr => {{ t += arr.length; }}));
    return t;
  }});
  const maxTotal = Math.max(0, ...totals);
  const ticks = yTicks(maxTotal);
  const yMax = ticks[ticks.length - 1];

  const activeCats = new Set();
  byCountry.forEach(cmap => cmap.forEach((_, cat) => activeCats.add(cat)));

  document.getElementById(\"kpiPolicies\").textContent = rows.filter(r => countries.includes(r.Country)).length;
  document.getElementById(\"kpiCountries\").textContent = countries.length;
  document.getElementById(\"kpiCats\").textContent = activeCats.size;
  document.getElementById(\"kpiMax\").textContent = maxTotal;
  subtitle.textContent = `${{groupSelect.value}} · ${{categorySelect.options[categorySelect.selectedIndex].text}} · ${{subcategorySelect.options[subcategorySelect.selectedIndex].text}} · ${{statusSelect.options[statusSelect.selectedIndex].text}}`;

  drawLegend(activeCats);

  const countryCount = Math.max(countries.length, 1);
  const width = Math.max(920, countryCount * 82 + 130);
  const height = 600;
  const margin = {{top: 20, right: 26, bottom: 80, left: 42}};
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;
  const barSlot = plotW / countryCount;
  const barW = Math.min(48, barSlot * 0.48);
  svg.setAttribute(\"viewBox\", `0 0 ${{width}} ${{height}}`);
  svg.setAttribute(\"width\", width); svg.setAttribute(\"height\", height);
  svg.innerHTML = \"\";
  const ns = \"http://www.w3.org/2000/svg\";
  function el(name, attrs = {{}}, text = null) {{
    const node = document.createElementNS(ns, name);
    Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
    if (text !== null) node.textContent = text;
    svg.appendChild(node);
    return node;
  }}
  function yScale(v) {{ return margin.top + plotH - (v / yMax) * plotH; }}
  ticks.forEach(t => {{
    const y = yScale(t);
    el(\"line\", {{x1: margin.left, y1: y, x2: margin.left + plotW, y2: y, class: \"axis-line\", stroke: t === 0 ? \"#cfcfcf\" : \"#d9d9d9\", \"stroke-width\": t === 0 ? 1.4 : 1.2}});
    el(\"text\", {{x: margin.left - 18, y: y + 5, \"text-anchor\": \"end\", fill: \"#666\", \"font-size\": \"15\"}}, t);
  }});

  countries.forEach((country, i) => {{
    const xCenter = margin.left + i * barSlot + barSlot / 2;
    const x = xCenter - barW / 2;
    let cumulative = 0;
    const cmap = byCountry.get(country) || new Map();
    D.categories.forEach(cat => {{
      const smap = cmap.get(cat);
      if (!smap) return;
      const subs = Array.from(smap.keys()).sort();
      subs.forEach(sub => {{
        const policies = smap.get(sub) || [];
        const value = policies.length;
        if (value <= 0) return;
        const y1 = yScale(cumulative + value);
        const y0 = yScale(cumulative);
        const rect = el(\"rect\", {{x: x, y: y1, width: barW, height: Math.max(1, y0 - y1), fill: D.categoryColor[cat] || \"#999\", class: \"bar-segment\", \"data-country\": country, \"data-category\": cat, \"data-subcategory\": sub}});
        const tip = tooltipHTML(country, cat, sub, policies);
        rect.addEventListener(\"mouseenter\", e => showTooltip(e, tip));
        rect.addEventListener(\"mousemove\", moveTooltip);
        rect.addEventListener(\"mouseleave\", hideTooltip);
        rect.addEventListener(\"click\", () => pinDetails(country, cat, sub, policies));
        cumulative += value;
      }});
    }});
    const text = document.createElementNS(ns, \"text\");
    text.setAttribute(\"x\", xCenter);
    text.setAttribute(\"y\", margin.top + plotH + 22);
    text.setAttribute(\"text-anchor\", \"middle\");
    text.setAttribute(\"fill\", \"#666\");
    text.setAttribute(\"font-size\", \"13\");
    const lines = wrapCountryLabel(country);
    lines.forEach((line, idx) => {{
      const tsp = document.createElementNS(ns, \"tspan\");
      tsp.setAttribute(\"x\", xCenter);
      tsp.setAttribute(\"dy\", idx === 0 ? 0 : 15);
      tsp.textContent = line;
      text.appendChild(tsp);
    }});
    svg.appendChild(text);
  }});
  el(\"line\", {{x1: margin.left, y1: margin.top, x2: margin.left, y2: margin.top + plotH, class: \"axis-line\"}});
  el(\"line\", {{x1: margin.left, y1: margin.top + plotH, x2: margin.left + plotW, y2: margin.top + plotH, class: \"axis-line\"}});
  if (countries.length === 0) {{ el(\"text\", {{x: width / 2, y: height / 2, \"text-anchor\": \"middle\", fill: \"#777\", \"font-size\": \"18\"}}, \"No rows match the current filters.\"); }}
}}
initControls();
render();
</script>
</body>
</html>"""
