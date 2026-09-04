"""Generate a standalone dashboard HTML with a regional policy tab plus the
three EPU/Topics views. Each tab lives in its own iframe srcdoc, and tab
switching is CSS-only (radio + label) so the host page contains zero inline
<script> blocks. This shape is what survives corporate sanitizers that strip
inline scripts on upload.

The policy iframe is sourced from the per-region HTML files in
``src/text/plotting/addons/{tracker}/{region}_policy_addon.html``.
"""

import json
from pathlib import Path

import pandas as pd

from text.plotting.trackers import (
    ADDON_SUFFIX,
    addon_filename,
    dashboard_filename,
    get_tracker,
    tracker_chip_groups,
    tracker_dir,
    tracker_groups,
    tracker_label,
)


EXCLUDE_COUNTRIES = []

ADDONS_DIR = Path(__file__).resolve().parent / "addons"
VENDOR_DIR = Path(__file__).resolve().parent / "vendor"


_VENDOR_CACHE: dict[str, str] = {}


def _vendor(name: str) -> str:
    if name not in _VENDOR_CACHE:
        _VENDOR_CACHE[name] = (VENDOR_DIR / name).read_text(encoding="utf-8")
    return _VENDOR_CACHE[name]


def _addon_path(region: str, tracker: str | None = None) -> Path:
    return tracker_dir(ADDONS_DIR, tracker) / addon_filename(region)


def available_regions(tracker: str | None = None) -> list[str]:
    """Region slugs with an addon HTML in the tracker's addons subdirectory."""
    addons_dir = tracker_dir(ADDONS_DIR, tracker)
    if not addons_dir.exists():
        return []
    return sorted(
        p.name[: -len(ADDON_SUFFIX)]
        for p in addons_dir.iterdir()
        if p.is_file() and p.name.endswith(ADDON_SUFFIX)
    )


# ---------- Loaders ----------


def fmt_country(c):
    """Format country name from snake_case to Title Case."""
    return " ".join(w[0].upper() + w[1:] for w in c.split("_"))


def load_topics_epu_data(country, data_dir):
    f = data_dir / f"{country}/epu/topics_epu.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f)
    df["date"] = pd.to_datetime(df["date"], format="mixed")
    return df.sort_values("date")


def load_actors_epu_data(country, data_dir):
    f = data_dir / f"{country}/epu/actors_epu.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f)
    df["date"] = pd.to_datetime(df["date"], format="mixed")
    return df.sort_values("date")


_GROUP_COL_SUFFIXES = (
    # Longest first: `_group_of` matches on endswith, and a bare "_absolute"
    # would otherwise never see the "_absolute_z" twin. A suffix missing here
    # reads as an id column, so `_keep_groups` stops filtering it and every
    # tracker ships all 43 groups instead of its own slice.
    "_absolute_z",
    "_framing_z",
    "_intensity_z",
    "_absolute",
    "_framing",
    "_intensity",
)


def _group_of(col: str) -> str | None:
    """Keyword group a data column belongs to, or None for an id column."""
    for suffix in _GROUP_COL_SUFFIXES:
        if col.endswith(suffix):
            return col[: -len(suffix)]
    return None


_TOPIC_MEASURES = ("intensity", "absolute", "framing")


def _topic_payload(rows: list) -> tuple[list, dict, list]:
    """Trim an attribution table to index-scale columns and derive the z factors.

    Every `<group>_<measure>` column is an exact affine rescale of its `_z` twin
    — `index = factor * z`, with one factor for the whole column — so shipping
    the factor costs a single float where shipping the second series costs a
    full column. Across 43 topics and three measures that is the difference
    between a dashboard the intranet serves and one it chokes on.

    Values are rounded to three decimals. The index sits around 100, so three
    decimals is well past what the chart can draw, and full float repr is
    roughly two and a half times the bytes.

    Returns (rows, factors, groups) where `factors` maps a `<group>_<measure>`
    column to the divisor that converts it back to a z-score, or None when the
    column is flat at zero and no factor is recoverable.
    """
    if not rows:
        return [], {}, []
    first = rows[0]
    groups = sorted(
        {col[: -len("_intensity")] for col in first if col.endswith("_intensity")}
    )
    wanted = [
        f"{g}_{m}" for g in groups for m in _TOPIC_MEASURES if f"{g}_{m}" in first
    ]

    factors: dict = {}
    for col in wanted:
        z_col = f"{col}_z"
        factor = None
        if z_col in first:
            for row in rows:
                idx_v, z_v = row.get(col), row.get(z_col)
                if idx_v is None or z_v is None or z_v == 0:
                    continue
                factor = idx_v / z_v
                break
        factors[col] = factor

    out = []
    for row in rows:
        trimmed = {"date": row.get("date"), "ym": row.get("ym")}
        for col in wanted:
            v = row.get(col)
            trimmed[col] = None if v is None else round(v, 3)
        out.append(trimmed)
    return out, factors, groups


def _keep_groups(rows: list, groups: set) -> list:
    """Drop columns for groups this tracker does not display.

    Every build computes every theme, so the per-unit CSVs carry all groups.
    A tracker shows its own slice; the numbers are shared, only the view differs.
    """
    return [
        {
            col: val
            for col, val in row.items()
            if _group_of(col) is None or _group_of(col) in groups
        }
        for row in rows
    ]


def load_attribution_data(country, data_dir, source_file):
    f = data_dir / f"{country}/uncertainty_attribution/{source_file}.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f)
    df["date"] = pd.to_datetime(df["date"], format="mixed")
    return df.sort_values("date")


def df_to_json(df):
    data = []
    for _, row in df.iterrows():
        r = {}
        for col in df.columns:
            v = row[col]
            if pd.isna(v):
                r[col] = None
            elif isinstance(v, pd.Timestamp):
                r[col] = v.strftime("%Y-%m-%d")
            elif isinstance(v, (int, float)):
                r[col] = float(v) if not pd.isna(v) else None
            else:
                r[col] = str(v)
        data.append(r)
    return data


PALETTE = [
    "#1d77b2",
    "#d95e10",
    "#00a37c",
    "#e7298a",
    "#66a61e",
    "#e6ab02",
    "#7570b3",
    "#a6761d",
    "#666666",
    "#1b9e77",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#17becf",
    "#bcbd22",
    "#ff7f0e",
    "#2ca02c",
    "#e377c2",
    "#7f7f7f",
    "#aec7e8",
    "#ffbb78",
    "#98df8a",
]


def escape_srcdoc(s):
    """Minimal HTML escape for content inside srcdoc='...' (single-quoted).
    Only & < > ' need escaping; double quotes pass through unescaped, which
    keeps embedded JSON payloads from inflating ~5x."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("'", "&#39;")
    )


# ---------- Shared CSS for EPU mini-pages ----------

EPU_PAGE_CSS = """
:root {
    --bg: #f6f7fb;
    --panel: #ffffff;
    --text: #1e2432;
    --muted: #667085;
    --accent: #1d77b2;
    --border: #e3e7ef;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--panel);
    color: var(--text);
    padding: 14px 18px 18px 18px;
}
.controls { margin-bottom: 10px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
/* Five controls on one row: a bare flex row breaks between a label and its own
   input, so "Top N:" ends a line and its box starts the next. Each pair becomes
   one unbreakable column instead, and the row wraps between pairs. */
.field-row { align-items: flex-end; gap: 14px 16px; }
.field-row .field { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.field-row .field > label {
    font-size: 0.78em;
    font-weight: 600;
    color: #667085;
    letter-spacing: 0.02em;
}
.field-row .field > select { width: 100%; min-width: 150px; }
.field-row .field-narrow > input { width: 84px; }
label { font-weight: 600; color: #333; font-size: 0.95em; }
select { padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 0.9em; cursor: pointer; background: #fff; }
select:hover { border-color: #667eea; }
select:focus { outline: 0; border-color: #667eea; }
input[type="number"] { padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 0.9em; width: 70px; }
input[type="number"]:hover { border-color: #667eea; }
input[type="number"]:focus { outline: 0; border-color: #667eea; }
.chart-wrapper { position: relative; height: 65vh; min-height: 360px; }
.plot-row { display: flex; gap: 14px; align-items: stretch; margin-top: 8px; }
.chart-col { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.chart-col .chart-wrapper { flex: 1 1 auto; }
.toggle-group { display: inline-flex; }
.toggle-group label {
    padding: 4px 12px;
    border: 1px solid #ddd;
    font-size: 0.82em;
    font-weight: 400;
    cursor: pointer;
    user-select: none;
    transition: all 0.15s;
    margin-left: -1px;
}
.toggle-group label:first-child { margin-left: 0; border-radius: 16px 0 0 16px; }
.toggle-group label:last-child { border-radius: 0 16px 16px 0; }
.toggle-group input[type="checkbox"] { display: none; }
.toggle-group label:has(input:checked) {
    background: #667eea;
    color: #fff;
    border-color: #667eea;
    z-index: 1;
    position: relative;
}
.toggle-group label:hover:not(:has(input:checked)) { border-color: #667eea; background: #f0f4ff; }
.chip-sidebar {
    flex: 0 0 232px;
    width: 232px;
    height: 65vh;
    min-height: 360px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    border-right: 1px solid #eee;
    padding-right: 10px;
}
.chip-header { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 0.9em; }
.chip-tools { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.chip-tools input[type="text"] { padding: 6px 10px; border: 1px solid #ddd; border-radius: 16px; font-size: 0.82em; flex: 1 1 100%; min-width: 0; }
.chip-tools input[type="text"]:hover { border-color: #667eea; }
.chip-tools input[type="text"]:focus { outline: 0; border-color: #667eea; }
.chip-tools button { padding: 4px 8px; border: 1px solid #ddd; border-radius: 12px; background: #fff; font-size: 0.8em; cursor: pointer; }
.chip-tools button:hover { border-color: #667eea; background: #f0f4ff; }
.chip-container {
    display: flex;
    flex-wrap: wrap;
    align-content: flex-start;
    gap: 6px;
    flex: 1 1 auto;
    overflow-y: auto;
    padding: 4px 2px 4px 0;
}
/* Groups stack: a full-width flex item forces a line break in the wrap
   container, so grouped and ungrouped chip lists share one container. */
.chip-group { width: 100%; }
.chip-group.is-empty { display: none; }
.chip-group-header {
    display: flex;
    align-items: center;
    gap: 6px;
    width: 100%;
    padding: 4px 2px;
    border: 0;
    background: none;
    cursor: pointer;
    font-size: 0.78em;
    font-weight: 600;
    color: #444;
    text-align: left;
}
.chip-group-header:hover { color: #667eea; }
.chip-group-caret { display: inline-block; transition: transform 0.15s; color: #999; }
.chip-group.is-open .chip-group-caret { transform: rotate(90deg); }
.chip-group-label { flex: 1; }
.chip-group-count { color: #999; font-weight: 400; font-variant-numeric: tabular-nums; }
.chip-group-body { display: flex; flex-wrap: wrap; gap: 6px; padding: 0 0 8px 10px; }
/* Collapsed hides its members, except the ones the reader still needs to see:
   a selected pill (its line is on the chart and this is the only way off) and
   a search hit (otherwise search could not reach into a closed group). */
.chip-group:not(.is-open) .chip-group-body > .chip { display: none; }
.chip-group:not(.is-open) .chip-group-body > .chip.is-hit,
.chip-group:not(.is-open) .chip-group-body > .chip:has(input:checked) { display: inline-flex; }
.chip.is-filtered { display: none !important; }
.chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    border: 1px solid var(--chip-color, #ddd);
    border-radius: 16px;
    font-size: 0.8em;
    font-weight: 400;
    cursor: pointer;
    user-select: none;
    transition: all 0.15s;
}
.chip:hover { border-color: var(--chip-color, #667eea); background: rgba(102, 126, 234, 0.08); }
.chip input[type="checkbox"] { display: none; }
.chip:has(input:checked) {
    background: var(--chip-color, #667eea);
    color: #fff;
    border-color: var(--chip-color, #667eea);
}
/* Colour identity lives on the pills, so the key carries only what the pills
   cannot say: what a line's stroke means. Three rows, one per stroke. */
.style-key {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 20px;
    margin-top: 10px;
    padding-top: 8px;
    border-top: 1px solid #eee;
    font-size: 0.78em;
    color: #555;
}
.style-key-row { display: flex; align-items: center; gap: 8px; }
.key-line { width: 26px; height: 0; border-top-color: #888; }
.key-ma { border-top: 2.5px solid #888; }
.key-raw { border-top: 1.5px dashed #888; }
.key-current { border-top: 2px dashed #888; position: relative; }
.key-current::after {
    content: '';
    position: absolute;
    right: 3px;
    top: -3px;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #888;
}
.chart-tooltip {
    position: absolute;
    background: #fff;
    border: 1px solid #ddd;
    border-radius: 6px;
    box-shadow: 0 6px 18px rgba(0,0,0,0.12);
    padding: 8px 10px;
    pointer-events: none;
    font-size: 0.82em;
    color: #222;
    z-index: 10;
    max-width: 260px;
}
.tooltip-title { font-weight: 700; margin-bottom: 6px; }
.tooltip-table { width: 100%; border-collapse: collapse; }
.tooltip-table td { padding: 1px 0; }
.tooltip-group-title-row td { padding-top: 4px; font-weight: 600; }
.tooltip-indent { padding-left: 12px; }
.tooltip-val { text-align: right; font-variant-numeric: tabular-nums; }
/* The handle tooltips render above the track, so the row needs headroom or
   they sit on top of the dropdowns in the control row above. */
.slider-row { display: flex; align-items: center; gap: 10px; margin: 38px 0 14px; overflow: visible; }
.slider-row label { font-weight: 600; color: #333; font-size: 0.95em; white-space: nowrap; }
.range-label { font-size: 0.85em; color: #555; min-width: 140px; text-align: center; white-space: nowrap; }
.date-slider { flex: 0 0 320px; min-width: 200px; max-width: 320px; }
.noUi-connect { background: #667eea !important; }
.noUi-handle {
    border: 2px solid #667eea !important;
    border-radius: 50% !important;
    background: #fff !important;
    box-shadow: 0 1px 4px rgba(102,126,234,0.35) !important;
    cursor: ew-resize;
}
.noUi-horizontal .noUi-handle { width: 18px; height: 18px; right: -9px; top: -8px; }
.noUi-handle:before, .noUi-handle:after { display: none !important; }
.noUi-handle:hover { background: #667eea !important; box-shadow: 0 0 0 3px rgba(102,126,234,0.2) !important; }
.noUi-tooltip { font-size: 0.75em; padding: 2px 6px; background: #667eea; color: #fff; border: none; border-radius: 4px; }
@media (max-width: 900px) {
    .plot-row { flex-direction: column; }
    .chip-sidebar {
        flex: 1 1 auto;
        width: 100%;
        height: auto;
        min-height: 0;
        max-height: 200px;
        border-right: 0;
        border-bottom: 1px solid #eee;
        padding-right: 0;
        padding-bottom: 8px;
    }
    .chart-col .chart-wrapper { height: 65vh; }
}
@media (max-width: 760px) {
    .date-slider { flex: 1; max-width: none; }
}
.table-section { margin-top: 14px; }
.table-header {
    display: flex;
    align-items: baseline;
    gap: 10px;
    margin-bottom: 6px;
    font-size: 0.9em;
    font-weight: 600;
    color: #344054;
}
.table-note { font-weight: 400; font-size: 0.85em; color: #667085; }
/* The table lists every topic and runs to the full length of the page rather
   than scrolling in its own box, so the whole ranking is scannable at once. */
.table-scroll {
    border: 1px solid #eaecf0;
    border-radius: 6px;
}
.rank-table { width: 100%; border-collapse: collapse; font-size: 0.85em; }
.rank-table th, .rank-table td { padding: 5px 10px; text-align: left; }
.rank-table thead th {
    position: sticky;
    top: 0;
    background: #f9fafb;
    border-bottom: 1px solid #eaecf0;
    color: #667085;
    font-weight: 600;
}
.rank-table tbody tr { border-bottom: 1px solid #f2f4f7; }
.rank-table td.num, .rank-table th.num { text-align: right; font-variant-numeric: tabular-nums; }
/* Topics this tracker is about, highlighted in place rather than filtered out,
   so their rank against everything else stays visible. */
.rank-table tr.focus-row { background: #fff7e6; }
.rank-table tr.focus-row td:nth-child(2) { font-weight: 600; }
.rank-table td.up { color: #b42318; }
.rank-table td.down { color: #067647; }
/* Readers kept asking what an EPU actually is, so the recipe sits on the page
   rather than in a separate methodology note nobody opens. */
.method-box {
    margin-top: 18px;
    padding: 12px 14px;
    border: 1px solid #eaecf0;
    border-radius: 8px;
    background: #f9fafb;
    font-size: 0.82em;
    line-height: 1.5;
    color: #475467;
}
.method-box h3 { font-size: 1em; color: #344054; margin-bottom: 6px; }
.method-box ol { margin: 0 0 0 18px; }
.method-box li { margin-bottom: 3px; }
.method-box .method-foot { margin-top: 8px; color: #667085; }
"""


# ---------- Shared JS helpers (used by all three EPU iframes) ----------

EPU_COMMON_JS = """
const VARIANT_ORDER = ['ma3', 'ma6', 'ma12', 'rawMonthly', 'rawDaily'];
const VARIANT_LABELS = {
    ma3: '3-Mo MA',
    ma6: '6-Mo MA',
    ma12: '12-Mo MA',
    rawMonthly: 'Raw (monthly)',
    rawDaily: 'Raw (weekly/daily)'
};

function isDaily(r) { return r && typeof r.ym === 'string' && r.ym.split('-').length === 3; }
function getDayOfMonth(dateStr) { return parseInt(dateStr.split('-')[2], 10); }
function getMonthKey(dateStr) { const p = dateStr.split('-'); return p[0] + '-' + p[1]; }
function formatYM(d) { const x = new Date(d); return x.getFullYear() + '-' + String(x.getMonth() + 1).padStart(2, '0'); }

function getTooltipEl() {
    let el = document.getElementById('chart-tooltip');
    if (!el) {
        el = document.createElement('div');
        el.id = 'chart-tooltip';
        el.className = 'chart-tooltip';
        document.body.appendChild(el);
    }
    return el;
}

function computeMA(values, w) {
    if (w <= 1) return values.slice();
    var result = [];
    for (var i = 0; i < values.length; i++) {
        if (i < w - 1) { result.push(null); continue; }
        var sum = 0, count = 0;
        for (var j = i - w + 1; j <= i; j++) {
            if (values[j] != null) { sum += values[j]; count++; }
        }
        result.push(count > 0 ? sum / count : null);
    }
    return result;
}

function computeAverage(values) {
    if (!values.length) return null;
    return values.reduce((s, v) => s + v, 0) / values.length;
}

function buildDailyDisplay(dailyData) {
    if (!dailyData || !dailyData.length) return { labels: [], entries: [] };
    const monthKey = getMonthKey(dailyData[0].date);
    const withDay = dailyData
        .map(r => ({ row: r, day: getDayOfMonth(r.date) }))
        .sort((a, b) => a.day - b.day);
    const latestDay = Math.max.apply(null, withDay.map(d => d.day));
    const entries = [];
    const weeks = [
        { key: 'W1', start: 1, end: 7 },
        { key: 'W2', start: 8, end: 14 },
        { key: 'W3', start: 15, end: 21 },
        { key: 'W4', start: 22, end: 29 }
    ];
    weeks.forEach(week => {
        const rows = withDay.filter(d => d.day >= week.start && d.day <= week.end);
        if (!rows.length) return;
        if (latestDay >= week.end) {
            entries.push({ type: 'weekly', label: monthKey + '-' + week.key, rows: rows.map(r => r.row) });
        } else {
            rows.forEach(item => entries.push({ type: 'daily', label: item.row.date, rows: [item.row] }));
        }
    });
    withDay.filter(d => d.day >= 30).forEach(item => {
        entries.push({ type: 'daily', label: item.row.date, rows: [item.row] });
    });
    return { labels: entries.map(e => e.label), entries: entries };
}

function hexToRgba(hex, alpha) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
}

function getActiveWindows(toggleName) {
    return Array.from(document.querySelectorAll('input[name="' + toggleName + '"]:checked'))
           .map(cb => parseInt(cb.value));
}

function buildMADatasets(rawValues, baseColor, seriesLabel, toggleName) {
    const windows = getActiveWindows(toggleName).sort((a, b) => a - b);
    const suffixMap = {
        1:  { dash: [5, 5], width: 1.5, suffix: '(Raw)' },
        3:  { dash: [],     width: 2.5, suffix: '(3-Mo MA)' },
        6:  { dash: [],     width: 2,   suffix: '(6-Mo MA)' },
        12: { dash: [],     width: 2,   suffix: '(12-Mo MA)' }
    };
    const variantMap = { 1: 'rawMonthly', 3: 'ma3', 6: 'ma6', 12: 'ma12' };
    const opacitySteps = [1.0, 0.55, 0.35, 0.2];
    const maWindows = windows.filter(w => w !== 1);
    return windows.map(w => {
        const s = suffixMap[w];
        let opacity;
        if (w === 1) {
            opacity = 0.45;
        } else {
            const maIdx = maWindows.indexOf(w);
            opacity = opacitySteps[maIdx] !== undefined ? opacitySteps[maIdx] : 0.2;
        }
        return {
            label: seriesLabel + ' ' + s.suffix,
            data: computeMA(rawValues, w),
            borderColor: hexToRgba(baseColor, opacity),
            borderDash: s.dash,
            borderWidth: s.width,
            fill: false, tension: 0.1, pointRadius: 0, pointHoverRadius: 5,
            _variant: variantMap[w] || 'ma'
        };
    });
}

function initSlider(state, data, defaultMonths, sliderId, rangeLabelId) {
    if (!data || !data.length) return;
    state.sliderDates = data.map(r => r.date);
    const maxIdx = state.sliderDates.length - 1;
    const maxDate = new Date(state.sliderDates[maxIdx]);
    const startDate = new Date(maxDate.getTime());
    startDate.setMonth(startDate.getMonth() - Math.max(0, defaultMonths - 1));
    let startIdx = state.sliderDates.findIndex(d => new Date(d) >= startDate);
    if (startIdx < 0) startIdx = 0;
    const el = document.getElementById(sliderId);
    if (state.slider) { state.slider.destroy(); }
    state.slider = noUiSlider.create(el, {
        start: [startIdx, maxIdx],
        connect: true,
        step: 1,
        range: { min: 0, max: maxIdx || 1 },
        tooltips: [
            { to: v => { const r = data[Math.round(v)]; return r && isDaily(r) ? r.date : formatYM(state.sliderDates[Math.round(v)]); } },
            { to: v => { const r = data[Math.round(v)]; return r && isDaily(r) ? r.date : formatYM(state.sliderDates[Math.round(v)]); } }
        ]
    });
    const rangeLabel = document.getElementById(rangeLabelId);
    function updateLabel() {
        const vals = state.slider.get().map(v => Math.round(v));
        rangeLabel.textContent = formatYM(state.sliderDates[vals[0]]) + ' -> ' + formatYM(state.sliderDates[vals[1]]);
    }
    updateLabel();
    state.slider.on('update', function() { updateLabel(); });
    state.slider.on('change', function() { state.onChange(); });
}

function getSliderRange(state) {
    if (!state.slider || !state.sliderDates.length) return { from: '', to: '' };
    const vals = state.slider.get().map(v => Math.round(v));
    return { from: state.sliderDates[vals[0]], to: state.sliderDates[vals[1]] };
}

function buildTooltipGroups(chart, dataIndex) {
    const groups = {};
    const order = chart._groupOrder || [];
    chart.data.datasets.forEach((ds, i) => {
        if (!chart.isDatasetVisible(i)) return;
        const key = ds._legendGroup || ds.label || 'Series';
        if (!groups[key]) {
            groups[key] = { label: ds._legendLabel || ds.label || key, items: [] };
        }
        if (!VARIANT_LABELS[ds._variant]) return;
        const pointType = ds._pointTypes ? ds._pointTypes[dataIndex] : null;
        groups[key].items.push({ variant: ds._variant, value: ds.data[dataIndex], pointType: pointType });
    });
    const orderedKeys = order.length ? order.filter(k => groups[k]) : Object.keys(groups);
    return orderedKeys.map(key => {
        const group = groups[key];
        group.items.sort((a, b) => {
            const av = VARIANT_ORDER.indexOf(a.variant);
            const bv = VARIANT_ORDER.indexOf(b.variant);
            return (av === -1 ? 99 : av) - (bv === -1 ? 99 : bv);
        });
        return group;
    });
}

function externalTooltipHandler(context) {
    const tooltip = context.tooltip;
    const chart = context.chart;
    const tooltipEl = getTooltipEl();
    if (!tooltip || tooltip.opacity === 0) {
        tooltipEl.style.opacity = 0;
        return;
    }
    const dataIndex = tooltip.dataPoints && tooltip.dataPoints.length ? tooltip.dataPoints[0].dataIndex : null;
    if (dataIndex == null) return;
    const label = (tooltip.title && tooltip.title.length) ? tooltip.title[0] : '';
    const groups = buildTooltipGroups(chart, dataIndex);
    let html = '<div class="tooltip-title">' + label + '</div><table class="tooltip-table">';
    groups.forEach(group => {
        html += '<tr class="tooltip-group-title-row"><td colspan="2">' + group.label + '</td></tr>';
        group.items.forEach(item => {
            const val = (item.value == null) ? '-' : (typeof item.value === 'number' ? item.value.toFixed(2) : item.value);
            let variantLabel = VARIANT_LABELS[item.variant] || item.variant;
            if (item.variant === 'rawDaily' && item.pointType) {
                variantLabel = item.pointType === 'weekly' ? 'Raw (weekly)' : 'Raw (daily)';
            }
            html += '<tr class="tooltip-row"><td class="tooltip-indent">' + variantLabel + '</td><td class="tooltip-val">' + val + '</td></tr>';
        });
    });
    html += '</table>';
    tooltipEl.innerHTML = html;
    const rect = chart.canvas.getBoundingClientRect();
    tooltipEl.style.opacity = 1;
    tooltipEl.style.left = rect.left + window.pageXOffset + tooltip.caretX + 'px';
    tooltipEl.style.top = rect.top + window.pageYOffset + tooltip.caretY + 'px';
}
"""


# ---------- Tab 1: Uncertainty Topics (rank chart) ----------

TOPIC_PAGE_TEMPLATE = r"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>Uncertainty Topics (Ranked)</title>
<script>__CHARTJS_INLINE__</script>
<style>__NOUI_CSS_INLINE__</style>
<script>__NOUI_JS_INLINE__</script>
<style>__CSS__</style>
</head>
<body>
<div class="controls field-row">
    <div class="field">
        <label for="topic-country">Country</label>
        <select id="topic-country">__COUNTRY_OPTIONS__</select>
    </div>
    <div class="field">
        <label for="topic-measure">Measure</label>
        <select id="topic-measure">
            <option value="intensity">How much the topic is discussed</option>
            <option value="absolute" selected>How much uncertainty is about the topic</option>
            <option value="framing">The topic&#39;s share of uncertainty</option>
        </select>
    </div>
    <div class="field">
        <label for="topic-scale">Scale</label>
        <select id="topic-scale">
            <option value="index" selected>Index (baseline = 100)</option>
            <option value="z">Z-score</option>
        </select>
    </div>
    <div class="field">
        <label for="topic-universe">Compared against</label>
        <select id="topic-universe">
            <option value="focus" selected>Tracker topics (__N_FOCUS__)</option>
            <option value="all">All topics (__N_ALL__)</option>
        </select>
    </div>
    <div class="field field-narrow">
        <label for="topic-topn">Top N</label>
        <input type="number" id="topic-topn" value="5" min="1">
    </div>
</div>
<div class="slider-row">
    <label>Date Range:</label>
    <span class="range-label" id="topic-range">-</span>
    <div id="topic-slider" class="date-slider"></div>
</div>
<p style="margin: 6px 0 0; font-size: 0.85em; color: #667085;" id="topic-explainer">-</p>
<div class="chart-wrapper">
    <canvas id="topic-chart"></canvas>
</div>
<div class="table-section">
    <div class="table-header">
        <span id="topic-table-title">Latest month</span>
        <span class="table-note" id="topic-table-note"></span>
    </div>
    <div class="table-scroll">
        <table class="rank-table" id="topic-table">
            <thead><tr><th>#</th><th>Topic</th><th class="num">Value</th><th class="num">Prev.</th><th class="num">Change</th></tr></thead>
            <tbody></tbody>
        </table>
    </div>
</div>
<script>
__COMMON_JS__

const topicData = __DATA_JSON__;
const topicFactors = __FACTORS_JSON__;
const topicFocusGroups = __FOCUS_JSON__;
const topicAllGroups = __ALL_GROUPS_JSON__;
const topicPalette = __PALETTE_JSON__;

// Each measure is a different question with a different denominator. Naming the
// denominator on screen is the point: an index of 150 is only alarming once you
// know what it is 150 relative to, and which articles were in the pool at all.
const MEASURE_META = {
    intensity: {
        short: 'intensity',
        blurb: 'Articles mentioning the topic, as a share of all articles. No uncertainty condition &mdash; this is how much the topic is covered, full stop.'
    },
    absolute: {
        short: 'uncertainty',
        blurb: 'Articles that are both uncertain and about the topic, as a share of all articles.'
    },
    framing: {
        short: 'framing',
        blurb: 'Articles that are both uncertain and about the topic, as a share of uncertain articles only. This is a composition measure: it rises when a topic takes a larger slice of the same uncertainty.'
    }
};
const SCALE_META = {
    index: 'rescaled so the baseline period averages 100',
    z: 'expressed in units of its own baseline standard deviation'
};
const topicState = { slider: null, sliderDates: [], chart: null, onChange: () => {} };

const labelMap = {
    'Imf': 'IMF',
    'Us Government': 'US Government',
    'Us China Trade War': 'US-China Trade War',
    'Covid Pandemic': 'COVID-19 Pandemic',
    'Inflation Prices': 'Inflation & Prices',
    'Climate Environment': 'Climate & Environment',
    'Corruption Governance': 'Corruption & Governance',
    'Housing Real Estate': 'Housing & Real Estate'
};
function fmtLabel(key) {
    const raw = key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
    return labelMap[raw] || raw;
}

function initTopicTab() {
    const select = document.getElementById('topic-country');
    const topnInput = document.getElementById('topic-topn');
    function render() {
        const country = select.value;
        const rawData = topicData[country];
        if (!rawData || !rawData.length) return;
        const range = getSliderRange(topicState);
        let data = rawData;
        if (range.from) data = data.filter(r => r.date >= range.from);
        if (range.to) data = data.filter(r => r.date <= range.to);
        const measure = document.getElementById('topic-measure').value;
        const scale = document.getElementById('topic-scale').value;
        const universe = document.getElementById('topic-universe').value;
        const factors = topicFactors[country] || {};
        const suffix = '_' + measure;

        // Value in the requested scale. The index is `factor * z` with one
        // factor per column, so dividing recovers the z-score exactly; only a
        // column that never left zero has no recoverable factor, and there the
        // two scales agree at zero anyway.
        function valueOf(row, item) {
            const raw = row[item + suffix];
            if (raw == null) return null;
            if (scale === 'index') return raw;
            const f = factors[item + suffix];
            return (f == null || f === 0) ? null : raw / f;
        }

        const present = Object.keys(rawData[0])
            .filter(k => k.endsWith(suffix))
            .map(k => k.slice(0, -suffix.length));
        const pool = universe === 'all' ? topicAllGroups : topicFocusGroups;
        const items = present.filter(it => pool.indexOf(it) !== -1);
        if (!items.length) return;
        data = data.filter(r => !isDaily(r) || items.some(item => r[item + suffix] != null));
        if (!data.length) return;
        let topN = parseInt(topnInput.value, 10) || 5;
        topN = Math.max(1, Math.min(topN, items.length));

        const monthlyData = data.filter(r => !isDaily(r));
        const dailyData = data.filter(r => isDaily(r));
        const dailyDisplay = buildDailyDisplay(dailyData);
        const displayEntries = monthlyData.map(r => ({
            type: 'monthly',
            label: r.date.split('-')[0] + '-' + r.date.split('-')[1],
            rows: [r]
        })).concat(dailyDisplay.entries);
        const dateToIndex = new Map(rawData.map((r, idx) => [r.date, idx]));
        const smoothedFull = {};
        items.forEach(item => {
            const fullVals = rawData.map(r => valueOf(r, item) || 0);
            smoothedFull[item] = computeMA(fullVals, 3);
        });
        const smoothed = {};
        items.forEach(item => {
            smoothed[item] = displayEntries.map(entry => {
                const vals = entry.rows
                    .map(r => {
                        const idx = dateToIndex.get(r.date);
                        return idx == null ? null : smoothedFull[item][idx];
                    })
                    .filter(v => v != null);
                if (!vals.length) return null;
                return vals.reduce((s, v) => s + v, 0) / vals.length;
            });
        });

        const meanSmoothed = items.map(item => {
            const vals = smoothed[item].filter(v => v != null);
            const mean = vals.length > 0 ? vals.reduce((s, v) => s + v, 0) / vals.length : 0;
            return { item: item, mean: mean };
        });
        meanSmoothed.sort((a, b) => b.mean - a.mean);
        const visible = meanSmoothed.slice(0, topN).map(v => v.item).sort();

        const ranks = displayEntries.map((entry, t) => {
            const vals = visible.map(item => ({ item: item, value: smoothed[item][t] != null ? smoothed[item][t] : 0 }));
            vals.sort((a, b) => b.value - a.value);
            const monthRanks = {};
            vals.forEach((v, i) => { monthRanks[v.item] = i + 1; });
            return monthRanks;
        });

        const labels = displayEntries.map(entry => entry.label);

        const datasets = visible.map((item, i) => {
            const color = topicPalette[i % topicPalette.length];
            return {
                label: fmtLabel(item),
                data: ranks.map(mr => mr[item]),
                borderColor: color,
                borderWidth: 2.5,
                fill: false,
                tension: 0,
                pointRadius: displayEntries.map(entry => entry.type === 'daily' ? 7 : (entry.type === 'weekly' ? 6 : 5)),
                pointStyle: displayEntries.map(entry => entry.type === 'daily' ? 'rectRot' : (entry.type === 'weekly' ? 'rect' : 'circle')),
                pointBackgroundColor: displayEntries.map(entry => (entry.type === 'daily' || entry.type === 'weekly') ? '#fff' : color),
                pointBorderColor: color,
                pointBorderWidth: displayEntries.map(entry => (entry.type === 'daily' || entry.type === 'weekly') ? 2 : 1.5),
                pointHoverRadius: 8,
                segment: { borderDash: (ctx) => ['daily', 'weekly'].includes(displayEntries[ctx.p1DataIndex].type) ? [4, 4] : [] },
                _itemKey: item
            };
        });

        const ctx = document.getElementById('topic-chart').getContext('2d');
        if (topicState.chart) topicState.chart.destroy();
        topicState.chart = new Chart(ctx, {
            type: 'line',
            data: { labels: labels, datasets: datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top', labels: { usePointStyle: true, padding: 10, font: { size: 11 } } },
                    tooltip: {
                        mode: 'nearest',
                        intersect: false,
                        backgroundColor: 'rgba(0,0,0,0.8)',
                        padding: 12,
                        callbacks: {
                            label: function(context) {
                                const itemKey = context.dataset._itemKey;
                                const rank = context.raw;
                                const smoothedVal = smoothed[itemKey][context.dataIndex];
                                const entryType = displayEntries[context.dataIndex].type;
                                const tag = MEASURE_META[measure].short + (scale === 'z' ? ' z' : '');
                                const note = entryType === 'daily' ? ' [daily]' : (entryType === 'weekly' ? ' [weekly]' : '');
                                return context.dataset.label + ': Rank ' + rank + ' (' + tag + ': ' + (smoothedVal != null ? smoothedVal.toFixed(3) : 'N/A') + ')' + note;
                            }
                        }
                    }
                },
                scales: {
                    x: { display: true, title: { display: true, text: 'Date' } },
                    y: { display: true, title: { display: true, text: 'Rank (smoothed)' }, reverse: true, ticks: { stepSize: 1 } }
                }
            }
        });

        renderExplainer(measure, scale, items.length, pool.length);
        renderTable(data, valueOf, measure, scale);
    }

    // The chart follows the "compared against" selector; this table never does.
    // It always ranks the full topic set, because its whole job is to answer
    // "what else was in the pool" — the question a filtered chart cannot answer.
    function renderTable(data, valueOf, measure, scale) {
        const tbody = document.querySelector('#topic-table tbody');
        const note = document.getElementById('topic-table-note');
        const title = document.getElementById('topic-table-title');
        tbody.innerHTML = '';
        const monthly = data.filter(r => !isDaily(r));
        if (monthly.length < 1) { note.textContent = 'No monthly data in range.'; return; }
        const last = monthly[monthly.length - 1];
        const prev = monthly.length > 1 ? monthly[monthly.length - 2] : null;

        const rows = topicAllGroups.map(item => ({
            item: item,
            value: valueOf(last, item),
            prev: prev ? valueOf(prev, item) : null
        })).filter(r => r.value != null);
        rows.sort((a, b) => b.value - a.value);

        title.textContent = 'All topics ranked \u2014 ' + last.date.slice(0, 7);
        note.textContent = rows.length + ' topics, ' + MEASURE_META[measure].short +
            (scale === 'z' ? ' (z-score)' : ' (index)') +
            (prev ? ', change vs ' + prev.date.slice(0, 7) : '');

        rows.forEach((r, i) => {
            const tr = document.createElement('tr');
            if (topicFocusGroups.indexOf(r.item) !== -1) tr.className = 'focus-row';
            const delta = (r.prev == null) ? null : r.value - r.prev;
            const dTxt = delta == null ? '\u2013'
                : (delta > 0 ? '+' : '') + delta.toFixed(1);
            const dCls = delta == null ? '' : (delta > 0 ? 'up' : (delta < 0 ? 'down' : ''));
            tr.innerHTML = '<td class="num">' + (i + 1) + '</td>' +
                '<td>' + fmtLabel(r.item) + '</td>' +
                '<td class="num">' + r.value.toFixed(1) + '</td>' +
                '<td class="num">' + (r.prev == null ? '\u2013' : r.prev.toFixed(1)) + '</td>' +
                '<td class="num ' + dCls + '">' + dTxt + '</td>';
            tbody.appendChild(tr);
        });
    }

    function renderExplainer(measure, scale, nShown, nPool) {
        document.getElementById('topic-explainer').innerHTML =
            'Denominator: ' + MEASURE_META[measure].blurb +
            ' Each topic is then ' + SCALE_META[scale] + '.' +
            ' The chart ranks the top N of ' + nPool + ' topics in the selected comparison set' +
            ' (' + nShown + ' with data) against each other, month by month;' +
            ' the table below always ranks all ' + topicAllGroups.length + ' topics.';
    }

    topicState.onChange = render;
    select.addEventListener('change', function(e) {
        initSlider(topicState, topicData[e.target.value], 12, 'topic-slider', 'topic-range');
        render();
    });
    topnInput.addEventListener('change', render);
    ['topic-measure', 'topic-scale', 'topic-universe'].forEach(id => {
        document.getElementById(id).addEventListener('change', render);
    });
    initSlider(topicState, topicData[select.value], 12, 'topic-slider', 'topic-range');
    render();
}

initTopicTab();
</script>
</body></html>"""


# ---------- Tabs 2 & 3: EPU (Topics / Actors) ----------

EPU_PAGE_TEMPLATE = r"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>__TITLE__</title>
<script>__CHARTJS_INLINE__</script>
<style>__NOUI_CSS_INLINE__</style>
<script>__NOUI_JS_INLINE__</script>
<style>__CSS__</style>
</head>
<body>
<div class="controls field-row">
    <div class="field">
        <label for="country">Country</label>
        <select id="country">__COUNTRY_OPTIONS__</select>
    </div>
    <div class="field">
        <label for="actor-measure">Measure</label>
        <select id="actor-measure">
            <option value="intensity">How much the __NOUN__ is discussed</option>
            <option value="absolute" selected>How much uncertainty is about the __NOUN__</option>
            <option value="framing">The __NOUN__&#39;s share of uncertainty</option>
        </select>
    </div>
    <div class="field">
        <label for="actor-scale">Scale</label>
        <select id="actor-scale">
            <option value="index" selected>Index (baseline = 100)</option>
            <option value="z">Z-score</option>
        </select>
    </div>
</div>
<div class="slider-row">
    <label>Date Range:</label>
    <span class="range-label" id="range-label">-</span>
    <div id="slider" class="date-slider"></div>
</div>
<div class="controls">
    <label>Smoothing:</label>
    <div class="toggle-group">
        <label><input type="checkbox" name="ma-toggle" value="1" checked>Raw</label>
        <label><input type="checkbox" name="ma-toggle" value="3" checked>3-Mo MA</label>
        <label><input type="checkbox" name="ma-toggle" value="6">6-Mo MA</label>
        <label><input type="checkbox" name="ma-toggle" value="12">12-Mo MA</label>
    </div>
</div>
<p style="margin: 6px 0 0; font-size: 0.85em; color: #667085;" id="actor-explainer">-</p>
<div class="plot-row">
    <div class="chip-sidebar">
        <div class="chip-header">__ITEM_LABEL__: <span id="selected-count">0</span> selected</div>
        <div class="chip-tools">
            <input type="text" id="item-search" placeholder="__SEARCH_PLACEHOLDER__">
            <button type="button" id="default-btn">Default</button>
            <button type="button" id="clear-btn">Clear</button>
        </div>
        <div class="chip-container" id="item-select">__CHIP_HTML__</div>
    </div>
    <div class="chart-col">
        <div class="chart-wrapper"><canvas id="chart"></canvas></div>
        <div class="style-key">
            <div class="style-key-row"><span class="key-line key-ma"></span>Moving average &mdash; 3, 6 or 12 months</div>
            <div class="style-key-row"><span class="key-line key-raw"></span>Raw monthly</div>
            <div class="style-key-row"><span class="key-line key-current"></span>Current month &mdash; weekly and daily points</div>
        </div>
    </div>
</div>
<script>
__COMMON_JS__

const epuData = __DATA_JSON__;
const items = __ITEMS_JSON__;
const defaultItems = __DEFAULTS_JSON__;
const palette = __PALETTE_JSON__;
const chipLabelMap = __LABEL_MAP_JSON__;
const actorFactors = __FACTORS_JSON__;
const MEASURE_META = {
    intensity: {
        blurb: 'Articles mentioning the __NOUN__, as a share of all articles. No uncertainty condition &mdash; this is how much the __NOUN__ is covered, full stop.'
    },
    absolute: {
        blurb: 'Articles that are both uncertain and about the __NOUN__, as a share of all articles.'
    },
    framing: {
        blurb: 'Articles that are both uncertain and about the __NOUN__, as a share of uncertain articles only. This is a composition measure: it rises when one __NOUN__ takes a larger slice of the same uncertainty.'
    }
};
const SCALE_META = {
    index: 'rescaled so the baseline period averages 100',
    z: 'expressed in units of its own baseline standard deviation'
};
const toggleName = 'ma-toggle';
const state = { slider: null, sliderDates: [], chart: null, onChange: () => {} };

function getSelectedItems() {
    return Array.from(document.querySelectorAll('#item-select input:checked')).map(cb => cb.value);
}
function updateSelectedCount() {
    const el = document.getElementById('selected-count');
    if (el) el.textContent = getSelectedItems().length;
}
function fmtChipLabel(raw) {
    if (chipLabelMap[raw]) return chipLabelMap[raw];
    return raw.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}
function getChipColor(item) { return palette[items.indexOf(item) % palette.length]; }
function applyChipFilters() {
    const q = (document.getElementById('item-search').value || '').toLowerCase().trim();
    document.querySelectorAll('#item-select .chip').forEach(chip => {
        const input = chip.querySelector('input');
        const labelEl = chip.querySelector('.chip-label');
        const raw = input.value;
        const label = fmtChipLabel(raw);
        const color = getChipColor(raw);
        if (color) chip.style.setProperty('--chip-color', color);
        if (labelEl) labelEl.textContent = label;
        const txt = label.toLowerCase();
        const match = !q || txt.indexOf(q) !== -1;
        // A selected pill always stays on screen: its line is on the chart and
        // the pill is the only way to take it off again.
        chip.classList.toggle('is-filtered', !(match || input.checked));
        chip.classList.toggle('is-hit', !!(q && match));
    });
    document.querySelectorAll('#item-select .chip-group').forEach(group => {
        const shown = group.querySelectorAll('.chip:not(.is-filtered)').length;
        group.classList.toggle('is-empty', shown === 0);
        const cnt = group.querySelector('.chip-group-count');
        if (cnt) cnt.textContent = shown;
    });
}
function setSelected(picks) {
    const set = new Set(picks);
    document.querySelectorAll('#item-select input').forEach(cb => { cb.checked = set.has(cb.value); });
    updateSelectedCount();
    applyChipFilters();
}

function render() {
    const country = document.getElementById('country').value;
    const rawData = epuData[country];
    if (!rawData || !rawData.length) return;
    const range = getSliderRange(state);
    let data = rawData;
    if (range.from) data = data.filter(r => r.date >= range.from);
    if (range.to) data = data.filter(r => r.date <= range.to);
    if (!data.length) return;
    const selectedItems = getSelectedItems();
    const measure = document.getElementById('actor-measure').value;
    const scale = document.getElementById('actor-scale').value;
    const factors = actorFactors[country] || {};
    const suffix = '_' + measure;

    // The index is `factor * z` with one factor per column, so dividing
    // recovers the z-score exactly; a column that never left zero has no
    // recoverable factor, and there the two scales agree at zero anyway.
    function valueOf(row, item) {
        const raw = row[item + suffix];
        if (raw == null) return null;
        if (scale === 'index') return raw;
        const f = factors[item + suffix];
        return (f == null || f === 0) ? null : raw / f;
    }

    const monthlyData = data.filter(r => !isDaily(r));
    const dailyData = data
        .filter(r => isDaily(r) && selectedItems.some(i => r[i + suffix] != null))
        .slice()
        .sort((a, b) => a.date.localeCompare(b.date));
    const dailyDisplay = buildDailyDisplay(dailyData);
    const monthlyLabels = monthlyData.map(r => r.date.split('-')[0] + '-' + r.date.split('-')[1]);
    const labels = monthlyLabels.concat(dailyDisplay.labels);
    const datasets = [];
    selectedItems.forEach(item => {
        const color = palette[items.indexOf(item) % palette.length];
        const seriesLabel = fmtChipLabel(item);
        const maSets = buildMADatasets(monthlyData.map(r => valueOf(r, item)), color, seriesLabel, toggleName);
        maSets.forEach(ds => {
            ds._legendGroup = item;
            ds._legendLabel = seriesLabel;
            ds._legendColor = color;
        });
        datasets.push.apply(datasets, maSets);
        if (dailyDisplay.entries.length) {
            const lastMonthly = monthlyData.length > 0 ? valueOf(monthlyData[monthlyData.length - 1], item) : null;
            const dailyValues = dailyDisplay.entries.map(entry => {
                const vals = entry.rows.map(r => valueOf(r, item)).filter(v => v != null && v !== 0);
                if (!vals.length) return null;
                return entry.type === 'weekly' ? computeAverage(vals) : vals[0];
            });
            const dataPoints = [];
            const pointRadius = [];
            const pointHoverRadius = [];
            const pointStyle = [];
            const pointTypes = [];
            if (monthlyData.length > 0) {
                const nBridge = monthlyData.length - 1;
                for (let i = 0; i < nBridge; i++) {
                    dataPoints.push(null);
                    pointRadius.push(0);
                    pointHoverRadius.push(0);
                    pointStyle.push('circle');
                    pointTypes.push(null);
                }
                dataPoints.push(lastMonthly);
                pointRadius.push(0);
                pointHoverRadius.push(0);
                pointStyle.push('circle');
                pointTypes.push(null);
            }
            dailyDisplay.entries.forEach((entry, idx) => {
                const val = dailyValues[idx];
                const isWeekly = entry.type === 'weekly';
                dataPoints.push(val);
                if (val == null) {
                    pointRadius.push(0);
                    pointHoverRadius.push(0);
                } else {
                    pointRadius.push(isWeekly ? 5 : 4);
                    pointHoverRadius.push(isWeekly ? 7 : 6);
                }
                pointStyle.push(isWeekly ? 'rect' : 'circle');
                pointTypes.push(entry.type);
            });
            datasets.push({
                label: fmtChipLabel(item) + ' (current month)',
                data: dataPoints,
                borderColor: hexToRgba(color, 0.8),
                borderDash: [4, 4],
                borderWidth: 2,
                fill: false,
                tension: 0,
                spanGaps: true,
                pointRadius: pointRadius,
                pointHoverRadius: pointHoverRadius,
                pointStyle: pointStyle,
                pointBackgroundColor: color,
                _legendGroup: item,
                _legendLabel: seriesLabel,
                _legendColor: color,
                _variant: 'rawDaily',
                _pointTypes: pointTypes
            });
        }
    });
    const allVals = selectedItems.flatMap(item => {
        const monthlyVals = monthlyData.map(r => valueOf(r, item));
        const dailyVals = dailyDisplay.entries.map(entry => {
            const vals = entry.rows.map(r => valueOf(r, item)).filter(v => v != null && v !== 0);
            if (!vals.length) return null;
            return entry.type === 'weekly' ? computeAverage(vals) : vals[0];
        });
        return monthlyVals.concat(dailyVals);
    }).filter(v => v != null && v !== 0);
    const yMax = (scale === 'index' && allVals.length)
        ? Math.max.apply(null, allVals) * 1.1
        : undefined;
    const ctx = document.getElementById('chart').getContext('2d');
    if (state.chart) state.chart.destroy();
    state.chart = new Chart(ctx, {
        type: 'line',
        data: { labels: labels, datasets: datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false, mode: 'index', intersect: false, external: externalTooltipHandler }
            },
            scales: {
                x: { display: true, title: { display: true, text: 'Date' } },
                y: {
                    display: true,
                    title: { display: true, text: scale === 'index' ? 'Index (baseline = 100)' : 'Z-score' },
                    max: yMax
                }
            }
        }
    });
    state.chart._groupOrder = selectedItems.slice();
    document.getElementById('actor-explainer').innerHTML =
        'Denominator: ' + MEASURE_META[measure].blurb +
        ' Each __NOUN__ is then ' + SCALE_META[scale] + '.';
}

state.onChange = render;
document.getElementById('country').addEventListener('change', function(e) {
    initSlider(state, epuData[e.target.value], 12, 'slider', 'range-label');
    render();
});
document.getElementById('item-select').addEventListener('change', function() {
    updateSelectedCount();
    applyChipFilters();
    render();
});
document.getElementById('item-search').addEventListener('input', applyChipFilters);
document.querySelectorAll('#item-select .chip-group-header').forEach(h => {
    h.addEventListener('click', function() {
        h.parentElement.classList.toggle('is-open');
    });
});
document.getElementById('default-btn').addEventListener('click', function() {
    setSelected(defaultItems);
    render();
});
document.getElementById('clear-btn').addEventListener('click', function() {
    setSelected([]);
    render();
});
document.querySelectorAll('input[name="ma-toggle"]').forEach(r => r.addEventListener('change', render));
['actor-measure', 'actor-scale'].forEach(id => {
    document.getElementById(id).addEventListener('change', render);
});
initSlider(state, epuData[document.getElementById('country').value], 12, 'slider', 'range-label');
updateSelectedCount();
applyChipFilters();
render();
</script>
<div class="method-box">
    <h3>How this index is calculated</h3>
    <ol>
        <li>Every article is checked for two things: whether it uses an
            uncertainty keyword, and whether it mentions the
            __NOUN__. The Measure selector decides which of the two
            conditions apply.</li>
        <li>For each newspaper and month, count the articles that qualify and
            divide by the denominator named above the chart &mdash; all
            articles, or uncertain articles only.</li>
        <li>Divide that share by its own standard deviation over the baseline
            period, so outlets of different size and house style sit on a
            comparable scale.</li>
        <li>Average the newspapers together, weighting each by its share of that
            month's articles.</li>
        <li>On the index scale, rescale so the baseline period averages 100. On
            the z-score scale, leave it in standard deviations.</li>
    </ol>
    <div class="method-foot">
        On the index scale a reading of 130 means the conversation was 30% more
        intense than its baseline norm; 70 means 30% less. The baseline period
        runs from the start of the series to the end of 2020 unless the build was
        given other dates.__METHOD_FOOT_EXTRA__
    </div>
</div>
</body></html>"""


# ---------- Builders ----------


def _country_options(data):
    return "\n".join(
        f'<option value="{c}">{fmt_country(c)}</option>' for c in sorted(data.keys())
    )


def _chip_one(item, defaults):
    return (
        f'<label class="chip"><input type="checkbox" value="{item}"'
        f"{' checked' if item in defaults else ''}>"
        f'<span class="chip-label">{fmt_country(item)}</span></label>'
    )


def _chip_group_html(label, members, defaults, expanded):
    body = "\n".join(_chip_one(i, defaults) for i in members)
    return (
        f'<div class="chip-group{" is-open" if expanded else ""}">'
        f'<button type="button" class="chip-group-header">'
        f'<span class="chip-group-caret">&#9656;</span>'
        f'<span class="chip-group-label">{label}</span>'
        f'<span class="chip-group-count">{len(members)}</span></button>'
        f'<div class="chip-group-body">{body}</div></div>'
    )


def _chip_html(items, defaults, groups=None):
    """Chip markup, grouped when the tracker declares groups and flat otherwise.

    A group lists only the items this region actually has, and anything a
    group misses falls through to a trailing catch-all, so a keyword pack can
    gain a topic without it silently vanishing from the pill list.
    """
    if not groups:
        return "\n".join(_chip_one(i, defaults) for i in items)

    out = []
    grouped = set()
    for g in groups:
        members = [i for i in g["topics"] if i in items]
        if not members:
            continue
        grouped.update(members)
        out.append(
            _chip_group_html(g["label"], members, defaults, g.get("expanded", False))
        )
    rest = [i for i in items if i not in grouped]
    if rest:
        out.append(_chip_group_html("Other", rest, defaults, False))
    return "\n".join(out)


def build_topic_iframe_html(
    topic_data,
    dropdown_options_html=None,
    factors=None,
    focus_groups=None,
    all_groups=None,
    data_expr=None,
    factors_expr=None,
):
    options = (
        dropdown_options_html
        if dropdown_options_html is not None
        else _country_options(topic_data)
    )
    factors = factors or {}
    all_groups = all_groups or []
    # An empty focus set would leave the default view with nothing to draw, so
    # fall back to the full set rather than rendering a blank chart.
    focus_groups = focus_groups or all_groups
    return (
        TOPIC_PAGE_TEMPLATE.replace("__CHARTJS_INLINE__", _vendor("chart.umd.min.js"))
        .replace("__NOUI_CSS_INLINE__", _vendor("nouislider.min.css"))
        .replace("__NOUI_JS_INLINE__", _vendor("nouislider.min.js"))
        .replace("__CSS__", EPU_PAGE_CSS)
        .replace("__COUNTRY_OPTIONS__", options)
        .replace("__N_FOCUS__", str(len(focus_groups)))
        .replace("__N_ALL__", str(len(all_groups)))
        .replace("__COMMON_JS__", EPU_COMMON_JS)
        .replace("__DATA_JSON__", data_expr or json.dumps(topic_data))
        .replace("__FACTORS_JSON__", factors_expr or json.dumps(factors))
        .replace("__FOCUS_JSON__", json.dumps(focus_groups))
        .replace("__ALL_GROUPS_JSON__", json.dumps(all_groups))
        .replace("__PALETTE_JSON__", json.dumps(PALETTE))
    )


TOPICS_LABEL_MAP = {
    "us_china_trade_war": "US-China Trade War",
    "covid_pandemic": "COVID-19 Pandemic",
    "inflation_prices": "Inflation & Prices",
    "climate_environment": "Climate & Environment",
    "corruption_governance": "Corruption & Governance",
    "housing_real_estate": "Housing & Real Estate",
}


ACTORS_LABEL_MAP = {
    "imf": "IMF",
    "us_government": "US Government",
    "china_government": "China Government",
    "multilateral_development_bank": "Multilateral Dev. Bank",
    "credit_rating_agency": "Credit Rating Agency",
    "state_owned_enterprises": "State-Owned Enterprises",
    "international_organizations": "International Organizations",
    "international_investors": "International Investors",
    "courts_judiciary": "Courts & Judiciary",
    "military_security": "Military & Security",
    "labor_unions": "Labor Unions",
    "central_bank": "Central Bank",
    "finance_ministry": "Finance Ministry",
    "world_bank": "World Bank",
    "commercial_banks": "Commercial Banks",
    "parliament": "Parliament",
    "government": "Government",
}


def build_epu_iframe_html(
    data,
    items,
    defaults,
    title,
    item_label,
    search_placeholder,
    label_map,
    noun,
    dropdown_options_html=None,
    factors=None,
    data_expr=None,
    factors_expr=None,
    method_foot_extra="",
    chip_groups=None,
):
    options = (
        dropdown_options_html
        if dropdown_options_html is not None
        else _country_options(data)
    )
    return (
        EPU_PAGE_TEMPLATE.replace("__CHARTJS_INLINE__", _vendor("chart.umd.min.js"))
        .replace("__NOUI_CSS_INLINE__", _vendor("nouislider.min.css"))
        .replace("__NOUI_JS_INLINE__", _vendor("nouislider.min.js"))
        .replace("__CSS__", EPU_PAGE_CSS)
        .replace("__TITLE__", title)
        .replace("__NOUN__", noun)
        .replace("__METHOD_FOOT_EXTRA__", method_foot_extra)
        .replace("__ITEM_LABEL__", item_label)
        .replace("__SEARCH_PLACEHOLDER__", search_placeholder)
        .replace("__CHIP_HTML__", _chip_html(items, defaults, chip_groups))
        .replace("__COUNTRY_OPTIONS__", options)
        .replace("__COMMON_JS__", EPU_COMMON_JS)
        .replace("__DATA_JSON__", data_expr or json.dumps(data))
        .replace("__ITEMS_JSON__", json.dumps(items))
        .replace("__DEFAULTS_JSON__", json.dumps(defaults))
        .replace("__PALETTE_JSON__", json.dumps(PALETTE))
        .replace("__LABEL_MAP_JSON__", json.dumps(label_map))
        .replace("__FACTORS_JSON__", factors_expr or json.dumps(factors or {}))
    )


def _load_addon_html(region: str, tracker: str | None = None) -> str:
    path = _addon_path(region, tracker)
    if not path.exists():
        regions = available_regions(tracker)
        raise FileNotFoundError(
            f"{tracker_label(tracker)} addon HTML not found for region '{region}': "
            f"{path}. Available regions: {regions or '(none)'}"
        )
    return path.read_text(encoding="utf-8")


def _build_hierarchical_options(tree: list) -> str:
    """Build hierarchical <option> HTML from a (single-region) tree subtree."""
    lines = []
    for region_node in sorted(tree, key=lambda n: n["label"]):
        rgn_val = f"region:{region_node['slug']}"
        lines.append(f'<option value="{rgn_val}">{region_node["label"]}</option>')
        for sub_node in sorted(
            region_node.get("children", []), key=lambda n: n["label"]
        ):
            sub_val = f"subregion:{sub_node['slug']}"
            sub_label = f"  {sub_node['label']}"
            lines.append(f'<option value="{sub_val}">{sub_label}</option>')
            for ctry_node in sorted(
                sub_node.get("children", []), key=lambda n: n["label"]
            ):
                ctry_val = ctry_node["slug"]
                ctry_label = f"    {ctry_node['label']}"
                lines.append(f'<option value="{ctry_val}">{ctry_label}</option>')
    return "\n".join(lines)


# ---------- Host page (CSS-only tab switching, no inline <script>) ----------

HOST_TEMPLATE = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>__HOST_TITLE__</title>
<style>
:root {
    --bg: #f6f7fb;
    --panel: #ffffff;
    --text: #1e2432;
    --muted: #667085;
    --accent: #1d77b2;
    --border: #e3e7ef;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 16px;
}
.tab-radio { position: absolute; opacity: 0; pointer-events: none; }
.shell {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    box-shadow: 0 12px 30px rgba(30, 36, 50, 0.08);
    overflow: hidden;
}
.header {
    padding: 16px 18px 10px 18px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
}
.title { font-size: 1.1em; font-weight: 700; }
.subtitle { color: var(--muted); font-size: 0.9em; }
.tabs { display: flex; gap: 8px; flex-wrap: wrap; }
.tabs label {
    border: 1px solid var(--border);
    background: #fff;
    color: var(--text);
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 0.85em;
    cursor: pointer;
    user-select: none;
    transition: all 0.15s;
}
.tabs label:hover { border-color: var(--accent); }
.tab-panel { display: none; }
.panel-body { padding: 14px 18px 18px 18px; }
.tab-frame {
    width: 100%;
    height: 82vh;
    min-height: 720px;
    border: 0;
    border-radius: 8px;
    background: #f5f6f8;
}
/* Active tab panel */
#r0:checked ~ .shell #p0,
#r1:checked ~ .shell #p1,
#r2:checked ~ .shell #p2,
#r3:checked ~ .shell #p3 { display: block; }
/* Active tab button */
#r0:checked ~ .shell .tabs label[for="r0"],
#r1:checked ~ .shell .tabs label[for="r1"],
#r2:checked ~ .shell .tabs label[for="r2"],
#r3:checked ~ .shell .tabs label[for="r3"] {
    background: var(--accent);
    color: #fff;
    border-color: var(--accent);
}
</style>
<script>window.__DASH__ = __SHARED_DATA_JSON__;</script>
</head>
<body>
<input class="tab-radio" type="radio" name="tabs" id="r0" checked>
<input class="tab-radio" type="radio" name="tabs" id="r1">
<input class="tab-radio" type="radio" name="tabs" id="r2">
<input class="tab-radio" type="radio" name="tabs" id="r3">
<div class="shell">
    <div class="header">
        <div>
            <div class="title">__HOST_TITLE__</div>
            <div class="subtitle">__HOST_SUBTITLE__</div>
        </div>
        <div class="tabs" role="tablist">
            <label for="r0">Uncertainty Topics</label>
            <label for="r1">Uncertainty Topics (Ranked)</label>
            <label for="r2">__POLICY_TAB_LABEL__</label>
            <label for="r3">Uncertainty Actors</label>
        </div>
    </div>
    <div class="tab-panel" id="p0"><div class="panel-body"><iframe class="tab-frame" srcdoc='__TOPIC_SERIES_SRCDOC__' title="Uncertainty Topics"></iframe></div></div>
    <div class="tab-panel" id="p1"><div class="panel-body"><iframe class="tab-frame" srcdoc='__TOPIC_SRCDOC__' title="Uncertainty Topics (Ranked)"></iframe></div></div>
    <div class="tab-panel" id="p2"><div class="panel-body"><iframe class="tab-frame" srcdoc='__POLICY_SRCDOC__' title="__POLICY_TAB_LABEL__"></iframe></div></div>
    <div class="tab-panel" id="p3"><div class="panel-body"><iframe class="tab-frame" srcdoc='__ACTORS_EPU_SRCDOC__' title="Uncertainty Actors"></iframe></div></div>
</div>
</body>
</html>"""


def build_host_html(
    policy_html,
    topic_series_html,
    topic_html,
    actors_epu_html,
    host_title,
    host_subtitle,
    policy_tab_label="Fuel Crisis Policy",
    shared_data=None,
):
    """Assemble the four-tab host page.

    The two topic tabs are two readings of one table: a per-topic time series
    and a ranking over time. Their payload is written once into ``window.__DASH__``
    here rather than into each iframe, because a second embedded copy would take
    the page from 39 MB to about 68 MB.

    The per-topic E∩P∩U index used to have its own tab. It is gone by request:
    conditioning a topic index on economic *and* policy language answered a
    question nobody was asking of it, and a food-price series that only counts
    articles which also read as policy commentary undercounts the thing it
    names. The uncertainty attribution tab is now the single topic index.
    """
    return (
        HOST_TEMPLATE.replace("__HOST_TITLE__", host_title)
        .replace("__HOST_SUBTITLE__", host_subtitle)
        .replace("__POLICY_TAB_LABEL__", policy_tab_label)
        .replace("__SHARED_DATA_JSON__", json.dumps(shared_data or {}))
        .replace("__POLICY_SRCDOC__", escape_srcdoc(policy_html))
        .replace("__TOPIC_SERIES_SRCDOC__", escape_srcdoc(topic_series_html))
        .replace("__TOPIC_SRCDOC__", escape_srcdoc(topic_html))
        .replace("__ACTORS_EPU_SRCDOC__", escape_srcdoc(actors_epu_html))
    )


_ACTORS_DEFAULTS = [
    "central_bank",
    "parliament",
    "government",
    "world_bank",
    "international_organizations",
]


def _filter_tree_to_region(tree: list, region: str) -> list:
    """Return the subtree containing only the requested region node."""
    return [n for n in tree if n.get("slug") == region]


def _collect_region_keys(region_subtree: list) -> set[str]:
    """Build the set of unit keys (composite for aggregates, plain for countries)
    that belong to the region subtree."""
    keys: set[str] = set()
    for region_node in region_subtree:
        keys.add(f"region:{region_node['slug']}")
        for sub_node in region_node.get("children", []):
            keys.add(f"subregion:{sub_node['slug']}")
            for ctry_node in sub_node.get("children", []):
                keys.add(ctry_node["slug"])
    return keys


def _resolve_region_label(region_subtree: list, region: str) -> str:
    if region_subtree:
        return region_subtree[0].get("label", region)
    return region


def generate_dashboard_from_json(json_path, region: str, tracker: str | None = None):
    """Generate the special EPU+policy dashboard for ``region``.

    Reads dashboard_data.json, filters units to the region, and writes
    ``outputs/text/dashboards/{tracker}/{region}_policy_dashboard_{suffix}.html``.
    """
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    units = data.get("units", {})
    tree = data.get("tree", [])
    region_subtree = _filter_tree_to_region(tree, region)
    if not region_subtree:
        raise ValueError(
            f"Region '{region}' not found in dashboard data tree. "
            f"Available: {[n.get('slug') for n in tree]}"
        )

    valid_keys = _collect_region_keys(region_subtree)

    topic_data: dict = {}
    actors_data: dict = {}
    actors_set: set = set()

    for key, unit in units.items():
        if key not in valid_keys:
            continue
        attribution = unit.get("attribution") or {}
        if attribution.get("topics"):
            topic_data[key] = attribution["topics"]
        if attribution.get("actors"):
            actors_data[key] = attribution["actors"]

    shown_topics = set(tracker_groups("topics", tracker))
    shown_actors = set(tracker_groups("actors", tracker))
    # The attribution tab deliberately keeps every group, not just the tracker's
    # slice. Reading one topic's index without the others is what makes it look
    # alarming: a food index of 150 means nothing until you can see that
    # governance sits at 300. The tracker slice becomes the default focus
    # instead of a hard filter, so the full universe is one click away.
    topic_factors: dict = {}
    topic_groups: set = set()
    for key, rows in list(topic_data.items()):
        trimmed, factors, groups = _topic_payload(rows)
        topic_data[key] = trimmed
        topic_factors[key] = factors
        topic_groups.update(groups)
    # Actors read the same uncertainty attribution as topics rather than the
    # three-way EPU intersection, so the two tabs answer the same question.
    actor_factors: dict = {}
    for key, rows in list(actors_data.items()):
        trimmed, factors, groups = _topic_payload(rows)
        actors_data[key] = _keep_groups(trimmed, shown_actors)
        actor_factors[key] = factors
        actors_set.update(groups)
    actors_set &= shown_actors

    actors_items = sorted(actors_set)
    actors_defaults = [
        a for a in _ACTORS_DEFAULTS if a in actors_items
    ] or actors_items[:5]

    hier_options = _build_hierarchical_options(region_subtree)

    addon_html = _load_addon_html(region, tracker)
    topic_data_expr = 'window.parent.__DASH__["topics"]'
    topic_factors_expr = 'window.parent.__DASH__["topicFactors"]'
    topic_html = build_topic_iframe_html(
        topic_data,
        dropdown_options_html=hier_options,
        focus_groups=sorted(topic_groups & shown_topics),
        all_groups=sorted(topic_groups),
        data_expr=topic_data_expr,
        factors_expr=topic_factors_expr,
    )
    topic_items = sorted(topic_groups)
    # Default to the head of the tracker's own configured order rather than its
    # whole slice: the food tracker lists eighteen topics and eighteen lines on
    # one chart is not a reading. The rest are one click away in the chip list.
    topic_defaults = [
        g for g in tracker_groups("topics", tracker) if g in topic_groups
    ][:5]
    topic_series_html = build_epu_iframe_html(
        topic_data,
        topic_items,
        topic_defaults or topic_items[:5],
        title="Uncertainty Topics",
        item_label="Topics",
        search_placeholder="Search topics",
        label_map=TOPICS_LABEL_MAP,
        noun="topic",
        dropdown_options_html=hier_options,
        data_expr=topic_data_expr,
        factors_expr=topic_factors_expr,
        method_foot_extra=(
            " The Uncertainty Topics (Ranked) tab reads the same"
            " numbers, ordered against each other month by month."
        ),
        chip_groups=tracker_chip_groups("topics", tracker),
    )
    actors_epu_html = build_epu_iframe_html(
        actors_data,
        actors_items,
        actors_defaults,
        title="Uncertainty Actors",
        item_label="Actors",
        search_placeholder="Search actors",
        label_map=ACTORS_LABEL_MAP,
        noun="actor",
        dropdown_options_html=hier_options,
        factors=actor_factors,
        method_foot_extra=(
            " This tab previously required three conditions at once (economic,"
            " policy and uncertainty); it now uses uncertainty alone,"
            " matching the Uncertainty Topics tabs."
        ),
    )

    region_label = _resolve_region_label(region_subtree, region)
    tracker_cfg = get_tracker(tracker)
    policy_tab_label = tracker_cfg["label"]
    host_title = f"{region_label} — {policy_tab_label} & Uncertainty Dashboard"
    host_subtitle = (
        f"uncertainty topics over time and ranked, {policy_tab_label.lower()}, "
        "and uncertainty actors"
    )

    out = build_host_html(
        addon_html,
        topic_series_html,
        topic_html,
        actors_epu_html,
        host_title=host_title,
        host_subtitle=host_subtitle,
        policy_tab_label=policy_tab_label,
        shared_data={"topics": topic_data, "topicFactors": topic_factors},
    )

    project_root = Path(__file__).resolve().parents[3]
    output_dir = tracker_dir(project_root / "outputs" / "text" / "dashboards", tracker)
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_path = output_dir / dashboard_filename(region, tracker)
    dashboard_path.write_text(out, encoding="utf-8")
    print(f"Created {dashboard_path}")
    return dashboard_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate region-specific Fuel Crisis Policy + EPU dashboard."
    )
    parser.add_argument(
        "--region",
        required=True,
        help="Region slug with an addon HTML in src/text/plotting/addons/",
    )
    parser.add_argument(
        "--json",
        default=None,
        help="Path to dashboard JSON (default: outputs/text/dashboard_data/json/<region>.json)",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[3]
    json_path = (
        Path(args.json)
        if args.json
        else (
            project_root
            / "outputs"
            / "text"
            / "dashboard_data"
            / "json"
            / f"{args.region}.json"
        )
    )
    if not json_path.exists():
        raise SystemExit(
            f"dashboard_data.json not found at {json_path}. Run 'po text publish' first."
        )

    generate_dashboard_from_json(json_path, args.region)
