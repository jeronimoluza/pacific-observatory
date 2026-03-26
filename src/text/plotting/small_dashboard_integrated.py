"""Generate a standalone small dashboard HTML with integrated charts."""

import json
import os
from pathlib import Path

import pandas as pd


# Countries to exclude from EPU and sentiment visualizations
EXCLUDE_COUNTRIES = [
    # 'american_samoa', 'guam', 'malaysia', 'marshall_islands', 'palau',
    # 'south_korea', 'singapore', 'thailand', 'timor_leste', 'tuvalu', 'vanuatu'
]


def fmt_country(c):
    """Format country name from snake_case to Title Case."""
    return " ".join(w[0].upper() + w[1:] for w in c.split("_"))


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
    """Load uncertainty attribution data (topics or actors)."""
    f = data_dir / f"{country}/uncertainty_attribution/{source_file}.csv"
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


def _build_dashboard_html(
    topic_data,
    topics_data,
    topics_items,
    topics_defaults,
    actors_data,
    actors_items,
    actors_defaults,
):
    topic_countries = sorted(topic_data.keys())
    topics_countries = sorted(topics_data.keys())
    actors_countries = sorted(actors_data.keys())

    topic_options = "\n".join(
        f'<option value="{c}">{fmt_country(c)}</option>' for c in topic_countries
    )
    topics_options = "\n".join(
        f'<option value="{c}">{fmt_country(c)}</option>' for c in topics_countries
    )
    actors_options = "\n".join(
        f'<option value="{c}">{fmt_country(c)}</option>' for c in actors_countries
    )

    topic_palette = [
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

    topics_palette = [
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

    actors_palette = [
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

    topics_checkboxes = "\n".join(
        f'<label class="chip"><input type="checkbox" value="{item}"'
        f"{' checked' if item in topics_defaults else ''}>"
        f'<span class="chip-label">{fmt_country(item)}</span></label>'
        for item in topics_items
    )

    actors_checkboxes = "\n".join(
        f'<label class="chip"><input type="checkbox" value="{item}"'
        f"{' checked' if item in actors_defaults else ''}>"
        f'<span class="chip-label">{fmt_country(item)}</span></label>'
        for item in actors_items
    )

    template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Small Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/nouislider@15.7.1/dist/nouislider.min.css">
    <script src="https://cdn.jsdelivr.net/npm/nouislider@15.7.1/dist/nouislider.min.js"></script>
    <style>
        :root {{
            --bg: #f6f7fb;
            --panel: #ffffff;
            --text: #1e2432;
            --muted: #667085;
            --accent: #1d77b2;
            --border: #e3e7ef;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            padding: 16px;
        }}
        .shell {{
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 12px;
            box-shadow: 0 12px 30px rgba(30, 36, 50, 0.08);
            overflow: hidden;
        }}
        .header {{
            padding: 16px 18px 10px 18px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            flex-wrap: wrap;
        }}
        .title {{ font-size: 1.1em; font-weight: 700; }}
        .subtitle {{ color: var(--muted); font-size: 0.9em; }}
        .tabs {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}
        .tab {{
            border: 1px solid var(--border);
            background: #fff;
            color: var(--text);
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            cursor: pointer;
            transition: all 0.15s;
        }}
        .tab.is-active {{
            background: var(--accent);
            color: #fff;
            border-color: var(--accent);
        }}
        .tab:hover {{ border-color: var(--accent); }}
        .tab-panel {{ display: none; }}
        .tab-panel.is-active {{ display: block; }}
        .panel-body {{ padding: 14px 18px 18px 18px; }}
        .controls {{
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }}
        label {{
            font-weight: 600;
            color: #333;
            font-size: 0.95em;
        }}
        select {{
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 0.9em;
            cursor: pointer;
            background: #fff;
        }}
        select:hover {{ border-color: #667eea; }}
        select:focus {{ outline: 0; border-color: #667eea; }}
        input[type="number"] {{
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 0.9em;
            width: 70px;
        }}
        input[type="number"]:hover {{ border-color: #667eea; }}
        input[type="number"]:focus {{ outline: 0; border-color: #667eea; }}
        .chart-wrapper {{ position: relative; height: 65vh; min-height: 360px; }}
        .plot-row {{
            display: flex;
            gap: 14px;
            align-items: stretch;
            margin-top: 8px;
        }}
        .plot-row .chart-wrapper {{ flex: 1; min-width: 0; }}
        .toggle-group {{ display: inline-flex; }}
        .toggle-group label {{
            padding: 4px 12px;
            border: 1px solid #ddd;
            font-size: 0.82em;
            font-weight: 400;
            cursor: pointer;
            user-select: none;
            transition: all 0.15s;
            margin-left: -1px;
        }}
        .toggle-group label:first-child {{ margin-left: 0; border-radius: 16px 0 0 16px; }}
        .toggle-group label:last-child {{ border-radius: 0 16px 16px 0; }}
        .toggle-group input[type="checkbox"] {{ display: none; }}
        .toggle-group label:has(input:checked) {{
            background: #667eea;
            color: #fff;
            border-color: #667eea;
            z-index: 1;
            position: relative;
        }}
        .toggle-group label:hover:not(:has(input:checked)) {{ border-color: #667eea; background: #f0f4ff; }}
        .chip-section {{ margin-bottom: 10px; }}
        .chip-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 6px;
            flex-wrap: wrap;
        }}
        .chip-tools {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            flex-wrap: wrap;
        }}
        .chip-tools input[type="text"] {{
            padding: 6px 10px;
            border: 1px solid #ddd;
            border-radius: 16px;
            font-size: 0.82em;
            width: 160px;
        }}
        .chip-tools input[type="text"]:hover {{ border-color: #667eea; }}
        .chip-tools input[type="text"]:focus {{ outline: 0; border-color: #667eea; }}
        .chip-tools button {{
            padding: 4px 8px;
            border: 1px solid #ddd;
            border-radius: 12px;
            background: #fff;
            font-size: 0.8em;
            cursor: pointer;
        }}
        .chip-tools button:hover {{ border-color: #667eea; background: #f0f4ff; }}
        .chip-container {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-bottom: 12px;
            max-height: 120px;
            overflow-y: auto;
            padding: 4px 0;
        }}
        .chip {{
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
        }}
        .chip:hover {{ border-color: var(--chip-color, #667eea); background: rgba(102, 126, 234, 0.08); }}
        .chip input[type="checkbox"] {{ display: none; }}
        .chip:has(input:checked) {{
            background: var(--chip-color, #667eea);
            color: #fff;
            border-color: var(--chip-color, #667eea);
        }}
        .legend-panel {{
            width: 260px;
            height: 65vh;
            min-height: 360px;
            overflow-y: auto;
            border-left: 1px solid #eee;
            padding-left: 10px;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}
        .legend-group {{
            display: flex;
            flex-direction: column;
            gap: 4px;
            border: 1px solid #eee;
            border-radius: 8px;
            padding: 6px 8px;
            cursor: pointer;
            user-select: none;
        }}
        .legend-group:hover {{ border-color: #667eea; background: #f8faff; }}
        .legend-group.is-hidden {{ opacity: 0.5; }}
        .legend-title {{ font-size: 0.85em; font-weight: 600; color: #333; }}
        .legend-subitem {{ display: flex; align-items: center; gap: 6px; padding-left: 12px; font-size: 0.78em; color: #555; }}
        .legend-line {{ width: 22px; border-top: 2px solid #999; }}
        .chart-tooltip {{
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
        }}
        .tooltip-title {{ font-weight: 700; margin-bottom: 6px; }}
        .tooltip-table {{ width: 100%; border-collapse: collapse; }}
        .tooltip-table td {{ padding: 1px 0; }}
        .tooltip-group-title-row td {{ padding-top: 4px; font-weight: 600; }}
        .tooltip-indent {{ padding-left: 12px; }}
        .tooltip-val {{ text-align: right; font-variant-numeric: tabular-nums; }}
        .slider-row {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 10px;
            overflow: visible;
        }}
        .slider-row label {{ font-weight: 600; color: #333; font-size: 0.95em; white-space: nowrap; }}
        .range-label {{
            font-size: 0.85em;
            color: #555;
            min-width: 140px;
            text-align: center;
            white-space: nowrap;
        }}
        .date-slider {{ flex: 0 0 320px; min-width: 200px; max-width: 320px; }}
        .noUi-connect {{ background: #667eea !important; }}
        .noUi-handle {{
            border: 2px solid #667eea !important;
            border-radius: 50% !important;
            background: #fff !important;
            box-shadow: 0 1px 4px rgba(102,126,234,0.35) !important;
            cursor: ew-resize;
        }}
        .noUi-horizontal .noUi-handle {{ width: 18px; height: 18px; right: -9px; top: -8px; }}
        .noUi-handle:before, .noUi-handle:after {{ display: none !important; }}
        .noUi-handle:hover {{ background: #667eea !important; box-shadow: 0 0 0 3px rgba(102,126,234,0.2) !important; }}
        .noUi-tooltip {{ font-size: 0.75em; padding: 2px 6px; background: #667eea; color: #fff; border: none; border-radius: 4px; }}
        @media (max-width: 900px) {{
            .plot-row {{ flex-direction: column; }}
            .legend-panel {{
                width: 100%;
                height: auto;
                max-height: 160px;
                border-left: 0;
                border-top: 1px solid #eee;
                padding-left: 0;
                padding-top: 8px;
            }}
        }}
        @media (max-width: 760px) {{
            .date-slider {{ flex: 1; max-width: none; }}
        }}
    </style>
</head>
<body>
    <div class="shell">
        <div class="header">
            <div>
                <div class="title">Small Dashboard</div>
                <div class="subtitle">Uncertainty topics and EPU views</div>
            </div>
            <div class="tabs" role="tablist">
                <button class="tab is-active" type="button" data-tab="tab-1">Uncertainty Topics</button>
                <button class="tab" type="button" data-tab="tab-2">Topics EPU</button>
                <button class="tab" type="button" data-tab="tab-3">Actors EPU</button>
            </div>
        </div>
        <div class="tab-panel is-active" id="tab-1">
            <div class="panel-body">
                <div class="controls">
                    <label for="topic-country">Country:</label>
                    <select id="topic-country">{topic_options}</select>
                    <label for="topic-topn">Top N:</label>
                    <input type="number" id="topic-topn" value="5" min="1">
                </div>
                <div class="slider-row">
                    <label>Date Range:</label>
                    <span class="range-label" id="topic-range">-</span>
                    <div id="topic-slider" class="date-slider"></div>
                </div>
                <div class="chart-wrapper">
                    <canvas id="topic-chart"></canvas>
                </div>
            </div>
        </div>
        <div class="tab-panel" id="tab-2">
            <div class="panel-body">
                <div class="controls">
                    <label for="topics-country">Country:</label>
                    <select id="topics-country">{topics_options}</select>
                </div>
                <div class="slider-row">
                    <label>Date Range:</label>
                    <span class="range-label" id="topics-range">-</span>
                    <div id="topics-slider" class="date-slider"></div>
                </div>
                <div class="controls">
                    <label>Smoothing:</label>
                    <div class="toggle-group">
                        <label><input type="checkbox" name="ma-toggle-topics" value="1" checked>Raw</label>
                        <label><input type="checkbox" name="ma-toggle-topics" value="3" checked>3-Mo MA</label>
                        <label><input type="checkbox" name="ma-toggle-topics" value="6">6-Mo MA</label>
                        <label><input type="checkbox" name="ma-toggle-topics" value="12">12-Mo MA</label>
                    </div>
                </div>
                <div class="chip-section" id="topics-chip-section">
                    <div class="chip-header">
                        <label>Topics: <span id="topics-selected-count">0</span> selected</label>
                        <div class="chip-tools">
                            <input type="text" id="topics-item-search" placeholder="Search topics">
                            <button type="button" id="topics-default">Default</button>
                            <button type="button" id="topics-clear">Clear</button>
                        </div>
                    </div>
                    <div class="chip-container" id="topics-item-select">{topics_checkboxes}</div>
                </div>
                <div class="plot-row">
                    <div class="chart-wrapper">
                        <canvas id="topics-chart"></canvas>
                    </div>
                    <div class="legend-panel" id="topics-legend"></div>
                </div>
            </div>
        </div>
        <div class="tab-panel" id="tab-3">
            <div class="panel-body">
                <div class="controls">
                    <label for="actors-country">Country:</label>
                    <select id="actors-country">{actors_options}</select>
                </div>
                <div class="slider-row">
                    <label>Date Range:</label>
                    <span class="range-label" id="actors-range">-</span>
                    <div id="actors-slider" class="date-slider"></div>
                </div>
                <div class="controls">
                    <label>Smoothing:</label>
                    <div class="toggle-group">
                        <label><input type="checkbox" name="ma-toggle-actors" value="1" checked>Raw</label>
                        <label><input type="checkbox" name="ma-toggle-actors" value="3" checked>3-Mo MA</label>
                        <label><input type="checkbox" name="ma-toggle-actors" value="6">6-Mo MA</label>
                        <label><input type="checkbox" name="ma-toggle-actors" value="12">12-Mo MA</label>
                    </div>
                </div>
                <div class="chip-section" id="actors-chip-section">
                    <div class="chip-header">
                        <label>Actors: <span id="actors-selected-count">0</span> selected</label>
                        <div class="chip-tools">
                            <input type="text" id="actors-item-search" placeholder="Search actors">
                            <button type="button" id="actors-default">Default</button>
                            <button type="button" id="actors-clear">Clear</button>
                        </div>
                    </div>
                    <div class="chip-container" id="actors-item-select">{actors_checkboxes}</div>
                </div>
                <div class="plot-row">
                    <div class="chart-wrapper">
                        <canvas id="actors-chart"></canvas>
                    </div>
                    <div class="legend-panel" id="actors-legend"></div>
                </div>
            </div>
        </div>
    </div>
    <script>
        const topicData = {topic_data_json};
        const topicsData = {topics_data_json};
        const actorsData = {actors_data_json};
        const topicsItems = {topics_items_json};
        const actorsItems = {actors_items_json};
        const topicsDefaultItems = {topics_defaults_json};
        const actorsDefaultItems = {actors_defaults_json};

        const topicPalette = {topic_palette_json};
        const topicsPalette = {topics_palette_json};
        const actorsPalette = {actors_palette_json};

        const VARIANT_ORDER = ['ma3', 'ma6', 'ma12', 'rawMonthly', 'rawDaily'];
        const VARIANT_LABELS = {{
            ma3: '3-Mo MA',
            ma6: '6-Mo MA',
            ma12: '12-Mo MA',
            rawMonthly: 'Raw (monthly)',
            rawDaily: 'Raw (weekly/daily)'
        }};

        function isDaily(r) {{ return r && typeof r.ym === 'string' && r.ym.split('-').length === 3; }}

        function getDayOfMonth(dateStr) {{
            const parts = dateStr.split('-');
            return parseInt(parts[2], 10);
        }}

        function getMonthKey(dateStr) {{
            const parts = dateStr.split('-');
            return parts[0] + '-' + parts[1];
        }}

        function formatYM(d) {{
            const date = new Date(d);
            return date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0');
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

        function computeMA(values, w) {{
            if (w <= 1) return values.slice();
            var result = [];
            for (var i = 0; i < values.length; i++) {{
                if (i < w - 1) {{ result.push(null); continue; }}
                var sum = 0, count = 0;
                for (var j = i - w + 1; j <= i; j++) {{
                    if (values[j] != null) {{ sum += values[j]; count++; }}
                }}
                result.push(count > 0 ? sum / count : null);
            }}
            return result;
        }}

        function computeAverage(values) {{
            if (!values.length) return null;
            const sum = values.reduce((s, v) => s + v, 0);
            return sum / values.length;
        }}

        function buildDailyDisplay(dailyData) {{
            if (!dailyData || !dailyData.length) return {{ labels: [], entries: [] }};
            const monthKey = getMonthKey(dailyData[0].date);
            const withDay = dailyData
                .map(r => ({{ row: r, day: getDayOfMonth(r.date) }}))
                .sort((a, b) => a.day - b.day);
            const latestDay = Math.max.apply(null, withDay.map(d => d.day));
            const entries = [];
            const weeks = [
                {{ key: 'W1', start: 1, end: 7 }},
                {{ key: 'W2', start: 8, end: 14 }},
                {{ key: 'W3', start: 15, end: 21 }},
                {{ key: 'W4', start: 22, end: 29 }}
            ];
            weeks.forEach(week => {{
                const rows = withDay.filter(d => d.day >= week.start && d.day <= week.end);
                if (!rows.length) return;
                if (latestDay >= week.end) {{
                    entries.push({{ type: 'weekly', label: monthKey + '-' + week.key, rows: rows.map(r => r.row) }});
                }} else {{
                    rows.forEach(item => entries.push({{ type: 'daily', label: item.row.date, rows: [item.row] }}));
                }}
            }});
            withDay.filter(d => d.day >= 30).forEach(item => {{
                entries.push({{ type: 'daily', label: item.row.date, rows: [item.row] }});
            }});
            return {{ labels: entries.map(e => e.label), entries: entries }};
        }}

        function hexToRgba(hex, alpha) {{
            const r = parseInt(hex.slice(1, 3), 16);
            const g = parseInt(hex.slice(3, 5), 16);
            const b = parseInt(hex.slice(5, 7), 16);
            return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
        }}

        function getActiveWindows(toggleName) {{
            return Array.from(document.querySelectorAll('input[name="' + toggleName + '"]:checked'))
                   .map(cb => parseInt(cb.value));
        }}

        function buildMADatasets(rawValues, baseColor, seriesLabel, toggleName) {{
            const windows = getActiveWindows(toggleName).sort((a, b) => a - b);
            const suffixMap = {{
                1:  {{ dash: [5, 5], width: 1.5, suffix: '(Raw)' }},
                3:  {{ dash: [],     width: 2.5, suffix: '(3-Mo MA)' }},
                6:  {{ dash: [],     width: 2,   suffix: '(6-Mo MA)' }},
                12: {{ dash: [],     width: 2,   suffix: '(12-Mo MA)' }}
            }};
            const variantMap = {{ 1: 'rawMonthly', 3: 'ma3', 6: 'ma6', 12: 'ma12' }};
            const opacitySteps = [1.0, 0.55, 0.35, 0.2];
            const maWindows = windows.filter(w => w !== 1);
            return windows.map(w => {{
                const s = suffixMap[w];
                let opacity;
                if (w === 1) {{
                    opacity = 0.45;
                }} else {{
                    const maIdx = maWindows.indexOf(w);
                    opacity = opacitySteps[maIdx] !== undefined ? opacitySteps[maIdx] : 0.2;
                }}
                return {{
                    label: seriesLabel + ' ' + s.suffix,
                    data: computeMA(rawValues, w),
                    borderColor: hexToRgba(baseColor, opacity),
                    borderDash: s.dash,
                    borderWidth: s.width,
                    fill: false, tension: 0.1, pointRadius: 0, pointHoverRadius: 5,
                    _variant: variantMap[w] || 'ma'
                }};
            }});
        }}

        function initSlider(state, data, defaultMonths, sliderId, rangeLabelId) {{
            if (!data || !data.length) return;
            state.sliderDates = data.map(r => r.date);
            const maxIdx = state.sliderDates.length - 1;
            const maxDate = new Date(state.sliderDates[maxIdx]);
            const startDate = new Date(maxDate.getTime());
            startDate.setMonth(startDate.getMonth() - Math.max(0, defaultMonths - 1));
            let startIdx = state.sliderDates.findIndex(d => new Date(d) >= startDate);
            if (startIdx < 0) startIdx = 0;
            const el = document.getElementById(sliderId);
            if (state.slider) {{ state.slider.destroy(); }}
            state.slider = noUiSlider.create(el, {{
                start: [startIdx, maxIdx],
                connect: true,
                step: 1,
                range: {{ min: 0, max: maxIdx || 1 }},
                tooltips: [
                    {{ to: v => {{ const r = data[Math.round(v)]; return r && isDaily(r) ? r.date : formatYM(state.sliderDates[Math.round(v)]); }} }},
                    {{ to: v => {{ const r = data[Math.round(v)]; return r && isDaily(r) ? r.date : formatYM(state.sliderDates[Math.round(v)]); }} }}
                ]
            }});
            const rangeLabel = document.getElementById(rangeLabelId);
            function updateLabel() {{
                const vals = state.slider.get().map(v => Math.round(v));
                rangeLabel.textContent = formatYM(state.sliderDates[vals[0]]) + ' -> ' + formatYM(state.sliderDates[vals[1]]);
            }}
            updateLabel();
            state.slider.on('update', function() {{ updateLabel(); }});
            state.slider.on('change', function() {{ state.onChange(); }});
        }}

        function getSliderRange(state) {{
            if (!state.slider || !state.sliderDates.length) return {{ from: '', to: '' }};
            const vals = state.slider.get().map(v => Math.round(v));
            return {{ from: state.sliderDates[vals[0]], to: state.sliderDates[vals[1]] }};
        }}

        function updateLegend(chart, legendId) {{
            const container = document.getElementById(legendId);
            if (!container || !chart) return;
            container.innerHTML = '';
            const groups = {{}};
            const order = chart._groupOrder || [];
            chart.data.datasets.forEach((ds, i) => {{
                const key = ds._legendGroup || ds.label || 'Series';
                if (!groups[key]) {{
                    groups[key] = {{ label: ds._legendLabel || ds.label || key, datasets: [] }};
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
                    const av = VARIANT_ORDER.indexOf(a.ds._variant || '');
                    const bv = VARIANT_ORDER.indexOf(b.ds._variant || '');
                    return (av === -1 ? 99 : av) - (bv === -1 ? 99 : bv);
                }});
                sorted.forEach(entry => {{
                    const v = entry.ds._variant;
                    if (!VARIANT_LABELS[v]) return;
                    const row = document.createElement('div');
                    row.className = 'legend-subitem';
                    const line = document.createElement('span');
                    line.className = 'legend-line';
                    line.style.borderTopColor = entry.ds.borderColor || '#999';
                    line.style.borderTopStyle = entry.ds.borderDash && entry.ds.borderDash.length ? 'dashed' : 'solid';
                    const label = document.createElement('span');
                    label.textContent = VARIANT_LABELS[v];
                    row.appendChild(line);
                    row.appendChild(label);
                    groupEl.appendChild(row);
                }});
                groupEl.addEventListener('click', () => {{
                    const nextVisible = !allVisible;
                    group.datasets.forEach(d => chart.setDatasetVisibility(d.i, nextVisible));
                    chart.update();
                    updateLegend(chart, legendId);
                }});
                container.appendChild(groupEl);
            }});
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
                const pointType = ds._pointTypes ? ds._pointTypes[dataIndex] : null;
                groups[key].items.push({{ variant: ds._variant, value: ds.data[dataIndex], pointType: pointType }});
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
            let html = '<div class="tooltip-title">' + label + '</div><table class="tooltip-table">';
            groups.forEach(group => {{
                html += '<tr class="tooltip-group-title-row"><td colspan="2">' + group.label + '</td></tr>';
                group.items.forEach(item => {{
                    const val = (item.value == null) ? '-' : (typeof item.value === 'number' ? item.value.toFixed(2) : item.value);
                    let variantLabel = VARIANT_LABELS[item.variant] || item.variant;
                    if (item.variant === 'rawDaily' && item.pointType) {{
                        variantLabel = item.pointType === 'weekly' ? 'Raw (weekly)' : 'Raw (daily)';
                    }}
                    html += '<tr class="tooltip-row"><td class="tooltip-indent">' + variantLabel + '</td><td class="tooltip-val">' + val + '</td></tr>';
                }});
            }});
            html += '</table>';
            tooltipEl.innerHTML = html;
            const rect = chart.canvas.getBoundingClientRect();
            tooltipEl.style.opacity = 1;
            tooltipEl.style.left = rect.left + window.pageXOffset + tooltip.caretX + 'px';
            tooltipEl.style.top = rect.top + window.pageYOffset + tooltip.caretY + 'px';
        }}

        const topicState = {{ slider: null, sliderDates: [], chart: null, onChange: () => {{}} }};
        const topicsState = {{ slider: null, sliderDates: [], chart: null, onChange: () => {{}} }};
        const actorsState = {{ slider: null, sliderDates: [], chart: null, onChange: () => {{}} }};

        function initTopicTab() {{
            const select = document.getElementById('topic-country');
            const topnInput = document.getElementById('topic-topn');
            function render() {{
                const country = select.value;
                const rawData = topicData[country];
                if (!rawData || !rawData.length) return;
                const range = getSliderRange(topicState);
                let data = rawData;
                if (range.from) data = data.filter(r => r.date >= range.from);
                if (range.to) data = data.filter(r => r.date <= range.to);
                const framingKeys = Object.keys(rawData[0]).filter(k => k.endsWith('_framing'));
                const items = framingKeys.map(k => k.replace('_framing', ''));
                data = data.filter(r => !isDaily(r) || items.some(item => r[item + '_framing'] != null));
                if (!data.length) return;
                let topN = parseInt(topnInput.value, 10) || 5;
                topN = Math.max(1, Math.min(topN, items.length));

                const filterFrom = range.from || '';
                const filterTo = range.to || '';
                const monthlyData = data.filter(r => !isDaily(r));
                const dailyData = data.filter(r => isDaily(r));
                const dailyDisplay = buildDailyDisplay(dailyData);
                const displayEntries = monthlyData.map(r => ({{
                    type: 'monthly',
                    label: r.date.split('-')[0] + '-' + r.date.split('-')[1],
                    rows: [r]
                }})).concat(dailyDisplay.entries);
                const dateToIndex = new Map(rawData.map((r, idx) => [r.date, idx]));
                const smoothedFull = {{}};
                items.forEach(item => {{
                    const fullVals = rawData.map(r => r[item + '_framing'] || 0);
                    smoothedFull[item] = computeMA(fullVals, 3);
                }});
                const smoothed = {{}};
                items.forEach(item => {{
                    smoothed[item] = displayEntries.map(entry => {{
                        const vals = entry.rows
                            .map(r => {{
                                const idx = dateToIndex.get(r.date);
                                return idx == null ? null : smoothedFull[item][idx];
                            }})
                            .filter(v => v != null);
                        if (!vals.length) return null;
                        return vals.reduce((s, v) => s + v, 0) / vals.length;
                    }});
                }});

                const meanSmoothed = items.map(item => {{
                    const vals = smoothed[item].filter(v => v != null);
                    const mean = vals.length > 0 ? vals.reduce((s, v) => s + v, 0) / vals.length : 0;
                    return {{ item: item, mean: mean }};
                }});
                meanSmoothed.sort((a, b) => b.mean - a.mean);
                const visible = meanSmoothed.slice(0, topN).map(v => v.item).sort();

                const ranks = displayEntries.map((entry, t) => {{
                    const vals = visible.map(item => ({{ item: item, value: smoothed[item][t] != null ? smoothed[item][t] : 0 }}));
                    vals.sort((a, b) => b.value - a.value);
                    const monthRanks = {{}};
                    vals.forEach((v, i) => {{ monthRanks[v.item] = i + 1; }});
                    return monthRanks;
                }});

                const labels = displayEntries.map(entry => entry.label);

                const labelMap = {{
                    'Imf': 'IMF',
                    'Us Government': 'US Government',
                    'Us China Trade War': 'US-China Trade War',
                    'Covid Pandemic': 'COVID-19 Pandemic',
                    'Inflation Prices': 'Inflation & Prices',
                    'Climate Environment': 'Climate & Environment',
                    'Corruption Governance': 'Corruption & Governance',
                    'Housing Real Estate': 'Housing & Real Estate'
                }};
                function fmtLabel(key) {{
                    const raw = key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
                    return labelMap[raw] || raw;
                }}

                const datasets = visible.map((item, i) => {{
                    const color = topicPalette[i % topicPalette.length];
                    return {{
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
                        segment: {{ borderDash: (ctx) => ['daily', 'weekly'].includes(displayEntries[ctx.p1DataIndex].type) ? [4, 4] : [] }},
                        _itemKey: item
                    }};
                }});

                const ctx = document.getElementById('topic-chart').getContext('2d');
                if (topicState.chart) topicState.chart.destroy();
                topicState.chart = new Chart(ctx, {{
                    type: 'line',
                    data: {{ labels: labels, datasets: datasets }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{ position: 'top', labels: {{ usePointStyle: true, padding: 10, font: {{ size: 11 }} }} }},
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
                                        const entryType = displayEntries[context.dataIndex].type;
                                        const suffix = entryType === 'daily' ? ' [daily]' : (entryType === 'weekly' ? ' [weekly]' : '');
                                        return context.dataset.label + ': Rank ' + rank + ' (framing: ' + (smoothedVal != null ? smoothedVal.toFixed(3) : 'N/A') + ')' + suffix;
                                    }}
                                }}
                            }}
                        }},
                        scales: {{
                            x: {{ display: true, title: {{ display: true, text: 'Date' }} }},
                            y: {{ display: true, title: {{ display: true, text: 'Rank (smoothed)' }}, reverse: true, ticks: {{ stepSize: 1 }} }}
                        }}
                    }}
                }});
            }}

            topicState.onChange = render;
            select.addEventListener('change', function(e) {{
                initSlider(topicState, topicData[e.target.value], 12, 'topic-slider', 'topic-range');
                render();
            }});
            topnInput.addEventListener('change', render);
            initSlider(topicState, topicData[select.value], 12, 'topic-slider', 'topic-range');
            render();
        }}

        function initEpuTab(state, cfg) {{
            const select = document.getElementById(cfg.countryId);
            function getSelectedItems() {{
                return Array.from(document.querySelectorAll('#' + cfg.itemSelectId + ' input:checked')).map(cb => cb.value);
            }}
            function updateSelectedCount() {{
                const count = getSelectedItems().length;
                const el = document.getElementById(cfg.selectedCountId);
                if (el) el.textContent = count;
            }}
            function fmtChipLabel(raw) {{
                if (cfg.chipLabelMap[raw]) return cfg.chipLabelMap[raw];
                return raw.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
            }}
            function applyChipFilters() {{
                const q = (document.getElementById(cfg.searchId).value || '').toLowerCase().trim();
                document.querySelectorAll('#' + cfg.itemSelectId + ' .chip').forEach(chip => {{
                    const input = chip.querySelector('input');
                    const labelEl = chip.querySelector('.chip-label');
                    const raw = input.value;
                    const label = fmtChipLabel(raw);
                    const color = cfg.getChipColor(raw);
                    if (color) chip.style.setProperty('--chip-color', color);
                    if (labelEl) labelEl.textContent = label;
                    const txt = label.toLowerCase();
                    const match = !q || txt.indexOf(q) !== -1;
                    chip.style.display = match ? 'inline-flex' : 'none';
                }});
            }}
            function setSelected(items) {{
                const set = new Set(items);
                document.querySelectorAll('#' + cfg.itemSelectId + ' input').forEach(cb => {{
                    cb.checked = set.has(cb.value);
                }});
                updateSelectedCount();
                applyChipFilters();
            }}

            function render() {{
                const country = select.value;
                const rawData = cfg.data[country];
                if (!rawData || !rawData.length) return;
                const range = getSliderRange(state);
                let data = rawData;
                if (range.from) data = data.filter(r => r.date >= range.from);
                if (range.to) data = data.filter(r => r.date <= range.to);
                if (!data.length) return;
                const selectedItems = getSelectedItems();
                const monthlyData = data.filter(r => !isDaily(r));
                const dailyData = data
                    .filter(r => isDaily(r) && selectedItems.some(i => r['EPU_' + i + '_index'] != null))
                    .slice()
                    .sort((a, b) => a.date.localeCompare(b.date));
                const dailyDisplay = buildDailyDisplay(dailyData);
                const monthlyLabels = monthlyData.map(r => r.date.split('-')[0] + '-' + r.date.split('-')[1]);
                const labels = monthlyLabels.concat(dailyDisplay.labels);
                const datasets = [];
                selectedItems.forEach(item => {{
                    const colKey = 'EPU_' + item + '_index';
                    const color = cfg.palette[cfg.items.indexOf(item) % cfg.palette.length];
                    const seriesLabel = fmtChipLabel(item) + ' EPU';
                    const maSets = buildMADatasets(monthlyData.map(r => r[colKey]), color, seriesLabel, cfg.toggleName);
                    maSets.forEach(ds => {{
                        ds._legendGroup = item;
                        ds._legendLabel = seriesLabel;
                        ds._legendColor = color;
                    }});
                    datasets.push.apply(datasets, maSets);
                    if (dailyDisplay.entries.length) {{
                        const lastMonthly = monthlyData.length > 0 ? monthlyData[monthlyData.length - 1][colKey] : null;
                        const dailyValues = dailyDisplay.entries.map(entry => {{
                            const vals = entry.rows
                                .map(r => r[colKey])
                                .filter(v => v != null && v !== 0);
                            if (!vals.length) return null;
                            return entry.type === 'weekly' ? computeAverage(vals) : vals[0];
                        }});
                        const dataPoints = [];
                        const pointRadius = [];
                        const pointHoverRadius = [];
                        const pointStyle = [];
                        const pointTypes = [];
                        if (monthlyData.length > 0) {{
                            const nBridge = monthlyData.length - 1;
                            for (let i = 0; i < nBridge; i++) {{
                                dataPoints.push(null);
                                pointRadius.push(0);
                                pointHoverRadius.push(0);
                                pointStyle.push('circle');
                                pointTypes.push(null);
                            }}
                            dataPoints.push(lastMonthly);
                            pointRadius.push(0);
                            pointHoverRadius.push(0);
                            pointStyle.push('circle');
                            pointTypes.push(null);
                        }}
                        dailyDisplay.entries.forEach((entry, idx) => {{
                            const val = dailyValues[idx];
                            const isWeekly = entry.type === 'weekly';
                            dataPoints.push(val);
                            if (val == null) {{
                                pointRadius.push(0);
                                pointHoverRadius.push(0);
                            }} else {{
                                pointRadius.push(isWeekly ? 5 : 4);
                                pointHoverRadius.push(isWeekly ? 7 : 6);
                            }}
                            pointStyle.push(isWeekly ? 'rect' : 'circle');
                            pointTypes.push(entry.type);
                        }});
                        datasets.push({{
                            label: fmtChipLabel(item) + ' EPU (current month)',
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
                        }});
                    }}
                }});
                const allVals = selectedItems.flatMap(item => {{
                    const colKey = 'EPU_' + item + '_index';
                    const monthlyVals = monthlyData.map(r => r[colKey]);
                    const dailyVals = dailyDisplay.entries.map(entry => {{
                        const vals = entry.rows
                            .map(r => r[colKey])
                            .filter(v => v != null && v !== 0);
                        if (!vals.length) return null;
                        return entry.type === 'weekly' ? computeAverage(vals) : vals[0];
                    }});
                    return monthlyVals.concat(dailyVals);
                }}).filter(v => v != null && v !== 0);
                const yMax = allVals.length ? Math.max.apply(null, allVals) * 1.1 : undefined;
                const ctx = document.getElementById(cfg.chartId).getContext('2d');
                if (state.chart) state.chart.destroy();
                state.chart = new Chart(ctx, {{
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
                state.chart._groupOrder = selectedItems.slice();
                updateLegend(state.chart, cfg.legendId);
            }}

            state.onChange = render;
            select.addEventListener('change', function(e) {{
                initSlider(state, cfg.data[e.target.value], 12, cfg.sliderId, cfg.rangeId);
                render();
            }});
            document.getElementById(cfg.itemSelectId).addEventListener('change', function() {{
                updateSelectedCount();
                applyChipFilters();
                render();
            }});
            document.getElementById(cfg.searchId).addEventListener('input', applyChipFilters);
            document.getElementById(cfg.defaultId).addEventListener('click', function() {{
                setSelected(cfg.defaultItems);
                render();
            }});
            document.getElementById(cfg.clearId).addEventListener('click', function() {{
                setSelected([]);
                render();
            }});
            document.querySelectorAll('input[name="' + cfg.toggleName + '"]').forEach(r => r.addEventListener('change', render));
            initSlider(state, cfg.data[select.value], 12, cfg.sliderId, cfg.rangeId);
            updateSelectedCount();
            applyChipFilters();
            render();
        }}

        function initTopicsTab() {{
            initEpuTab(topicsState, {{
                data: topicsData,
                items: topicsItems,
                defaultItems: topicsDefaultItems,
                palette: topicsPalette,
                getChipColor: (item) => topicsPalette[topicsItems.indexOf(item) % topicsPalette.length],
                chipLabelMap: {{ gasoline: 'Gas', natural_gas: 'Natural Gas' }},
                toggleName: 'ma-toggle-topics',
                countryId: 'topics-country',
                sliderId: 'topics-slider',
                rangeId: 'topics-range',
                chartId: 'topics-chart',
                legendId: 'topics-legend',
                itemSelectId: 'topics-item-select',
                selectedCountId: 'topics-selected-count',
                searchId: 'topics-item-search',
                defaultId: 'topics-default',
                clearId: 'topics-clear'
            }});
        }}

        function initActorsTab() {{
            initEpuTab(actorsState, {{
                data: actorsData,
                items: actorsItems,
                defaultItems: actorsDefaultItems,
                palette: actorsPalette,
                getChipColor: (item) => actorsPalette[actorsItems.indexOf(item) % actorsPalette.length],
                chipLabelMap: {{
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
                }},
                toggleName: 'ma-toggle-actors',
                countryId: 'actors-country',
                sliderId: 'actors-slider',
                rangeId: 'actors-range',
                chartId: 'actors-chart',
                legendId: 'actors-legend',
                itemSelectId: 'actors-item-select',
                selectedCountId: 'actors-selected-count',
                searchId: 'actors-item-search',
                defaultId: 'actors-default',
                clearId: 'actors-clear'
            }});
        }}

        const tabs = Array.from(document.querySelectorAll('.tab'));
        const panels = Array.from(document.querySelectorAll('.tab-panel'));
        const tabInit = {{ 'tab-1': false, 'tab-2': false, 'tab-3': false }};

        function setActiveTab(tabId) {{
            tabs.forEach(t => t.classList.toggle('is-active', t.dataset.tab === tabId));
            panels.forEach(p => p.classList.toggle('is-active', p.id === tabId));
            if (!tabInit[tabId]) {{
                if (tabId === 'tab-1') initTopicTab();
                if (tabId === 'tab-2') initTopicsTab();
                if (tabId === 'tab-3') initActorsTab();
                tabInit[tabId] = true;
            }} else {{
                if (tabId === 'tab-1' && topicState.chart) topicState.chart.resize();
                if (tabId === 'tab-2' && topicsState.chart) topicsState.chart.resize();
                if (tabId === 'tab-3' && actorsState.chart) actorsState.chart.resize();
            }}
            if (window.localStorage) {{
                window.localStorage.setItem('small-dashboard-tab', tabId);
            }}
        }}

        tabs.forEach(tab => {{
            tab.addEventListener('click', () => setActiveTab(tab.dataset.tab));
        }});

        setActiveTab('tab-1');
    </script>
</body>
</html>"""

    return template.format(
        topic_options=topic_options,
        topics_options=topics_options,
        actors_options=actors_options,
        topics_checkboxes=topics_checkboxes,
        actors_checkboxes=actors_checkboxes,
        topic_data_json=json.dumps(topic_data),
        topics_data_json=json.dumps(topics_data),
        actors_data_json=json.dumps(actors_data),
        topics_items_json=json.dumps(topics_items),
        actors_items_json=json.dumps(actors_items),
        topics_defaults_json=json.dumps(topics_defaults),
        actors_defaults_json=json.dumps(actors_defaults),
        topic_palette_json=json.dumps(topic_palette),
        topics_palette_json=json.dumps(topics_palette),
        actors_palette_json=json.dumps(actors_palette),
    )


def generate_dashboard(
    output_dir,
    topic_data,
    topics_data,
    topics_items,
    topics_defaults,
    actors_data,
    actors_items,
    actors_defaults,
):
    dashboard_path = output_dir / "small_dashboard_integrated.html"
    with open(dashboard_path, "w") as f:
        f.write(
            _build_dashboard_html(
                topic_data,
                topics_data,
                topics_items,
                topics_defaults,
                actors_data,
                actors_items,
                actors_defaults,
            )
        )
    print(f"Created {dashboard_path}")


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[3]
    data_dir = project_root / "outputs" / "text"
    output_dir = project_root / "docs/images/interactive/text"

    countries = [d for d in os.listdir(data_dir) if (data_dir / d).is_dir()]

    topic_data = {}
    for c in sorted([c for c in countries if c not in EXCLUDE_COUNTRIES]):
        df = load_attribution_data(c, data_dir, "topics")
        if df is not None:
            topic_data[c] = df_to_json(df)

    topics_data = {}
    topics_set = set()
    for c in sorted([c for c in countries if c not in EXCLUDE_COUNTRIES]):
        df = load_topics_epu_data(c, data_dir)
        if df is not None:
            topics_data[c] = df_to_json(df)
            topics_set.update(
                col.replace("EPU_", "").replace("_index", "")
                for col in df.columns
                if col.startswith("EPU_") and col.endswith("_index")
            )

    topics_items = sorted(topics_set)
    topics_defaults = [
        "inflation_prices",
        "energy",
        "diesel",
        "oil",
        "natural_gas",
        "fuel_rationing",
    ]
    topics_defaults = [t for t in topics_defaults if t in topics_items]
    if not topics_defaults:
        topics_defaults = topics_items[:5]

    actors_data = {}
    actors_set = set()
    for c in sorted([c for c in countries if c not in EXCLUDE_COUNTRIES]):
        df = load_actors_epu_data(c, data_dir)
        if df is not None:
            actors_data[c] = df_to_json(df)
            for col in df.columns:
                if col.startswith("EPU_") and col.endswith("_index"):
                    actors_set.add(col[4:-6])

    actors_items = sorted(actors_set)
    actors_defaults = [
        "central_bank",
        "parliament",
        "government",
        "world_bank",
        "international_organizations",
    ]
    actors_defaults = [a for a in actors_defaults if a in actors_items]
    if not actors_defaults:
        actors_defaults = actors_items[:5]

    if not topic_data or not topics_data or not actors_data:
        raise SystemExit("Missing data for one or more tabs.")

    generate_dashboard(
        output_dir,
        topic_data,
        topics_data,
        topics_items,
        topics_defaults,
        actors_data,
        actors_items,
        actors_defaults,
    )
