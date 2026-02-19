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
            max-width: 900px;
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
        .chart-wrapper { position: relative; height: 350px; }
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
        .chip-container {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-bottom: 12px;
            max-height: 120px;
            overflow-y: auto;
            padding: 4px 0;
        }
        .chip {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 4px 10px;
            border: 1px solid #ddd;
            border-radius: 16px;
            font-size: 0.8em;
            font-weight: 400;
            cursor: pointer;
            user-select: none;
            transition: all 0.15s;
        }
        .chip:hover { border-color: #667eea; background: #f0f4ff; }
        .chip input[type="checkbox"] { display: none; }
        .chip:has(input:checked) {
            background: #667eea;
            color: #fff;
            border-color: #667eea;
        }
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
            flex: 1;
            min-width: 200px;
        }
        .noUi-connect {
            background: #667eea !important;
        }
        .noUi-handle {
            border-color: #667eea !important;
            box-shadow: none !important;
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
            const startIdx = Math.max(0, maxIdx - (defaultMonths - 1));

            const el = document.getElementById('date-slider');
            if (slider) { slider.destroy(); }

            slider = noUiSlider.create(el, {
                start: [startIdx, maxIdx],
                connect: true,
                step: 1,
                range: { min: 0, max: maxIdx || 1 },
                tooltips: [
                    { to: v => formatYM(sliderDates[Math.round(v)]) },
                    { to: v => formatYM(sliderDates[Math.round(v)]) }
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
                    fill: false, tension: 0.1, pointRadius: 0, pointHoverRadius: 5
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
        f'{" checked" if item in default_checked else ""}>'
        f'{fmt_country(item)}</label>'
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
        f'{" checked" if item in default_checked else ""}>'
        f'{fmt_country(item)}</label>'
        for item in items
    )

    css_styles = _BASE_CSS + _TOGGLE_CSS + _CHIP_CSS + _SLIDER_CSS

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
    {_TOGGLE_HTML}
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

        {_COMPUTE_MA_JS}

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
        document.querySelectorAll('input[name="ma-toggle"]').forEach(r => r.addEventListener('change', rerender));
        initSlider(document.getElementById('country-select').value, {default_months});
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
            const epuRaw = data.map(r => r.EPU_index);
            const datasets = buildMADatasets(epuRaw, '#1d77b2', 'EPU Index');

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
                        y: { display: true, title: { display: true, text: 'EPU Index' } }
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
    topics = None
    for c in countries:
        df = load_topics_epu_data(c, data_dir)
        if df is not None:
            all_data[c] = df_to_json(df)
            if topics is None:
                topics = [
                    col.replace("EPU_", "").replace("_index", "")
                    for col in df.columns
                    if col.startswith("EPU_") and col.endswith("_index")
                ]
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
    default_checked = ["inflation_prices", "trade", "fiscal_policy"]

    script = f"""
        const palette = {palette_json};

        function fmtLabel(key) {{
            return key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
        }}

        function formatDate(d) {{
            const date = new Date(d);
            return `${{date.getFullYear()}}-${{String(date.getMonth() + 1).padStart(2, '0')}}`;
        }}

        function renderChart(country, selectedItems) {{
            const rawData = allData[country];
            if (!rawData || !rawData.length) return;

            const range = getSliderRange();
            let data = rawData;
            if (range.from) data = data.filter(r => r.date >= range.from);
            if (range.to) data = data.filter(r => r.date <= range.to);
            if (!data.length) return;

            const labels = data.map(r => formatDate(r.date));
            const datasets = [];
            selectedItems.forEach((topic, i) => {{
                const colKey = `EPU_${{topic}}_index`;
                const rawValues = data.map(r => r[colKey]);
                const color = palette[allItems.indexOf(topic) % palette.length];
                datasets.push(...buildMADatasets(rawValues, color, fmtLabel(topic) + ' EPU'));
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
                        legend: {{ position: 'top', labels: {{ usePointStyle: true, padding: 15 }} }},
                        tooltip: {{ mode: 'index', intersect: false, backgroundColor: 'rgba(0,0,0,0.8)', padding: 12 }}
                    }},
                    scales: {{
                        x: {{ display: true, title: {{ display: true, text: 'Date' }} }},
                        y: {{ display: true, title: {{ display: true, text: 'EPU Index' }} }}
                    }}
                }}
            }});
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
            const newsCounts = data.map(r => r.news_total);

            const ctx = document.getElementById('chart').getContext('2d');
            if (currentChart) currentChart.destroy();

            currentChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'News Count',
                            data: newsCounts,
                            borderColor: '#2aa8f7',
                            backgroundColor: 'rgba(42, 168, 247, 0.1)',
                            borderWidth: 3,
                            fill: true,
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
            const datasets = [
                ...buildMADatasets(data.map(r => r.E_breadth), '#1d77b2', 'Economic Breadth'),
                ...buildMADatasets(data.map(r => r.P_breadth), '#d95e10', 'Policy Breadth'),
                ...buildMADatasets(data.map(r => r.U_breadth), '#00a37c', 'Uncertainty Breadth')
            ];

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
            const datasets = [
                ...buildMADatasets(data.map(r => r.E_intensity), '#1d77b2', 'Economic Intensity'),
                ...buildMADatasets(data.map(r => r.P_intensity), '#d95e10', 'Policy Intensity'),
                ...buildMADatasets(data.map(r => r.U_intensity), '#00a37c', 'Uncertainty Intensity')
            ];

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
            const datasets = [
                ...buildMADatasets(data.map(r => r.EU_index), '#1d77b2', 'Economic-Uncertainty (EU)'),
                ...buildMADatasets(data.map(r => r.PU_index), '#d95e10', 'Policy-Uncertainty (PU)'),
                ...buildMADatasets(data.map(r => r.EP_index), '#00a37c', 'Economic-Policy (EP)')
            ];

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

        function formatDate(d) {{
            const date = new Date(d);
            return `${{date.getFullYear()}}-${{String(date.getMonth() + 1).padStart(2, '0')}}`;
        }}

        function renderChart(country, topN) {{
            const rawData = allData[country];
            if (!rawData || !rawData.length) return;

            // Filter by date range using slider
            const range = getSliderRange();
            let data = rawData;
            if (range.from) data = data.filter(r => r.date >= range.from);
            if (range.to) data = data.filter(r => r.date <= range.to);
            if (!data.length) return;

            // Discover all _framing columns
            const framingKeys = Object.keys(rawData[0]).filter(k => k.endsWith('_framing'));
            const items = framingKeys.map(k => k.replace('_framing', ''));

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

            // Rank only among the visible top-N items per month
            const ranks = data.map((row, t) => {{
                const vals = visible.map(item => ({{ item: item, value: smoothed[item][t] != null ? smoothed[item][t] : 0 }}));
                vals.sort((a, b) => b.value - a.value);
                const monthRanks = {{}};
                vals.forEach((v, i) => {{ monthRanks[v.item] = i + 1; }});
                return monthRanks;
            }});

            const labels = data.map(r => formatDate(r.date));
            const datasets = visible.map((item, i) => {{
                const color = palette[i % palette.length];
                return {{
                    label: fmtLabel(item),
                    data: ranks.map(mr => mr[item]),
                    borderColor: color,
                    borderWidth: 2.5,
                    fill: false,
                    tension: 0,
                    pointRadius: 5,
                    pointBackgroundColor: color,
                    pointBorderColor: '#fff',
                    pointBorderWidth: 1.5,
                    pointHoverRadius: 7,
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
                                    return context.dataset.label + ': Rank ' + rank + ' (framing: ' + (smoothedVal != null ? smoothedVal.toFixed(3) : 'N/A') + ')';
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

        function formatDate(d) {{
            const date = new Date(d);
            return `${{date.getFullYear()}}-${{String(date.getMonth() + 1).padStart(2, '0')}}`;
        }}

        function renderChart(country, topN) {{
            const rawData = allData[country];
            if (!rawData || !rawData.length) return;

            // Filter by date range using slider
            const range = getSliderRange();
            let data = rawData;
            if (range.from) data = data.filter(r => r.date >= range.from);
            if (range.to) data = data.filter(r => r.date <= range.to);
            if (!data.length) return;

            // Discover all _framing columns
            const framingKeys = Object.keys(rawData[0]).filter(k => k.endsWith('_framing'));
            const items = framingKeys.map(k => k.replace('_framing', ''));

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

            // Rank only among the visible top-N items per month
            const ranks = data.map((row, t) => {{
                const vals = visible.map(item => ({{ item: item, value: smoothed[item][t] != null ? smoothed[item][t] : 0 }}));
                vals.sort((a, b) => b.value - a.value);
                const monthRanks = {{}};
                vals.forEach((v, i) => {{ monthRanks[v.item] = i + 1; }});
                return monthRanks;
            }});

            const labels = data.map(r => formatDate(r.date));
            const datasets = visible.map((item, i) => {{
                const color = palette[i % palette.length];
                return {{
                    label: fmtLabel(item),
                    data: ranks.map(mr => mr[item]),
                    borderColor: color,
                    borderWidth: 2.5,
                    fill: false,
                    tension: 0,
                    pointRadius: 5,
                    pointBackgroundColor: color,
                    pointBorderColor: '#fff',
                    pointBorderWidth: 1.5,
                    pointHoverRadius: 7,
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
                                    return context.dataset.label + ': Rank ' + rank + ' (framing: ' + (smoothedVal != null ? smoothedVal.toFixed(3) : 'N/A') + ')';
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
