"""Generate standalone HTML interactive fuel budget simulation visualization.

Produces a single fuel_budget_sim.html:
  - Multi-select chips: one per (country, year) e.g. "FJI (2019)"
  - Percentile on the Y axis
  - bsgasoline_mnth_2021_ppp on the X axis (baseline, colored)
  - bsgasoline_mnth_2021_ppp_sim20..sim100 in same color as baseline but lighter (alpha)
"""

import json
import pandas as pd
from pathlib import Path


EXCLUDE_COUNTRIES = {"JPN", "KOR", "LAO"}

COUNTRY_NAMES = {
    "FJI": "Fiji",
    "IDN": "Indonesia",
    "MNG": "Mongolia",
    "MYS": "Malaysia",
    "PHL": "Philippines",
    "SLB": "Solomon Islands",
    "TLS": "Timor-Leste",
    "VNM": "Vietnam",
    "WSM": "Samoa",
}

SIM_COLS = [
    "bsgasoline_mnth_2021_ppp_sim20",
    "bsgasoline_mnth_2021_ppp_sim40",
    "bsgasoline_mnth_2021_ppp_sim60",
    "bsgasoline_mnth_2021_ppp_sim80",
    "bsgasoline_mnth_2021_ppp_sim100",
]

PALETTE = [
    "#1d77b2",
    "#d95e10",
    "#00a37c",
    "#e7298a",
    "#66a61e",
    "#e6ab02",
    "#7570b3",
    "#a6761d",
    "#1b9e77",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#17becf",
    "#bcbd22",
    "#ff7f0e",
]

_CSS = """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        padding: 12px 20px;
        background: #fff;
        max-width: 1000px;
    }
    .ctrl-row {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
        margin-bottom: 6px;
    }
    .row-label {
        font-weight: 600;
        color: #333;
        font-size: 0.9em;
        white-space: nowrap;
        min-width: 80px;
    }
    .section-label {
        font-weight: 600; color: #333; font-size: 0.9em;
        margin-bottom: 4px; margin-top: 4px;
    }
    .chip-container {
        display: flex; flex-wrap: wrap; gap: 5px;
        margin-bottom: 6px; padding: 2px 0;
    }
    .chip {
        display: inline-flex; align-items: center; gap: 4px;
        padding: 3px 10px; border: 1px solid #ddd;
        border-radius: 16px; font-size: 0.8em; font-weight: 400;
        cursor: pointer; user-select: none; transition: all 0.15s;
        white-space: nowrap;
    }
    .chip:hover { border-color: #667eea; background: #f0f4ff; }
    .chip input[type="checkbox"] { display: none; }
    .chip:has(input:checked) {
        background: #667eea; color: #fff; border-color: #667eea;
    }
    .legend-row {
        display: flex; align-items: center; gap: 16px;
        font-size: 0.8em; color: #555; margin: 4px 0 8px 0;
        flex-wrap: wrap;
    }
    .legend-item { display: flex; align-items: center; gap: 5px; }
    .legend-swatch {
        width: 24px; height: 3px; border-radius: 2px; flex-shrink: 0;
    }
    .chart-wrapper { position: relative; height: 460px; margin-top: 8px; }
"""


def load_budget_sim_data(csv_path: Path) -> dict:
    df = pd.read_csv(csv_path, low_memory=False)
    df = df[~df["country"].isin(EXCLUDE_COUNTRIES)].copy()
    df = df.dropna(subset=["percentile", "bsgasoline_mnth_2021_ppp"])

    result = {}
    for (country, year), grp in df.groupby(["country", "year"]):
        grp = grp.sort_values("percentile")
        year_int = int(year) if pd.notna(year) else "?"
        country_label = COUNTRY_NAMES.get(country, country)
        key = f"{country_label} ({year_int})"
        rows = []
        for _, row in grp.iterrows():
            r = {
                "percentile": float(row["percentile"]),
                "baseline": float(row["bsgasoline_mnth_2021_ppp"])
                if pd.notna(row["bsgasoline_mnth_2021_ppp"])
                else None,
            }
            for col in SIM_COLS:
                r[col] = (
                    float(row[col])
                    if col in grp.columns and pd.notna(row[col])
                    else None
                )
            rows.append(r)
        result[key] = rows

    return result


def gen_budget_sim_html(all_data: dict, out: Path):
    series_keys = sorted(all_data.keys())
    palette_json = json.dumps(PALETTE)
    data_json = json.dumps(all_data)
    sim_cols_json = json.dumps(SIM_COLS)
    sim_labels_json = json.dumps(
        {
            "bsgasoline_mnth_2021_ppp_sim20": "+20%",
            "bsgasoline_mnth_2021_ppp_sim40": "+40%",
            "bsgasoline_mnth_2021_ppp_sim60": "+60%",
            "bsgasoline_mnth_2021_ppp_sim80": "+80%",
            "bsgasoline_mnth_2021_ppp_sim100": "+100%",
        }
    )

    # Build chip HTML (all checked by default)
    chips_html = ""
    for key in series_keys:
        safe = key.replace('"', "&quot;")
        chips_html += f'<label class="chip"><input type="checkbox" value="{safe}" checked onchange="rerender()">{safe}</label>\n'

    script = f"""
        const palette = {palette_json};
        const allData = {data_json};
        const SIM_COLS = {sim_cols_json};
        const SIM_LABELS = {sim_labels_json};

        function getChecked() {{
            return Array.from(
                document.querySelectorAll('#series-chips input:checked')
            ).map(cb => cb.value);
        }}

        function hexToRgba(hex, alpha) {{
            var r = parseInt(hex.slice(1,3),16);
            var g = parseInt(hex.slice(3,5),16);
            var b = parseInt(hex.slice(5,7),16);
            return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
        }}

        function makeDataset(label, points, color, isSim) {{
            var lineColor = isSim ? hexToRgba(color, 0.25) : color;
            return {{
                label: label,
                data: points,
                borderColor: lineColor,
                backgroundColor: lineColor,
                borderWidth: isSim ? 1 : 2,
                fill: false,
                tension: 0.1,
                pointRadius: 0,
                pointHoverRadius: isSim ? 0 : 4,
                spanGaps: false,
                _isGray: isSim,
            }};
        }}

        function rerender() {{
            var selected = getChecked();
            var datasets = [];
            var colorIdx = 0;

            selected.forEach(function(key) {{
                var rows = allData[key];
                if (!rows || !rows.length) return;
                var color = palette[colorIdx % palette.length];
                colorIdx++;

                // Baseline colored line
                var baselinePts = rows.map(r => ({{ x: r.percentile, y: r.baseline }}));
                datasets.push(makeDataset(key, baselinePts, color, false));

                // Simulated gray lines
                SIM_COLS.forEach(function(col) {{
                    var simPts = rows.map(r => ({{ x: r.percentile, y: r[col] }}));
                    datasets.push(makeDataset(key + ' ' + SIM_LABELS[col], simPts, color, true));
                }});
            }});

            var ctx = document.getElementById('chart').getContext('2d');
            if (window.currentChart) window.currentChart.destroy();
            if (!datasets.length) {{ window.currentChart = null; return; }}

            window.currentChart = new Chart(ctx, {{
                type: 'line',
                data: {{ datasets: datasets }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'top',
                            labels: {{
                                usePointStyle: true,
                                padding: 14,
                                font: {{ size: 11 }},
                                filter: function(item) {{
                                    return !datasets[item.datasetIndex]._isGray;
                                }}
                            }}
                        }},
                        tooltip: {{
                            mode: 'index',
                            intersect: false,
                            backgroundColor: 'rgba(0,0,0,0.82)',
                            padding: 12,
                            filter: function(item) {{
                                return !datasets[item.datasetIndex]._isGray;
                            }},
                            callbacks: {{
                                title: function(items) {{
                                    return items.length ? 'Percentile: ' + items[0].raw.x : '';
                                }},
                                label: function(item) {{
                                    var val = item.raw ? item.raw.y : null;
                                    if (val == null) return null;
                                    return datasets[item.datasetIndex].label + ': ' + val.toFixed(3);
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            type: 'linear',
                            display: true,
                            title: {{ display: true, text: 'Percentile' }},
                            min: 0,
                            max: 100,
                        }},
                        y: {{
                            display: true,
                            title: {{ display: true, text: 'Budget Share of Gasoline (%)' }},
                        }}
                    }}
                }}
            }});
        }}

        rerender();
    """

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Fuel Budget Simulation</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <style>{_CSS}</style>
</head>
<body>
    <div class="section-label">Country &amp; Year:</div>
    <div class="chip-container" id="series-chips">
        {chips_html}
    </div>
    <div class="legend-row">
        <div class="legend-item">
            <div class="legend-swatch" style="background:#1d77b2;"></div>
            <span>Baseline</span>
        </div>
        <div class="legend-item">
            <div class="legend-swatch" style="background:rgba(29,119,178,0.25);"></div>
            <span>Simulated price shock (+20% to +100%)</span>
        </div>
    </div>
    <div class="chart-wrapper"><canvas id="chart"></canvas></div>
    <script>
        {script}
    </script>
</body>
</html>"""

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Created {out}")


def main():
    project_root = Path(__file__).resolve().parents[3]
    data_dir = project_root / "data" / "cpi" / "fuel_prices_pilot"
    all_data = load_budget_sim_data(data_dir / "fuel_budget_sim.csv")
    gen_budget_sim_html(all_data, data_dir / "fuel_budget_sim.html")


if __name__ == "__main__":
    main()
