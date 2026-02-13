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
    df["EPU_index_ma3"] = df["EPU_index"].rolling(window=3).mean()
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


def gen_html(title, subtitle, chart_id, all_data, countries, script_content):
    """Generate standalone HTML page with Chart.js visualization and country dropdown"""
    # Build country options, filtering out excluded countries
    opts = "\n".join(
        f'<option value="{c}">{fmt_country(c)}</option>'
        for c in countries
        if (c in all_data) and (c not in EXCLUDE_COUNTRIES)
    )

    # CSS styling for responsive layout
    css_styles = """
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            padding: 15px;
            background: #fff;
        }
        .controls {
            margin-bottom: 15px;
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

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <style>{css_styles}</style>
</head>
<body>
    <div class="controls">
        <label for="country-select">Country:</label>
        <select id="country-select">{opts}</select>
    </div>
    <div class="chart-wrapper">
        <canvas id="chart"></canvas>
    </div>
    <script>
        const allData = {json.dumps(all_data)};
        let currentChart = null;
        {script_content}
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
):
    """Generate standalone HTML page with Chart.js, country dropdown, and multi-select checkboxes"""
    # Build country options, filtering out excluded countries
    opts = "\n".join(
        f'<option value="{c}">{fmt_country(c)}</option>'
        for c in countries
        if (c in all_data) and (c not in EXCLUDE_COUNTRIES)
    )

    # Build checkbox items
    checkboxes = "\n".join(
        f'<label class="chip"><input type="checkbox" value="{item}"'
        f'{" checked" if item in default_checked else ""}>'
        f'{fmt_country(item)}</label>'
        for item in items
    )

    # CSS styling for responsive layout with multi-select
    css_styles = """
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            padding: 15px;
            background: #fff;
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
        .chart-wrapper { position: relative; height: 350px; }
    """

    items_json = json.dumps(items)

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <style>{css_styles}</style>
</head>
<body>
    <div class="controls">
        <label for="country-select">Country:</label>
        <select id="country-select">{opts}</select>
    </div>
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

        function getSelectedItems() {{
            return Array.from(document.querySelectorAll('#item-select input:checked')).map(cb => cb.value);
        }}

        {script_content}

        document.getElementById('country-select').addEventListener('change', e => renderChart(e.target.value, getSelectedItems()));
        document.getElementById('item-select').addEventListener('change', () => renderChart(document.getElementById('country-select').value, getSelectedItems()));
        renderChart(document.getElementById('country-select').value, getSelectedItems());
    </script>
</body>
</html>"""


def gen_epu_html(countries, data_dir, out):
    """Generate EPU visualization with raw and 3-month moving average lines"""
    countries = sorted([c for c in countries if c not in EXCLUDE_COUNTRIES])
    all_data = {
        c: df_to_json(load_epu_data(c, data_dir))
        for c in countries
        if load_epu_data(c, data_dir) is not None
    }
    if not all_data:
        return

    # JavaScript code for EPU chart rendering
    script = """
        // Format date from YYYY-MM-DD to YYYY-MM
        function formatDate(d) {
            const date = new Date(d);
            return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
        }

        // Render chart for selected country
        function renderChart(country) {
            const data = allData[country];
            if (!data || !data.length) return;

            // Extract date labels and EPU values
            const labels = data.map(r => formatDate(r.date));
            const epuWeighted = data.map(r => r.EPU_index);
            const epuMA3 = data.map(r => r.EPU_index_ma3);

            // Get canvas context and destroy previous chart if exists
            const ctx = document.getElementById('chart').getContext('2d');
            if (currentChart) currentChart.destroy();

            // Create new line chart with two datasets
            currentChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'EPU',
                            data: epuWeighted,
                            borderColor: '#aacddd',
                            borderWidth: 1.5,
                            borderDash: [5, 5],  // Dotted line
                            fill: false,
                            tension: 0.1,
                            pointRadius: 0,
                            pointHoverRadius: 5
                        },
                        {
                            label: 'EPU (3-Month MA)',
                            data: epuMA3,
                            borderColor: '#1d77b2',
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
                        y: { display: true, title: { display: true, text: 'EPU Index' } }
                    }
                }
            });
        }

        // Event listener: re-render chart when country selection changes
        document.getElementById('country-select').addEventListener('change', e => renderChart(e.target.value));

        // Initial chart render with first country
        renderChart(document.getElementById('country-select').value);
    """

    with open(out, "w") as f:
        f.write(
            gen_html(
                "Economic Policy Uncertainty Index",
                "EPU Weighted and 3-Month Moving Average",
                "epu-chart",
                all_data,
                countries,
                script,
            )
        )
    print(f"Created {out}")


def gen_epu_topics_html(countries, data_dir, out):
    """Generate topic-specific EPU visualization with multi-select checkboxes"""
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

    # 22-color palette for topics
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

    # JavaScript code for topic-based EPU chart rendering
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
            const data = allData[country];
            if (!data || !data.length) return;

            const labels = data.map(r => formatDate(r.date));
            const datasets = [];
            selectedItems.forEach((topic, i) => {{
                const colKey = `EPU_${{topic}}_index`;
                datasets.push({{
                    label: fmtLabel(topic) + ' EPU',
                    data: data.map(r => r[colKey]),
                    borderColor: palette[allItems.indexOf(topic) % palette.length],
                    borderWidth: 2.5,
                    fill: false,
                    tension: 0.1,
                    pointRadius: 0,
                    pointHoverRadius: 5
                }});
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
            gen_html_multi_select(
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

    # JavaScript code for news count chart rendering
    script = """
        // Format date from YYYY-MM-DD to YYYY-MM
        function formatDate(d) {
            const date = new Date(d);
            return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
        }

        // Render chart for selected country
        function renderChart(country) {
            const data = allData[country];
            if (!data || !data.length) return;

            // Extract date labels and article counts
            const labels = data.map(r => formatDate(r.date));
            const newsCounts = data.map(r => r.news_total);

            // Get canvas context and destroy previous chart if exists
            const ctx = document.getElementById('chart').getContext('2d');
            if (currentChart) currentChart.destroy();

            // Create new line chart with filled area
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
                            fill: true,  // Fill area under line
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

        // Event listener: re-render chart when country selection changes
        document.getElementById('country-select').addEventListener('change', e => renderChart(e.target.value));

        // Initial chart render with first country
        renderChart(document.getElementById('country-select').value);
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
    """Generate E/P/U breadth index comparison visualization"""
    countries = sorted([c for c in countries if c not in EXCLUDE_COUNTRIES])
    all_data = {
        c: df_to_json(load_epu_data(c, data_dir))
        for c in countries
        if load_epu_data(c, data_dir) is not None
    }
    if not all_data:
        return

    # JavaScript code for breadth chart rendering
    script = """
        // Format date from YYYY-MM-DD to YYYY-MM
        function formatDate(d) {
            const date = new Date(d);
            return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
        }

        // Render chart for selected country
        function renderChart(country) {
            const data = allData[country];
            if (!data || !data.length) return;

            // Extract date labels
            const labels = data.map(r => formatDate(r.date));

            // Get canvas context and destroy previous chart if exists
            const ctx = document.getElementById('chart').getContext('2d');
            if (currentChart) currentChart.destroy();

            // Create new line chart with E/P/U breadth datasets
            currentChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Economic Breadth',
                            data: data.map(r => r.E_breadth),
                            borderColor: '#1d77b2',
                            borderWidth: 2.5,
                            fill: false,
                            tension: 0.1,
                            pointRadius: 0,
                            pointHoverRadius: 5
                        },
                        {
                            label: 'Political Breadth',
                            data: data.map(r => r.P_breadth),
                            borderColor: '#d95e10',
                            borderWidth: 2.5,
                            fill: false,
                            tension: 0.1,
                            pointRadius: 0,
                            pointHoverRadius: 5
                        },
                        {
                            label: 'Uncertainty Breadth',
                            data: data.map(r => r.U_breadth),
                            borderColor: '#00a37c',
                            borderWidth: 2.5,
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
                        y: { display: true, title: { display: true, text: 'Breadth Index' } }
                    }
                }
            });
        }

        // Event listener: re-render chart when country selection changes
        document.getElementById('country-select').addEventListener('change', e => renderChart(e.target.value));

        // Initial chart render with first country
        renderChart(document.getElementById('country-select').value);
    """

    with open(out, "w") as f:
        f.write(
            gen_html(
                "EPU Breadth Index",
                "Economic, Political, and Uncertainty Breadth",
                "breadth-chart",
                all_data,
                countries,
                script,
            )
        )
    print(f"Created {out}")


def gen_intensity_html(countries, data_dir, out):
    """Generate E/P/U intensity index comparison visualization"""
    countries = sorted([c for c in countries if c not in EXCLUDE_COUNTRIES])
    all_data = {
        c: df_to_json(load_epu_data(c, data_dir))
        for c in countries
        if load_epu_data(c, data_dir) is not None
    }
    if not all_data:
        return

    # JavaScript code for intensity chart rendering
    script = """
        // Format date from YYYY-MM-DD to YYYY-MM
        function formatDate(d) {
            const date = new Date(d);
            return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
        }

        // Render chart for selected country
        function renderChart(country) {
            const data = allData[country];
            if (!data || !data.length) return;

            // Extract date labels
            const labels = data.map(r => formatDate(r.date));

            // Get canvas context and destroy previous chart if exists
            const ctx = document.getElementById('chart').getContext('2d');
            if (currentChart) currentChart.destroy();

            // Create new line chart with E/P/U intensity datasets
            currentChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Economic Intensity',
                            data: data.map(r => r.E_intensity),
                            borderColor: '#1d77b2',
                            borderWidth: 2.5,
                            fill: false,
                            tension: 0.1,
                            pointRadius: 0,
                            pointHoverRadius: 5
                        },
                        {
                            label: 'Political Intensity',
                            data: data.map(r => r.P_intensity),
                            borderColor: '#d95e10',
                            borderWidth: 2.5,
                            fill: false,
                            tension: 0.1,
                            pointRadius: 0,
                            pointHoverRadius: 5
                        },
                        {
                            label: 'Uncertainty Intensity',
                            data: data.map(r => r.U_intensity),
                            borderColor: '#00a37c',
                            borderWidth: 2.5,
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
                        y: { display: true, title: { display: true, text: 'Intensity Index' } }
                    }
                }
            });
        }

        // Event listener: re-render chart when country selection changes
        document.getElementById('country-select').addEventListener('change', e => renderChart(e.target.value));

        // Initial chart render with first country
        renderChart(document.getElementById('country-select').value);
    """

    with open(out, "w") as f:
        f.write(
            gen_html(
                "EPU Intensity Index",
                "Economic, Political, and Uncertainty Intensity",
                "intensity-chart",
                all_data,
                countries,
                script,
            )
        )
    print(f"Created {out}")


def gen_pairwise_html(countries, data_dir, out):
    """Generate EU/PU/EP pairwise interaction index visualization"""
    countries = sorted([c for c in countries if c not in EXCLUDE_COUNTRIES])
    all_data = {
        c: df_to_json(load_epu_data(c, data_dir))
        for c in countries
        if load_epu_data(c, data_dir) is not None
    }
    if not all_data:
        return

    # JavaScript code for pairwise chart rendering
    script = """
        // Format date from YYYY-MM-DD to YYYY-MM
        function formatDate(d) {
            const date = new Date(d);
            return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
        }

        // Render chart for selected country
        function renderChart(country) {
            const data = allData[country];
            if (!data || !data.length) return;

            // Extract date labels
            const labels = data.map(r => formatDate(r.date));

            // Get canvas context and destroy previous chart if exists
            const ctx = document.getElementById('chart').getContext('2d');
            if (currentChart) currentChart.destroy();

            // Create new line chart with pairwise datasets
            currentChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Economic-Uncertainty (EU)',
                            data: data.map(r => r.EU_index),
                            borderColor: '#1d77b2',
                            borderWidth: 2.5,
                            fill: false,
                            tension: 0.1,
                            pointRadius: 0,
                            pointHoverRadius: 5
                        },
                        {
                            label: 'Policy-Uncertainty (PU)',
                            data: data.map(r => r.PU_index),
                            borderColor: '#d95e10',
                            borderWidth: 2.5,
                            fill: false,
                            tension: 0.1,
                            pointRadius: 0,
                            pointHoverRadius: 5
                        },
                        {
                            label: 'Economic-Policy (EP)',
                            data: data.map(r => r.EP_index),
                            borderColor: '#00a37c',
                            borderWidth: 2.5,
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
                        y: { display: true, title: { display: true, text: 'Pairwise Index' } }
                    }
                }
            });
        }

        // Event listener: re-render chart when country selection changes
        document.getElementById('country-select').addEventListener('change', e => renderChart(e.target.value));

        // Initial chart render with first country
        renderChart(document.getElementById('country-select').value);
    """

    with open(out, "w") as f:
        f.write(
            gen_html(
                "Pairwise Interaction Indices",
                "EU, PU, and EP Pairwise Indices",
                "pairwise-chart",
                all_data,
                countries,
                script,
            )
        )
    print(f"Created {out}")


def gen_topic_attribution_html(countries, data_dir, out):
    """Generate uncertainty attribution by topic with multi-select checkboxes"""
    countries = sorted([c for c in countries if c not in EXCLUDE_COUNTRIES])
    all_data = {}
    topics = None
    for c in countries:
        df = load_attribution_data(c, data_dir, "topics")
        if df is not None:
            all_data[c] = df_to_json(df)
            if topics is None:
                topics = sorted(
                    set(
                        col.replace("_absolute", "").replace("_framing", "")
                        for col in df.columns
                        if col.endswith("_absolute") or col.endswith("_framing")
                    )
                )
    if not all_data or not topics:
        return

    # 22-color palette for topics
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
    default_checked = ["economic_growth"]

    # JavaScript code for topic attribution chart rendering
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
            const data = allData[country];
            if (!data || !data.length) return;

            const labels = data.map(r => formatDate(r.date));
            const datasets = [];
            selectedItems.forEach((topic) => {{
                const color = palette[allItems.indexOf(topic) % palette.length];
                datasets.push({{
                    label: fmtLabel(topic) + ' (Absolute)',
                    data: data.map(r => r[topic + '_absolute']),
                    borderColor: color,
                    borderWidth: 2.5,
                    fill: false,
                    tension: 0.1,
                    pointRadius: 0,
                    pointHoverRadius: 5
                }});
                datasets.push({{
                    label: fmtLabel(topic) + ' (Framing)',
                    data: data.map(r => r[topic + '_framing']),
                    borderColor: color,
                    borderWidth: 2,
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.1,
                    pointRadius: 0,
                    pointHoverRadius: 5
                }});
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
                        y: {{ display: true, title: {{ display: true, text: 'Attribution Index' }} }}
                    }}
                }}
            }});
        }}
    """

    with open(out, "w") as f:
        f.write(
            gen_html_multi_select(
                "Uncertainty Attribution by Topic",
                "Absolute and Framing Attribution per Topic",
                "topic-attr-chart",
                all_data,
                countries,
                topics,
                "Topics",
                default_checked,
                script,
            )
        )
    print(f"Created {out}")


def gen_actor_attribution_html(countries, data_dir, out):
    """Generate uncertainty attribution by actor with multi-select checkboxes"""
    countries = sorted([c for c in countries if c not in EXCLUDE_COUNTRIES])
    all_data = {}
    actors = None
    for c in countries:
        df = load_attribution_data(c, data_dir, "actors")
        if df is not None:
            all_data[c] = df_to_json(df)
            if actors is None:
                actors = sorted(
                    set(
                        col.replace("_absolute", "").replace("_framing", "")
                        for col in df.columns
                        if col.endswith("_absolute") or col.endswith("_framing")
                    )
                )
    if not all_data or not actors:
        return

    # 17-color palette for actors
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
    default_checked = ["government"]

    # JavaScript code for actor attribution chart rendering
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
            const data = allData[country];
            if (!data || !data.length) return;

            const labels = data.map(r => formatDate(r.date));
            const datasets = [];
            selectedItems.forEach((actor) => {{
                const color = palette[allItems.indexOf(actor) % palette.length];
                datasets.push({{
                    label: fmtLabel(actor) + ' (Absolute)',
                    data: data.map(r => r[actor + '_absolute']),
                    borderColor: color,
                    borderWidth: 2.5,
                    fill: false,
                    tension: 0.1,
                    pointRadius: 0,
                    pointHoverRadius: 5
                }});
                datasets.push({{
                    label: fmtLabel(actor) + ' (Framing)',
                    data: data.map(r => r[actor + '_framing']),
                    borderColor: color,
                    borderWidth: 2,
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.1,
                    pointRadius: 0,
                    pointHoverRadius: 5
                }});
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
                        y: {{ display: true, title: {{ display: true, text: 'Attribution Index' }} }}
                    }}
                }}
            }});
        }}
    """

    with open(out, "w") as f:
        f.write(
            gen_html_multi_select(
                "Uncertainty Attribution by Actor",
                "Absolute and Framing Attribution per Actor",
                "actor-attr-chart",
                all_data,
                countries,
                actors,
                "Actors",
                default_checked,
                script,
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

    # JavaScript code for inflation prediction chart rendering
    script = """
        // Format date from YYYY-MM-DD to YYYY-MM
        function formatDate(d) {
            const date = new Date(d);
            return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
        }

        // Render chart for selected country
        function renderChart(country) {
            const data = allData[country];
            if (!data || !data.length) return;

            // Extract date labels and inflation values
            const labels = data.map(r => formatDate(r.date));
            const predictedInflation = data.map(r => r.predicted_inflation);
            const actualInflation = data.map(r => r.actual_inflation);

            // Get canvas context and destroy previous chart if exists
            const ctx = document.getElementById('chart').getContext('2d');
            if (currentChart) currentChart.destroy();

            // Create new line chart comparing predicted vs actual inflation
            currentChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Predicted Inflation',
                            data: predictedInflation,
                            borderColor: '#ff9a00',  // Orange
                            borderWidth: 3,
                            fill: false,
                            tension: 0.1,
                            pointRadius: 0,
                            pointHoverRadius: 5
                        },
                        {
                            label: 'Actual Inflation',
                            data: actualInflation,
                            borderColor: '#43a5e3',  // Blue
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

        // Event listener: re-render chart when country selection changes
        document.getElementById('country-select').addEventListener('change', e => renderChart(e.target.value));

        // Initial chart render with first country
        renderChart(document.getElementById('country-select').value);
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

    # JavaScript code for out-of-bag inflation prediction chart rendering
    script = """
        // Format date from YYYY-MM-DD to YYYY-MM
        function formatDate(d) {
            const date = new Date(d);
            return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
        }

        // Render chart for selected country
        function renderChart(country) {
            const data = allData[country];
            if (!data || !data.length) return;

            // Extract date labels and inflation values
            const labels = data.map(r => formatDate(r.date));
            const predictedInflation = data.map(r => r.predicted_inflation);
            const actualInflation = data.map(r => r.actual_inflation);

            // Get canvas context and destroy previous chart if exists
            const ctx = document.getElementById('chart').getContext('2d');
            if (currentChart) currentChart.destroy();

            // Create new line chart comparing predicted vs actual inflation
            currentChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Predicted Inflation (OOB)',
                            data: predictedInflation,
                            borderColor: '#ff6b6b',  // Red
                            borderWidth: 3,
                            fill: false,
                            tension: 0.1,
                            pointRadius: 0,
                            pointHoverRadius: 5
                        },
                        {
                            label: 'Actual Inflation',
                            data: actualInflation,
                            borderColor: '#43a5e3',  // Blue
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

        // Event listener: re-render chart when country selection changes
        document.getElementById('country-select').addEventListener('change', e => renderChart(e.target.value));

        // Initial chart render with first country
        renderChart(document.getElementById('country-select').value);
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
        countries, DATA_DIR, OUTPUT_DIR / "topic_attribution_pic.html"
    )
    gen_actor_attribution_html(
        countries, DATA_DIR, OUTPUT_DIR / "actor_attribution_pic.html"
    )
    gen_pred_html(countries, DATA_DIR, OUTPUT_DIR / "train_predictions_pic.html")
    gen_oob_pred_html(
        countries, DATA_DIR, OUTPUT_DIR / "out_of_bag_predictions_pic.html"
    )
    print("All plots generated successfully!")
