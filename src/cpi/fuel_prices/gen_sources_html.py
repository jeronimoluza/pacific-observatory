"""Generate a standalone HTML data-source catalog for all EAP fuel price fetchers.

Reads SOURCE_META from each fetcher module, loads the actual CSV data to compute
per-source freshness stats, and renders a filterable/sortable standalone HTML file.

Run directly::

    python -m src.cpi.fuel_prices.gen_sources_html

Output: data/cpi/fuel_prices/data_sources.html
"""

from __future__ import annotations

import html as _html
import importlib
from datetime import date
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Collect metadata from all fetcher modules
# ---------------------------------------------------------------------------

_FETCHER_MODULES = [
    "src.cpi.fuel_prices.fetchers.australia",
    "src.cpi.fuel_prices.fetchers.cambodia",
    "src.cpi.fuel_prices.fetchers.fiji",
    "src.cpi.fuel_prices.fetchers.global_commodities",
    "src.cpi.fuel_prices.fetchers.imf_weo_gdp",
    "src.cpi.fuel_prices.fetchers.indonesia",
    "src.cpi.fuel_prices.fetchers.japan",
    "src.cpi.fuel_prices.fetchers.korea",
    "src.cpi.fuel_prices.fetchers.lao",
    "src.cpi.fuel_prices.fetchers.malaysia",
    "src.cpi.fuel_prices.fetchers.mongolia",
    "src.cpi.fuel_prices.fetchers.myanmar",
    "src.cpi.fuel_prices.fetchers.new_zealand",
    "src.cpi.fuel_prices.fetchers.pacific_islands",
    "src.cpi.fuel_prices.fetchers.philippines",
    "src.cpi.fuel_prices.fetchers.thailand",
    "src.cpi.fuel_prices.fetchers.timor_leste",
    "src.cpi.fuel_prices.fetchers.vietnam",
    "src.cpi.fuel_prices.fetchers.world_bank_population",
]


def collect_all_meta() -> list[dict[str, Any]]:
    """Import every fetcher module and collect SOURCE_META entries."""
    all_entries: list[dict[str, Any]] = []
    for mod_name in _FETCHER_MODULES:
        try:
            mod = importlib.import_module(mod_name)
            meta = getattr(mod, "SOURCE_META", None)
            if meta is None:
                print(f"  [sources] WARNING: no SOURCE_META in {mod_name}")
                continue
            for entry in meta:
                entry.setdefault("_module", mod_name.split(".")[-1])
            all_entries.extend(meta)
        except Exception as exc:
            print(f"  [sources] ERROR importing {mod_name}: {exc}")
    return all_entries


# ---------------------------------------------------------------------------
# CSV freshness stats
# ---------------------------------------------------------------------------


def _load_freshness_stats() -> dict[str, dict]:
    """Load all three CSVs and compute per-source_key stats."""
    try:
        import pandas as pd
    except ImportError:
        print("  [sources] pandas not available — skipping freshness stats")
        return {}

    from .constants import PRIMARY_CSV, SECONDARY_CSV, COMMODITY_CSV

    stats: dict[str, dict] = {}
    today = date.today()

    dfs = []
    for path in (PRIMARY_CSV, SECONDARY_CSV, COMMODITY_CSV):
        if path.exists():
            try:
                df = pd.read_csv(
                    path, low_memory=False, parse_dates=["observation_date"]
                )
                dfs.append(df)
            except Exception as e:
                print(f"  [sources] Could not load {path.name}: {e}")

    if not dfs:
        return {}

    all_df = pd.concat(dfs, ignore_index=True)

    for sk, grp in all_df.groupby("source_key"):
        latest = grp["observation_date"].max()
        earliest = grp["observation_date"].min()
        n_products = grp["fuel_product"].nunique()
        freq_series = grp["publication_frequency"].dropna()
        freq = freq_series.mode()[0] if len(freq_series) > 0 else ""

        latest_date = latest.date() if hasattr(latest, "date") else None
        earliest_date = earliest.date() if hasattr(earliest, "date") else None
        days_since = (today - latest_date).days if latest_date else None

        stats[str(sk)] = {
            "latest": latest_date,
            "earliest": earliest_date,
            "n_products": int(n_products),
            "freq": str(freq),
            "days_since": days_since,
        }

    return stats


# ---------------------------------------------------------------------------
# Badge / cell helpers
# ---------------------------------------------------------------------------

_METHOD_COLORS: dict[str, str] = {
    "web scraping": "#e76f51",
    "rest api": "#2a9d8f",
    "json api": "#2a9d8f",
    "excel download": "#457b9d",
    "csv download": "#3a86ff",
    "pdf parsing": "#9b2226",
    "ocr": "#7b2d8b",
    "local files": "#6c757d",
}


def _method_badge(method: str) -> str:
    m = method.lower()
    color = "#999"
    for kw, c in _METHOD_COLORS.items():
        if kw in m:
            color = c
            break
    label = _html.escape(method)
    return f'<span class="badge" style="background:{color}">{label}</span>'


def _method_badges(methods: list[str] | str) -> str:
    if isinstance(methods, str):
        methods = [methods]
    return " ".join(_method_badge(m) for m in methods if m)


def _status_badge(days_since: int | None) -> str:
    if days_since is None:
        return '<span class="badge status-unknown">unknown</span>'
    if days_since <= 14:
        return '<span class="badge status-ok">up-to-date</span>'
    if days_since <= 60:
        return '<span class="badge status-aging">aging</span>'
    return '<span class="badge status-stale">stale</span>'


def _notes_html(notes: str) -> str:
    """Highlight CRITICAL / WARNING / Requires in notes."""
    escaped = _html.escape(notes)
    for kw in ("CRITICAL:", "WARNING:", "Requires "):
        escaped = escaped.replace(kw, f'<span class="warn">{kw}</span>')
    return escaped


def _expected_period_days(freq: str) -> int | None:
    if not freq:
        return None
    f = freq.lower()
    if "irregular" in f:
        return None
    if "10-day" in f or "10 day" in f:
        return 10
    if "daily" in f:
        return 1
    if "biweekly" in f:
        return 14
    if "weekly" in f:
        return 7
    if "monthly" in f:
        return 30
    if "quarterly" in f:
        return 90
    if "annual" in f or "year" in f:
        return 365
    return None


# ---------------------------------------------------------------------------
# CSS / JS
# ---------------------------------------------------------------------------

_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: "Fira Sans", "Avenir Next", "Segoe UI", sans-serif;
    padding: 20px 28px;
    background: #f8f9fa;
    color: #222;
}
h1 { font-size: 1.25em; font-weight: 700; margin-bottom: 4px; color: #1a1a2e; }
.subtitle { font-size: 0.82em; color: #666; margin-bottom: 18px; }

/* Filter bar */
.filter-bar {
    display: flex; flex-wrap: wrap; gap: 10px;
    background: #fff; border: 1px solid #e0e0e0; border-radius: 8px;
    padding: 12px 16px; margin-bottom: 16px; align-items: flex-end;
}
.filter-group { display: flex; flex-direction: column; gap: 3px; }
.filter-group label { font-size: 0.76em; font-weight: 600; color: #555; }
.filter-group input, .filter-group select {
    padding: 5px 9px; border: 1px solid #ccc; border-radius: 4px;
    font-size: 0.85em; background: #fafafa; color: #222;
    min-width: 140px;
}
.filter-group input:focus, .filter-group select:focus {
    outline: none; border-color: #667eea;
}
#clear-btn {
    padding: 5px 14px; border: 1px solid #ccc; border-radius: 4px;
    font-size: 0.82em; background: #fff; cursor: pointer; color: #555;
    align-self: flex-end;
}
#clear-btn:hover { border-color: #667eea; color: #667eea; }
#result-count { font-size: 0.78em; color: #888; align-self: flex-end; margin-left: auto; }

/* Table */
.table-wrap { overflow-x: auto; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
table {
    border-collapse: collapse; width: 100%; background: #fff;
    font-size: 0.82em;
}
thead th {
    background: #1a1a2e; color: #fff;
    padding: 9px 14px; text-align: left;
    font-weight: 600; font-size: 0.8em; white-space: nowrap;
    cursor: pointer; user-select: none;
}
thead th:hover { background: #2d2d54; }
thead th .sort-icon { margin-left: 5px; opacity: 0.5; font-size: 0.75em; }
thead th.sort-asc  .sort-icon::after { content: ' ▲'; opacity: 1; }
thead th.sort-desc .sort-icon::after { content: ' ▼'; opacity: 1; }
thead th:not(.sort-asc):not(.sort-desc) .sort-icon::after { content: ' ⇅'; }

tbody tr { border-bottom: 1px solid #f0f0f0; transition: background 0.1s; }
tbody tr:hover { background: #f0f4ff; }
tbody tr.hidden { display: none; }
td { padding: 7px 14px; vertical-align: top; }
td.country { font-weight: 600; white-space: nowrap; }
td.source  { min-width: 180px; }
td.source a { color: #667eea; text-decoration: none; font-size: 0.78em; }
td.source a:hover { text-decoration: underline; }
td.source .fn { display: block; color: #aaa; font-size: 0.72em; font-family: monospace; margin-top: 2px; }
td.desc    { max-width: 240px; font-size: 0.78em; color: #444; line-height: 1.4; }
td.products { max-width: 200px; font-size: 0.78em; }
td.products .prod-count { font-weight: 600; color: #333; display: block; margin-bottom: 3px; }
td.products ul { margin: 0; padding-left: 14px; }
td.products li { margin-bottom: 1px; color: #555; }
td.time-coverage { max-width: 190px; font-size: 0.78em; color: #444; line-height: 1.6; }
td.time-coverage .date-range { font-weight: 600; color: #222; white-space: nowrap; }
td.time-coverage .freq-str { color: #666; font-size: 0.92em; }
td.time-coverage .coverage-note { color: #888; font-size: 0.9em; }
td.updated-to { max-width: 180px; font-size: 0.78em; line-height: 1.6; }
td.updated-to .latest-date { font-weight: 600; color: #222; }
td.updated-to .days-info { color: #888; font-size: 0.9em; }
td.updated-to .schedule { color: #666; font-size: 0.9em; }
td.updated-to .next-info { color: #888; font-size: 0.9em; }
td.notes { max-width: 240px; font-size: 0.78em; color: #444; line-height: 1.4; }
td.notes .warn { color: #c0392b; font-weight: 600; }

.badge {
    display: inline-block; padding: 2px 9px; border-radius: 12px;
    font-size: 0.76em; font-weight: 600; color: #fff; white-space: nowrap;
    margin: 1px 0;
}
.status-ok     { background: #2a9d8f; }
.status-aging  { background: #e9c46a; color: #333; }
.status-stale  { background: #e63946; }
.status-unknown { background: #adb5bd; }

/* Legend */
.legend-section { margin-top: 20px; display: flex; flex-wrap: wrap; gap: 24px; }
.legend-group h4 { font-size: 0.76em; font-weight: 700; color: #555; margin-bottom: 5px; text-transform: uppercase; letter-spacing: 0.04em; }
.legend-items { display: flex; flex-wrap: wrap; gap: 5px; }
"""

_JS = r"""
const rows = Array.from(document.querySelectorAll('tbody tr'));
const countEl = document.getElementById('result-count');

function updateCount() {
    const visible = rows.filter(r => !r.classList.contains('hidden')).length;
    countEl.textContent = visible + ' of ' + rows.length + ' sources';
}

// Filters
const searchEl   = document.getElementById('f-search');
const countryEl  = document.getElementById('f-country');
const methodEl   = document.getElementById('f-method');
const statusEl   = document.getElementById('f-status');

function applyFilters() {
    const q       = searchEl.value.toLowerCase().trim();
    const country = countryEl.value;
    const method  = methodEl.value.toLowerCase();
    const status  = statusEl.value.toLowerCase();

    rows.forEach(row => {
        const text     = row.textContent.toLowerCase();
        const rCountry = row.dataset.country || '';
        const rMethod  = (row.dataset.method  || '').toLowerCase();
        const rStatus  = (row.dataset.status  || '').toLowerCase();

        const ok =
            (!q       || text.includes(q)) &&
            (!country || rCountry === country) &&
            (!method  || rMethod.includes(method)) &&
            (!status  || rStatus === status);

        row.classList.toggle('hidden', !ok);
    });
    updateCount();
}

searchEl.addEventListener('input',   applyFilters);
countryEl.addEventListener('change', applyFilters);
methodEl.addEventListener('change',  applyFilters);
statusEl.addEventListener('change',  applyFilters);

document.getElementById('clear-btn').addEventListener('click', () => {
    searchEl.value = '';
    countryEl.value = '';
    methodEl.value = '';
    statusEl.value = '';
    applyFilters();
});

// Sorting
let sortCol = -1, sortDir = 1;
document.querySelectorAll('thead th[data-col]').forEach(th => {
    th.addEventListener('click', () => {
        const col = parseInt(th.dataset.col);
        if (sortCol === col) { sortDir *= -1; }
        else { sortCol = col; sortDir = 1; }

        document.querySelectorAll('thead th').forEach(t => t.classList.remove('sort-asc','sort-desc'));
        th.classList.add(sortDir === 1 ? 'sort-asc' : 'sort-desc');

        const tbody = document.querySelector('tbody');
        const sorted = rows.slice().sort((a, b) => {
            const ta = a.cells[col] ? a.cells[col].textContent.trim() : '';
            const tb = b.cells[col] ? b.cells[col].textContent.trim() : '';
            return ta.localeCompare(tb) * sortDir;
        });
        sorted.forEach(r => tbody.appendChild(r));
    });
});

updateCount();
"""


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------


def _build_country_options(entries: list[dict]) -> list[str]:
    seen: set[str] = set()
    for e in entries:
        v = e.get("country", "")
        if v:
            seen.add(v)
    return sorted(seen)


def _build_method_options(entries: list[dict]) -> list[str]:
    seen: set[str] = set()
    for e in entries:
        methods = e.get("extraction_method", [])
        if isinstance(methods, str):
            methods = [methods]
        for m in methods:
            if m:
                seen.add(m)
    return sorted(seen)


def gen_sources_html(out_path: Path | None = None) -> Path:
    """Collect metadata and write standalone HTML catalog."""
    from .constants import DATA_DIR

    if out_path is None:
        out_path = DATA_DIR / "data_sources.html"

    print("  [sources] Collecting metadata from fetcher modules ...")
    entries = collect_all_meta()
    print(f"  [sources] Found {len(entries)} source entries.")

    print("  [sources] Loading freshness stats from CSVs ...")
    freshness = _load_freshness_stats()
    print(f"  [sources] Freshness stats loaded for {len(freshness)} source keys.")

    # Sort entries by country then source_name
    entries.sort(key=lambda e: (e.get("country", ""), e.get("source_name", "")))

    countries = _build_country_options(entries)
    all_methods = _build_method_options(entries)

    def _opts(values: list[str]) -> str:
        return "\n".join(
            f'<option value="{_html.escape(v)}">{_html.escape(v)}</option>'
            for v in values
        )

    # Build table rows
    tbody_html = ""
    for e in entries:
        country = _html.escape(e.get("country", ""))
        source_name = _html.escape(e.get("source_name", ""))
        url = e.get("url", "")
        url_link = (
            f'<a href="{_html.escape(url)}" target="_blank" rel="noopener">Link to source</a>'
            if url
            else ""
        )
        fn = _html.escape(e.get("fetcher_fn", ""))
        methods = e.get("extraction_method", [])
        if isinstance(methods, str):
            methods = [methods]
        description = _html.escape(e.get("description", ""))
        products = e.get("products", [])
        notes = e.get("notes", "")
        source_keys: list[str] = e.get("source_keys", [])
        publishes_on: str = e.get("publishes_on", "")

        # --- Source cell ---
        source_cell = source_name
        if url_link:
            source_cell += "<br>" + url_link
        if fn:
            source_cell += f'<span class="fn">{fn}</span>'

        # --- Extraction method cell ---
        method_cell = _method_badges(methods)
        method_data = " | ".join(methods)

        # --- Freshness stats: aggregate over all source_keys ---
        if source_keys:
            sk_stats = [freshness[sk] for sk in source_keys if sk in freshness]
        else:
            sk_stats = []

        if sk_stats:
            # aggregate: latest of latests, earliest of earliests, sum n_products, first freq
            latest_date = max(s["latest"] for s in sk_stats if s["latest"])
            earliest_date = min(s["earliest"] for s in sk_stats if s["earliest"])
            total_products = sum(s["n_products"] for s in sk_stats)
            freq_str = sk_stats[0]["freq"]
            days_since = (date.today() - latest_date).days if latest_date else None
        else:
            latest_date = None
            earliest_date = None
            total_products = None
            freq_str = e.get("frequency", "")
            days_since = None

        # --- Products cell ---
        if products:
            n = len(products)
        else:
            n = (
                total_products
                if total_products is not None and total_products > 0
                else 0
            )
        prod_count_label = f"{n} product{'s' if n != 1 else ''}"
        prods_html = f'<span class="prod-count">{prod_count_label}:</span>'
        if products:
            prods_html += (
                "<ul>"
                + "".join(f"<li>{_html.escape(p)}</li>" for p in products)
                + "</ul>"
            )

        # --- Time Coverage cell ---
        if earliest_date and latest_date:
            date_range = f"{earliest_date.strftime('%Y-%m-%d')} &rarr; {latest_date.strftime('%Y-%m-%d')}"
        else:
            date_range = "—"

        freq_display = _html.escape(freq_str) if freq_str else "—"
        if days_since is None or not earliest_date or not latest_date:
            coverage_note = "Coverage: unknown"
        elif days_since <= 14:
            coverage_note = "Coverage: current"
        elif days_since <= 60:
            coverage_note = "Coverage: lagging"
        else:
            coverage_note = "Coverage: stale"
        time_coverage_cell = (
            f'<span class="date-range">{date_range}</span><br>'
            f'<span class="freq-str">{freq_display}</span><br>'
            f'<span class="coverage-note">{coverage_note}</span>'
        )

        # --- Updated To cell ---
        status_label = "unknown"
        if days_since is not None:
            if days_since <= 14:
                status_label = "up-to-date"
            elif days_since <= 60:
                status_label = "aging"
            else:
                status_label = "stale"

        status_badge_html = _status_badge(days_since)

        if latest_date:
            latest_str = latest_date.strftime("%Y-%m-%d")
            days_info = f"{days_since}d ago"
        else:
            latest_str = "—"
            days_info = ""

        expected_days = _expected_period_days(freq_str)
        next_info = "next: —"
        if days_since is not None and expected_days is not None:
            days_until = expected_days - days_since
            if days_until >= 0:
                next_info = f"next in {days_until}d"
            else:
                next_info = f"overdue by {abs(days_until)}d"

        schedule_html = (
            f'<span class="schedule">Publishes: {_html.escape(publishes_on)}</span><br>'
            if publishes_on
            else ""
        )

        updated_to_cell = (
            f'<span class="latest-date">{latest_str}</span><br>'
            f'<span class="days-info">{days_info}</span><br>'
            f'<span class="next-info">{next_info}</span><br>'
            + schedule_html
            + status_badge_html
        )

        tbody_html += (
            f'<tr data-country="{_html.escape(e.get("country", ""))}" '
            f'data-method="{_html.escape(method_data)}" '
            f'data-status="{status_label}">'
            f'<td class="country">{country}</td>'
            f'<td class="source">{source_cell}</td>'
            f'<td class="desc">{description}</td>'
            f'<td class="products">{prods_html}</td>'
            f'<td class="method">{method_cell}</td>'
            f'<td class="time-coverage">{time_coverage_cell}</td>'
            f'<td class="updated-to">{updated_to_cell}</td>'
            f'<td class="notes">{_notes_html(notes)}</td>'
            f"</tr>\n"
        )

    # Legend
    def _legend_block(title: str, items: dict[str, str]) -> str:
        badges = "".join(
            f'<span class="badge" style="background:{c}">{_html.escape(k.title())}</span>'
            for k, c in items.items()
        )
        return (
            f'<div class="legend-group">'
            f"<h4>{title}</h4>"
            f'<div class="legend-items">{badges}</div>'
            f"</div>"
        )

    status_colors = {
        "up-to-date": "#2a9d8f",
        "aging": "#e9c46a",
        "stale": "#e63946",
        "unknown": "#adb5bd",
    }
    legend_html = _legend_block("Extraction Method", _METHOD_COLORS) + _legend_block(
        "Freshness Status", status_colors
    )

    generated_on = date.today().isoformat()
    n_countries = len(countries)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EAP Fuel Prices — Data Source Catalog</title>
    <style>{_CSS}</style>
</head>
<body>

<h1>EAP Fuel Prices &mdash; Data Source Catalog</h1>
<p class="subtitle">Auto-generated {generated_on} &nbsp;&middot;&nbsp; {len(entries)} sources across {n_countries} countries/regions &nbsp;&middot;&nbsp; Edit metadata in <code>src/cpi/fuel_prices/fetchers/&lt;country&gt;.py</code> &rarr; <code>SOURCE_META</code></p>

<div class="filter-bar">
    <div class="filter-group">
        <label for="f-search">Search</label>
        <input id="f-search" type="search" placeholder="keyword&hellip;" style="min-width:200px">
    </div>
    <div class="filter-group">
        <label for="f-country">Country</label>
        <select id="f-country"><option value="">All countries</option>{_opts(countries)}</select>
    </div>
    <div class="filter-group">
        <label for="f-method">Extraction Method</label>
        <select id="f-method"><option value="">All methods</option>{_opts(all_methods)}</select>
    </div>
    <div class="filter-group">
        <label for="f-status">Freshness Status</label>
        <select id="f-status">
            <option value="">All statuses</option>
            <option value="up-to-date">Up-to-date</option>
            <option value="aging">Aging</option>
            <option value="stale">Stale</option>
            <option value="unknown">Unknown</option>
        </select>
    </div>
    <button id="clear-btn">Clear filters</button>
    <span id="result-count"></span>
</div>

<div class="table-wrap">
<table>
    <thead>
        <tr>
            <th data-col="0">Country <span class="sort-icon"></span></th>
            <th data-col="1">Source / Fetcher <span class="sort-icon"></span></th>
            <th data-col="2">Description</th>
            <th data-col="3">Products Covered</th>
            <th data-col="4">Extraction Method</th>
            <th data-col="5">Time Coverage <span class="sort-icon"></span></th>
            <th data-col="6">Updated To <span class="sort-icon"></span></th>
            <th data-col="7">Notes / Known Gaps</th>
        </tr>
    </thead>
    <tbody>
{tbody_html}    </tbody>
</table>
</div>

<div class="legend-section">
{legend_html}
</div>

<script>
{_JS}
</script>
</body>
</html>
"""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"  [sources] Written: {out_path}")
    return out_path


if __name__ == "__main__":
    gen_sources_html()
