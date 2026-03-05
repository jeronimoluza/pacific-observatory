"""Generate standalone HTML interactive fuel prices visualization.

Produces a single fuel_prices.html:
  - Country dropdown
  - Multi-select chips: fuel_family x quality_group combinations
  - National Average (solid color) + per-location gray lines for multi-location countries
  - Raw | 3-Mo MA smoothing toggle (90-day calendar window)
  - Location price table (raw prices, no Latest Date column) for multi-location countries
"""

import json
import pandas as pd
from pathlib import Path


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
    select {
        padding: 6px 10px;
        border: 1px solid #ddd;
        border-radius: 4px;
        font-size: 0.9em;
        cursor: pointer;
        background: #fff;
    }
    select:hover { border-color: #667eea; }
    select:focus { outline: 0; border-color: #667eea; }
    .toggle-group {
        display: inline-flex;
        flex-wrap: wrap;
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
        white-space: nowrap;
    }
    .toggle-group label:first-child { margin-left: 0; border-radius: 16px 0 0 16px; }
    .toggle-group label:last-child  { border-radius: 0 16px 16px 0; }
    .toggle-group label:only-child  { border-radius: 16px; }
    .toggle-group input[type="radio"] { display: none; }
    .toggle-group label:has(input:checked) {
        background: #667eea; color: #fff; border-color: #667eea;
        z-index: 1; position: relative;
    }
    .toggle-group label:hover:not(:has(input:checked)) {
        border-color: #667eea; background: #f0f4ff;
    }
    .chip-container {
        display: flex; flex-wrap: wrap; gap: 5px;
        margin-bottom: 6px; max-height: 120px;
        overflow-y: auto; padding: 2px 0;
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
    .section-label {
        font-weight: 600; color: #333; font-size: 0.9em;
        margin-bottom: 4px; margin-top: 4px;
    }
    #meta-panel {
        font-size: 0.82em; color: #555; margin: 4px 0; line-height: 1.7;
    }
    .chart-wrapper { position: relative; height: 420px; margin-top: 8px; }
    #loc-table-section { margin-top: 14px; }
    #loc-table-section .section-label { margin-bottom: 6px; }
    #loc-table-toggles { display: flex; flex-wrap: wrap; gap: 0; margin-bottom: 10px; }
    #loc-table-toggles label {
        padding: 4px 12px; border: 1px solid #ddd; font-size: 0.82em;
        cursor: pointer; user-select: none; transition: all 0.15s;
        margin-left: -1px; white-space: nowrap;
    }
    #loc-table-toggles label:first-child { margin-left: 0; border-radius: 16px 0 0 16px; }
    #loc-table-toggles label:last-child  { border-radius: 0 16px 16px 0; }
    #loc-table-toggles label:only-child  { border-radius: 16px; }
    #loc-table-toggles input[type="radio"] { display: none; }
    #loc-table-toggles label:has(input:checked) {
        background: #667eea; color: #fff; border-color: #667eea;
        z-index: 1; position: relative;
    }
    #loc-table-toggles label:hover:not(:has(input:checked)) {
        border-color: #667eea; background: #f0f4ff;
    }
    #loc-table-wrap { overflow-x: auto; }
    #loc-table {
        border-collapse: collapse; font-size: 0.82em; min-width: 260px; width: 100%;
    }
    #loc-table th, #loc-table td {
        padding: 5px 12px; text-align: left; border-bottom: 1px solid #eee;
    }
    #loc-table th { font-weight: 600; background: #f7f7f7; }
    #loc-table tr.nat-avg-row td { font-weight: 600; }
    #loc-table tr:hover td { background: #f0f4ff; }
"""


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
                r[col] = float(v)
            else:
                r[col] = str(v)
        data.append(r)
    return data


def load_fuel_data(csv_path: Path) -> dict:
    df = pd.read_csv(csv_path, low_memory=False)
    df["observation_date"] = pd.to_datetime(df["observation_date"])

    # Malaysia: geography encoded in product name
    def fix_malaysia(row):
        prod = str(row["fuel_product"])
        if " (East Malaysia)" in prod:
            return pd.Series(
                [prod.replace(" (East Malaysia)", "").strip(), "East Malaysia"]
            )
        if " (Peninsular Malaysia)" in prod:
            return pd.Series(
                [
                    prod.replace(" (Peninsular Malaysia)", "").strip(),
                    "Peninsular Malaysia",
                ]
            )
        return pd.Series([prod, None])

    malaysia_mask = df["country"] == "Malaysia"
    df.loc[malaysia_mask, ["fuel_product", "_my_loc"]] = (
        df[malaysia_mask].apply(fix_malaysia, axis=1).values
    )

    def make_location(row):
        my_loc = row.get("_my_loc")
        if pd.notna(my_loc) and str(my_loc).strip():
            return str(my_loc).strip()
        city = row["city"]
        sub = row["subnational_area"]
        if pd.notna(city) and str(city).strip():
            return str(city).strip()
        if pd.notna(sub) and str(sub).strip():
            if str(sub).strip().lower().startswith("national"):
                return "National"
            return str(sub).strip()
        return "National"

    df["location"] = df.apply(make_location, axis=1)

    keep = [
        "country",
        "observation_date",
        "price_local",
        "currency",
        "unit",
        "fuel_family",
        "fuel_product",
        "quality_group",
        "location",
    ]
    df = df[keep].copy()
    df = df.sort_values("observation_date")

    result = {}
    for country, grp in df.groupby("country"):
        result[country] = df_to_json(grp)

    return result


def gen_fuel_html(all_data: dict, out: Path):
    countries = sorted(all_data.keys())
    palette_json = json.dumps(PALETTE)
    data_json = json.dumps(all_data)
    country_opts = "\n".join(f'<option value="{c}">{c}</option>' for c in countries)

    # shared_js is a raw string — single braces are literal JS braces
    shared_js = r"""
        const LABELS = {
            diesel: "Diesel", gasoline: "Gasoline", lpg: "LPG",
            kerosene: "Kerosene", fuel_oil: "Fuel Oil",
            natural_gas: "Natural Gas", town_gas: "Town Gas",
            premium: "Premium", regular: "Regular",
            premix: "Premix", super_premium: "Super Premium",
        };
        function lbl(v) { return (v && LABELS[v]) ? LABELS[v] : (v || "—"); }

        function chipKey(r) {
            return r.fuel_family + "|||" + (r.fuel_product || "") + "|||" + (r.quality_group || "");
        }
        function chipLabel(key) {
            var parts = key.split("|||");
            var fam  = lbl(parts[0]);
            var prod = parts[1] || "";
            var q    = parts[2] || "";
            var label = fam;
            if (prod) label += " \u2013 " + prod;
            if (q)    label += " (" + lbl(q) + ")";
            return label;
        }

        // 90-day calendar rolling mean on [{x,y}] sorted ascending
        function computeMA90(points) {
            var result = [];
            for (var i = 0; i < points.length; i++) {
                var tEnd   = new Date(points[i].x).getTime();
                var tStart = tEnd - 90 * 86400000;
                var sum = 0, count = 0;
                for (var j = i; j >= 0; j--) {
                    var t = new Date(points[j].x).getTime();
                    if (t < tStart) break;
                    if (points[j].y != null) { sum += points[j].y; count++; }
                }
                result.push(count > 0 ? sum / count : null);
            }
            return result;
        }

        function isMA() {
            var el = document.querySelector('input[name="ma-toggle"]:checked');
            return el && el.value === "ma";
        }

        function applyMA(points) {
            if (!isMA()) return points;
            var smoothed = computeMA90(points);
            return points.map(function(p, i) { return { x: p.x, y: smoothed[i] }; });
        }

        function getCheckedValues(containerId) {
            return Array.from(
                document.querySelectorAll("#" + containerId + " input:checked")
            ).map(function(cb) { return cb.value; });
        }

        function buildChips(containerId, keys) {
            var c = document.getElementById(containerId);
            c.innerHTML = "";
            keys.forEach(function(key) {
                var lel = document.createElement("label");
                lel.className = "chip";
                var cb = document.createElement("input");
                cb.type = "checkbox"; cb.value = key; cb.checked = true;
                cb.addEventListener("change", rerender);
                lel.appendChild(cb);
                lel.appendChild(document.createTextNode(chipLabel(key)));
                c.appendChild(lel);
            });
        }

        // Average raw [{x,y}] across locations by date
        function buildNationalAvg(locSeries) {
            var byDate = {};
            Object.keys(locSeries).forEach(function(loc) {
                locSeries[loc].forEach(function(pt) {
                    if (pt.y == null) return;
                    if (!byDate[pt.x]) byDate[pt.x] = { sum: 0, count: 0 };
                    byDate[pt.x].sum   += pt.y;
                    byDate[pt.x].count += 1;
                });
            });
            return Object.keys(byDate).sort().map(function(d) {
                return { x: d, y: byDate[d].sum / byDate[d].count };
            });
        }

        // locDataStore: chipKey -> { locName: [{x,y}...] } for multi-location chips
        var locDataStore = {};

        function buildLocTable(key) {
            var wrap = document.getElementById("loc-table-wrap");
            if (!key || !locDataStore[key]) { wrap.innerHTML = ""; return; }
            var locMap = locDataStore[key];
            var locs   = Object.keys(locMap);

            // Get most-recent RAW price per location
            var entries = locs.map(function(loc) {
                var pts  = locMap[loc];
                var last = pts.length ? pts[pts.length - 1] : null;
                return { loc: loc, val: last ? last.y : null };
            });

            // Add national average (raw)
            var avgPts  = buildNationalAvg(locMap);
            var lastAvg = avgPts.length ? avgPts[avgPts.length - 1] : null;
            entries.push({ loc: "National Average", val: lastAvg ? lastAvg.y : null, isAvg: true });

            // Sort highest to lowest (nulls last)
            entries.sort(function(a, b) {
                if (a.val == null && b.val == null) return 0;
                if (a.val == null) return 1;
                if (b.val == null) return -1;
                return b.val - a.val;
            });

            // Determine currency/unit label
            var allRows = window._countryRows || [];
            var keyRows = allRows.filter(function(r) { return chipKey(r) === key; });
            var cu = keyRows.length ? ((keyRows[0].currency || "") + "/" + (keyRows[0].unit || "")) : "";

            var html = "<table id='loc-table'><thead><tr>" +
                "<th>Location</th><th>Price (" + cu + ")</th>" +
                "</tr></thead><tbody>";
            entries.forEach(function(e) {
                var cls = e.isAvg ? " class='nat-avg-row'" : "";
                var val = e.val != null ? e.val.toFixed(2) : "\u2014";
                html += "<tr" + cls + "><td>" + e.loc + "</td><td>" + val + "</td></tr>";
            });
            html += "</tbody></table>";
            wrap.innerHTML = html;
        }

        function rebuildLocToggles(multiKeys) {
            var sec  = document.getElementById("loc-table-section");
            var togs = document.getElementById("loc-table-toggles");
            togs.innerHTML = "";
            if (!multiKeys.length) { sec.style.display = "none"; return; }
            sec.style.display = "";

            multiKeys.forEach(function(key, idx) {
                var lel = document.createElement("label");
                var rb  = document.createElement("input");
                rb.type  = "radio";
                rb.name  = "loc-tab";
                rb.value = key;
                if (idx === 0) rb.checked = true;
                rb.addEventListener("change", function() { buildLocTable(rb.value); });
                lel.appendChild(rb);
                lel.appendChild(document.createTextNode(chipLabel(key)));
                togs.appendChild(lel);
            });

            buildLocTable(multiKeys[0]);
        }

        function makeDataset(label, points, color, isGray) {
            var pts = applyMA(points);
            return {
                label:            label,
                data:             pts,
                borderColor:      isGray ? "#cccccc" : color,
                backgroundColor:  isGray ? "#cccccc" : color,
                borderWidth:      isGray ? 1 : 1.8,
                fill:             false,
                tension:          0.1,
                pointRadius:      0,
                pointHoverRadius: isGray ? 3 : 5,
                spanGaps:         false,
                _isGray:          isGray,
            };
        }

        function updateMeta(rows) {
            var panel = document.getElementById("meta-panel");
            if (!rows || !rows.length) { panel.innerHTML = ""; return; }
            var dates = rows.map(function(r) { return r.observation_date; }).sort();
            panel.innerHTML = "<strong>Date Range:</strong> " +
                dates[0] + " \u2013 " + dates[dates.length - 1];
        }

        function drawChart(datasets, yLabel) {
            var ctx = document.getElementById("chart").getContext("2d");
            if (window.currentChart) window.currentChart.destroy();
            if (!datasets.length) { window.currentChart = null; return; }

            window.currentChart = new Chart(ctx, {
                type: "line",
                data: { datasets: datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: "top",
                            labels: {
                                usePointStyle: true, padding: 14,
                                font: { size: 11 },
                                filter: function(item) {
                                    return !datasets[item.datasetIndex]._isGray;
                                }
                            }
                        },
                        tooltip: {
                            mode: "index",
                            intersect: false,
                            backgroundColor: "rgba(0,0,0,0.82)",
                            padding: 12,
                            filter: function(item) {
                                return !datasets[item.datasetIndex]._isGray;
                            },
                            callbacks: {
                                title: function(items) {
                                    return items.length ? items[0].raw.x : "";
                                },
                                label: function(item) {
                                    var val = item.raw ? item.raw.y : null;
                                    if (val == null) return null;
                                    return datasets[item.datasetIndex].label + ": " + val.toFixed(2);
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            type: "time",
                            time: { unit: "month", tooltipFormat: "yyyy-MM-dd" },
                            display: true,
                            title: { display: true, text: "Date" }
                        },
                        y: {
                            display: true,
                            title: { display: true, text: yLabel }
                        }
                    }
                }
            });
        }
    """

    # script is an f-string — JS braces doubled
    script = f"""
        const palette = {palette_json};
        const allData = {data_json};

        {shared_js}

        function getCountryRows() {{
            return allData[document.getElementById("country-select").value] || [];
        }}

        function rebuildChips() {{
            var rows = getCountryRows();
            var keys = [...new Set(rows.map(chipKey))].sort();
            buildChips("axis-chips", keys);
        }}

        function rerender() {{
            var rows         = getCountryRows();
            window._countryRows = rows;
            var selectedKeys = getCheckedValues("axis-chips");
            var visibleRows  = rows.filter(function(r) {{
                return selectedKeys.includes(chipKey(r));
            }});

            updateMeta(visibleRows);
            if (!visibleRows.length) {{ drawChart([], ""); rebuildLocToggles([]); return; }}

            var firstRow = visibleRows[0];
            var yLabel   = (firstRow.currency || "") + " / " + (firstRow.unit || "");

            var datasets  = [];
            var colorIdx  = 0;
            var multiKeys = [];
            locDataStore  = {{}};

            selectedKeys.forEach(function(key) {{
                var keyRows = visibleRows.filter(function(r) {{ return chipKey(r) === key; }});
                if (!keyRows.length) return;

                var locMap = {{}};
                keyRows.forEach(function(r) {{
                    var loc = r.location || "National";
                    if (!locMap[loc]) locMap[loc] = [];
                    locMap[loc].push({{ x: r.observation_date, y: r.price_local }});
                }});
                Object.keys(locMap).forEach(function(loc) {{
                    locMap[loc].sort(function(a, b) {{ return a.x.localeCompare(b.x); }});
                }});

                var locs   = Object.keys(locMap);
                var color  = palette[colorIdx % palette.length];
                var serLbl = chipLabel(key);
                colorIdx++;

                if (locs.length === 1) {{
                    datasets.push(makeDataset(serLbl, locMap[locs[0]], color, false));
                }} else {{
                    locDataStore[key] = locMap;
                    multiKeys.push(key);
                    var avgPts = buildNationalAvg(locMap);
                    datasets.push(makeDataset(serLbl + " (Nat. Avg.)", avgPts, color, false));
                    locs.sort().forEach(function(loc) {{
                        datasets.push(makeDataset(serLbl + " \u2014 " + loc, locMap[loc], color, true));
                    }});
                }}
            }});

            drawChart(datasets, yLabel);
            rebuildLocToggles(multiKeys.filter(function(k) {{ return selectedKeys.includes(k); }}));
        }}

        document.getElementById("country-select").addEventListener("change", function() {{
            rebuildChips();
            rerender();
        }});
        document.querySelectorAll('input[name="ma-toggle"]').forEach(function(r) {{
            r.addEventListener("change", rerender);
        }});

        rebuildChips();
        rerender();
    """

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Fuel Prices — East Asia &amp; Pacific</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
    <style>{_CSS}</style>
</head>
<body>
    <div class="ctrl-row">
        <span class="row-label">Country:</span>
        <select id="country-select">{country_opts}</select>
    </div>
    <div class="ctrl-row">
        <span class="row-label">Smoothing:</span>
        <div class="toggle-group">
            <label><input type="radio" name="ma-toggle" value="raw" checked>Raw</label>
            <label><input type="radio" name="ma-toggle" value="ma">3-Mo MA</label>
        </div>
    </div>
    <div class="section-label">Fuel Family:</div>
    <div class="chip-container" id="axis-chips"></div>
    <div id="meta-panel"></div>
    <div class="chart-wrapper"><canvas id="chart"></canvas></div>
    <div id="loc-table-section" style="display:none">
        <div class="section-label">Location Prices:</div>
        <div id="loc-table-toggles"></div>
        <div id="loc-table-wrap"></div>
    </div>
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
    all_data = load_fuel_data(data_dir / "eap_fuel_prices_pilot_safe.csv")
    gen_fuel_html(all_data, data_dir / "fuel_prices_safe.html")


if __name__ == "__main__":
    main()
