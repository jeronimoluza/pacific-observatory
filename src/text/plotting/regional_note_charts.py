"""Generate static HTML charts for regional notes (no dropdowns or sliders)."""

import json
import pandas as pd
from pathlib import Path


# ---------------------------------------------------------------------------
# Label map (same as interactive.py)
# ---------------------------------------------------------------------------

LABEL_MAP = {
    "Imf": "IMF",
    "Us Government": "US Government",
    "Us China Trade War": "US-China Trade War",
    "Covid Pandemic": "COVID-19 Pandemic",
    "Inflation Prices": "Inflation & Prices",
    "Climate Environment": "Climate & Environment",
    "Corruption Governance": "Corruption & Governance",
    "Housing Real Estate": "Housing & Real Estate",
}

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


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------


def load_epu_data(country, data_dir):
    f = data_dir / f"{country}/epu/epu.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f)
    df["date"] = pd.to_datetime(df["date"], format="mixed")
    return df.sort_values("date")


def load_attribution_data(country, data_dir):
    f = data_dir / f"{country}/uncertainty_attribution/topics.csv"
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


def fmt_label(key):
    raw = " ".join(w.capitalize() for w in key.split("_"))
    return LABEL_MAP.get(raw, raw)


# ---------------------------------------------------------------------------
# EPU chart
# ---------------------------------------------------------------------------

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
"""


def gen_regional_epu_html(
    country, title, date_from, date_to, annotations, data_dir, out
):
    """Generate a static EPU chart (6MA + 12MA) with right-side annotations.

    Parameters
    ----------
    country : str
        Country folder name under data_dir.
    title : str
        Chart title (e.g. "Figure 3: EPU Tonga").
    date_from : str
        Start date filter "YYYY-MM".
    date_to : str
        End date filter "YYYY-MM".
    annotations : list of dict
        Each dict: {"label": str, "date": str, "yValue": float}
        date is "YYYY-MM" of the event; yValue is the EPU index at that date.
    data_dir : Path
        Root data directory.
    out : Path
        Output HTML file path.
    """
    df = load_epu_data(country, data_dir)
    if df is None:
        print(f"No EPU data for {country}, skipping.")
        return

    # Filter date range
    df = df[df["date"].dt.strftime("%Y-%m") >= date_from]
    df = df[df["date"].dt.strftime("%Y-%m") <= date_to]

    raw_data = df_to_json(df)
    annotations_json = json.dumps(annotations)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            padding: 16px 20px;
            background: #fff;
            max-width: 1060px;
        }}
        h2 {{
            text-align: center;
            font-size: 1.05em;
            font-weight: 700;
            margin-bottom: 14px;
            color: #111;
        }}
        .chart-outer {{
            position: relative;
            display: flex;
            align-items: flex-start;
        }}
        .chart-wrapper {{
            position: relative;
            height: 380px;
            flex: 1 1 0;
            min-width: 0;
        }}
        .annotation-panel {{
            position: relative;
            width: 200px;
            flex-shrink: 0;
            height: 380px;
        }}
        .annotation-svg {{
            position: absolute;
            top: 0;
            left: 0;
            pointer-events: none;
        }}
        .annotation-label {{
            position: absolute;
            font-size: 0.76em;
            color: #333;
            line-height: 1.35;
            max-width: 190px;
            text-align: left;
            transform: translateY(-50%);
        }}
    </style>
</head>
<body>
    <h2>{title}</h2>
    <div class="chart-outer" id="chart-outer">
        <div class="chart-wrapper">
            <canvas id="chart"></canvas>
        </div>
        <div class="annotation-panel" id="annotation-panel"></div>
    </div>
    <script>
        const rawData = {json.dumps(raw_data)};
        const annotations = {annotations_json};

        {_COMPUTE_MA_JS}

        function formatDate(d) {{
            const date = new Date(d);
            return date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0');
        }}

        const labels = rawData.map(r => formatDate(r.date));
        const epuRaw = rawData.map(r => r.EPU_index);
        const ma6 = computeMA(epuRaw, 6);
        const ma12 = computeMA(epuRaw, 12);

        const ctx = document.getElementById('chart').getContext('2d');
        const chart = new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [
                    {{
                        label: 'EPU Index (6-Mo MA)',
                        data: ma6,
                        borderColor: 'rgba(29,119,178,1.0)',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.1,
                        pointRadius: 0,
                        pointHoverRadius: 4
                    }},
                    {{
                        label: 'EPU Index (12-Mo MA)',
                        data: ma12,
                        borderColor: 'rgba(29,119,178,0.45)',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.1,
                        pointRadius: 0,
                        pointHoverRadius: 4
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'top',
                        labels: {{
                            usePointStyle: true,
                            pointStyle: 'circle',
                            padding: 20,
                            font: {{ size: 12 }}
                        }}
                    }},
                    tooltip: {{
                        mode: 'index',
                        intersect: false,
                        backgroundColor: 'rgba(0,0,0,0.8)',
                        padding: 10
                    }}
                }},
                scales: {{
                    x: {{
                        display: true,
                        grid: {{ color: 'rgba(0,0,0,0.08)' }},
                        ticks: {{
                            maxRotation: 45,
                            font: {{ size: 10 }},
                            maxTicksLimit: 20
                        }}
                    }},
                    y: {{
                        display: true,
                        title: {{ display: true, text: 'EPU Index', font: {{ size: 11 }} }},
                        grid: {{ color: 'rgba(0,0,0,0.08)' }},
                        ticks: {{ font: {{ size: 10 }} }}
                    }}
                }}
            }}
        }});

        // Draw SVG lines + label divs after chart renders
        // ann.yValue is the 6MA value at ann.date
        function positionAnnotations() {{
            const canvas = document.getElementById('chart');
            const outer = document.getElementById('chart-outer');
            const panel = document.getElementById('annotation-panel');
            panel.innerHTML = '';
            // Remove any previously appended SVG
            const oldSvg = outer.querySelector('.annotation-svg');
            if (oldSvg) oldSvg.remove();

            const xScale = chart.scales.x;
            const yScale = chart.scales.y;

            // Canvas offset relative to chart-outer
            const outerRect = outer.getBoundingClientRect();
            const canvasRect = canvas.getBoundingClientRect();
            const canvasLeft = canvasRect.left - outerRect.left;
            const canvasTop = canvasRect.top - outerRect.top;

            // Panel offset relative to chart-outer
            const panelRect = panel.getBoundingClientRect();
            const panelLeft = panelRect.left - outerRect.left;

            // SVG spans the full chart-outer
            const svgNS = 'http://www.w3.org/2000/svg';
            const svg = document.createElementNS(svgNS, 'svg');
            svg.setAttribute('width', outer.offsetWidth);
            svg.setAttribute('height', outer.offsetHeight);
            svg.classList.add('annotation-svg');
            outer.appendChild(svg);

            annotations.forEach(function(ann) {{
                // Find label index matching ann.date (YYYY-MM)
                const labelIdx = labels.findIndex(function(l) {{ return l === ann.date; }});
                if (labelIdx < 0) return;

                // X from the date position; Y from the 6MA value at that date
                const xPx = canvasLeft + xScale.getPixelForValue(labelIdx);
                const yPx = canvasTop + yScale.getPixelForValue(ann.yValue);

                // Label is placed at yPx + optional vertical offset to avoid overlap
                const labelY = yPx + (ann.labelOffset || 0);

                // Line: from data point to left edge of annotation panel at label height
                const lineEndX = panelLeft + 4;

                const line = document.createElementNS(svgNS, 'line');
                line.setAttribute('x1', xPx);
                line.setAttribute('y1', yPx);
                line.setAttribute('x2', lineEndX);
                line.setAttribute('y2', labelY);
                line.setAttribute('stroke', '#888');
                line.setAttribute('stroke-width', '1');
                line.setAttribute('stroke-dasharray', '4,3');
                svg.appendChild(line);

                // Small dot exactly at data point
                const dot = document.createElementNS(svgNS, 'circle');
                dot.setAttribute('cx', xPx);
                dot.setAttribute('cy', yPx);
                dot.setAttribute('r', '3.5');
                dot.setAttribute('fill', 'rgba(29,119,178,0.85)');
                dot.setAttribute('stroke', '#fff');
                dot.setAttribute('stroke-width', '1');
                svg.appendChild(dot);

                // Label div in panel, vertically centered at labelY
                const div = document.createElement('div');
                div.className = 'annotation-label';
                div.style.top = labelY + 'px';
                div.style.left = '8px';
                div.textContent = ann.label;
                panel.appendChild(div);
            }});
        }}

        // Chart.js fires animation onComplete after first render
        chart.options.animation = {{
            onComplete: positionAnnotations
        }};
        chart.update();
    </script>
</body>
</html>"""

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Created {out}")


# ---------------------------------------------------------------------------
# Bump chart
# ---------------------------------------------------------------------------


def gen_regional_bump_html(country, title, date_from, date_to, topics, data_dir, out):
    """Generate a static bump chart ranking specified topics by framing value.

    Parameters
    ----------
    country : str
        Country folder name under data_dir.
    title : str
        Chart title.
    date_from : str
        Start date filter "YYYY-MM".
    date_to : str
        End date filter "YYYY-MM".
    topics : list of str
        Topic keys (snake_case) to display. Ranked among themselves after a
        global ranking of all topics over the period (mirrors interactive.py).
    data_dir : Path
        Root data directory.
    out : Path
        Output HTML file path.
    """
    df_all = load_attribution_data(country, data_dir)
    if df_all is None:
        print(f"No attribution data for {country}, skipping.")
        return

    # Detect all framing columns
    all_framing_cols = [
        c.replace("_framing", "") for c in df_all.columns if c.endswith("_framing")
    ]

    # --- Step 1: compute 3-month MA on the FULL series (mirrors interactive.py) ---
    def compute_ma(values, w):
        result = []
        for i in range(len(values)):
            if i < w - 1:
                result.append(None)
                continue
            window = [v for v in values[i - w + 1 : i + 1] if v is not None]
            result.append(sum(window) / len(window) if window else None)
        return result

    smoothed_full = {}
    for t in all_framing_cols:
        vals = list(df_all[f"{t}_framing"].fillna(0))
        smoothed_full[t] = compute_ma(vals, 3)

    # --- Step 2: slice to the requested date range ---
    mask = (df_all["date"].dt.strftime("%Y-%m") >= date_from) & (
        df_all["date"].dt.strftime("%Y-%m") <= date_to
    )
    slice_indices = [i for i, m in enumerate(mask) if m]

    smoothed_sliced = {
        t: [smoothed_full[t][i] for i in slice_indices] for t in all_framing_cols
    }

    df = df_all[mask].copy()

    # --- Step 3: rank ALL topics globally per month, display only requested topics ---
    n_months = len(slice_indices)
    ranks = []
    for t_idx in range(n_months):
        vals = [
            {"topic": t, "value": smoothed_sliced[t][t_idx] or 0}
            for t in all_framing_cols
        ]
        vals.sort(key=lambda x: x["value"], reverse=True)
        month_ranks = {v["topic"]: i + 1 for i, v in enumerate(vals)}
        ranks.append(month_ranks)

    # Build per-topic rank series and smoothed value series for JS tooltip
    topic_ranks = {t: [r[t] for r in ranks] for t in topics}
    topic_smoothed = {t: smoothed_sliced[t] for t in topics}

    # Y-axis: min=1 always; max = worst rank among selected topics + 1 padding
    worst_rank = max(max(topic_ranks[t]) for t in topics)
    y_min = 0  # 0 gives ~1 rank of padding above rank-1 line
    y_max = worst_rank + 1

    raw_data = df_to_json(df)
    n_topics = len(topics)
    topics_json = json.dumps(topics)
    palette_json = json.dumps(PALETTE[:n_topics])
    label_map_js = json.dumps(LABEL_MAP)
    topic_ranks_json = json.dumps(topic_ranks)
    topic_smoothed_json = json.dumps(topic_smoothed)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            padding: 16px 20px;
            background: #fff;
            max-width: 900px;
        }}
        h2 {{
            text-align: center;
            font-size: 1.05em;
            font-weight: 700;
            margin-bottom: 14px;
            color: #111;
        }}
        .chart-wrapper {{
            position: relative;
            height: 420px;
        }}
    </style>
</head>
<body>
    <h2>{title}</h2>
    <div class="chart-wrapper">
        <canvas id="chart"></canvas>
    </div>
    <script>
        const rawData = {json.dumps(raw_data)};
        const topics = {topics_json};
        const palette = {palette_json};
        const LABEL_MAP = {label_map_js};
        const topicRanks = {topic_ranks_json};
        const topicSmoothed = {topic_smoothed_json};
        const Y_MIN = {y_min};
        const Y_MAX = {y_max};

        function fmtLabel(key) {{
            const raw = key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
            return LABEL_MAP[raw] || raw;
        }}

        function formatDate(d) {{
            const date = new Date(d);
            return date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0');
        }}

        const labels = rawData.map(r => formatDate(r.date));

        const datasets = topics.map(function(topic, i) {{
            const color = palette[i % palette.length];
            return {{
                label: fmtLabel(topic),
                data: topicRanks[topic],
                borderColor: color,
                borderWidth: 2.5,
                fill: false,
                tension: 0,
                pointRadius: 5,
                pointBackgroundColor: color,
                pointBorderColor: '#fff',
                pointBorderWidth: 1.5,
                pointHoverRadius: 7,
                _topicKey: topic
            }};
        }});

        const ctx = document.getElementById('chart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{ labels: labels, datasets: datasets }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'top',
                        labels: {{
                            usePointStyle: true,
                            pointStyle: 'circle',
                            padding: 20,
                            font: {{ size: 12 }}
                        }}
                    }},
                    tooltip: {{
                        mode: 'nearest',
                        intersect: false,
                        backgroundColor: 'rgba(0,0,0,0.8)',
                        padding: 10,
                        callbacks: {{
                            label: function(context) {{
                                const topicKey = context.dataset._topicKey;
                                const rank = context.raw;
                                const smoothedVal = topicSmoothed[topicKey][context.dataIndex];
                                return context.dataset.label + ': Rank ' + rank +
                                    ' (framing: ' + (smoothedVal != null ? smoothedVal.toFixed(3) : 'N/A') + ')';
                            }}
                        }}
                    }}
                }},
                scales: {{
                    x: {{
                        display: true,
                        grid: {{ color: 'rgba(0,0,0,0.08)' }},
                        ticks: {{ font: {{ size: 11 }} }}
                    }},
                    y: {{
                        display: true,
                        reverse: true,
                        title: {{ display: true, text: 'Rank (among all topics)', font: {{ size: 11 }} }},
                        min: Y_MIN,
                        max: Y_MAX,
                        ticks: {{
                            stepSize: 1,
                            font: {{ size: 11 }}
                        }},
                        grid: {{ color: 'rgba(0,0,0,0.08)' }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>"""

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Created {out}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    DATA_DIR = PROJECT_ROOT / "outputs" / "text"
    OUTPUT_DIR = PROJECT_ROOT / "docs/images/interactive/text/regional_note"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Figure 3: EPU Tonga
    gen_regional_epu_html(
        country="tonga",
        title="Figure 3: EPU Tonga",
        date_from="2014-12",
        date_to="2025-12",
        annotations=[
            {
                "label": "Ministry of FA under the royal family, Lord Fatafehi Fakafānua PM.",
                "date": "2025-04",
                "yValue": 48.74,
                "labelOffset": -35,
            },
            {
                "label": "Resignation of Prime Minister",
                "date": "2024-09",
                "yValue": 43.328,
                "labelOffset": 35,
            },
        ],
        data_dir=DATA_DIR,
        out=OUTPUT_DIR / "tonga_epu.html",
    )

    # Figure 4: Tonga bump chart
    gen_regional_bump_html(
        country="tonga",
        title="Figure 4: Tonga salient topics ranking",
        date_from="2025-10",
        date_to="2025-12",
        topics=["corruption_governance", "education", "energy", "health"],
        data_dir=DATA_DIR,
        out=OUTPUT_DIR / "tonga_bump.html",
    )

    # Figure 5: Laos EPU
    gen_regional_epu_html(
        country="lao",
        title="Figure 5: Laos Policy Uncertainty Index",
        date_from="2014-12",
        date_to="2025-12",
        annotations=[
            {
                "label": "FX repatriation rules; policy rate raised to 8.5%; raise VAT rate from 7% to 10%.",
                "date": "2024-04",
                "yValue": 57.152,
            },
        ],
        data_dir=DATA_DIR,
        out=OUTPUT_DIR / "lao_epu.html",
    )

    # Figure 6: Laos bump chart
    gen_regional_bump_html(
        country="lao",
        title="Figure 6: Laos salient topics ranking",
        date_from="2024-05",
        date_to="2024-11",
        topics=["education", "exchange_rate", "inflation_prices", "poverty"],
        data_dir=DATA_DIR,
        out=OUTPUT_DIR / "lao_bump.html",
    )

    print("All regional note charts generated successfully!")
