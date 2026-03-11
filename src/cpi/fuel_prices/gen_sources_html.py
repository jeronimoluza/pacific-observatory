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
from datetime import date, timedelta
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

_COVERAGE_START = date(2026, 1, 1)


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

    coverage_ts = pd.Timestamp(_COVERAGE_START)

    def _observed_periods(dates: "pd.Series", freq: str) -> int:
        if dates.empty:
            return 0
        f = (freq or "").lower()
        if "daily" in f or "" == f:
            return int(dates.dt.normalize().nunique())
        if "weekly" in f:
            iso = dates.dt.isocalendar()
            if "biweekly" in f:
                bins = (
                    iso["year"].astype(str)
                    + "-"
                    + (((iso["week"] - 1) // 2) + 1).astype(str)
                )
            else:
                bins = iso["year"].astype(str) + "-" + iso["week"].astype(str)
            return int(bins.nunique())
        if "monthly" in f:
            return int(dates.dt.to_period("M").nunique())
        if "quarterly" in f:
            return int(dates.dt.to_period("Q").nunique())
        if "annual" in f or "year" in f:
            return int(dates.dt.year.nunique())
        if "10-day" in f or "10 day" in f:
            bins = (
                dates.dt.year.astype(str)
                + "-"
                + (((dates.dt.dayofyear - 1) // 10) + 1).astype(str)
            )
            return int(bins.nunique())
        if "irregular" in f:
            return int(dates.dt.normalize().nunique())
        return int(dates.dt.normalize().nunique())

    def _missing_summary(dates: "pd.Series", freq: str) -> str:
        if dates.empty:
            return "Data gaps: N/A"
        f = (freq or "").lower()
        if f in ("", "daily"):
            start = dates.min().normalize()
            end = dates.max().normalize()
            expected = pd.date_range(start=start, end=end, freq="D")
            observed = dates.dt.normalize().unique()
            missing = expected.difference(pd.DatetimeIndex(observed))
            missing_dates = [d.date() for d in missing]
        elif "weekly" in f:
            start = dates.min().to_period("W")
            end = dates.max().to_period("W")
            expected = pd.period_range(start, end, freq="W")
            observed = dates.dt.to_period("W").unique()
            missing = expected.difference(observed)
            missing_dates = [p.start_time.date() for p in missing]
        elif "monthly" in f:
            start = dates.min().to_period("M")
            end = dates.max().to_period("M")
            expected = pd.period_range(start, end, freq="M")
            observed = dates.dt.to_period("M").unique()
            missing = expected.difference(observed)
            missing_dates = [p.start_time.date() for p in missing]
        elif "quarterly" in f:
            start = dates.min().to_period("Q")
            end = dates.max().to_period("Q")
            expected = pd.period_range(start, end, freq="Q")
            observed = dates.dt.to_period("Q").unique()
            missing = expected.difference(observed)
            missing_dates = [p.start_time.date() for p in missing]
        elif "annual" in f or "year" in f:
            start = dates.min().to_period("A")
            end = dates.max().to_period("A")
            expected = pd.period_range(start, end, freq="A")
            observed = dates.dt.to_period("A").unique()
            missing = expected.difference(observed)
            missing_dates = [p.start_time.date() for p in missing]
        else:
            return "Data gaps: N/A"

        if not missing_dates:
            return "Data gaps: none"
        if len(missing_dates) < 3:
            dates_str = ", ".join(d.strftime("%Y-%m-%d") for d in missing_dates)
            return f"Data gaps: {dates_str}"

        # collapse into ranges
        ranges: list[tuple[date, date]] = []
        start = prev = missing_dates[0]
        for d in missing_dates[1:]:
            if (d - prev).days > 1:
                ranges.append((start, prev))
                start = d
            prev = d
        ranges.append((start, prev))

        # Prefer a contiguous missing block if any exists; otherwise summarize count.
        ranges.sort(key=lambda r: (r[1] - r[0]).days, reverse=True)
        longest = ranges[0]
        if (longest[1] - longest[0]).days >= 1:
            extra = f" (+{len(ranges) - 1} more ranges)" if len(ranges) > 1 else ""
            return (
                f"Data gaps: {longest[0].strftime('%Y-%m-%d')} → {longest[1].strftime('%Y-%m-%d')}"
                + extra
            )

        # Many single-period gaps.
        example = missing_dates[0].strftime("%Y-%m-%d")
        return f"Data gaps: {len(missing_dates)} missing periods (e.g., {example})"

    def _expected_periods(
        start: date | None, end: date | None, freq: str
    ) -> int | None:
        if start is None or end is None:
            return None
        if end < start:
            return 0
        f = (freq or "").lower()
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        if "daily" in f or "" == f:
            return int((end - start).days + 1)
        if "weekly" in f:
            weeks = pd.period_range(start_ts, end_ts, freq="W").nunique()
            if "biweekly" in f:
                return int((weeks + 1) // 2)
            return int(weeks)
        if "monthly" in f:
            return int(pd.period_range(start_ts, end_ts, freq="M").nunique())
        if "quarterly" in f:
            return int(pd.period_range(start_ts, end_ts, freq="Q").nunique())
        if "annual" in f or "year" in f:
            return int(pd.period_range(start_ts, end_ts, freq="A").nunique())
        if "10-day" in f or "10 day" in f:
            day_span = (end - start).days + 1
            return int((day_span + 9) // 10)
        if "irregular" in f:
            return None
        return int((end - start).days + 1)

    for sk, grp in all_df.groupby("source_key"):
        dates = grp["observation_date"].dropna()
        latest = dates.max()
        earliest = dates.min()
        n_products = grp["fuel_product"].nunique()
        freq_series = grp["publication_frequency"].dropna()
        freq = freq_series.mode()[0] if len(freq_series) > 0 else ""

        period_obs = _observed_periods(dates, str(freq))
        period_obs_since = _observed_periods(dates[dates >= coverage_ts], str(freq))
        period_obs_before = _observed_periods(dates[dates < coverage_ts], str(freq))

        latest_date = latest.date() if hasattr(latest, "date") else None
        earliest_date = earliest.date() if hasattr(earliest, "date") else None
        days_since = (today - latest_date).days if latest_date else None

        expected_total = _expected_periods(earliest_date, latest_date, str(freq))
        expected_since = _expected_periods(
            max(_COVERAGE_START, earliest_date) if earliest_date else None,
            latest_date,
            str(freq),
        )
        expected_before = _expected_periods(
            earliest_date,
            min(latest_date, _COVERAGE_START - timedelta(days=1))
            if latest_date
            else None,
            str(freq),
        )

        missing_summary = _missing_summary(dates, str(freq))

        stats[str(sk)] = {
            "latest": latest_date,
            "earliest": earliest_date,
            "n_products": int(n_products),
            "freq": str(freq),
            "days_since": days_since,
            "period_obs": period_obs,
            "period_obs_since_2026": period_obs_since,
            "period_obs_before_2026": period_obs_before,
            "expected_total": expected_total,
            "expected_since_2026": expected_since,
            "expected_before_2026": expected_before,
            "missing_summary": missing_summary,
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
    return "".join(f"{_method_badge(m)}<br>" for m in methods if m).rstrip("<br>")


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


def _description_html(description: str, notes: str) -> str:
    first_sentence = description.strip()
    if "." in first_sentence:
        first_sentence = first_sentence.split(".", 1)[0] + "."
    critical = ""
    if "CRITICAL:" in notes:
        critical = notes.split("CRITICAL:", 1)[1].strip()
        if "." in critical:
            critical = critical.split(".", 1)[0] + "."
        critical = f'<span class="warn">CRITICAL:</span> {_html.escape(critical)}'
    desc = _html.escape(first_sentence)
    if critical:
        desc += f"<br>{critical}"
    return desc


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


def _expected_observations(
    start: date | None, end: date | None, period_days: int | None
) -> int | None:
    if start is None or end is None or period_days is None:
        return None
    if end < start:
        return 0
    span_days = (end - start).days
    return (span_days // period_days) + 1


def _ratio_str(numer: int | None, denom: int | None) -> str:
    if numer is None or denom is None or denom <= 0:
        return "N/A"
    return f"{(numer / denom) * 100:.0f}%"


def _ratio_detail(numer: int | None, denom: int | None) -> str:
    if numer is None or denom is None or denom <= 0:
        return "N/A"
    return f"{numer}/{denom} ({(numer / denom) * 100:.0f}%)"


def _granularity_weight(freq: str) -> float:
    f = (freq or "").lower()
    if "daily" in f:
        return 1.0
    if "weekly" in f:
        return 0.9
    if "biweekly" in f:
        return 0.8
    if "monthly" in f:
        return 0.85
    if "quarterly" in f:
        return 0.7
    if "annual" in f or "year" in f:
        return 0.55
    if "irregular" in f:
        return 0.3
    return 0.5


def _recency_weight(days_since: int | None) -> float:
    if days_since is None:
        return 0.5
    if days_since <= 14:
        return 1.0
    if days_since <= 60:
        return 0.7
    return 0.4


def _breadth_weight(n_products: int | None) -> float:
    if n_products is None or n_products <= 0:
        return 0.5
    # Saturate quickly: 3+ products is usually sufficient for a usable source.
    return min(1.0, n_products / 3)


def _usability_score(
    coverage_ratio: float | None,
    freq: str,
    days_since: int | None,
    n_products: int | None,
) -> int:
    coverage_weight = coverage_ratio if coverage_ratio is not None else 0.5
    granularity_weight = _granularity_weight(freq)
    recency_weight = _recency_weight(days_since)
    breadth_weight = _breadth_weight(n_products)
    score = (
        0.5 * coverage_weight
        + 0.2 * granularity_weight
        + 0.2 * recency_weight
        + 0.1 * breadth_weight
    )
    return max(1, min(10, int(round(score * 10))))


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
td.source  { min-width: 220px; }
td.source a { color: #667eea; text-decoration: none; font-size: 0.78em; }
td.source a:hover { text-decoration: underline; }
td.source .fn { display: block; color: #aaa; font-size: 0.72em; font-family: monospace; margin-top: 2px; }
td.source .metric { color: #444; font-size: 0.74em; line-height: 1.5; }
td.source .metric-label { font-weight: 600; color: #222; }
td.source .source-name { font-weight: 600; color: #1a1a2e; display: block; margin-top: 6px; }
td.desc    { max-width: 240px; font-size: 0.78em; color: #444; line-height: 1.4; }
td.desc .warn { color: #c0392b; font-weight: 600; }
td.products { max-width: 200px; font-size: 0.78em; }
td.products .prod-count { font-weight: 600; color: #333; display: block; margin-bottom: 3px; }
td.products .coverage-score { color: #666; font-size: 0.74em; display: block; margin-bottom: 3px; }
td.products ul { margin: 0; padding-left: 14px; }
td.products li { margin-bottom: 1px; color: #555; }
td.time-coverage { max-width: 220px; font-size: 0.78em; color: #444; line-height: 1.6; }
td.time-coverage .date-range { font-weight: 600; color: #222; white-space: nowrap; }
td.time-coverage .freq-str { color: #666; font-size: 0.92em; }
td.time-coverage .coverage-note { color: #888; font-size: 0.9em; }
td.updated-to { max-width: 180px; font-size: 0.78em; line-height: 1.6; }
td.updated-to .latest-date { font-weight: 600; color: #222; }
td.updated-to .days-info { color: #888; font-size: 0.9em; }
td.updated-to .schedule { color: #666; font-size: 0.9em; }
td.updated-to .next-info { color: #888; font-size: 0.9em; }
td.usability { max-width: 180px; font-size: 0.78em; line-height: 1.5; }
td.usability .score { font-weight: 700; color: #1a1a2e; }
/* legend spacing */
.legend-section { margin: 12px 0 18px 0; }

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
const statusEl   = document.getElementById('f-status');

function applyFilters() {
    const q       = searchEl.value.toLowerCase().trim();
    const country = countryEl.value;
    const status  = statusEl.value.toLowerCase();

    rows.forEach(row => {
        const text     = row.textContent.toLowerCase();
        const rCountry = row.dataset.country || '';
        const rStatus  = (row.dataset.status  || '').toLowerCase();

        const ok =
            (!q       || text.includes(q)) &&
            (!country || rCountry === country) &&
            (!status  || rStatus === status);

        row.classList.toggle('hidden', !ok);
    });
    updateCount();
}

searchEl.addEventListener('input',   applyFilters);
countryEl.addEventListener('change', applyFilters);
statusEl.addEventListener('change',  applyFilters);

document.getElementById('clear-btn').addEventListener('click', () => {
    searchEl.value = '';
    countryEl.value = '';
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


def _load_ancillary_stats(data_dir: Path) -> dict[str, dict[str, int]]:
    try:
        import pandas as pd
    except ImportError:
        return {}

    stats: dict[str, dict[str, int]] = {}
    for filename in ("population.csv", "gdp_per_capita.csv"):
        path = data_dir / filename
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if "year" not in df.columns or "wb_iso3" not in df.columns:
            continue
        year_min = int(df["year"].min())
        year_max = int(df["year"].max())
        latest = df[df["year"] == year_max]
        countries = int(latest["wb_iso3"].nunique())
        records = int(len(df))
        stats[filename] = {
            "year_min": year_min,
            "year_max": year_max,
            "countries": countries,
            "records": records,
        }

    return stats


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
    ancillary_stats = _load_ancillary_stats(DATA_DIR)

    # Sort entries by country then source_name
    entries.sort(key=lambda e: (e.get("country", ""), e.get("source_name", "")))

    countries = _build_country_options(entries)

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
        notes = e.get("notes", "")
        description = _description_html(e.get("description", ""), notes)
        products = e.get("products", [])
        source_keys: list[str] = e.get("source_keys", [])
        publishes_on: str = e.get("publishes_on", "")
        output = e.get("output", "")
        module_slug = e.get("_module", "")
        if not output and module_slug == "imf_weo_gdp":
            output = "gdp_per_capita.csv"
        ancillary_info = ancillary_stats.get(output)
        is_ancillary = ancillary_info is not None

        # --- Extraction method cell ---
        method_cell = _method_badges(methods)
        method_data = " | ".join(methods)

        # --- Freshness stats: aggregate over all source_keys ---
        if source_keys:
            sk_stats = [freshness[sk] for sk in source_keys if sk in freshness]
        else:
            sk_stats = []

        if sk_stats:
            latest_date = max(s["latest"] for s in sk_stats if s["latest"])
            earliest_date = min(s["earliest"] for s in sk_stats if s["earliest"])
            total_products = sum(s["n_products"] for s in sk_stats)
            freqs = [s["freq"] for s in sk_stats if s["freq"]]
            freq_str = freqs[0] if freqs else e.get("frequency", "")
            if len(set(freqs)) > 1:
                freq_str = "mixed"
            if not freq_str and publishes_on and "annual" in publishes_on.lower():
                freq_str = "Annual"
            days_since = (date.today() - latest_date).days if latest_date else None
            total_obs = sum(s["period_obs"] for s in sk_stats)
            obs_since_2026 = sum(s["period_obs_since_2026"] for s in sk_stats)
            obs_before_2026 = sum(s["period_obs_before_2026"] for s in sk_stats)

            expected_totals = [s.get("expected_total") for s in sk_stats]
            expected_since = [s.get("expected_since_2026") for s in sk_stats]
            expected_before = [s.get("expected_before_2026") for s in sk_stats]

            if any(v is None for v in expected_totals):
                expected_total = None
            else:
                expected_total = int(sum(v for v in expected_totals if v is not None))

            if any(v is None for v in expected_since):
                expected_since_2026 = None
            else:
                expected_since_2026 = int(
                    sum(v for v in expected_since if v is not None)
                )

            if any(v is None for v in expected_before):
                expected_before_2026 = None
            else:
                expected_before_2026 = int(
                    sum(v for v in expected_before if v is not None)
                )
        else:
            latest_date = None
            earliest_date = None
            total_products = None
            freq_str = e.get("frequency", "")
            if not freq_str and publishes_on and "annual" in publishes_on.lower():
                freq_str = "Annual"
            days_since = None
            total_obs = None
            obs_since_2026 = None
            obs_before_2026 = None
            expected_total = None
            expected_since_2026 = None
            expected_before_2026 = None

        # --- Coverage metrics ---
        freq_display = _html.escape(freq_str) if freq_str else "—"
        coverage_score = _ratio_str(total_obs, expected_total)
        completion_since_2026 = _ratio_detail(obs_since_2026, expected_since_2026)
        history_completion = _ratio_detail(obs_before_2026, expected_before_2026)
        coverage_since_score = _ratio_str(obs_since_2026, expected_since_2026)

        if earliest_date and latest_date:
            date_range = f"{earliest_date.strftime('%Y-%m-%d')} &rarr; {latest_date.strftime('%Y-%m-%d')}"
            earliest_label = earliest_date.strftime("%Y-%m-%d")
        elif is_ancillary:
            year_min = ancillary_info.get("year_min")
            year_max = ancillary_info.get("year_max")
            date_range = (
                f"{year_min} &rarr; {year_max}" if year_min and year_max else "—"
            )
            earliest_label = str(year_min) if year_min else "—"
        else:
            date_range = "—"
            earliest_label = "—"

        # --- Source cell ---
        source_metrics = [
            f'<span class="source-name">{source_name}</span>',
            f'<span class="metric"><span class="metric-label">Coverage:</span> {coverage_score}</span>',
            f'<span class="metric"><span class="metric-label">Granularity:</span> {freq_display}</span>',
            f'<span class="metric"><span class="metric-label">Date range:</span> {date_range}</span>',
            f'<span class="metric"><span class="metric-label">Completion since 01-01-2026:</span> {completion_since_2026}</span>',
            f'<span class="metric"><span class="metric-label">Earliest date:</span> {earliest_label}</span>',
            f'<span class="metric"><span class="metric-label">History completion:</span> {history_completion}</span>',
        ]

        if is_ancillary:
            source_metrics.extend(
                [
                    f'<span class="metric"><span class="metric-label">Countries covered:</span> {ancillary_info.get("countries", "—")}</span>',
                    f'<span class="metric"><span class="metric-label">Latest year:</span> {ancillary_info.get("year_max", "—")}</span>',
                    f'<span class="metric"><span class="metric-label">Records:</span> {ancillary_info.get("records", "—")}</span>',
                ]
            )

        source_cell = "<br>".join(source_metrics)
        if url_link:
            source_cell += "<br>" + url_link
        if fn:
            slug = f"{module_slug}:{fn}" if module_slug else fn
            source_cell += f'<span class="fn">{_html.escape(slug)}</span>'

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
        if not is_ancillary:
            prods_html += f'<span class="coverage-score">2026 coverage: {coverage_since_score}</span>'
        if products:
            prods_html += ""

        # --- Time Coverage cell ---
        if is_ancillary:
            year_label = (
                str(ancillary_info.get("year_max"))
                if ancillary_info.get("year_min") == ancillary_info.get("year_max")
                else date_range
            )
            time_coverage_cell = (
                f'<span class="date-range">Year: {year_label}</span><br>'
                f'<span class="freq-str">Countries: {ancillary_info.get("countries", "—")}</span><br>'
                f'<span class="coverage-note">Records: {ancillary_info.get("records", "—")}</span>'
            )
        else:
            obs_detail = _ratio_detail(total_obs, expected_total)
            since_detail = _ratio_detail(obs_since_2026, expected_since_2026)
            history_detail = _ratio_detail(obs_before_2026, expected_before_2026)
            recency_label = (
                f"{days_since}d ago" if days_since is not None else "unknown"
            )
            time_coverage_cell = (
                f'<span class="date-range">Observations: {obs_detail}</span><br>'
                f'<span class="freq-str">Granularity: {freq_display}</span><br>'
                f'<span class="coverage-note">Since 2026: {since_detail}</span><br>'
                f'<span class="coverage-note">History: {history_detail}</span><br>'
                f'<span class="coverage-note">Recency: {recency_label}</span>'
            )
            if len(sk_stats) == 1:
                gap_note = sk_stats[0].get("missing_summary", "")
                if gap_note:
                    time_coverage_cell += f'<br><span class="coverage-note">{_html.escape(gap_note)}</span>'

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
        elif is_ancillary and ancillary_info:
            latest_str = str(ancillary_info.get("year_max", "—"))
            days_info = "annual"
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
            f'<span class="latest-date">Last Date: {latest_str}</span><br>'
            + status_badge_html
            + "<br>"
            f'<span class="days-info">{days_info}</span><br>'
            f'<span class="next-info">{next_info}</span><br>' + schedule_html
        )

        # --- Usability score cell ---
        coverage_ratio_val = (
            obs_since_2026 / expected_since_2026
            if expected_since_2026 and obs_since_2026 is not None
            else None
        )
        usability_score = _usability_score(coverage_ratio_val, freq_str, days_since, n)
        recency_text = (
            f"{days_since}d since last update" if days_since is not None else "unknown"
        )
        usability_cell = (
            f'<span class="score">Score: {usability_score}/10</span><br>'
            f"Coverage: {coverage_since_score} since 2026.<br>"
            f"Granularity: {freq_display}.<br>"
            f"Recency: {recency_text}.<br>"
            f"Breadth: {n} products."
        )
        if products:
            usability_cell += '<br><span class="prod-count">Products:</span>'
            usability_cell += (
                "<ul>"
                + "".join(
                    f"<li>{_html.escape(p)} — usability {usability_score}/10, coverage {coverage_since_score}, granularity {freq_display}</li>"
                    for p in products
                )
                + "</ul>"
            )

        tbody_html += (
            f'<tr data-country="{_html.escape(e.get("country", ""))}" '
            f'data-method="{_html.escape(method_data)}" '
            f'data-status="{status_label}" '
            f'data-usability="{usability_score}">'
            f'<td class="country">{country}</td>'
            f'<td class="source">{source_cell}</td>'
            f'<td class="desc">{description}</td>'
            f'<td class="updated-to">{updated_to_cell}</td>'
            f'<td class="time-coverage">{time_coverage_cell}</td>'
            f'<td class="products">{prods_html}{usability_cell}</td>'
            f'<td class="method">{method_cell}</td>'
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
    status_legend_html = f'<div class="legend-section">{_legend_block("Freshness Status", status_colors)}</div>'

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



{status_legend_html}

<div class="table-wrap">
<table>
    <thead>
        <tr>
            <th data-col="0">Country <span class="sort-icon"></span></th>
            <th data-col="1">Source <span class="sort-icon"></span></th>
            <th data-col="2">Description</th>
            <th data-col="3">Updated To <span class="sort-icon"></span></th>
            <th data-col="4">Time Coverage <span class="sort-icon"></span></th>
            <th data-col="5">Products / Usability</th>
            <th data-col="6">Extraction Methods</th>
        </tr>
    </thead>
    <tbody>
{tbody_html}    </tbody>
</table>
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
