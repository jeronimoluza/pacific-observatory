"""Generate standalone HTML plots with dropdown menus"""

import os
import json
import pandas as pd
from pathlib import Path

# Countries to exclude from EPU and sentiment visualizations
EXCLUDE_COUNTRIES = [
    # 'american_samoa', 'guam', 'malaysia', 'marshall_islands', 'palau',
    # 'south_korea', 'singapore', 'thailand', 'timor_leste', 'tuvalu', 'vanuatu'
]

# Countries to exclude from prediction visualizations
EXCLUDE_PREDS = [
    "american_samoa",
    "guam",
    "malaysia",
    "marshall_islands",
    "mongolia",
    "singapore",
    "thailand",
    "timor_leste",
    "tuvalu",
]


def fmt_country(c):
    """Format country name from snake_case to Title Case (e.g., 'solomon_islands' -> 'Solomon Islands')"""
    return " ".join(w[0].upper() + w[1:] for w in c.split("_"))


def load_epu_data(country, data_dir):
    """Load all EPU data from consolidated epu.csv"""
    f = data_dir / f"{country}/epu/epu.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f)
    df["date"] = pd.to_datetime(df["date"], format="mixed")
    return df.sort_values("date")


def load_topics_epu_data(country, data_dir):
    """Load topic-specific EPU data from topics_epu.csv"""
    f = data_dir / f"{country}/epu/topics_epu.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f)
    df["date"] = pd.to_datetime(df["date"], format="mixed")
    return df.sort_values("date")


def load_actors_epu_data(country, data_dir):
    """Load actor-specific EPU data from actors_epu.csv"""
    f = data_dir / f"{country}/epu/actors_epu.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f)
    df["date"] = pd.to_datetime(df["date"], format="mixed")
    return df.sort_values("date")


def load_attribution_data(country, data_dir, source_file):
    """Load uncertainty attribution data (topics or actors)"""
    f = data_dir / f"{country}/uncertainty_attribution/{source_file}.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f)
    df["date"] = pd.to_datetime(df["date"], format="mixed")
    return df.sort_values("date")


def load_pred(country, data_dir):
    """Load inflation prediction data for a country"""
    f = data_dir / f"{country}/lasso_preds/predictions.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f)
    df["date"] = pd.to_datetime(df["date"], format="mixed")
    return df.sort_values("date")


def load_oob_pred(country, data_dir):
    """Load out-of-bag inflation prediction data for a country"""
    f = data_dir / f"{country}/lasso_preds_oob/predictions_oob.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f)
    df["date"] = pd.to_datetime(df["date"], format="mixed")
    return df.sort_values("date")


def df_to_json(df):
    """Convert DataFrame to JSON-serializable list of dictionaries"""
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


# ---------------------------------------------------------------------------
# CSS constants shared across templates
# ---------------------------------------------------------------------------

_BASE_CSS = """
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            padding: 12px 20px;
            background: #fff;
            max-width: none;
            width: 100%;
            min-height: 100vh;
        }
        .controls {
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        label {
            font-weight: 600;
            color: #333;
            font-size: 0.95em;
        }
        select {
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 0.9em;
            cursor: pointer;
            background: #fff;
        }
        select:hover { border-color: #667eea; }
        select:focus { outline: 0; border-color: #667eea; }
        .chart-wrapper { position: relative; height: 65vh; min-height: 360px; }
        .plot-row {
            display: flex;
            gap: 14px;
            align-items: stretch;
            margin-top: 8px;
        }
        .plot-row .chart-wrapper { flex: 1; min-width: 0; }
        @media (max-width: 760px) {
            .plot-row { flex-direction: column; }
        }
"""

_TOGGLE_CSS = """
        .toggle-group {
            display: inline-flex;
        }
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
        .toggle-group label:first-child {
            margin-left: 0;
            border-radius: 16px 0 0 16px;
        }
        .toggle-group label:last-child {
            border-radius: 0 16px 16px 0;
        }
        .toggle-group input[type="checkbox"] { display: none; }
        .toggle-group label:has(input:checked) {
            background: #667eea;
            color: #fff;
            border-color: #667eea;
            z-index: 1;
            position: relative;
        }
        .toggle-group label:hover:not(:has(input:checked)) {
            border-color: #667eea;
            background: #f0f4ff;
        }
"""

_CHIP_CSS = """
        .chip-section {
            margin-bottom: 10px;
        }
        .chip-header {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 6px;
            flex-wrap: wrap;
        }
        .chip-tools {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            flex-wrap: wrap;
        }
        .chip-tools input[type="text"] {
            padding: 6px 10px;
            border: 1px solid #ddd;
            border-radius: 16px;
            font-size: 0.82em;
            width: 160px;
        }
        .chip-tools input[type="text"]:hover { border-color: #667eea; }
        .chip-tools input[type="text"]:focus { outline: 0; border-color: #667eea; }
        .chip-tools button {
            padding: 4px 8px;
            border: 1px solid #ddd;
            border-radius: 12px;
            background: #fff;
            font-size: 0.8em;
            cursor: pointer;
        }
        .chip-tools button:hover { border-color: #667eea; background: #f0f4ff; }
        .chip-container {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-bottom: 12px;
            max-height: 120px;
            overflow-y: auto;
            padding: 4px 0;
        }
        .chip-container.is-collapsed {
            max-height: 0;
            padding: 0;
            margin-bottom: 0;
            overflow: hidden;
        }
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
        .legend-panel {
            width: 260px;
            height: 65vh;
            min-height: 360px;
            overflow-y: auto;
            border-left: 1px solid #eee;
            padding-left: 10px;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        @media (max-width: 760px) {
            .legend-panel {
                width: 100%;
                height: auto;
                max-height: 160px;
                border-left: 0;
                border-top: 1px solid #eee;
                padding-left: 0;
                padding-top: 8px;
            }
        }
        .legend-group {
            display: flex;
            flex-direction: column;
            gap: 4px;
            border: 1px solid #eee;
            border-radius: 8px;
            padding: 6px 8px;
            cursor: pointer;
            user-select: none;
        }
        .legend-group:hover { border-color: #667eea; background: #f8faff; }
        .legend-group.is-hidden { opacity: 0.5; }
        .legend-title {
            font-size: 0.85em;
            font-weight: 600;
            color: #333;
        }
        .legend-subitem {
            display: flex;
            align-items: center;
            gap: 6px;
            padding-left: 12px;
            font-size: 0.78em;
            color: #555;
        }
        .legend-line {
            width: 22px;
            border-top: 2px solid #999;
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
        .tooltip-group { margin-bottom: 6px; }
        .tooltip-group:last-child { margin-bottom: 0; }
        .tooltip-group-title { font-weight: 600; }
        .tooltip-table { width: 100%; border-collapse: collapse; }
        .tooltip-table td { padding: 1px 0; }
        .tooltip-group-title-row td { padding-top: 4px; font-weight: 600; }
        .tooltip-indent { padding-left: 12px; }
        .tooltip-val { text-align: right; font-variant-numeric: tabular-nums; }
"""

_SLIDER_CSS = """
        .slider-row {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 10px;
            overflow: visible;
        }
        .slider-row label {
            font-weight: 600;
            color: #333;
            font-size: 0.95em;
            white-space: nowrap;
        }
        #range-label {
            font-size: 0.85em;
            color: #555;
            min-width: 140px;
            text-align: center;
            white-space: nowrap;
        }
        #date-slider {
            flex: 0 0 320px;
            min-width: 200px;
            max-width: 320px;
        }
        @media (max-width: 760px) {
            #date-slider {
                flex: 1;
                max-width: none;
            }
        }
        .noUi-connect {
            background: #667eea !important;
        }
        .noUi-handle {
            border: 2px solid #667eea !important;
            border-radius: 50% !important;
            background: #fff !important;
            box-shadow: 0 1px 4px rgba(102,126,234,0.35) !important;
            cursor: ew-resize;
        }
        .noUi-horizontal .noUi-handle {
            width: 18px;
            height: 18px;
            right: -9px;
            top: -8px;
        }
        .noUi-handle:before,
        .noUi-handle:after {
            display: none !important;
        }
        .noUi-handle:hover {
            background: #667eea !important;
            box-shadow: 0 0 0 3px rgba(102,126,234,0.2) !important;
        }
        .noUi-tooltip {
            font-size: 0.75em;
            padding: 2px 6px;
            background: #667eea;
            color: #fff;
            border: none;
            border-radius: 4px;
        }
"""

_SLIDER_HTML = """
    <div class="slider-row">
        <label>Date Range:</label>
        <span id="range-label">&mdash;</span>
        <div id="date-slider"></div>
    </div>
"""

_SLIDER_JS = """
        let sliderDates = [];
        let slider = null;

        function isDaily(r) { return r && typeof r.ym === 'string' && r.ym.split('-').length === 3; }

        function formatYM(d) {
            const date = new Date(d);
            return date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0');
        }

        function getSliderRange() {
            if (!slider || !sliderDates.length) return { from: '', to: '' };
            const vals = slider.get().map(v => Math.round(v));
            return { from: sliderDates[vals[0]], to: sliderDates[vals[1]] };
        }

        function initSlider(country, defaultMonths) {
            const data = allData[country];
            if (!data || !data.length) return;

            sliderDates = data.map(r => r.date);
            const maxIdx = sliderDates.length - 1;
            const maxDate = new Date(sliderDates[maxIdx]);
            const startDate = new Date(maxDate.getTime());
            startDate.setMonth(startDate.getMonth() - Math.max(0, defaultMonths - 1));
            let startIdx = sliderDates.findIndex(d => new Date(d) >= startDate);
            if (startIdx < 0) startIdx = 0;

            const el = document.getElementById('date-slider');
            if (slider) { slider.destroy(); }

            slider = noUiSlider.create(el, {
                start: [startIdx, maxIdx],
                connect: true,
                step: 1,
                range: { min: 0, max: maxIdx || 1 },
                tooltips: [
                    { to: v => { const r = allData[country][Math.round(v)]; return r && isDaily(r) ? r.date : formatYM(sliderDates[Math.round(v)]); } },
                    { to: v => { const r = allData[country][Math.round(v)]; return r && isDaily(r) ? r.date : formatYM(sliderDates[Math.round(v)]); } }
                ]
            });

            const rangeLabel = document.getElementById('range-label');
            function updateLabel() {
                const vals = slider.get().map(v => Math.round(v));
                rangeLabel.textContent = formatYM(sliderDates[vals[0]]) + '  \u2192  ' + formatYM(sliderDates[vals[1]]);
            }
            updateLabel();

            slider.on('update', function() {
                updateLabel();
            });
            slider.on('change', function() {
                rerender();
            });
        }
"""

_COMPUTE_MA_JS = """
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

        function getActiveWindows() {
            return Array.from(document.querySelectorAll('input[name="ma-toggle"]:checked'))
                   .map(cb => parseInt(cb.value));
        }

        function hexToRgba(hex, alpha) {
            const r = parseInt(hex.slice(1, 3), 16);
            const g = parseInt(hex.slice(3, 5), 16);
            const b = parseInt(hex.slice(5, 7), 16);
            return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
        }

        function buildMADatasets(rawValues, baseColor, seriesLabel) {
            const windows = getActiveWindows().sort((a, b) => a - b);
            const suffixMap = {
                1:  { dash: [5, 5], width: 1.5, suffix: '(Raw)' },
                3:  { dash: [],     width: 2.5, suffix: '(3-Mo MA)' },
                6:  { dash: [],     width: 2,   suffix: '(6-Mo MA)' },
                12: { dash: [],     width: 2,   suffix: '(12-Mo MA)' }
            };
            const variantMap = { 1: 'rawMonthly', 3: 'ma3', 6: 'ma6', 12: 'ma12' };
            // MA opacity hierarchy: lowest MA = solid (1.0), each higher MA more transparent
            const opacitySteps = [1.0, 0.55, 0.35, 0.2];
            const maWindows = windows.filter(w => w !== 1);
            return windows.map(w => {
                const s = suffixMap[w];
                let opacity;
                if (w === 1) {
                    opacity = 0.45; // Raw always fixed: dashed + semi-transparent
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
"""

_TOGGLE_HTML = """
    <div class="controls">
        <label>Smoothing:</label>
        <div class="toggle-group">
            <label><input type="checkbox" name="ma-toggle" value="1" checked>Raw</label>
            <label><input type="checkbox" name="ma-toggle" value="3" checked>3-Mo MA</label>
            <label><input type="checkbox" name="ma-toggle" value="6">6-Mo MA</label>
            <label><input type="checkbox" name="ma-toggle" value="12">12-Mo MA</label>
        </div>
    </div>
"""


# ---------------------------------------------------------------------------
# HTML template generators
# ---------------------------------------------------------------------------


def gen_html(
    title, subtitle, chart_id, all_data, countries, script_content, default_months=24
):
    """Generate standalone HTML page with Chart.js visualization, country dropdown, and date slider"""
    opts = "\n".join(
        f'<option value="{c}">{fmt_country(c)}</option>'
        for c in countries
        if (c in all_data) and (c not in EXCLUDE_COUNTRIES)
    )

    css_styles = _BASE_CSS + _SLIDER_CSS

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/nouislider@15.7.1/dist/nouislider.min.css">
    <script src="https://cdn.jsdelivr.net/npm/nouislider@15.7.1/dist/nouislider.min.js"></script>
    <style>{css_styles}</style>
</head>
<body>
    <div class="controls">
        <label for="country-select">Country:</label>
        <select id="country-select">{opts}</select>
    </div>
    {_SLIDER_HTML}
    <div class="chart-wrapper">
        <canvas id="chart"></canvas>
    </div>
    <script>
        const allData = {json.dumps(all_data)};
        let currentChart = null;

        {_SLIDER_JS}

        {script_content}

        function rerender() {{ renderChart(document.getElementById('country-select').value); }}
        document.getElementById('country-select').addEventListener('change', function(e) {{
            initSlider(e.target.value, {default_months});
            rerender();
        }});
        initSlider(document.getElementById('country-select').value, {default_months});
        rerender();
    </script>
</body>
</html>"""


def gen_html_with_radio(
    title, subtitle, chart_id, all_data, countries, script_content, default_months=24
):
    """Generate standalone HTML page with Chart.js, country dropdown, MA radio toggle, and date slider"""
    opts = "\n".join(
        f'<option value="{c}">{fmt_country(c)}</option>'
        for c in countries
        if (c in all_data) and (c not in EXCLUDE_COUNTRIES)
    )

    css_styles = _BASE_CSS + _TOGGLE_CSS + _SLIDER_CSS

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/nouislider@15.7.1/dist/nouislider.min.css">
    <script src="https://cdn.jsdelivr.net/npm/nouislider@15.7.1/dist/nouislider.min.js"></script>
    <style>{css_styles}</style>
</head>
<body>
    <div class="controls">
        <label for="country-select">Country:</label>
        <select id="country-select">{opts}</select>
    </div>
    {_TOGGLE_HTML}
    {_SLIDER_HTML}
    <div class="chart-wrapper">
        <canvas id="chart"></canvas>
    </div>
    <script>
        const allData = {json.dumps(all_data)};
        let currentChart = null;

        {_COMPUTE_MA_JS}

        {_SLIDER_JS}

        {script_content}

        function rerender() {{ renderChart(document.getElementById('country-select').value); }}
        document.getElementById('country-select').addEventListener('change', function(e) {{
            initSlider(e.target.value, {default_months});
            rerender();
        }});
        document.querySelectorAll('input[name="ma-toggle"]').forEach(r => r.addEventListener('change', rerender));
        initSlider(document.getElementById('country-select').value, {default_months});
        rerender();
    </script>
</body>
</html>"""


def gen_html_multi_select(
    title,
    subtitle,
    chart_id,
    all_data,
    countries,
    items,
    item_label,
    default_checked,
    script_content,
    default_months=24,
):
    """Generate standalone HTML page with Chart.js, country dropdown, multi-select checkboxes, and date slider"""
    opts = "\n".join(
        f'<option value="{c}">{fmt_country(c)}</option>'
        for c in countries
        if (c in all_data) and (c not in EXCLUDE_COUNTRIES)
    )

    checkboxes = "\n".join(
        f'<label class="chip"><input type="checkbox" value="{item}"'
        f"{' checked' if item in default_checked else ''}>"
        f'<span class="chip-label">{fmt_country(item)}</span></label>'
        for item in items
    )

    css_styles = _BASE_CSS + _CHIP_CSS + _SLIDER_CSS

    items_json = json.dumps(items)

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/nouislider@15.7.1/dist/nouislider.min.css">
    <script src="https://cdn.jsdelivr.net/npm/nouislider@15.7.1/dist/nouislider.min.js"></script>
    <style>{css_styles}</style>
</head>
<body>
    <div class="controls">
        <label for="country-select">Country:</label>
        <select id="country-select">{opts}</select>
    </div>
    {_SLIDER_HTML}
    <div>
        <label>{item_label}:</label>
        <div class="chip-container" id="item-select">{checkboxes}</div>
    </div>
    <div class="chart-wrapper">
        <canvas id="chart"></canvas>
    </div>
    <script>
        const allData = {json.dumps(all_data)};
        const allItems = {items_json};
        let currentChart = null;

        {_SLIDER_JS}

        function getSelectedItems() {{
            return Array.from(document.querySelectorAll('#item-select input:checked')).map(cb => cb.value);
        }}

        {script_content}

        function rerender() {{ renderChart(document.getElementById('country-select').value, getSelectedItems()); }}
        document.getElementById('country-select').addEventListener('change', function(e) {{
            initSlider(e.target.value, {default_months});
            rerender();
        }});
        document.getElementById('item-select').addEventListener('change', rerender);
        initSlider(document.getElementById('country-select').value, {default_months});
        rerender();
    </script>
</body>
</html>"""


def gen_html_multi_select_with_radio(
    title,
    subtitle,
    chart_id,
    all_data,
    countries,
    items,
    item_label,
    default_checked,
    script_content,
    default_months=24,
):
    """Generate standalone HTML page with Chart.js, country dropdown, multi-select checkboxes, MA radio toggle, and date slider"""
    opts = "\n".join(
        f'<option value="{c}">{fmt_country(c)}</option>'
        for c in countries
        if (c in all_data) and (c not in EXCLUDE_COUNTRIES)
    )

    checkboxes = "\n".join(
        f'<label class="chip"><input type="checkbox" value="{item}"'
        f"{' checked' if item in default_checked else ''}>"
        f'<span class="chip-label">{fmt_country(item)}</span></label>'
        for item in items
    )

    css_styles = _BASE_CSS + _TOGGLE_CSS + _CHIP_CSS + _SLIDER_CSS

    items_json = json.dumps(items)
    default_items_json = json.dumps(default_checked)

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/nouislider@15.7.1/dist/nouislider.min.css">
    <script src="https://cdn.jsdelivr.net/npm/nouislider@15.7.1/dist/nouislider.min.js"></script>
    <style>{css_styles}</style>
</head>
<body>
    <div class="controls">
        <label for="country-select">Country:</label>
        <select id="country-select">{opts}</select>
    </div>
    {_SLIDER_HTML}
    <div class="controls">
        <label>Smoothing:</label>
        <div class="toggle-group">
            <label><input type="checkbox" name="ma-toggle" value="1" checked>Raw</label>
            <label><input type="checkbox" name="ma-toggle" value="3" checked>3-Mo MA</label>
            <label><input type="checkbox" name="ma-toggle" value="6">6-Mo MA</label>
            <label><input type="checkbox" name="ma-toggle" value="12">12-Mo MA</label>
        </div>
    </div>
    <div class="chip-section" id="chip-section">
        <div class="chip-header">
            <label>{item_label}: <span id="selected-count">0</span> selected</label>
            <div class="chip-tools">
                <input type="text" id="item-search" placeholder="Search {item_label.lower()}" />
                <button type="button" id="chip-default">Default</button>
                <button type="button" id="chip-clear">Clear</button>
            </div>
        </div>
        <div class="chip-container" id="item-select">{checkboxes}</div>
    </div>
    <div class="plot-row">
        <div class="chart-wrapper">
            <canvas id="chart"></canvas>
        </div>
        <div class="legend-panel" id="legend"></div>
    </div>
    <script>
        const allData = {json.dumps(all_data)};
        const allItems = {items_json};
        const defaultItems = {default_items_json};
        let currentChart = null;

        {_COMPUTE_MA_JS}

        {_SLIDER_JS}

        function getSelectedItems() {{
            return Array.from(document.querySelectorAll('#item-select input:checked')).map(cb => cb.value);
        }}

        function updateSelectedCount() {{
            const count = getSelectedItems().length;
            const el = document.getElementById('selected-count');
            if (el) el.textContent = count;
        }}

        function fmtChipLabel(raw) {{
            const map = {{
                gasoline: 'Gas',
                natural_gas: 'Natural Gas',
                imf: 'IMF',
                us_government: 'US Government',
                china_government: 'China Government',
                multilateral_development_bank: 'Multilateral Dev. Bank',
                credit_rating_agency: 'Credit Rating Agency',
                state_owned_enterprises: 'State-Owned Enterprises',
                international_organizations: 'International Organizations',
                international_investors: 'International Investors',
                courts_judiciary: 'Courts & Judiciary',
                military_security: 'Military & Security',
                labor_unions: 'Labor Unions',
                central_bank: 'Central Bank',
                finance_ministry: 'Finance Ministry',
                world_bank: 'World Bank',
                commercial_banks: 'Commercial Banks',
                parliament: 'Parliament',
                government: 'Government'
            }};
            if (map[raw]) return map[raw];
            return raw.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
        }}

        function applyChipFilters() {{
            const q = (document.getElementById('item-search').value || '').toLowerCase().trim();
            document.querySelectorAll('#item-select .chip').forEach(chip => {{
                const input = chip.querySelector('input');
                const labelEl = chip.querySelector('.chip-label');
                const raw = input.value;
                const label = fmtChipLabel(raw);
                if (typeof getChipColor === 'function') {{
                    const color = getChipColor(raw);
                    if (color) chip.style.setProperty('--chip-color', color);
                }}
                if (labelEl) labelEl.textContent = label;
                const txt = label.toLowerCase();
                const isSelected = input.checked;
                const match = !q || txt.indexOf(q) !== -1;
                const visible = match;
                chip.style.display = visible ? 'inline-flex' : 'none';
            }});
        }}

        function setSelected(items) {{
            const set = new Set(items);
            document.querySelectorAll('#item-select input').forEach(cb => {{
                cb.checked = set.has(cb.value);
            }});
            updateSelectedCount();
            applyChipFilters();
        }}

        function updateLegend(chart) {{
            const container = document.getElementById('legend');
            if (!container || !chart) return;
            container.innerHTML = '';
            const groups = {{}};
            const order = chart._groupOrder || [];
            const variantOrder = ['ma3', 'ma6', 'ma12', 'rawMonthly', 'rawDaily'];
            const variantLabels = {{
                ma3: '3-Mo MA',
                ma6: '6-Mo MA',
                ma12: '12-Mo MA',
                rawMonthly: 'Raw (monthly)',
                rawDaily: 'Raw (daily)'
            }};
            chart.data.datasets.forEach((ds, i) => {{
                const key = ds._legendGroup || ds.label || 'Series';
                if (!groups[key]) {{
                    groups[key] = {{
                        label: ds._legendLabel || ds.label || key,
                        datasets: []
                    }};
                }}
                groups[key].datasets.push({{ ds, i }});
            }});
            const orderedKeys = order.length ? order.filter(k => groups[k]) : Object.keys(groups);
            orderedKeys.forEach(key => {{
                const group = groups[key];
                const allVisible = group.datasets.every(d => chart.isDatasetVisible(d.i));
                const groupEl = document.createElement('div');
                groupEl.className = 'legend-group' + (allVisible ? '' : ' is-hidden');
                const title = document.createElement('div');
                title.className = 'legend-title';
                title.textContent = group.label;
                groupEl.appendChild(title);
                const sorted = group.datasets.slice().sort((a, b) => {{
                    const av = variantOrder.indexOf(a.ds._variant || '');
                    const bv = variantOrder.indexOf(b.ds._variant || '');
                    return (av === -1 ? 99 : av) - (bv === -1 ? 99 : bv);
                }});
                sorted.forEach(entry => {{
                    const v = entry.ds._variant;
                    if (!variantLabels[v]) return;
                    const row = document.createElement('div');
                    row.className = 'legend-subitem';
                    const line = document.createElement('span');
                    line.className = 'legend-line';
                    line.style.borderTopColor = entry.ds.borderColor || '#999';
                    line.style.borderTopStyle = entry.ds.borderDash && entry.ds.borderDash.length ? 'dashed' : 'solid';
                    const label = document.createElement('span');
                    label.textContent = variantLabels[v];
                    row.appendChild(line);
                    row.appendChild(label);
                    groupEl.appendChild(row);
                }});
                groupEl.addEventListener('click', () => {{
                    const nextVisible = !allVisible;
                    group.datasets.forEach(d => chart.setDatasetVisibility(d.i, nextVisible));
                    chart.update();
                    updateLegend(chart);
                }});
                container.appendChild(groupEl);
            }});
        }}

        {script_content}

        function rerender() {{ renderChart(document.getElementById('country-select').value, getSelectedItems()); }}
        document.getElementById('country-select').addEventListener('change', function(e) {{
            initSlider(e.target.value, {default_months});
            rerender();
        }});
        document.getElementById('item-select').addEventListener('change', function() {{
            updateSelectedCount();
            applyChipFilters();
            rerender();
        }});
        document.getElementById('item-search').addEventListener('input', applyChipFilters);
        document.getElementById('chip-default').addEventListener('click', function() {{
            setSelected(defaultItems);
            rerender();
        }});
        document.getElementById('chip-clear').addEventListener('click', function() {{
            setSelected([]);
            rerender();
        }});
        document.querySelectorAll('input[name="ma-toggle"]').forEach(r => r.addEventListener('change', rerender));
        initSlider(document.getElementById('country-select').value, {default_months});
        updateSelectedCount();
        applyChipFilters();
        rerender();
    </script>
</body>
</html>"""


def gen_html_bump_chart(
    title,
    subtitle,
    chart_id,
    all_data,
    countries,
    default_top_n,
    script_content,
    default_months=24,
):
    """Generate standalone HTML page with Chart.js bump chart, country dropdown, Top N input, and date range slider"""
    opts = "\n".join(
        f'<option value="{c}">{fmt_country(c)}</option>'
        for c in countries
        if (c in all_data) and (c not in EXCLUDE_COUNTRIES)
    )

    _NUMBER_CSS = """
        input[type="number"] {
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 0.9em;
            width: 70px;
        }
        input[type="number"]:hover { border-color: #667eea; }
        input[type="number"]:focus { outline: 0; border-color: #667eea; }
    """

    css_styles = _BASE_CSS + _NUMBER_CSS + _SLIDER_CSS

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/nouislider@15.7.1/dist/nouislider.min.css">
    <script src="https://cdn.jsdelivr.net/npm/nouislider@15.7.1/dist/nouislider.min.js"></script>
    <style>{css_styles}</style>
</head>
<body>
    <div class="controls">
        <label for="country-select">Country:</label>
        <select id="country-select">{opts}</select>
        <label for="topn-input">Top N:</label>
        <input type="number" id="topn-input" value="{default_top_n}" min="1">
    </div>
    {_SLIDER_HTML}
    <div class="chart-wrapper">
        <canvas id="chart"></canvas>
    </div>
    <script>
        const allData = {json.dumps(all_data)};
        let currentChart = null;

        function getTopN() {{ return parseInt(document.getElementById('topn-input').value) || {default_top_n}; }}

        {_COMPUTE_MA_JS}

        {_SLIDER_JS}

        {script_content}

        function rerender() {{ renderChart(document.getElementById('country-select').value, getTopN()); }}
        document.getElementById('country-select').addEventListener('change', function(e) {{
            initSlider(e.target.value, {default_months});
            rerender();
        }});
        document.getElementById('topn-input').addEventListener('change', rerender);
        initSlider(document.getElementById('country-select').value, {default_months});
        rerender();
    </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Plot generators
# ---------------------------------------------------------------------------


def gen_epu_html(countries, data_dir, out):
    """Generate EPU visualization with smoothing radio toggle"""
    countries = sorted([c for c in countries if c not in EXCLUDE_COUNTRIES])
    all_data = {
        c: df_to_json(load_epu_data(c, data_dir))
        for c in countries
        if load_epu_data(c, data_dir) is not None
    }
    if not all_data:
        return

    script = """
        function formatDate(d) {
            const parts = d.split('-');
            return `${parts[0]}-${parts[1]}`;
        }

        function renderChart(country) {
            const rawData = allData[country];
            if (!rawData || !rawData.length) return;

            const range = getSliderRange();
            let data = rawData;
            if (range.from) data = data.filter(r => r.date >= range.from);
            if (range.to) data = data.filter(r => r.date <= range.to);
            if (!data.length) return;

            const monthlyData = data.filter(r => !isDaily(r));
            const dailyData   = data.filter(r =>  isDaily(r) && r.EPU_index != null);

            const monthlyLabels = monthlyData.map(r => formatDate(r.date));
            const dailyLabels   = dailyData.map(r => r.date);
            const labels = [...monthlyLabels, ...dailyLabels];

            const datasets = buildMADatasets(monthlyData.map(r => r.EPU_index), '#1d77b2', 'EPU Index');

            if (dailyData.length) {
                const lastMonthly = monthlyData.length > 0 ? monthlyData[monthlyData.length - 1].EPU_index : null;
                const nBridge = Math.max(0, monthlyData.length - 1);
                datasets.push({
                    label: 'EPU Index (current month, daily)',
                    data: [...Array(nBridge).fill(null), lastMonthly, ...dailyData.map(r => (r.EPU_index === 0 ? null : r.EPU_index))],
                    borderColor: hexToRgba('#1d77b2', 0.8),
                    borderDash: [4, 4],
                    borderWidth: 2,
                    fill: false,
                    tension: 0,
                    spanGaps: true,
                    pointRadius: [...Array(nBridge).fill(0), 0, ...dailyData.map(r => (r.EPU_index === 0 ? 0 : 4))],
                    pointHoverRadius: [...Array(nBridge).fill(0), 0, ...dailyData.map(r => (r.EPU_index === 0 ? 0 : 6))],
                    pointBackgroundColor: '#1d77b2'
                });
            }

            const allValues = [
                ...monthlyData.map(r => r.EPU_index),
                ...dailyData.map(r => r.EPU_index)
            ].filter(v => v != null && v !== 0);
            const yMax = allValues.length ? Math.max(...allValues) * 1.1 : undefined;

            const ctx = document.getElementById('chart').getContext('2d');
            if (currentChart) currentChart.destroy();

            currentChart = new Chart(ctx, {
                type: 'line',
                data: { labels: labels, datasets: datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                            labels: { usePointStyle: true, padding: 15 }
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                            backgroundColor: 'rgba(0,0,0,0.8)',
                            padding: 12
                        }
                    },
                    scales: {
                        x: { display: true, title: { display: true, text: 'Date' } },
                        y: { display: true, title: { display: true, text: 'EPU Index' }, max: yMax }
                    }
                }
            });
        }
    """

    with open(out, "w") as f:
        f.write(
            gen_html_with_radio(
                "Economic Policy Uncertainty Index",
                "EPU Index with Smoothing Options",
                "epu-chart",
                all_data,
                countries,
                script,
            )
        )
    print(f"Created {out}")


def gen_epu_topics_html(countries, data_dir, out):
    """Generate topic-specific EPU visualization with multi-select checkboxes and smoothing radio"""
    countries = sorted([c for c in countries if c not in EXCLUDE_COUNTRIES])
    all_data = {}
    topics_set = set()
    for c in countries:
        df = load_topics_epu_data(c, data_dir)
        if df is not None:
            all_data[c] = df_to_json(df)
            topics_set.update(
                col.replace("EPU_", "").replace("_index", "")
                for col in df.columns
                if col.startswith("EPU_") and col.endswith("_index")
            )

    topics = sorted(topics_set)
    if not all_data or not topics:
        return

    palette = [
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
    palette_json = json.dumps(palette)
    default_checked = ["inflation_prices", "energy", "diesel", "oil", "natural_gas"]

    script = f"""
        const palette = {palette_json};

        const VARIANT_ORDER = ['ma3', 'ma6', 'ma12', 'rawMonthly', 'rawDaily'];
        const VARIANT_LABELS = {{
            ma3: '3-Mo MA',
            ma6: '6-Mo MA',
            ma12: '12-Mo MA',
            rawMonthly: 'Raw (monthly)',
            rawDaily: 'Raw (daily)'
        }};

        function getChipColor(topic) {{
            const idx = allItems.indexOf(topic);
            return palette[idx % palette.length];
        }}

        function fmtLabel(key) {{
            const map = {{
                gasoline: 'Gas',
                natural_gas: 'Natural Gas'
            }};
            if (map[key]) return map[key];
            return key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
        }}

        function formatDate(d) {{
            const parts = d.split('-');
            return `${{parts[0]}}-${{parts[1]}}`;
        }}

        function formatValue(v) {{
            if (v == null) return '-';
            if (typeof v === 'number' && !isNaN(v)) return v.toFixed(2);
            return v;
        }}

        function getTooltipEl() {{
            let el = document.getElementById('chart-tooltip');
            if (!el) {{
                el = document.createElement('div');
                el.id = 'chart-tooltip';
                el.className = 'chart-tooltip';
                document.body.appendChild(el);
            }}
            return el;
        }}

        function buildTooltipGroups(chart, dataIndex) {{
            const groups = {{}};
            const order = chart._groupOrder || [];
            chart.data.datasets.forEach((ds, i) => {{
                if (!chart.isDatasetVisible(i)) return;
                const key = ds._legendGroup || ds.label || 'Series';
                if (!groups[key]) {{
                    groups[key] = {{ label: ds._legendLabel || ds.label || key, items: [] }};
                }}
                if (!VARIANT_LABELS[ds._variant]) return;
                groups[key].items.push({{ variant: ds._variant, value: ds.data[dataIndex] }});
            }});
            const orderedKeys = order.length ? order.filter(k => groups[k]) : Object.keys(groups);
            return orderedKeys.map(key => {{
                const group = groups[key];
                group.items.sort((a, b) => {{
                    const av = VARIANT_ORDER.indexOf(a.variant);
                    const bv = VARIANT_ORDER.indexOf(b.variant);
                    return (av === -1 ? 99 : av) - (bv === -1 ? 99 : bv);
                }});
                return group;
            }});
        }}

        function externalTooltipHandler(context) {{
            const tooltip = context.tooltip;
            const chart = context.chart;
            const tooltipEl = getTooltipEl();

            if (!tooltip || tooltip.opacity === 0) {{
                tooltipEl.style.opacity = 0;
                return;
            }}

            const dataIndex = tooltip.dataPoints && tooltip.dataPoints.length ? tooltip.dataPoints[0].dataIndex : null;
            if (dataIndex == null) return;
            const label = (tooltip.title && tooltip.title.length) ? tooltip.title[0] : '';
            const groups = buildTooltipGroups(chart, dataIndex);

            let html = `<div class="tooltip-title">${{label}}</div><table class="tooltip-table">`;
            groups.forEach(group => {{
                html += `<tr class="tooltip-group-title-row"><td colspan="2">${{group.label}}</td></tr>`;
                group.items.forEach(item => {{
                    html += `<tr class="tooltip-row"><td class="tooltip-indent">${{VARIANT_LABELS[item.variant]}}</td><td class="tooltip-val">${{formatValue(item.value)}}</td></tr>`;
                }});
            }});
            html += `</table>`;
            tooltipEl.innerHTML = html;

            const rect = chart.canvas.getBoundingClientRect();
            tooltipEl.style.opacity = 1;
            tooltipEl.style.left = rect.left + window.pageXOffset + tooltip.caretX + 'px';
            tooltipEl.style.top = rect.top + window.pageYOffset + tooltip.caretY + 'px';
        }}

        function renderChart(country, selectedItems) {{
            const rawData = allData[country];
            if (!rawData || !rawData.length) return;

            const range = getSliderRange();
            let data = rawData;
            if (range.from) data = data.filter(r => r.date >= range.from);
            if (range.to) data = data.filter(r => r.date <= range.to);
            if (!data.length) return;

            const monthlyData = data.filter(r => !isDaily(r));
            const dailyData   = data.filter(r =>  isDaily(r) && selectedItems.some(t => r[`EPU_${{t}}_index`] != null));

            const monthlyLabels = monthlyData.map(r => formatDate(r.date));
            const dailyLabels   = dailyData.map(r => r.date);
            const labels = [...monthlyLabels, ...dailyLabels];

            const datasets = [];
            selectedItems.forEach((topic, i) => {{
                const colKey = `EPU_${{topic}}_index`;
                const color = palette[allItems.indexOf(topic) % palette.length];
                const seriesLabel = fmtLabel(topic) + ' EPU';
                const maSets = buildMADatasets(monthlyData.map(r => r[colKey]), color, seriesLabel);
                maSets.forEach(ds => {{
                    ds._legendGroup = topic;
                    ds._legendLabel = seriesLabel;
                    ds._legendColor = color;
                }});
                datasets.push(...maSets);
                if (dailyData.length) {{
                    const lastMonthly = monthlyData.length > 0 ? monthlyData[monthlyData.length - 1][colKey] : null;
                    const nBridge = Math.max(0, monthlyData.length - 1);
                    datasets.push({{
                        label: fmtLabel(topic) + ' EPU (current month, daily)',
                        data: [...Array(nBridge).fill(null), lastMonthly, ...dailyData.map(r => (r[colKey] === 0 ? null : r[colKey]))],
                        borderColor: hexToRgba(color, 0.8),
                        borderDash: [4, 4],
                        borderWidth: 2,
                        fill: false,
                        tension: 0,
                        spanGaps: true,
                        pointRadius: [...Array(nBridge).fill(0), 0, ...dailyData.map(r => (r[colKey] === 0 ? 0 : 4))],
                        pointHoverRadius: [...Array(nBridge).fill(0), 0, ...dailyData.map(r => (r[colKey] === 0 ? 0 : 6))],
                        pointBackgroundColor: color,
                        _legendGroup: topic,
                        _legendLabel: seriesLabel,
                        _legendColor: color,
                        _variant: 'rawDaily'
                    }});
                }}
            }});

            const allTopicValues = selectedItems.flatMap(topic => {{
                const colKey = `EPU_${{topic}}_index`;
                return [
                    ...monthlyData.map(r => r[colKey]),
                    ...dailyData.map(r => r[colKey])
                ];
            }}).filter(v => v != null && v !== 0);
            const yMax = allTopicValues.length ? Math.max(...allTopicValues) * 1.1 : undefined;

            const ctx = document.getElementById('chart').getContext('2d');
            if (currentChart) currentChart.destroy();

            currentChart = new Chart(ctx, {{
                type: 'line',
                data: {{ labels: labels, datasets: datasets }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{ enabled: false, mode: 'index', intersect: false, external: externalTooltipHandler }}
                    }},
                    scales: {{
                        x: {{ display: true, title: {{ display: true, text: 'Date' }} }},
                        y: {{ display: true, title: {{ display: true, text: 'EPU Index' }}, max: yMax }}
                    }}
                }}
            }});
            currentChart._groupOrder = selectedItems.slice();
            if (typeof updateLegend === 'function') {{
                updateLegend(currentChart);
            }}
        }}
    """

    with open(out, "w") as f:
        f.write(
            gen_html_multi_select_with_radio(
                "Economic Policy Uncertainty by Topic",
                "Topic-based EPU Analysis",
                "epu-topics-chart",
                all_data,
                countries,
                topics,
                "Topics",
                default_checked,
                script,
                default_months=12,
            )
        )
    print(f"Created {out}")


def gen_epu_actors_html(countries, data_dir, out):
    """Generate actor-specific EPU visualization with multi-select checkboxes"""
    countries = sorted([c for c in countries if c not in EXCLUDE_COUNTRIES])
    all_data = {}
    actors = set()
    for c in countries:
        df = load_actors_epu_data(c, data_dir)
        if df is not None:
            all_data[c] = df_to_json(df)
            for col in df.columns:
                if col.startswith("EPU_") and col.endswith("_index"):
                    actors.add(col[4:-6])
    if not all_data:
        return

    actors = sorted(actors)
    default_checked = [
        "central_bank",
        "parliament",
        "government",
        "world_bank",
        "international_organizations",
    ]
    default_checked = [a for a in default_checked if a in actors]
    if not default_checked:
        default_checked = actors[:5]

    palette = [
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
    palette_json = json.dumps(palette)

    script = f"""
        const palette = {palette_json};

        const VARIANT_ORDER = ['ma3', 'ma6', 'ma12', 'rawMonthly', 'rawDaily'];
        const VARIANT_LABELS = {{
            ma3: '3-Mo MA',
            ma6: '6-Mo MA',
            ma12: '12-Mo MA',
            rawMonthly: 'Raw (monthly)',
            rawDaily: 'Raw (daily)'
        }};

        function getChipColor(actor) {{
            const idx = allItems.indexOf(actor);
            return palette[idx % palette.length];
        }}

        function fmtLabel(key) {{
            const map = {{
                imf: 'IMF',
                us_government: 'US Government',
                china_government: 'China Government',
            }};
            if (map[key]) return map[key];
            return key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
        }}

        function formatDate(d) {{
            const parts = d.split('-');
            return `${{parts[0]}}-${{parts[1]}}`;
        }}

        function formatValue(v) {{
            if (v == null) return '-';
            if (typeof v === 'number' && !isNaN(v)) return v.toFixed(2);
            return v;
        }}

        function getTooltipEl() {{
            let el = document.getElementById('chart-tooltip');
            if (!el) {{
                el = document.createElement('div');
                el.id = 'chart-tooltip';
                el.className = 'chart-tooltip';
                document.body.appendChild(el);
            }}
            return el;
        }}

        function buildTooltipGroups(chart, dataIndex) {{
            const groups = {{}};
            const order = chart._groupOrder || [];
            chart.data.datasets.forEach((ds, i) => {{
                if (!chart.isDatasetVisible(i)) return;
                const key = ds._legendGroup || ds.label || 'Series';
                if (!groups[key]) {{
                    groups[key] = {{ label: ds._legendLabel || ds.label || key, items: [] }};
                }}
                if (!VARIANT_LABELS[ds._variant]) return;
                groups[key].items.push({{ variant: ds._variant, value: ds.data[dataIndex] }});
            }});
            const orderedKeys = order.length ? order.filter(k => groups[k]) : Object.keys(groups);
            return orderedKeys.map(key => {{
                const group = groups[key];
                group.items.sort((a, b) => {{
                    const av = VARIANT_ORDER.indexOf(a.variant);
                    const bv = VARIANT_ORDER.indexOf(b.variant);
                    return (av === -1 ? 99 : av) - (bv === -1 ? 99 : bv);
                }});
                return group;
            }});
        }}

        function externalTooltipHandler(context) {{
            const tooltip = context.tooltip;
            const chart = context.chart;
            const tooltipEl = getTooltipEl();

            if (!tooltip || tooltip.opacity === 0) {{
                tooltipEl.style.opacity = 0;
                return;
            }}

            const dataIndex = tooltip.dataPoints && tooltip.dataPoints.length ? tooltip.dataPoints[0].dataIndex : null;
            if (dataIndex == null) return;
            const label = (tooltip.title && tooltip.title.length) ? tooltip.title[0] : '';
            const groups = buildTooltipGroups(chart, dataIndex);

            let html = `<div class="tooltip-title">${{label}}</div><table class="tooltip-table">`;
            groups.forEach(group => {{
                html += `<tr class="tooltip-group-title-row"><td colspan="2">${{group.label}}</td></tr>`;
                group.items.forEach(item => {{
                    html += `<tr class="tooltip-row"><td class="tooltip-indent">${{VARIANT_LABELS[item.variant]}}</td><td class="tooltip-val">${{formatValue(item.value)}}</td></tr>`;
                }});
            }});
            html += `</table>`;
            tooltipEl.innerHTML = html;

            const rect = chart.canvas.getBoundingClientRect();
            tooltipEl.style.opacity = 1;
            tooltipEl.style.left = rect.left + window.pageXOffset + tooltip.caretX + 'px';
            tooltipEl.style.top = rect.top + window.pageYOffset + tooltip.caretY + 'px';
        }}

        function renderChart(country, selectedItems) {{
            const rawData = allData[country];
            if (!rawData || !rawData.length) return;

            const range = getSliderRange();
            let data = rawData;
            if (range.from) data = data.filter(r => r.date >= range.from);
            if (range.to) data = data.filter(r => r.date <= range.to);
            if (!data.length) return;

            const monthlyData = data.filter(r => !isDaily(r));
            const dailyData   = data.filter(r =>  isDaily(r) && selectedItems.some(a => r[`EPU_${{a}}_index`] != null));

            const monthlyLabels = monthlyData.map(r => formatDate(r.date));
            const dailyLabels   = dailyData.map(r => r.date);
            const labels = [...monthlyLabels, ...dailyLabels];

            const datasets = [];
            selectedItems.forEach((actor, i) => {{
                const colKey = `EPU_${{actor}}_index`;
                const color = palette[allItems.indexOf(actor) % palette.length];
                const seriesLabel = fmtLabel(actor) + ' EPU';
                const maSets = buildMADatasets(monthlyData.map(r => r[colKey]), color, seriesLabel);
                maSets.forEach(ds => {{
                    ds._legendGroup = actor;
                    ds._legendLabel = seriesLabel;
                    ds._legendColor = color;
                }});
                datasets.push(...maSets);
                if (dailyData.length) {{
                    const lastMonthly = monthlyData.length > 0 ? monthlyData[monthlyData.length - 1][colKey] : null;
                    const nBridge = Math.max(0, monthlyData.length - 1);
                    datasets.push({{
                        label: fmtLabel(actor) + ' EPU (current month, daily)',
                        data: [...Array(nBridge).fill(null), lastMonthly, ...dailyData.map(r => (r[colKey] === 0 ? null : r[colKey]))],
                        borderColor: hexToRgba(color, 0.8),
                        borderDash: [4, 4],
                        borderWidth: 2,
                        fill: false,
                        tension: 0,
                        spanGaps: true,
                        pointRadius: [...Array(nBridge).fill(0), 0, ...dailyData.map(r => (r[colKey] === 0 ? 0 : 4))],
                        pointHoverRadius: [...Array(nBridge).fill(0), 0, ...dailyData.map(r => (r[colKey] === 0 ? 0 : 6))],
                        pointBackgroundColor: color,
                        _legendGroup: actor,
                        _legendLabel: seriesLabel,
                        _legendColor: color,
                        _variant: 'rawDaily'
                    }});
                }}
            }});

            const allActorValues = selectedItems.flatMap(actor => {{
                const colKey = `EPU_${{actor}}_index`;
                return [
                    ...monthlyData.map(r => r[colKey]),
                    ...dailyData.map(r => r[colKey])
                ];
            }}).filter(v => v != null && v !== 0);
            const yMax = allActorValues.length ? Math.max(...allActorValues) * 1.1 : undefined;

            const ctx = document.getElementById('chart').getContext('2d');
            if (currentChart) currentChart.destroy();

            currentChart = new Chart(ctx, {{
                type: 'line',
                data: {{ labels: labels, datasets: datasets }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{ enabled: false, mode: 'index', intersect: false, external: externalTooltipHandler }}
                    }},
                    scales: {{
                        x: {{ display: true, title: {{ display: true, text: 'Date' }} }},
                        y: {{ display: true, title: {{ display: true, text: 'EPU Index' }}, max: yMax }}
                    }}
                }}
            }});
            currentChart._groupOrder = selectedItems.slice();
            if (typeof updateLegend === 'function') {{
                updateLegend(currentChart);
            }}
        }}
    """

    with open(out, "w") as f:
        f.write(
            gen_html_multi_select_with_radio(
                "Economic Policy Uncertainty by Actor",
                "Actor-based EPU Analysis",
                "epu-actors-chart",
                all_data,
                countries,
                actors,
                "Actors",
                default_checked,
                script,
                default_months=12,
            )
        )
    print(f"Created {out}")


def gen_news_html(countries, data_dir, out):
    """Generate news article count visualization"""
    countries = sorted([c for c in countries if c not in EXCLUDE_COUNTRIES])
    all_data = {
        c: df_to_json(load_epu_data(c, data_dir))
        for c in countries
        if load_epu_data(c, data_dir) is not None
    }
    if not all_data:
        return

    script = """
        function formatDate(d) {
            const parts = d.split('-');
            return `${parts[0]}-${parts[1]}`;
        }

        function renderChart(country) {
            const rawData = allData[country];
            if (!rawData || !rawData.length) return;

            const range = getSliderRange();
            let data = rawData;
            if (range.from) data = data.filter(r => r.date >= range.from);
            if (range.to) data = data.filter(r => r.date <= range.to);
            if (!data.length) return;

            const monthlyData = data.filter(r => !isDaily(r));
            const dailyData   = data.filter(r =>  isDaily(r) && r.news_total != null);

            const monthlyLabels = monthlyData.map(r => formatDate(r.date));
            const dailyLabels   = dailyData.map(r => r.date);
            const labels = [...monthlyLabels, ...dailyLabels];

            const datasets = [
                {
                    label: 'News Count',
                    data: [...monthlyData.map(r => r.news_total), ...Array(dailyData.length).fill(null)],
                    borderColor: '#2aa8f7',
                    backgroundColor: 'rgba(42, 168, 247, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.1,
                    pointRadius: 0,
                    pointHoverRadius: 5
                }
            ];
            if (dailyData.length) {
                const lastMonthlyNews = monthlyData.length > 0 ? monthlyData[monthlyData.length - 1].news_total : null;
                const nBridgeNews = Math.max(0, monthlyData.length - 1);
                datasets.push({
                    label: 'News Count (current month, daily)',
                    data: [...Array(nBridgeNews).fill(null), lastMonthlyNews, ...dailyData.map(r => r.news_total)],
                    borderColor: 'rgba(42, 168, 247, 0.8)',
                    borderDash: [4, 4],
                    borderWidth: 2,
                    fill: false,
                    tension: 0,
                    pointRadius: [...Array(nBridgeNews).fill(0), 0, ...dailyData.map(() => 4)],
                    pointHoverRadius: [...Array(nBridgeNews).fill(0), 0, ...dailyData.map(() => 6)],
                    pointBackgroundColor: '#2aa8f7'
                });
            }

            const ctx = document.getElementById('chart').getContext('2d');
            if (currentChart) currentChart.destroy();

            currentChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                            labels: { usePointStyle: true, padding: 15 }
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                            backgroundColor: 'rgba(0,0,0,0.8)',
                            padding: 12
                        }
                    },
                    scales: {
                        x: { display: true, title: { display: true, text: 'Date' } },
                        y: { display: true, title: { display: true, text: 'Article Count' } }
                    }
                }
            });
        }
    """

    with open(out, "w") as f:
        f.write(
            gen_html(
                "News Article Count",
                "Number of Articles Scraped Per Month",
                "news-chart",
                all_data,
                countries,
                script,
            )
        )
    print(f"Created {out}")


def gen_breadth_html(countries, data_dir, out):
    """Generate E/P/U breadth index comparison with smoothing radio toggle"""
    countries = sorted([c for c in countries if c not in EXCLUDE_COUNTRIES])
    all_data = {
        c: df_to_json(load_epu_data(c, data_dir))
        for c in countries
        if load_epu_data(c, data_dir) is not None
    }
    if not all_data:
        return

    script = """
        function formatDate(d) {
            const parts = d.split('-');
            return `${parts[0]}-${parts[1]}`;
        }

        function renderChart(country) {
            const rawData = allData[country];
            if (!rawData || !rawData.length) return;

            const range = getSliderRange();
            let data = rawData;
            if (range.from) data = data.filter(r => r.date >= range.from);
            if (range.to) data = data.filter(r => r.date <= range.to);
            if (!data.length) return;

            const monthlyData = data.filter(r => !isDaily(r));
            const dailyData   = data.filter(r =>  isDaily(r) && (r.E_breadth != null || r.P_breadth != null || r.U_breadth != null));

            const monthlyLabels = monthlyData.map(r => formatDate(r.date));
            const dailyLabels   = dailyData.map(r => r.date);
            const labels = [...monthlyLabels, ...dailyLabels];

            const series = [
                { key: 'E_breadth', color: '#1d77b2', label: 'Economic Breadth' },
                { key: 'P_breadth', color: '#d95e10', label: 'Policy Breadth' },
                { key: 'U_breadth', color: '#00a37c', label: 'Uncertainty Breadth' }
            ];
            const datasets = [];
            series.forEach(s => {
                datasets.push(...buildMADatasets(monthlyData.map(r => r[s.key]), s.color, s.label));
                if (dailyData.length) {
                    const lastMonthly = monthlyData.length > 0 ? monthlyData[monthlyData.length - 1][s.key] : null;
                    const nBridge = Math.max(0, monthlyData.length - 1);
                    datasets.push({
                        label: s.label + ' (current month, daily)',
                        data: [...Array(nBridge).fill(null), lastMonthly, ...dailyData.map(r => r[s.key])],
                        borderColor: hexToRgba(s.color, 0.8),
                        borderDash: [4, 4],
                        borderWidth: 2,
                        fill: false,
                        tension: 0,
                        pointRadius: [...Array(nBridge).fill(0), 0, ...dailyData.map(() => 4)],
                        pointHoverRadius: [...Array(nBridge).fill(0), 0, ...dailyData.map(() => 6)],
                        pointBackgroundColor: s.color
                    });
                }
            });

            const ctx = document.getElementById('chart').getContext('2d');
            if (currentChart) currentChart.destroy();

            currentChart = new Chart(ctx, {
                type: 'line',
                data: { labels: labels, datasets: datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                            labels: { usePointStyle: true, padding: 15 }
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                            backgroundColor: 'rgba(0,0,0,0.8)',
                            padding: 12
                        }
                    },
                    scales: {
                        x: { display: true, title: { display: true, text: 'Date' } },
                        y: { display: true, title: { display: true, text: 'Breadth Index' } }
                    }
                }
            });
        }
    """

    with open(out, "w") as f:
        f.write(
            gen_html_with_radio(
                "EPU Breadth Index",
                "Economic, Policy, and Uncertainty Breadth",
                "breadth-chart",
                all_data,
                countries,
                script,
            )
        )
    print(f"Created {out}")


def gen_intensity_html(countries, data_dir, out):
    """Generate E/P/U intensity index comparison with smoothing radio toggle"""
    countries = sorted([c for c in countries if c not in EXCLUDE_COUNTRIES])
    all_data = {
        c: df_to_json(load_epu_data(c, data_dir))
        for c in countries
        if load_epu_data(c, data_dir) is not None
    }
    if not all_data:
        return

    script = """
        function formatDate(d) {
            const parts = d.split('-');
            return `${parts[0]}-${parts[1]}`;
        }

        function renderChart(country) {
            const rawData = allData[country];
            if (!rawData || !rawData.length) return;

            const range = getSliderRange();
            let data = rawData;
            if (range.from) data = data.filter(r => r.date >= range.from);
            if (range.to) data = data.filter(r => r.date <= range.to);
            if (!data.length) return;

            const monthlyData = data.filter(r => !isDaily(r));
            const dailyData   = data.filter(r =>  isDaily(r) && (r.E_intensity != null || r.P_intensity != null || r.U_intensity != null));

            const monthlyLabels = monthlyData.map(r => formatDate(r.date));
            const dailyLabels   = dailyData.map(r => r.date);
            const labels = [...monthlyLabels, ...dailyLabels];

            const series = [
                { key: 'E_intensity', color: '#1d77b2', label: 'Economic Intensity' },
                { key: 'P_intensity', color: '#d95e10', label: 'Policy Intensity' },
                { key: 'U_intensity', color: '#00a37c', label: 'Uncertainty Intensity' }
            ];
            const datasets = [];
            series.forEach(s => {
                datasets.push(...buildMADatasets(monthlyData.map(r => r[s.key]), s.color, s.label));
                if (dailyData.length) {
                    const lastMonthly = monthlyData.length > 0 ? monthlyData[monthlyData.length - 1][s.key] : null;
                    const nBridge = Math.max(0, monthlyData.length - 1);
                    datasets.push({
                        label: s.label + ' (current month, daily)',
                        data: [...Array(nBridge).fill(null), lastMonthly, ...dailyData.map(r => r[s.key])],
                        borderColor: hexToRgba(s.color, 0.8),
                        borderDash: [4, 4],
                        borderWidth: 2,
                        fill: false,
                        tension: 0,
                        pointRadius: [...Array(nBridge).fill(0), 0, ...dailyData.map(() => 4)],
                        pointHoverRadius: [...Array(nBridge).fill(0), 0, ...dailyData.map(() => 6)],
                        pointBackgroundColor: s.color
                    });
                }
            });

            const ctx = document.getElementById('chart').getContext('2d');
            if (currentChart) currentChart.destroy();

            currentChart = new Chart(ctx, {
                type: 'line',
                data: { labels: labels, datasets: datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                            labels: { usePointStyle: true, padding: 15 }
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                            backgroundColor: 'rgba(0,0,0,0.8)',
                            padding: 12
                        }
                    },
                    scales: {
                        x: { display: true, title: { display: true, text: 'Date' } },
                        y: { display: true, title: { display: true, text: 'Intensity Index' } }
                    }
                }
            });
        }
    """

    with open(out, "w") as f:
        f.write(
            gen_html_with_radio(
                "EPU Intensity Index",
                "Economic, Policy, and Uncertainty Intensity",
                "intensity-chart",
                all_data,
                countries,
                script,
            )
        )
    print(f"Created {out}")


def gen_pairwise_html(countries, data_dir, out):
    """Generate EU/PU/EP pairwise interaction index with smoothing radio toggle"""
    countries = sorted([c for c in countries if c not in EXCLUDE_COUNTRIES])
    all_data = {
        c: df_to_json(load_epu_data(c, data_dir))
        for c in countries
        if load_epu_data(c, data_dir) is not None
    }
    if not all_data:
        return

    script = """
        function formatDate(d) {
            const parts = d.split('-');
            return `${parts[0]}-${parts[1]}`;
        }

        function renderChart(country) {
            const rawData = allData[country];
            if (!rawData || !rawData.length) return;

            const range = getSliderRange();
            let data = rawData;
            if (range.from) data = data.filter(r => r.date >= range.from);
            if (range.to) data = data.filter(r => r.date <= range.to);
            if (!data.length) return;

            const monthlyData = data.filter(r => !isDaily(r));
            const dailyData   = data.filter(r =>  isDaily(r) && (r.EU_index != null || r.PU_index != null || r.EP_index != null));

            const monthlyLabels = monthlyData.map(r => formatDate(r.date));
            const dailyLabels   = dailyData.map(r => r.date);
            const labels = [...monthlyLabels, ...dailyLabels];

            const series = [
                { key: 'EU_index', color: '#1d77b2', label: 'Economic-Uncertainty (EU)' },
                { key: 'PU_index', color: '#d95e10', label: 'Policy-Uncertainty (PU)' },
                { key: 'EP_index', color: '#00a37c', label: 'Economic-Policy (EP)' }
            ];
            const datasets = [];
            series.forEach(s => {
                datasets.push(...buildMADatasets(monthlyData.map(r => r[s.key]), s.color, s.label));
                if (dailyData.length) {
                    const lastMonthly = monthlyData.length > 0 ? monthlyData[monthlyData.length - 1][s.key] : null;
                    const nBridge = Math.max(0, monthlyData.length - 1);
                    datasets.push({
                        label: s.label + ' (current month, daily)',
                        data: [...Array(nBridge).fill(null), lastMonthly, ...dailyData.map(r => r[s.key])],
                        borderColor: hexToRgba(s.color, 0.8),
                        borderDash: [4, 4],
                        borderWidth: 2,
                        fill: false,
                        tension: 0,
                        pointRadius: [...Array(nBridge).fill(0), 0, ...dailyData.map(() => 4)],
                        pointHoverRadius: [...Array(nBridge).fill(0), 0, ...dailyData.map(() => 6)],
                        pointBackgroundColor: s.color
                    });
                }
            });

            const ctx = document.getElementById('chart').getContext('2d');
            if (currentChart) currentChart.destroy();

            currentChart = new Chart(ctx, {
                type: 'line',
                data: { labels: labels, datasets: datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                            labels: { usePointStyle: true, padding: 15 }
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                            backgroundColor: 'rgba(0,0,0,0.8)',
                            padding: 12
                        }
                    },
                    scales: {
                        x: { display: true, title: { display: true, text: 'Date' } },
                        y: { display: true, title: { display: true, text: 'Pairwise Index' } }
                    }
                }
            });
        }
    """

    with open(out, "w") as f:
        f.write(
            gen_html_with_radio(
                "Pairwise Interaction Indices",
                "EU, PU, and EP Pairwise Indices",
                "pairwise-chart",
                all_data,
                countries,
                script,
            )
        )
    print(f"Created {out}")


def gen_topic_attribution_html(
    countries, data_dir, out, default_top_n=5, default_months=12
):
    """Generate uncertainty attribution by topic as a bump chart ranked by framing values"""
    countries = sorted([c for c in countries if c not in EXCLUDE_COUNTRIES])
    all_data = {}
    for c in countries:
        df = load_attribution_data(c, data_dir, "topics")
        if df is not None:
            all_data[c] = df_to_json(df)
    if not all_data:
        return

    palette = [
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
    palette_json = json.dumps(palette)

    script = f"""
        const palette = {palette_json};

        const LABEL_MAP = {{
            'Imf': 'IMF',
            'Us Government': 'US Government',
            'Us China Trade War': 'US-China Trade War',
            'Covid Pandemic': 'COVID-19 Pandemic',
            'Inflation Prices': 'Inflation & Prices',
            'Climate Environment': 'Climate & Environment',
            'Corruption Governance': 'Corruption & Governance',
            'Housing Real Estate': 'Housing & Real Estate',
        }};
        function fmtLabel(key) {{
            const raw = key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
            return LABEL_MAP[raw] || raw;
        }}

        function formatDate(d, r) {{
            if (r && isDaily(r)) return r.date;
            const parts = d.split('-');
            return `${{parts[0]}}-${{parts[1]}}`;
        }}

        function renderChart(country, topN) {{
            const rawData = allData[country];
            if (!rawData || !rawData.length) return;

            // Discover all _framing columns
            const framingKeys = Object.keys(rawData[0]).filter(k => k.endsWith('_framing'));
            const items = framingKeys.map(k => k.replace('_framing', ''));

            // Filter by date range using slider, also drop null-placeholder daily rows
            const range = getSliderRange();
            let data = rawData;
            if (range.from) data = data.filter(r => r.date >= range.from);
            if (range.to) data = data.filter(r => r.date <= range.to);
            data = data.filter(r => !isDaily(r) || items.some(item => r[item + '_framing'] != null));
            if (!data.length) return;

            // Clamp topN
            topN = Math.max(1, Math.min(topN, items.length));

            // Compute 3-month MA of framing values for each item over the full series,
            // then slice to the filtered window so MA uses context from before the window.
            const fullDates = rawData.map(r => r.date);
            const filterFrom = range.from || '';
            const filterTo = range.to || '';
            const smoothed = {{}};
            items.forEach(item => {{
                const fullVals = rawData.map(r => r[item + '_framing'] || 0);
                const maVals = computeMA(fullVals, 3);
                // Slice to the filtered window
                const sliced = [];
                rawData.forEach((r, idx) => {{
                    if (filterFrom && r.date < filterFrom) return;
                    if (filterTo && r.date > filterTo) return;
                    sliced.push(maVals[idx]);
                }});
                smoothed[item] = sliced;
            }});

            // Select top-N items by highest mean smoothed framing over the slider window
            const meanSmoothed = items.map(item => {{
                const vals = smoothed[item].filter(v => v != null);
                const mean = vals.length > 0 ? vals.reduce((s, v) => s + v, 0) / vals.length : 0;
                return {{ item: item, mean: mean }};
            }});
            meanSmoothed.sort((a, b) => b.mean - a.mean);
            const visible = meanSmoothed.slice(0, topN).map(v => v.item).sort();

            // Rank only among the visible top-N items per data point
            const ranks = data.map((row, t) => {{
                const vals = visible.map(item => ({{ item: item, value: smoothed[item][t] != null ? smoothed[item][t] : 0 }}));
                vals.sort((a, b) => b.value - a.value);
                const monthRanks = {{}};
                vals.forEach((v, i) => {{ monthRanks[v.item] = i + 1; }});
                return monthRanks;
            }});

            const labels = data.map(r => formatDate(r.date, r));
            const datasets = visible.map((item, i) => {{
                const color = palette[i % palette.length];
                return {{
                    label: fmtLabel(item),
                    data: ranks.map(mr => mr[item]),
                    borderColor: color,
                    borderWidth: 2.5,
                    fill: false,
                    tension: 0,
                    pointRadius: data.map(r => isDaily(r) ? 7 : 5),
                    pointStyle: data.map(r => isDaily(r) ? 'rectRot' : 'circle'),
                    pointBackgroundColor: data.map(r => isDaily(r) ? '#fff' : color),
                    pointBorderColor: color,
                    pointBorderWidth: data.map(r => isDaily(r) ? 2 : 1.5),
                    pointHoverRadius: 8,
                    segment: {{ borderDash: (ctx) => isDaily(data[ctx.p1DataIndex]) ? [4, 4] : [] }},
                    _itemKey: item
                }};
            }});

            const ctx = document.getElementById('chart').getContext('2d');
            if (currentChart) currentChart.destroy();

            currentChart = new Chart(ctx, {{
                type: 'line',
                data: {{ labels: labels, datasets: datasets }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'top',
                            labels: {{ usePointStyle: true, padding: 10, font: {{ size: 11 }} }}
                        }},
                        tooltip: {{
                            mode: 'nearest',
                            intersect: false,
                            backgroundColor: 'rgba(0,0,0,0.8)',
                            padding: 12,
                            callbacks: {{
                                label: function(context) {{
                                    const itemKey = context.dataset._itemKey;
                                    const rank = context.raw;
                                    const smoothedVal = smoothed[itemKey][context.dataIndex];
                                    const daily = isDaily(data[context.dataIndex]);
                                    return context.dataset.label + ': Rank ' + rank + ' (framing: ' + (smoothedVal != null ? smoothedVal.toFixed(3) : 'N/A') + ')' + (daily ? ' [daily]' : '');
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{ display: true, title: {{ display: true, text: 'Date' }} }},
                        y: {{
                            display: true,
                            title: {{ display: true, text: 'Rank (smoothed)' }},
                            reverse: true,
                            ticks: {{ stepSize: 1 }}
                        }}
                    }}
                }}
            }});
        }}
    """

    with open(out, "w") as f:
        f.write(
            gen_html_bump_chart(
                "Uncertainty Attribution by Topic (Ranked)",
                "Topic Ranking by Framing Attribution",
                "topic-attr-chart",
                all_data,
                countries,
                default_top_n,
                script,
                default_months=default_months,
            )
        )
    print(f"Created {out}")


def gen_actor_attribution_html(
    countries, data_dir, out, default_top_n=5, default_months=12
):
    """Generate uncertainty attribution by actor as a bump chart ranked by framing values"""
    countries = sorted([c for c in countries if c not in EXCLUDE_COUNTRIES])
    all_data = {}
    for c in countries:
        df = load_attribution_data(c, data_dir, "actors")
        if df is not None:
            all_data[c] = df_to_json(df)
    if not all_data:
        return

    palette = [
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
    ]
    palette_json = json.dumps(palette)

    script = f"""
        const palette = {palette_json};

        const LABEL_MAP = {{
            'Imf': 'IMF',
            'Us Government': 'US Government',
            'Us China Trade War': 'US-China Trade War',
            'Covid Pandemic': 'COVID-19 Pandemic',
            'Inflation Prices': 'Inflation & Prices',
            'Climate Environment': 'Climate & Environment',
            'Corruption Governance': 'Corruption & Governance',
            'Housing Real Estate': 'Housing & Real Estate',
        }};
        function fmtLabel(key) {{
            const raw = key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
            return LABEL_MAP[raw] || raw;
        }}

        function formatDate(d, r) {{
            if (r && isDaily(r)) return r.date;
            const parts = d.split('-');
            return `${{parts[0]}}-${{parts[1]}}`;
        }}

        function renderChart(country, topN) {{
            const rawData = allData[country];
            if (!rawData || !rawData.length) return;

            // Discover all _framing columns
            const framingKeys = Object.keys(rawData[0]).filter(k => k.endsWith('_framing'));
            const items = framingKeys.map(k => k.replace('_framing', ''));

            // Filter by date range using slider, also drop null-placeholder daily rows
            const range = getSliderRange();
            let data = rawData;
            if (range.from) data = data.filter(r => r.date >= range.from);
            if (range.to) data = data.filter(r => r.date <= range.to);
            data = data.filter(r => !isDaily(r) || items.some(item => r[item + '_framing'] != null));
            if (!data.length) return;

            // Clamp topN
            topN = Math.max(1, Math.min(topN, items.length));

            // Compute 3-month MA of framing values for each item over the full series,
            // then slice to the filtered window so MA uses context from before the window.
            const filterFrom = range.from || '';
            const filterTo = range.to || '';
            const smoothed = {{}};
            items.forEach(item => {{
                const fullVals = rawData.map(r => r[item + '_framing'] || 0);
                const maVals = computeMA(fullVals, 3);
                const sliced = [];
                rawData.forEach((r, idx) => {{
                    if (filterFrom && r.date < filterFrom) return;
                    if (filterTo && r.date > filterTo) return;
                    sliced.push(maVals[idx]);
                }});
                smoothed[item] = sliced;
            }});

            // Select top-N items by highest mean smoothed framing over the slider window
            const meanSmoothed = items.map(item => {{
                const vals = smoothed[item].filter(v => v != null);
                const mean = vals.length > 0 ? vals.reduce((s, v) => s + v, 0) / vals.length : 0;
                return {{ item: item, mean: mean }};
            }});
            meanSmoothed.sort((a, b) => b.mean - a.mean);
            const visible = meanSmoothed.slice(0, topN).map(v => v.item).sort();

            // Rank only among the visible top-N items per data point
            const ranks = data.map((row, t) => {{
                const vals = visible.map(item => ({{ item: item, value: smoothed[item][t] != null ? smoothed[item][t] : 0 }}));
                vals.sort((a, b) => b.value - a.value);
                const monthRanks = {{}};
                vals.forEach((v, i) => {{ monthRanks[v.item] = i + 1; }});
                return monthRanks;
            }});

            const labels = data.map(r => formatDate(r.date, r));
            const datasets = visible.map((item, i) => {{
                const color = palette[i % palette.length];
                return {{
                    label: fmtLabel(item),
                    data: ranks.map(mr => mr[item]),
                    borderColor: color,
                    borderWidth: 2.5,
                    fill: false,
                    tension: 0,
                    pointRadius: data.map(r => isDaily(r) ? 7 : 5),
                    pointStyle: data.map(r => isDaily(r) ? 'rectRot' : 'circle'),
                    pointBackgroundColor: data.map(r => isDaily(r) ? '#fff' : color),
                    pointBorderColor: color,
                    pointBorderWidth: data.map(r => isDaily(r) ? 2 : 1.5),
                    pointHoverRadius: 8,
                    segment: {{ borderDash: (ctx) => isDaily(data[ctx.p1DataIndex]) ? [4, 4] : [] }},
                    _itemKey: item
                }};
            }});

            const ctx = document.getElementById('chart').getContext('2d');
            if (currentChart) currentChart.destroy();

            currentChart = new Chart(ctx, {{
                type: 'line',
                data: {{ labels: labels, datasets: datasets }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'top',
                            labels: {{ usePointStyle: true, padding: 10, font: {{ size: 11 }} }}
                        }},
                        tooltip: {{
                            mode: 'nearest',
                            intersect: false,
                            backgroundColor: 'rgba(0,0,0,0.8)',
                            padding: 12,
                            callbacks: {{
                                label: function(context) {{
                                    const itemKey = context.dataset._itemKey;
                                    const rank = context.raw;
                                    const smoothedVal = smoothed[itemKey][context.dataIndex];
                                    const daily = isDaily(data[context.dataIndex]);
                                    return context.dataset.label + ': Rank ' + rank + ' (framing: ' + (smoothedVal != null ? smoothedVal.toFixed(3) : 'N/A') + ')' + (daily ? ' [daily]' : '');
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{ display: true, title: {{ display: true, text: 'Date' }} }},
                        y: {{
                            display: true,
                            title: {{ display: true, text: 'Rank (smoothed)' }},
                            reverse: true,
                            ticks: {{ stepSize: 1 }}
                        }}
                    }}
                }}
            }});
        }}
    """

    with open(out, "w") as f:
        f.write(
            gen_html_bump_chart(
                "Uncertainty Attribution by Actor (Ranked)",
                "Actor Ranking by Framing Attribution",
                "actor-attr-chart",
                all_data,
                countries,
                default_top_n,
                script,
                default_months=default_months,
            )
        )
    print(f"Created {out}")


def gen_pred_html(countries, data_dir, out):
    """Generate inflation prediction vs actual visualization"""
    countries = sorted([c for c in countries if c not in EXCLUDE_PREDS])
    all_data = {
        c: df_to_json(load_pred(c, data_dir))
        for c in countries
        if load_pred(c, data_dir) is not None
    }
    if not all_data:
        return

    script = """
        function formatDate(d) {
            const date = new Date(d);
            return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
        }

        function renderChart(country) {
            const rawData = allData[country];
            if (!rawData || !rawData.length) return;

            const range = getSliderRange();
            let data = rawData;
            if (range.from) data = data.filter(r => r.date >= range.from);
            if (range.to) data = data.filter(r => r.date <= range.to);
            if (!data.length) return;

            const labels = data.map(r => formatDate(r.date));
            const predictedInflation = data.map(r => r.predicted_inflation);
            const actualInflation = data.map(r => r.actual_inflation);

            const ctx = document.getElementById('chart').getContext('2d');
            if (currentChart) currentChart.destroy();

            currentChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Predicted Inflation',
                            data: predictedInflation,
                            borderColor: '#ff9a00',
                            borderWidth: 3,
                            fill: false,
                            tension: 0.1,
                            pointRadius: 0,
                            pointHoverRadius: 5
                        },
                        {
                            label: 'Actual Inflation',
                            data: actualInflation,
                            borderColor: '#43a5e3',
                            borderWidth: 3,
                            fill: false,
                            tension: 0.1,
                            pointRadius: 0,
                            pointHoverRadius: 5
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                            labels: { usePointStyle: true, padding: 15 }
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                            backgroundColor: 'rgba(0,0,0,0.8)',
                            padding: 12
                        }
                    },
                    scales: {
                        x: { display: true, title: { display: true, text: 'Date' } },
                        y: { display: true, title: { display: true, text: 'Inflation Rate' } }
                    }
                }
            });
        }
    """

    with open(out, "w") as f:
        f.write(
            gen_html(
                "Predicted Inflation",
                "Model Predictions vs Actual Inflation",
                "pred-chart",
                all_data,
                countries,
                script,
            )
        )
    print(f"Created {out}")


def gen_oob_pred_html(countries, data_dir, out):
    """Generate out-of-bag inflation prediction vs actual visualization"""
    countries = sorted([c for c in countries if c not in EXCLUDE_PREDS])
    all_data = {
        c: df_to_json(load_oob_pred(c, data_dir))
        for c in countries
        if load_oob_pred(c, data_dir) is not None
    }
    if not all_data:
        return

    script = """
        function formatDate(d) {
            const date = new Date(d);
            return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
        }

        function renderChart(country) {
            const rawData = allData[country];
            if (!rawData || !rawData.length) return;

            const range = getSliderRange();
            let data = rawData;
            if (range.from) data = data.filter(r => r.date >= range.from);
            if (range.to) data = data.filter(r => r.date <= range.to);
            if (!data.length) return;

            const labels = data.map(r => formatDate(r.date));
            const predictedInflation = data.map(r => r.predicted_inflation);
            const actualInflation = data.map(r => r.actual_inflation);

            const ctx = document.getElementById('chart').getContext('2d');
            if (currentChart) currentChart.destroy();

            currentChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Predicted Inflation (OOB)',
                            data: predictedInflation,
                            borderColor: '#ff6b6b',
                            borderWidth: 3,
                            fill: false,
                            tension: 0.1,
                            pointRadius: 0,
                            pointHoverRadius: 5
                        },
                        {
                            label: 'Actual Inflation',
                            data: actualInflation,
                            borderColor: '#43a5e3',
                            borderWidth: 3,
                            fill: false,
                            tension: 0.1,
                            pointRadius: 0,
                            pointHoverRadius: 5
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                            labels: { usePointStyle: true, padding: 15 }
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                            backgroundColor: 'rgba(0,0,0,0.8)',
                            padding: 12
                        }
                    },
                    scales: {
                        x: { display: true, title: { display: true, text: 'Date' } },
                        y: { display: true, title: { display: true, text: 'Inflation Rate' } }
                    }
                }
            });
        }
    """

    with open(out, "w") as f:
        f.write(
            gen_html(
                "Out-of-Bag Predictions",
                "Model Predictions on Unseen Countries vs Actual Inflation",
                "oob-pred-chart",
                all_data,
                countries,
                script,
            )
        )
    print(f"Created {out}")


if __name__ == "__main__":
    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    DATA_DIR = PROJECT_ROOT / "outputs" / "text"
    OUTPUT_DIR = PROJECT_ROOT / "docs/images/interactive/text"

    countries = [d for d in os.listdir(DATA_DIR) if (DATA_DIR / d).is_dir()]

    gen_epu_html(countries, DATA_DIR, OUTPUT_DIR / "epu_pic.html")
    gen_epu_topics_html(countries, DATA_DIR, OUTPUT_DIR / "epu_topics_pic.html")
    gen_epu_actors_html(countries, DATA_DIR, OUTPUT_DIR / "epu_actors_pic.html")
    gen_news_html(countries, DATA_DIR, OUTPUT_DIR / "news_count_pic.html")
    gen_breadth_html(countries, DATA_DIR, OUTPUT_DIR / "breadth_pic.html")
    gen_intensity_html(countries, DATA_DIR, OUTPUT_DIR / "intensity_pic.html")
    gen_pairwise_html(countries, DATA_DIR, OUTPUT_DIR / "pairwise_pic.html")
    gen_topic_attribution_html(
        countries,
        DATA_DIR,
        OUTPUT_DIR / "topic_attribution_pic.html",
        default_top_n=5,
        default_months=12,
    )
    gen_actor_attribution_html(
        countries,
        DATA_DIR,
        OUTPUT_DIR / "actor_attribution_pic.html",
        default_top_n=5,
        default_months=12,
    )
    gen_pred_html(countries, DATA_DIR, OUTPUT_DIR / "train_predictions_pic.html")
    gen_oob_pred_html(
        countries, DATA_DIR, OUTPUT_DIR / "out_of_bag_predictions_pic.html"
    )
    print("All plots generated successfully!")
