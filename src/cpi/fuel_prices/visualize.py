"""Generate standalone HTML interactive fuel prices visualization."""

import json
from pathlib import Path

from .constants import PALETTE


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
        min-width: 200px;
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


def gen_fuel_html(all_data: dict, out: Path) -> None:
    """Write a standalone interactive HTML file from the per-country data dict."""
    countries = sorted(all_data.keys())
    palette_json = json.dumps(PALETTE)
    data_json = json.dumps(all_data)
    country_opts = "\n".join(f'<option value="{c}">{c}</option>' for c in countries)

    shared_js = r"""
        const LABELS = {
            diesel: "Diesel", gasoline: "Gasoline", lpg: "LPG",
            kerosene: "Kerosene", fuel_oil: "Fuel Oil",
            natural_gas: "Natural Gas", town_gas: "Town Gas",
            premium: "Premium", regular: "Regular",
            premix: "Premix", super_premium: "Super Premium",
            octane_95: "Premium",
        };
        function lbl(v) { return (v && LABELS[v]) ? LABELS[v] : (v || "—"); }

        function chipKey(r) {
            return r.fuel_family + "|||" + (r.fuel_product || "") + "|||" + (r.quality_group || "");
        }

        function cleanProdDisplay(prod) {
            var s = prod
                .replace(/\s+average$/i, "")
                .replace(/\(regular\)/gi, "(Regular)")
                .replace(/\bgasoline\b/g, "Gasoline")
                .replace(/\bdiesel\b/g, "Diesel")
                .replace(/\bpetrol\b/g, "Petrol")
                .trim();
            return s.length ? s[0].toUpperCase() + s.slice(1) : s;
        }

        function qualityRedundant(displayProd, q) {
            if (!q || !displayProd) return false;
            var p = displayProd.toLowerCase();
            if (q === "regular" && /regular|unleaded|low[\s-]sulphur|propane/.test(p)) return true;
            if (q === "premium" && /premium|high[\s-]octane|octane[\s-]?9[0-9]|ron[\s-]?9[0-9]|95r/.test(p)) return true;
            if (q === "super_premium" && /turbo|dex$/.test(p)) return true;
            return false;
        }

        function getAmbiguousProds(rows) {
            var prodFamilies = {};
            rows.forEach(function(r) {
                var p = r.fuel_product || "";
                if (!prodFamilies[p]) prodFamilies[p] = {};
                prodFamilies[p][r.fuel_family] = true;
            });
            var ambiguous = {};
            Object.keys(prodFamilies).forEach(function(p) {
                if (Object.keys(prodFamilies[p]).length > 1) ambiguous[p] = true;
            });
            return ambiguous;
        }

        var _ambiguousProds = {};
        let sliderDates = [];
        let slider = null;

        function formatYM(d) {
            const date = new Date(d);
            return date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0') + '-' + String(date.getDate()).padStart(2, '0');
        }

        function getSliderRange() {
            if (!slider || !sliderDates.length) return { from: '', to: '' };
            const vals = slider.get().map(v => Math.round(v));
            return { from: sliderDates[vals[0]], to: sliderDates[vals[1]] };
        }

        function initSlider() {
            var rows = getCountryRows();
            if (!rows || !rows.length) return;
            var dateSet = {};
            rows.forEach(function(r) { dateSet[r.observation_date] = true; });
            sliderDates = Object.keys(dateSet).sort();
            const maxIdx = sliderDates.length - 1;
            if (maxIdx < 0) return;
            const el = document.getElementById('date-slider');
            if (slider) { slider.destroy(); }
            slider = noUiSlider.create(el, {
                start: [0, maxIdx],
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
            slider.on('update', function() { updateLabel(); });
            slider.on('change', function() { rerender(); });
        }

        function chipLabel(key) {
            var parts       = key.split("|||");
            var famRaw      = parts[0] || "";
            var prodRaw     = parts[1] || "";
            var qRaw        = parts[2] || "";
            var displayProd = prodRaw ? cleanProdDisplay(prodRaw) : "";
            var label;
            if (displayProd) {
                label = _ambiguousProds[prodRaw]
                    ? lbl(famRaw) + " \u2013 " + displayProd
                    : displayProd;
            } else {
                label = lbl(famRaw);
            }
            if (qRaw && !qualityRedundant(displayProd || label, qRaw)) {
                label += " (" + lbl(qRaw) + ")";
            }
            return label;
        }

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

        function buildChips(containerId, keys, rows) {
            _ambiguousProds = getAmbiguousProds(rows || []);
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

        var locDataStore = {};

        function buildLocTable(key) {
            var wrap = document.getElementById("loc-table-wrap");
            if (!key || !locDataStore[key]) { wrap.innerHTML = ""; return; }
            var locMap = locDataStore[key];
            var locs   = Object.keys(locMap);
            var entries = locs.map(function(loc) {
                var pts  = locMap[loc];
                var last = pts.length ? pts[pts.length - 1] : null;
                return { loc: loc, val: last ? last.y : null };
            });
            var avgPts  = buildNationalAvg(locMap);
            var lastAvg = avgPts.length ? avgPts[avgPts.length - 1] : null;
            entries.push({ loc: "National Average", val: lastAvg ? lastAvg.y : null, isAvg: true });
            entries.sort(function(a, b) {
                if (a.val == null && b.val == null) return 0;
                if (a.val == null) return 1;
                if (b.val == null) return -1;
                return b.val - a.val;
            });
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
            var allRows = window._countryRows || [];
            var visRows = allRows.filter(function(r) { return multiKeys.includes(chipKey(r)); });
            var lastDate = visRows.reduce(function(m, r) { return r.observation_date > m ? r.observation_date : m; }, "");
            var secLabel = sec.querySelector(".section-label");
            if (secLabel) secLabel.textContent = lastDate ? "Location Prices for " + lastDate : "Location Prices:";
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
                borderColor:      isGray ? "#e8e8e8" : color,
                backgroundColor:  isGray ? "#e8e8e8" : color,
                borderWidth:      isGray ? 1 : 1.8,
                fill:             false,
                tension:          0.1,
                pointRadius:      0,
                pointHoverRadius: isGray ? 3 : 5,
                spanGaps:         false,
                order:            isGray ? 2 : 1,
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
                                title: function(items) { return items.length ? items[0].raw.x : ""; },
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
            buildChips("axis-chips", keys, rows);
        }}

        function rerender() {{
            var rows         = getCountryRows();
            window._countryRows = rows;
            var selectedKeys = getCheckedValues("axis-chips");
            var visibleRows  = rows.filter(function(r) {{
                return selectedKeys.includes(chipKey(r));
            }});
            var range = getSliderRange();
            if (range.from) {{
                visibleRows = visibleRows.filter(function(r) {{ return r.observation_date >= range.from; }});
            }}
            if (range.to) {{
                visibleRows = visibleRows.filter(function(r) {{ return r.observation_date <= range.to; }});
            }}
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
            initSlider();
            rerender();
        }});
        document.querySelectorAll('input[name="ma-toggle"]').forEach(function(r) {{
            r.addEventListener("change", rerender);
        }});

        rebuildChips();
        initSlider();
        rerender();
    """

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Fuel Prices — East Asia &amp; Pacific</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/nouislider@15.7.1/dist/nouislider.min.css">
    <script src="https://cdn.jsdelivr.net/npm/nouislider@15.7.1/dist/nouislider.min.js"></script>
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
    <div class="slider-row">
        <label>Date Range:</label>
        <span id="range-label">&mdash;</span>
        <div id="date-slider"></div>
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
