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

from text.plotting.policy_subregions import ALL_LABEL, build_subregion_groups
from text.plotting.policy_year_composition import YEAR_CSS, YEAR_JS


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


_MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
# Spelling the months out matters: a bare ``[a-z]{3}`` matches "Act" in
# "Active 22-Aug-26" and the year is then read off the day.
_MON_YY_RE = re.compile(r"\b(" + "|".join(_MONTHS) + r")[a-z]*[-\s](\d{2})\b", re.I)
_BARE_YY_RE = re.compile(r"\b(\d{2})\b\s*$")


def _policy_year(raw: Any) -> int | None:
    """Year the workbook says a measure was active or proposed.

    The column is free text an analyst typed: ``Active 01-Aug-26``,
    ``Proposed April 2026``, ``Active May-Jun 26``, ``24-Apr-2026``. A
    four-digit year wins; failing that a ``Mon-YY`` pair; failing that a
    trailing two-digit year, which only appears after a month name.

    This must decide where a workbook dot sits. The corpus ``onset_year``
    cannot: it is the first year the policy's keywords reach 15% of their
    peak coverage, so a recurring measure like the FCCC's monthly fuel
    price cycle onsets in 2009 while the measure itself dates to 2026.
    """
    text = _clean(raw)
    if not text or text.lower() in {"nan", "none", "tbd", "n/a"}:
        return None
    match = _YEAR_RE.search(text)
    if match:
        return int(match.group(0))
    match = _MON_YY_RE.search(text)
    if match and match.group(1).lower() in _MONTHS:
        return 2000 + int(match.group(2))
    match = _BARE_YY_RE.search(text)
    if match and any(m in text.lower() for m in _MONTHS):
        return 2000 + int(match.group(1))
    return None


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
    timeline: Dict[str, Any] | None = None,
    coverage: Dict[str, Dict[str, int]] | None = None,
    discovered: List[Dict[str, Any]] | None = None,
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Shape the dashboard payload for the v6 renderer.

    ``country_groups`` and ``display_names`` are passed in so that the host
    module owns the region carve-out logic (PICs, regional groups, etc.).

    ``discovered`` carries measures found in the news corpus that no tracker row
    records. They are appended to the same list as workbook rows and separated
    only by ``provenance``, because the timeline's question -- when did this
    country act -- is the same for both, while their evidence is not: a workbook
    row was verified by an analyst, a discovered one was reported by a newspaper.

    ``coverage`` maps a country to its articles-per-year counts, drawn under the
    timeline lanes so a gap can be told apart from a thin corpus.

    ``timeline`` optionally maps ``"<Country>||<Policy>"`` to corpus-derived
    dating from :mod:`text.analysis.policy_retrieval`. The workbook itself
    carries no effective date, so without it the timeline panel has no x-axis.
    """
    timeline = timeline or {}
    coverage = coverage or {}
    discovered = discovered or []
    policies: List[Dict[str, Any]] = []
    blank_cat = 0
    dated = 0
    for row in rows:
        cat = _norm_cat(row.get("Category"))
        if not cat:
            blank_cat += 1
            continue
        country = _clean(row.get("Country"))
        policy = _clean(row.get("Policy"))
        entry = {
            "Country": country,
            "Policy": policy,
            "Policy Description": _clean(row.get("Policy Description")),
            "Active or Proposed Date": _clean(row.get("Active or Proposed Date")),
            "Source": _clean(row.get("Source")),
            "category": cat,
            "category_display": CATEGORY_DISPLAY.get(cat, cat),
            "subcategory": _clean(row.get("Subcategory")),
        }
        found = timeline.get(f"{country}||{policy}")
        if found and found.get("onset_year"):
            entry.update(
                {
                    "corpus_onset": found["onset_year"],
                    "peak_year": found.get("peak_year"),
                    "n_articles": found.get("n_articles", 0),
                    "years": found.get("years", {}),
                    "first_reported": found.get("first_reported"),
                }
            )
        year = _policy_year(row.get("Active or Proposed Date"))
        if year:
            entry["onset_year"] = year
            entry["date_basis"] = "workbook"
            dated += 1
        policies.append(entry)
    print(f"  timeline: dated {dated}/{len(policies)} policies from the workbook date")

    for entry in policies:
        entry["provenance"] = "workbook"
    if discovered:
        known = {
            (p["Country"], p.get("category"), p.get("subcategory")) for p in policies
        }
        policies.extend(discovered)
        overlap = sum(
            1
            for d in discovered
            if (d["Country"], d.get("category"), d.get("subcategory")) in known
        )
        print(
            f"  discovered: +{len(discovered)} corpus measures "
            f"({overlap} land in a taxonomy cell the workbook already uses)"
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

    subregion_groups, unmatched_subregion = build_subregion_groups(
        sorted(present_countries), region_cfg.get("key", "")
    )
    if subregion_groups and unmatched_subregion:
        print(
            f"  WARN: no subregion for {len(unmatched_subregion)} country cells: "
            f"{', '.join(unmatched_subregion)}"
        )

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
        # Lane order for the timeline. Taken from the full row set rather than
        # the filtered one so a measure keeps its row as the filters change.
        "taxonomy": subcats_by_category,
        "coverage": {c: coverage[c] for c in present_countries if coverage.get(c)},
        "countryGroups": filtered_groups,
        "subregionGroups": subregion_groups,
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
  .controls {{ display: grid; grid-template-columns: minmax(150px, .9fr) minmax(190px, 1.25fr) minmax(180px, 1.1fr) minmax(195px, 1.3fr) minmax(160px, .95fr); gap: 12px; align-items: end; margin-bottom: 14px; }}
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
  .detail-card {{ border: 1px solid #e2e2e2; border-radius: 6px; background: #fff; padding: 12px 14px; }}
  .detail-card h2 {{ font-size: 17px; font-weight: 600; margin: 0 0 8px; color: #444; }}
  .detail-card p {{ margin: 4px 0; font-size: 13px; color: #666; }}
  .policy-list {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 8px; margin-top: 8px; }}
  .policy-card {{ border-left: 5px solid #ccc; background: #fafafa; padding: 8px 10px; min-height: 72px; }}
  .policy-card .policy-title {{ font-weight: 600; color: #333; font-size: 13px; }}
  .policy-card .policy-desc {{ color: #666; font-size: 12px; margin-top: 3px; }}
  .policy-card .policy-foot {{ color: #888; font-size: 11px; margin-top: 5px; }}
  .note {{ margin-top: 14px; font-size: 12px; color: #777; }}
{YEAR_CSS}
  @media (max-width: 820px) {{ .controls {{ grid-template-columns: 1fr 1fr; }} .kpis {{ grid-template-columns: 1fr 1fr; }} }}
  @media (max-width: 540px) {{ .controls, .kpis {{ grid-template-columns: 1fr; }} .dashboard {{ padding: 14px; }} }}
</style>
</head>
<body>
<div class=\"page\">
  <div class=\"dashboard\">
    <div class=\"controls\">
      <div class=\"control-group\"><label for=\"subregionSelect\">Subregion view</label><select id=\"subregionSelect\"><option value=\"all\" selected>{ALL_LABEL}</option></select></div>
      <div class=\"control-group\"><label for=\"groupSelect\">Country view</label><select id=\"groupSelect\"></select></div>
      <div class=\"control-group\"><label for=\"categorySelect\">Policy category</label><select id=\"categorySelect\"></select></div>
      <div class=\"control-group\"><label for=\"subcategorySelect\">Policy subcategory</label><select id=\"subcategorySelect\"></select></div>
      <div class=\"control-group\"><label for=\"statusSelect\">Status</label><select id=\"statusSelect\"><option value=\"all\">Active and proposed</option><option value=\"active\">Active only</option><option value=\"proposed\">Proposed only</option></select></div>
    </div>
    <div class=\"kpis\">
      <div class=\"kpi\"><div class=\"value\" id=\"kpiPolicies\">0</div><div class=\"label\">Policies in current view</div></div>
      <div class=\"kpi\"><div class=\"value\" id=\"kpiCountries\">0</div><div class=\"label\">Countries/economies shown</div></div>
      <div class=\"kpi\"><div class=\"value\" id=\"kpiCats\">0</div><div class=\"label\">Policy categories present</div></div>
      <div class=\"kpi\"><div class=\"value\" id=\"kpiMax\">0</div><div class=\"label\">Measures in busiest year</div></div>
    </div>
    <h1 id=\"chartTitle\" class=\"chart-title\"></h1>
    <div class=\"chart-subtitle\" id=\"subtitle\"></div>
    <div class=\"yc-controls\">
      <label><input type=\"checkbox\" id=\"ycDiscovered\" checked> Show measures found in news</label>
      <label><input type=\"checkbox\" id=\"ycSqrt\"> Square-root scale (makes the thin early years readable)</label>
    </div>
    <div class=\"panel-split\">
      <div class=\"chart-col\">
        <div class=\"chart-frame\">
          <svg id=\"chartAxis\" aria-hidden=\"true\"></svg>
          <div class=\"chart-wrap\" id=\"chartScroll\">
            <svg id=\"chart\" aria-label=\"Stacked bar chart of {chart_aria_subject} policy measures per year, colored by category and split by subcategory\"></svg>
          </div>
        </div>
        <div id=\"legend\" class=\"legend\"></div>
      </div>
      <aside class=\"detail-col\">
        <div class=\"detail-card\" id=\"detailCard\"><h2>Policy details</h2><p>Click a bar segment to list the measures it holds here.</p></div>
      </aside>
    </div>
    <div class=\"note\">Note: bar height is the number of distinct measures dated to that year; colour is the policy category and each segment within a category is one subcategory. The axis begins at the oldest measure in the current view -- scroll left for earlier years. Measures found in the news corpus are dated from the article text and have not been verified against an official source; untick the box above to see tracker rows only.</div>
  </div>
</div>
<script>
const D = {data_json};

const groupSelect = document.getElementById(\"groupSelect\");
const categorySelect = document.getElementById(\"categorySelect\");
const subcategorySelect = document.getElementById(\"subcategorySelect\");
const statusSelect = document.getElementById(\"statusSelect\");
const subregionSelect = document.getElementById(\"subregionSelect\");
const CHART_TITLE = {safe_title};
{YEAR_JS}

initControls();
render();
</script>
</body>
</html>"""
