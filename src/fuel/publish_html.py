import html as _html
import json
from datetime import datetime, timezone
from pathlib import Path

VENDOR_DIR = Path(__file__).resolve().parent / "vendor"
_VENDOR_CACHE: dict[str, str] = {}


def _vendor(name: str) -> str:
    if name not in _VENDOR_CACHE:
        _VENDOR_CACHE[name] = (VENDOR_DIR / name).read_text(encoding="utf-8")
    return _VENDOR_CACHE[name]


PALETTE = [
    "#667eea",
    "#e6ab02",
    "#d62728",
    "#2ca02c",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#17becf",
    "#ff7f0e",
    "#1f77b4",
    "#bcbd22",
    "#7f7f7f",
    "#aec7e8",
    "#ffbb78",
    "#98df8a",
    "#ff9896",
    "#c5b0d5",
    "#c49c94",
    "#f7b6d2",
    "#c7c7c7",
]

_CSS = """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        padding: 12px 20px;
        background: #fff;
        max-width: 1100px;
    }
    h1 { font-size: 1.15em; font-weight: 700; color: #222; margin-bottom: 12px; }
    .tab-bar {
        display: flex; gap: 0; margin-bottom: 16px;
        border-bottom: 2px solid #e0e0e0;
    }
    .tab-btn {
        padding: 8px 22px; border: none; background: none; cursor: pointer;
        font-size: 0.92em; font-weight: 600; color: #888;
        border-bottom: 3px solid transparent; margin-bottom: -2px;
        transition: all 0.15s;
    }
    .tab-btn.active { color: #667eea; border-bottom-color: #667eea; }
    .tab-btn:hover:not(.active) { color: #444; }
    .tab-pane { display: none; }
    .tab-pane.active { display: block; }
    .ctrl-row {
        display: flex; align-items: center; gap: 8px;
        flex-wrap: wrap; margin-bottom: 8px;
    }
    .row-label {
        font-weight: 600; color: #333; font-size: 0.9em;
        white-space: nowrap; min-width: 80px;
    }
    .chip-container {
        display: flex; flex-wrap: wrap; gap: 5px;
        margin-bottom: 8px; max-height: 100px; overflow-y: auto; padding: 2px 0;
    }
    .chip {
        display: inline-flex; align-items: center; gap: 4px;
        padding: 3px 10px; border: 1px solid #ddd; border-radius: 16px;
        font-size: 0.8em; font-weight: 400; cursor: pointer;
        user-select: none; transition: all 0.15s; white-space: nowrap;
    }
    .chip:hover { border-color: #667eea; background: #f0f4ff; }
    .chip input[type="checkbox"] { display: none; }
    .chip:has(input:checked) { background: #667eea; color: #fff; border-color: #667eea; }
    .section-label {
        font-weight: 600; color: #333; font-size: 0.9em; margin-bottom: 4px; margin-top: 6px;
    }
    .chart-wrapper { position: relative; height: 420px; margin-top: 8px; }
    .slider-row {
        display: flex; align-items: center; gap: 10px; margin-bottom: 10px; overflow: visible;
    }
    .slider-row label {
        font-weight: 600; color: #333; font-size: 0.95em; white-space: nowrap;
    }
    #range-label {
        font-size: 0.85em; color: #555; min-width: 200px;
        text-align: center; white-space: nowrap;
    }
    #date-slider { flex: 1; min-width: 200px; }
    .noUi-connect { background: #667eea !important; }
    .noUi-handle { border-color: #667eea !important; box-shadow: none !important; }
    .noUi-tooltip {
        font-size: 0.75em; padding: 2px 6px; background: #667eea;
        color: #fff; border: none; border-radius: 4px;
        bottom: auto !important; top: 120% !important;
    }
    .regime-table-wrap { overflow-x: auto; margin-top: 14px; }
    .regime-table {
        border-collapse: collapse; font-size: 0.82em; min-width: 500px; width: 100%;
    }
    .regime-table th, .regime-table td {
        padding: 5px 14px; text-align: left; border-bottom: 1px solid #eee;
    }
    .regime-table th { font-weight: 600; background: #f7f7f7; }
    .regime-table tr:hover td { background: #f8f8ff; }
    .regime-badge {
        display: inline-block; padding: 2px 9px; border-radius: 12px;
        font-size: 0.78em; font-weight: 600; color: #fff; white-space: nowrap;
        cursor: default;
    }
    .regime-pill {
        display: inline-block; padding: 2px 9px; border-radius: 12px;
        font-size: 0.78em; font-weight: 600; color: #fff; white-space: nowrap;
        border: 1px solid transparent; cursor: pointer; font-family: inherit;
        vertical-align: middle;
    }
    .regime-pill:hover { filter: brightness(1.08); border-color: rgba(0,0,0,0.18); }
    .regime-pill:focus-visible { outline: 2px solid #667eea; outline-offset: 1px; }
    .regime-pill.regime-reform {
        background: transparent !important; color: #555;
        border: 1px dashed #b0b0b0; font-weight: 500;
    }
    .regime-pill.regime-reform:hover { color: #222; border-color: #667eea; }
    .regime-chip {
        display: inline-flex; white-space: nowrap; vertical-align: middle;
    }
    .regime-chip > .regime-pill { border-radius: 0; }
    .regime-chip > .regime-pill:first-child {
        border-top-left-radius: 12px; border-bottom-left-radius: 12px;
    }
    .regime-chip > .regime-pill:last-child {
        border-top-right-radius: 12px; border-bottom-right-radius: 12px;
    }
    .regime-chip > .regime-pill:not(:last-child) {
        border-right: 1px solid rgba(255,255,255,0.55);
    }
    .regime-hint {
        font-size: 0.84em; color: #777; font-style: italic;
        margin: 4px 0 8px 0;
    }
    .regime-popover {
        position: absolute; max-width: 340px; background: #fff;
        border: 1px solid #d0d0d0; border-radius: 6px;
        box-shadow: 0 4px 14px rgba(0,0,0,0.12);
        padding: 10px 12px; font-size: 0.82em; color: #333; line-height: 1.4;
        z-index: 9999;
    }
    .regime-popover .tip-title {
        font-weight: 700; font-size: 0.92em; margin-bottom: 6px; color: #222;
    }
    .regime-popover ul { margin: 4px 0 0 0; padding-left: 18px; }
    .regime-popover li { margin: 3px 0; }
    .regime-popover a { color: #4855c9; text-decoration: underline; }
    .regime-popover p { margin: 4px 0; }
    .regime-tip-source { display: none; }
    .chart-title {
        font-size: 1.04em; font-weight: 600; color: #222;
        margin: 14px 0 2px 0;
    }
    #tab3 .chart-title { margin: 18px 0 14px 0; }
    .chart-source {
        font-size: 0.78em; color: #888; margin: 0 0 8px 0;
    }
    .chart-source a { color: #667eea; text-decoration: none; }
    .chart-source a:hover { text-decoration: underline; }
    .panel-label {
        font-size: 0.86em; font-weight: 600; color: #555;
        margin: 10px 0 2px 0;
    }
    .regime-glossary {
        font-size: 0.84em; color: #555; margin: 4px 0 6px 0;
    }
    .regime-glossary summary {
        cursor: pointer; color: #667eea; user-select: none; padding: 2px 0;
    }
    .regime-glossary summary:hover { text-decoration: underline; }
    .regime-glossary ul { margin: 4px 0 4px 0; padding-left: 22px; }
    .regime-glossary li { margin: 2px 0; }
    .kpi-row { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 16px; }
    .kpi-card {
        flex: 1; min-width: 180px; padding: 14px 18px;
        border: 1px solid #e8e8e8; border-radius: 8px; background: #fafafa;
    }
    .kpi-value { font-size: 1.6em; font-weight: 700; color: #222; line-height: 1.1; }
    .kpi-label { font-size: 0.78em; color: #666; margin-top: 3px; }
    .scatter-wrapper { position: relative; height: 480px; margin-top: 8px; }
    .toggle-group {
        display: inline-flex; flex-wrap: wrap;
    }
    .toggle-group label {
        padding: 4px 12px; border: 1px solid #ddd; font-size: 0.82em;
        cursor: pointer; user-select: none; transition: all 0.15s;
        margin-left: -1px; white-space: nowrap;
    }
    .toggle-group label:first-child { margin-left: 0; border-radius: 16px 0 0 16px; }
    .toggle-group label:last-child  { border-radius: 0 16px 16px 0; }
    .toggle-group input[type="radio"] { display: none; }
    .toggle-group label:has(input:checked) {
        background: #667eea; color: #fff; border-color: #667eea;
        z-index:1; position:relative;
    }
    .toggle-group label:hover:not(:has(input:checked)) {
        border-color: #667eea; background: #f0f4ff;
    }
    .legend-row { display: flex; gap: 14px; flex-wrap: wrap; margin: 8px 0; }
    .legend-item { display: flex; align-items: center; gap: 5px; font-size: 0.82em; }
    .legend-dot { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }
    #fuel-country-select {
        padding: 6px 10px; border: 1px solid #ddd; border-radius: 4px;
        font-size: 0.9em; cursor: pointer; background: #fff;
    }
    #fuel-country-select:hover, #fuel-country-select:focus {
        border-color: #667eea; outline: 0;
    }
    #fuel-range-label {
        font-size: 0.85em; color: #555; min-width: 200px;
        text-align: center; white-space: nowrap;
    }
    #fuel-date-slider { flex: 0 1 55%; min-width: 140px; max-width: 55%; }
    #fuel-regime-section {
        margin: 8px 0 4px 0;
        padding: 8px 10px;
    }
    #fuel-regime-section .section-label { margin-top: 0; }
    .fuel-regime-grid {
        display: grid;
        grid-template-columns: 140px 1fr 1fr;
        gap: 0;
        align-items: start;
        border: 1px solid #e1e1e1;
        border-radius: 4px;
        overflow: hidden;
    }
    .fuel-regime-grid > div {
        padding: 4px 6px;
        border-top: 1px solid #e1e1e1;
        border-left: 1px solid #e1e1e1;
    }
    .fuel-regime-grid > div:nth-child(-n+3) { border-top: none; }
    .fuel-regime-grid > div:nth-child(3n+1) { border-left: none; }
    .fuel-regime-grid .grid-header {
        font-size: 0.82em;
        font-weight: 700;
        color: #555;
        text-align: left;
    }
    .fuel-regime-grid .row-label {
        font-size: 0.84em;
        font-weight: 600;
        color: #555;
    }
    .fuel-regime-cell {
        min-height: 22px;
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        align-items: center;
    }
    .fuel-regime-cell .regime-badge {
        font-size: 0.78em;
        padding: 3px 10px;
        font-weight: 600;
    }
    #fuel-meta-panel { font-size: 0.88em; color: #555; margin: 4px 0; line-height: 1.7; }
    .delta-chart-wrapper { position: relative; height: 180px; margin-top: 12px; }
    #compare-date-slider { flex: 0 1 55%; min-width: 140px; max-width: 55%; }
    #compare-range-label {
        font-size: 0.85em; color: #555; min-width: 200px;
        text-align: center; white-space: nowrap;
    }
    .compare-chart-wrapper { position: relative; height: 700px; margin-top: 8px; }
    #compare-breakdown-toggle {
        font-size: 0.82em; color: #667eea; cursor: pointer;
        user-select: none; margin: 4px 0 2px 0; display: inline-block;
    }
    #compare-breakdown-toggle:hover { text-decoration: underline; }
    #compare-product-breakdown {
        font-size: 0.78em; color: #555; line-height: 1.7;
        padding: 6px 10px; border: 1px solid #eee; border-radius: 4px;
        margin-bottom: 8px; background: #fafafa;
    }
"""


def gen_policy_html(
    data: dict,
    fuel_data: dict[str, list[dict]],
    usd_data: dict[str, list[dict]],
    out: Path,
    region_label: str,
) -> None:
    comm_series = data["comm_series"]
    region_countries = data["region_countries"]
    scatter = data["scatter"]
    regime_colors = data["regime_colors"]
    product_regimes = data.get("product_regimes", {})
    table_products = data.get("table_products", [])
    products = data.get("products", [])
    imf_raw_by_iso3 = data.get("imf_raw_by_iso3", {})
    regime_notes = data.get("regime_notes", {})

    region_isos = sorted(data.get("region_isos", []))
    region_isos_json = json.dumps(region_isos)

    # Enrich fuel_data records with price_usd from usd_data.
    fuel_data_enriched: dict[str, list[dict]] = {}
    for country, records in fuel_data.items():
        usd_records = usd_data.get(country, [])
        usd_lookup: dict[tuple[str, str], float] = {}
        for ur in usd_records:
            key = (
                str(ur.get("observation_date", ""))[:10],
                ur.get("fuel_family", ""),
            )
            if ur.get("price_usd") is not None:
                usd_lookup[key] = ur["price_usd"]

        enriched = []
        for r in records:
            rec = dict(r)
            if rec.get("price_usd") is None:
                usd_key = (
                    str(rec.get("observation_date", ""))[:10],
                    rec.get("fuel_family", ""),
                )
                usd_price = usd_lookup.get(usd_key)
                if usd_price is not None:
                    rec["price_usd"] = usd_price
            enriched.append(rec)
        fuel_data_enriched[country] = enriched

    comm_json = json.dumps(json.dumps(comm_series))
    scatter_json = json.dumps(json.dumps(scatter))
    colors_json = json.dumps(regime_colors)
    palette_json = json.dumps(PALETTE)
    fuel_data_json = json.dumps(json.dumps(fuel_data_enriched))
    product_regimes_json = json.dumps(product_regimes)
    fuel_countries = sorted(fuel_data_enriched.keys())
    fuel_country_opts = "\n".join(
        f'<option value="{c}">{c}</option>' for c in fuel_countries
    )
    products_json = json.dumps(products)
    _build_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    # --- Tab 4: fuel families with 2+ countries having USD data ---
    _FAMILY_LABELS = {
        "diesel": "Diesel",
        "gasoline": "Gasoline",
        "lpg": "LPG",
        "kerosene": "Kerosene",
        "natural_gas": "Natural Gas",
        "fuel_oil": "Fuel Oil",
        "electricity": "Electricity",
        "crude_oil": "Crude Oil",
    }
    _family_country_counts: dict[str, set[str]] = {}
    for _country, _records in fuel_data_enriched.items():
        for _r in _records:
            _ff = _r.get("fuel_family")
            _unit = _r.get("unit")
            if (
                _ff
                and _r.get("price_usd") is not None
                and (_unit == "L" or (_ff == "lpg" and _unit == "kg"))
            ):
                _family_country_counts.setdefault(_ff, set()).add(_country)
    _available_families = [
        (ff, _FAMILY_LABELS.get(ff, ff.title()))
        for ff in _FAMILY_LABELS
        if len(_family_country_counts.get(ff, set())) >= 2
    ]
    compare_family_radios_html = ""
    for _ff_key, _ff_label in _available_families:
        checked = "checked" if _ff_key == "diesel" else ""
        compare_family_radios_html += (
            f'<label><input type="radio" name="compare-family-toggle" value="{_ff_key}" '
            f'{checked} onchange="setCompareFamily(this.value)">{_ff_label}</label>\n'
        )

    # --- Regime table rows ---
    prod_headers = "".join(f"<th>{p}</th>" for p in table_products)
    _BASE_COLORS = {
        "Market": regime_colors.get("Market", "#6c757d"),
        "Price Control": regime_colors.get("Price Control", "#d62728"),
        "Unknown": regime_colors.get("Unknown", "#aec7e8"),
    }
    _SUBSIDY_COLOR = "#2196f3"

    def _src_entry_html(entry) -> str:
        if isinstance(entry, dict):
            label = _html.escape(str(entry.get("label", entry.get("url", ""))))
            url = entry.get("url")
            if url:
                return (
                    f'<a href="{_html.escape(str(url), quote=True)}" '
                    f'target="_blank" rel="noopener">{label}</a>'
                )
            return label
        return _html.escape(str(entry))

    def _sources_ul(items) -> str:
        if not items:
            return ""
        lis = "".join(f"<li>{_src_entry_html(e)}</li>" for e in items)
        return f"<ul>{lis}</ul>"

    popover_blocks: list[str] = []

    regime_rows_html = ""
    for c in sorted(
        region_countries, key=lambda x: x.get("country", x.get("country_name", ""))
    ):
        name = c.get("country", c.get("country_name", ""))
        iso3 = c.get("wb_iso3", "")
        tip = _html.escape(str(c.get("tooltip", "")), quote=True)
        tooltip_attr = f' title="{tip}"' if tip and tip.lower() != "nan" else ""

        per_prod = product_regimes.get(iso3, {})
        imf_raw_country = imf_raw_by_iso3.get(iso3, {})
        notes_country = regime_notes.get(iso3, {})
        prod_cells = ""
        for prod in table_products:
            info = per_prod.get(prod)
            if info is None:
                prod_cells += "<td></td>"
                continue
            base = (
                info.get("regime", "Unknown") if isinstance(info, dict) else str(info)
            )
            if base == "Unknown":
                prod_cells += "<td></td>"
                continue
            imf_val = imf_raw_country.get(prod)
            subsidy = imf_val is not None and imf_val > 0
            bc = _BASE_COLORS.get(base, "#aec7e8")
            base_label = "Price Controlled" if base == "Price Control" else base

            note_for_prod = notes_country.get(prod) or {}
            cls_sources = note_for_prod.get("classification_sources") or []

            primary_tip_id = f"tip-{iso3}-{prod}-primary"
            primary_tip_body = f'<div class="tip-title">{_html.escape(name)} · {_html.escape(prod)} · {base_label}</div>'
            if cls_sources:
                primary_tip_body += _sources_ul(cls_sources)
            else:
                primary_tip_body += (
                    "<p>Classification source: World Bank Energy Pricing Regimes Dataset "
                    "(2024 reference year).</p>"
                )
            popover_blocks.append(
                f'<div id="{primary_tip_id}" class="regime-tip-source">{primary_tip_body}</div>'
            )

            chip_inner = (
                f'<button type="button" class="regime-pill" '
                f'style="background:{bc}" data-tip-id="{primary_tip_id}"'
                f"{tooltip_attr}>{base_label}</button>"
            )

            if subsidy:
                subs_tip_id = f"tip-{iso3}-{prod}-subsidy"
                subs_tip_body = (
                    f'<div class="tip-title">{_html.escape(name)} · {_html.escape(prod)} · Subsidised</div>'
                    "<p>The IMF Fossil Fuel Subsidies Database reports a positive "
                    "<i>implicit</i> subsidy for this product (retail price below supply cost, "
                    "externalities, or standard consumption tax).</p>"
                    "<ul><li>"
                    '<a href="https://www.imf.org/en/Topics/climate-change/energy-subsidies" '
                    'target="_blank" rel="noopener">'
                    "IMF Fossil Fuel Subsidies Database (2025 release, 2024 reference year)"
                    "</a></li></ul>"
                )
                popover_blocks.append(
                    f'<div id="{subs_tip_id}" class="regime-tip-source">{subs_tip_body}</div>'
                )
                chip_inner += (
                    f'<button type="button" class="regime-pill" '
                    f'style="background:{_SUBSIDY_COLOR}" '
                    f'data-tip-id="{subs_tip_id}">Subsidised</button>'
                )

            cell_html = f'<span class="regime-chip">{chip_inner}</span>'

            reform = note_for_prod.get("reform") or {}
            if reform:
                ref_tip_id = f"tip-{iso3}-{prod}-reform"
                ref_label = _html.escape(str(reform.get("label", "Reform")))
                ref_note = _html.escape(str(reform.get("note", "")))
                ref_sources = reform.get("sources") or []
                ref_tip_body = (
                    f'<div class="tip-title">{_html.escape(name)} · {_html.escape(prod)} · {ref_label}</div>'
                    f"<p>{ref_note}</p>"
                )
                if ref_sources:
                    ref_tip_body += _sources_ul(ref_sources)
                popover_blocks.append(
                    f'<div id="{ref_tip_id}" class="regime-tip-source">{ref_tip_body}</div>'
                )
                cell_html += (
                    f' <button type="button" class="regime-pill regime-reform" '
                    f'data-tip-id="{ref_tip_id}">{ref_label}</button>'
                )

            prod_cells += f"<td>{cell_html}</td>"

        regime_rows_html += f"<tr><td>{name}</td>{prod_cells}</tr>\n"

    regime_popovers_html = "".join(popover_blocks)

    # --- Product radio buttons for Tab 2 ---
    product_radios_html = ""
    for i, prod in enumerate(products):
        checked = "checked" if i == 0 else ""
        product_radios_html += (
            f'<label><input type="radio" name="product-toggle" value="{prod}" '
            f'{checked} onchange="renderScatter()">{prod}</label>\n'
        )

    title_escaped = _html.escape(region_label)

    chartjs_inline = _vendor("chart.umd.min.js")
    adapter_inline = _vendor("chartjs-adapter-date-fns.bundle.min.js")
    noui_css_inline = _vendor("nouislider.min.css")
    noui_js_inline = _vendor("nouislider.min.js")

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Fuel Prices Overview &mdash; {title_escaped}</title>
    <script>{chartjs_inline}</script>
    <script>{adapter_inline}</script>
    <style>{noui_css_inline}</style>
    <script>{noui_js_inline}</script>
    <style>{_CSS}</style>
</head>
<body>
<h1>Fuel Prices Overview &mdash; {title_escaped}</h1>
<div id="last-updated" style="font-size:0.88em;color:#888;margin:-4px 0 10px 0" data-utc="{_build_utc}"></div>
<script>!function(){{var el=document.getElementById('last-updated'),u=el.dataset.utc;if(u){{var d=new Date(u+'Z');el.textContent='Last updated: '+d.toLocaleString(undefined,{{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}});}}}}();</script>

<div class="tab-bar">
    <button class="tab-btn active" onclick="switchTab('tab1',this)">Commodity Prices</button>
    <button class="tab-btn"       onclick="switchTab('tab2',this)">Country Subsidies</button>
    <button class="tab-btn"       onclick="switchTab('tab3',this)">Fuel Prices</button>
    <button class="tab-btn"       onclick="switchTab('tab4',this)">Cross-Economy Comparison</button>
</div>

<!-- ===== TAB 1 ===== -->
<div id="tab1" class="tab-pane active">

    <div class="chart-title">Trends in International Crude Oil and Refined Product Prices</div>
    <div class="chart-source">Source: <a href="https://www.investing.com/commodities/energy" target="_blank" rel="noopener">investing.com — Energy Commodities</a></div>

    <div class="ctrl-row">
        <span class="row-label">Products:</span>
    </div>
    <div class="chip-container" id="comm-chips"></div>

    <div class="slider-row">
        <label>Date Range:</label>
        <span id="range-label">&mdash;</span>
        <div id="date-slider"></div>
    </div>

    <div class="chart-wrapper"><canvas id="comm-chart"></canvas></div>

    <div class="chart-title" style="margin-top:18px">Country Pricing Regimes (2024)</div>
    <div class="regime-hint">Click any pill to see its source. Pills with a dashed outline mark recent reforms — click for details.</div>
    <details class="regime-glossary">
        <summary>Definitions</summary>
        <ul>
            <li><b>Market</b> — retail price set by suppliers without government control.</li>
            <li><b>Price Controlled</b> — government sets the retail price by regulation.</li>
            <li><b>Subsidised</b> — IMF Fossil Fuel Subsidies Database (2025 release, 2024 reference year) reports a positive implicit or explicit subsidy. Implicit = retail price below supply cost or excludes externalities and the standard consumption tax.</li>
        </ul>
    </details>
    <div class="regime-table-wrap">
        <table class="regime-table">
            <thead>
                <tr>
                    <th>Country</th>
                    {prod_headers}
                </tr>
            </thead>
            <tbody>{regime_rows_html}</tbody>
        </table>
    </div>
    <div id="regime-popover-sources" hidden>{regime_popovers_html}</div>
</div>

<!-- ===== TAB 2 ===== -->
<div id="tab2" class="tab-pane">

    <div class="chart-title">Relationship Between GDP per Capita and Fuel Subsidies Across Fuel Products</div>
    <div class="chart-source">
        Source: <a href="https://www.imf.org/en/Topics/climate-change/energy-subsidies" target="_blank" rel="noopener">IMF Fossil Fuel Subsidies Database</a> (2025 release, 2024 reference year);
        <a href="https://www.imf.org/en/Publications/WEO" target="_blank" rel="noopener">IMF WEO 2025</a> for GDP per capita.
    </div>

    <div class="kpi-row" id="kpi-row"></div>

    <div class="ctrl-row">
        <span class="row-label">Product:</span>
        <div class="toggle-group">
            {product_radios_html}
        </div>
    </div>

    <p style="font-size:0.85em;color:#555;margin:6px 0 10px 0">
        Subsidies are decomposed into explicit and implicit subsidies. Explicit subsidies occur when the retail price is below a fuel&#39;s supply cost. Implicit subsidies occur when the retail price fails to include external costs, inclusive of the standard consumption tax.
    </p>

    <div class="scatter-wrapper"><canvas id="scatter-chart"></canvas></div>

    <p style="font-size:0.78em;color:#888;margin-top:8px">
        X axis: GDP per capita (USD, log scale, <a href="https://www.imf.org/en/Publications/WEO" target="_blank" style="color:#667eea">IMF WEO 2025</a>) &nbsp;|&nbsp;
        Y axis: subsidy per capita (USD/person, <a href="https://www.imf.org/en/Topics/climate-change/energy-subsidies" target="_blank" style="color:#667eea">IMF Fossil Fuel Subsidies</a>) &nbsp;|&nbsp;
        Hollow markers = no IMF subsidy data available
    </p>
</div>

<!-- ===== TAB 3 ===== -->
<div id="tab3" class="tab-pane">
    <div class="chart-title">Short-Term Movements in Domestic Fuel Prices</div>
    <div class="ctrl-row">
        <span class="row-label">Country:</span>
        <select id="fuel-country-select">{fuel_country_opts}</select>
        <span class="row-label" style="margin-left:12px">Fuel:</span>
        <div class="toggle-group" id="fuel-family-radios"></div>
    </div>
    <div class="slider-row">
        <label>Date Range:</label>
        <span id="fuel-range-label">&mdash;</span>
        <div id="fuel-date-slider"></div>
    </div>
    <div id="fuel-regime-section" style="display:none">
        <div class="section-label">Price Regimes:</div>
        <div class="fuel-regime-grid">
            <div></div>
            <div class="grid-header">Subsidised</div>
            <div class="grid-header">Not Subsidised</div>
            <div class="row-label">Market Prices</div>
            <div id="fuel-regime-market-sub" class="fuel-regime-cell"></div>
            <div id="fuel-regime-market-nosub" class="fuel-regime-cell"></div>
            <div class="row-label">Price Controlled</div>
            <div id="fuel-regime-control-sub" class="fuel-regime-cell"></div>
            <div id="fuel-regime-control-nosub" class="fuel-regime-cell"></div>
        </div>
    </div>
    <div class="section-label">Fuel Family:</div>
    <div class="chip-container" id="fuel-axis-chips"></div>
    <div id="fuel-meta-panel"></div>
    <div class="panel-label">Price Levels</div>
    <div class="chart-wrapper"><canvas id="fuel-chart"></canvas></div>
    <div class="panel-label">Daily Changes (%)</div>
    <div class="delta-chart-wrapper"><canvas id="fuel-delta-chart"></canvas></div>
</div>

<!-- ===== TAB 4 ===== -->
<div id="tab4" class="tab-pane">
    <div class="chart-title">Cross-Economy Fuel Price Comparison</div>
    <div class="ctrl-row">
        <span class="row-label">Fuel:</span>
        <div class="toggle-group">
            {compare_family_radios_html}
        </div>
    </div>
    <div class="ctrl-row">
        <span class="row-label">Economies:</span>
    </div>
    <div class="chip-container" id="compare-country-chips"></div>
    <div class="slider-row">
        <label>Date Range:</label>
        <span id="compare-range-label">&mdash;</span>
        <div id="compare-date-slider"></div>
    </div>
    <span id="compare-breakdown-toggle" onclick="toggleCompareBreakdown()">&#9656; What products are included for each country?</span>
    <div id="compare-product-breakdown" style="display:none"></div>
    <div class="compare-chart-wrapper"><canvas id="compare-chart"></canvas></div>
</div>

<script>
// Data
const COMM_SERIES   = JSON.parse({comm_json});
const SCATTER_DATA  = JSON.parse({scatter_json});
const REGIME_COLORS = {colors_json};
const PALETTE       = {palette_json};
const PRODUCT_REGIMES = {product_regimes_json};
const ALL_PRODUCTS  = {products_json};
const REGION_ISOS   = new Set({region_isos_json});

// Regime pill popover
let _regimePopoverEl = null;
function _showRegimePopover(pill) {{
    var tipId = pill.dataset.tipId;
    if (!tipId) return;
    var src = document.getElementById(tipId);
    if (!src) return;
    if (!_regimePopoverEl) {{
        _regimePopoverEl = document.createElement('div');
        _regimePopoverEl.className = 'regime-popover';
        document.body.appendChild(_regimePopoverEl);
    }}
    _regimePopoverEl.innerHTML = src.innerHTML;
    _regimePopoverEl.style.display = 'block';
    _regimePopoverEl.style.left = '0px';
    _regimePopoverEl.style.top = '0px';
    var rect = pill.getBoundingClientRect();
    var pop = _regimePopoverEl.getBoundingClientRect();
    var top = rect.bottom + window.scrollY + 6;
    var left = rect.left + window.scrollX;
    if (left + pop.width > window.scrollX + window.innerWidth - 8) {{
        left = window.scrollX + window.innerWidth - pop.width - 8;
    }}
    if (left < window.scrollX + 8) left = window.scrollX + 8;
    if (rect.bottom + pop.height + 12 > window.innerHeight) {{
        top = rect.top + window.scrollY - pop.height - 6;
    }}
    _regimePopoverEl.style.left = left + 'px';
    _regimePopoverEl.style.top = top + 'px';
}}
function _hideRegimePopover() {{
    if (_regimePopoverEl) _regimePopoverEl.style.display = 'none';
}}
document.addEventListener('click', function(e) {{
    var pill = e.target.closest('.regime-pill');
    if (pill) {{
        _showRegimePopover(pill);
        e.stopPropagation();
        return;
    }}
    if (!e.target.closest('.regime-popover')) _hideRegimePopover();
}});
document.addEventListener('keydown', function(e) {{
    if (e.key === 'Escape') _hideRegimePopover();
}});
window.addEventListener('scroll', _hideRegimePopover, true);
window.addEventListener('resize', _hideRegimePopover);

// Tab switching
let fuelTabInitialized    = false;
let commTabInitialized    = false;
let scatterTabInitialized = false;
let compareTabInitialized = false;
function switchTab(id, btn) {{
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(id).classList.add('active');
    btn.classList.add('active');
    if (id === 'tab1' && !commTabInitialized) {{
        commTabInitialized = true;
        buildCommChips();
        initCommSlider();
        renderComm();
    }}
    if (id === 'tab2' && !scatterTabInitialized) {{
        scatterTabInitialized = true;
        renderScatter();
    }}
    if (id === 'tab3' && !fuelTabInitialized) {{
        fuelTabInitialized = true;
        rebuildFuelFamilyRadios();
        rebuildFuelChips();
        initFuelSlider();
        rerenderFuel();
    }}
    if (id === 'tab4' && !compareTabInitialized) {{
        compareTabInitialized = true;
        buildCompareCountryChips();
        initCompareSlider();
        rerenderCompare();
    }}
}}

// Composite regime helper
function compositeRegime(d, product) {{
    const base = d.base_regime || 'Unknown';
    const hasSub = d.imf_has_subsidy && d.imf_has_subsidy[product];
    if (base === 'Unknown') return 'Unknown';
    if (!hasSub) return base;
    if (base === 'Market') return 'Market Prices with Subsidies';
    if (base === 'Price Control') return 'Price Control with Subsidies';
    return base + ' + Subsidies';
}}

// KPI cards
function buildKPI(product, selectedCountry) {{
    const row = document.getElementById('kpi-row');
    row.innerHTML = '';

    const regionData = SCATTER_DATA.filter(d => REGION_ISOS.has(d.wb_iso3));
    const withData = regionData.filter(d =>
        d.subsidies && d.subsidies[product] != null && d.subsidies[product] > 0
    );

    let topCountry = 'N/A', topVal = 0;
    if (withData.length > 0) {{
        const top = withData.reduce((a, b) => b.subsidies[product] > a.subsidies[product] ? b : a);
        topCountry = top.country;
        topVal = top.subsidies[product];
    }}

    const count = withData.length;
    const avg   = count > 0
        ? withData.reduce((s, d) => s + d.subsidies[product], 0) / count
        : 0;

    let badgeCountry = selectedCountry || (regionData.length ? regionData[0].country : null);
    let badgeRegime = 'Unknown';
    if (badgeCountry) {{
        const found = SCATTER_DATA.find(d => d.country === badgeCountry);
        if (found) badgeRegime = compositeRegime(found, product);
    }}

    const cards = [
        {{
            value: topCountry !== 'N/A' ? topCountry + ' \u2014 $' + topVal.toFixed(1) : 'N/A',
            label: 'Highest ' + product + ' subsidy per capita (USD/person)'
        }},
        {{
            value: count,
            label: 'Countries with ' + product + ' subsidy'
        }},
        {{
            value: avg > 0 ? '$' + avg.toFixed(1) : 'N/A',
            label: 'Average ' + product + ' subsidy per capita (USD/person)'
        }},
    ];
    cards.forEach(c => {{
        const div = document.createElement('div');
        div.className = 'kpi-card';
        div.innerHTML = '<div class="kpi-value">' + c.value + '</div>'
                      + '<div class="kpi-label">' + c.label + '</div>';
        row.appendChild(div);
    }});
}}

// Commodity chart helpers
let sliderDates = [];
let commSlider  = null;
let commChart   = null;

function formatDate(d) {{
    const dt = new Date(d);
    return dt.getFullYear() + '-' + String(dt.getMonth()+1).padStart(2,'0') + '-' + String(dt.getDate()).padStart(2,'0');
}}

function buildCommChips() {{
    const c = document.getElementById('comm-chips');
    c.innerHTML = '';
    Object.keys(COMM_SERIES).sort().forEach((key) => {{
        const lel = document.createElement('label');
        lel.className = 'chip';
        const cb = document.createElement('input');
        cb.type = 'checkbox'; cb.value = key; cb.checked = true;
        cb.addEventListener('change', renderComm);
        lel.appendChild(cb);
        lel.appendChild(document.createTextNode(key));
        c.appendChild(lel);
    }});
}}

function initCommSlider() {{
    const allDates = new Set();
    Object.values(COMM_SERIES).forEach(s => s.points.forEach(p => allDates.add(p.x)));
    sliderDates = Array.from(allDates).sort();
    if (!sliderDates.length) return;

    const maxIdx = sliderDates.length - 1;
    const lastDate = new Date(sliderDates[maxIdx]);
    const oneYearBeforeLast = new Date(lastDate);
    oneYearBeforeLast.setFullYear(oneYearBeforeLast.getFullYear() - 1);
    const defaultStart = sliderDates.findIndex(d => new Date(d) >= oneYearBeforeLast);
    const startIdx = defaultStart >= 0 ? defaultStart : 0;

    const el = document.getElementById('date-slider');
    if (commSlider) commSlider.destroy();
    commSlider = noUiSlider.create(el, {{
        start: [startIdx, maxIdx],
        connect: true,
        step: 1,
        range: {{ min: 0, max: maxIdx || 1 }},
        tooltips: [
            {{ to: v => formatDate(sliderDates[Math.round(v)]) }},
            {{ to: v => formatDate(sliderDates[Math.round(v)]) }}
        ]
    }});
    const rangeLabel = document.getElementById('range-label');
    function updateLabel() {{
        const [a, b] = commSlider.get().map(v => Math.round(v));
        rangeLabel.textContent = formatDate(sliderDates[a]) + '  \u2192  ' + formatDate(sliderDates[b]);
    }}
    updateLabel();
    commSlider.on('update', updateLabel);
    commSlider.on('change', renderComm);
}}

function getSliderRange() {{
    if (!commSlider || !sliderDates.length) return {{ from: '', to: '' }};
    const [a, b] = commSlider.get().map(v => Math.round(v));
    return {{ from: sliderDates[a], to: sliderDates[b] }};
}}

function getChecked(containerId) {{
    return Array.from(document.querySelectorAll('#' + containerId + ' input:checked')).map(e => e.value);
}}

function renderComm() {{
    const selected = getChecked('comm-chips');
    const range    = getSliderRange();
    const ctx = document.getElementById('comm-chart').getContext('2d');

    const datasets = [];
    let colorIdx = 0;

    selected.forEach(key => {{
        const series = COMM_SERIES[key];
        if (!series) return;
        let pts = series.points;
        if (range.from) pts = pts.filter(p => p.x >= range.from);
        if (range.to)   pts = pts.filter(p => p.x <= range.to);
        datasets.push({{
            label: key,
            data: pts,
            borderColor: PALETTE[colorIdx % PALETTE.length],
            backgroundColor: PALETTE[colorIdx % PALETTE.length],
            borderWidth: 1.8,
            fill: false,
            tension: 0.1,
            pointRadius: 0,
            pointHoverRadius: 4,
            spanGaps: false,
        }});
        colorIdx++;
    }});

    const firstSeries = selected.length ? COMM_SERIES[selected[0]] : null;
    const yLabel = firstSeries ? (firstSeries.currency + '/' + firstSeries.unit) : '';

    if (!commChart) {{
        commChart = new Chart(ctx, {{
            type: 'line',
            data: {{ datasets }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ position: 'top', labels: {{ usePointStyle: true, padding: 14, font: {{ size: 11 }} }} }},
                    tooltip: {{
                        mode: 'index', intersect: false,
                        backgroundColor: 'rgba(0,0,0,0.82)', padding: 12,
                        callbacks: {{
                            title: items => items.length ? items[0].raw.x : '',
                            label: item => {{
                                const v = item.raw ? item.raw.y : null;
                                return v == null ? null : item.dataset.label + ': ' + v.toFixed(2);
                            }}
                        }}
                    }}
                }},
                scales: {{
                    x: {{ type: 'time', time: {{ unit: 'month' }}, display: true, title: {{ display: true, text: 'Date' }} }},
                    y: {{ display: true, title: {{ display: true, text: yLabel }} }}
                }}
            }}
        }});
    }} else {{
        commChart.data.datasets = datasets;
        commChart.options.scales.y.title.text = yLabel;
        commChart.update('none');
    }}
}}

// Scatter chart
let scatterChart = null;
let _scatterProduct = '';

function renderScatter() {{
    const productEl = document.querySelector('input[name="product-toggle"]:checked');
    const product   = productEl ? productEl.value : ALL_PRODUCTS[0];

    buildKPI(product);

    const regimes = Object.keys(REGIME_COLORS);
    const datasets = [];

    const regionScatter = SCATTER_DATA.filter(d => REGION_ISOS.has(d.wb_iso3));

    regimes.forEach(regime => {{
        const rPts = regionScatter.filter(d =>
            compositeRegime(d, product) === regime &&
            d.gdp_per_capita != null &&
            d.subsidies && d.subsidies[product] != null && d.subsidies[product] > 0
        );
        if (!rPts.length) return;
        datasets.push({{
            label: regime,
            data: rPts.map(d => ({{
                x: d.gdp_per_capita,
                y: d.subsidies[product],
                _meta: d,
            }})),
            backgroundColor: REGIME_COLORS[regime] + 'cc',
            borderColor:     REGIME_COLORS[regime],
            borderWidth: 1.5,
            pointRadius: 10,
            pointHoverRadius: 13,
        }});
    }});

    const noDataPts = regionScatter.filter(d =>
        d.gdp_per_capita != null &&
        compositeRegime(d, product) === 'Unknown' &&
        !(d.subsidies && d.subsidies[product] != null && d.subsidies[product] > 0)
    );
    if (noDataPts.length) {{
        datasets.push({{
            label: 'No subsidy data',
            data: noDataPts.map(d => ({{ x: d.gdp_per_capita, y: 1, _meta: d }})),
            backgroundColor: 'transparent',
            borderColor: '#999',
            borderWidth: 1.5,
            pointRadius: 10,
            pointHoverRadius: 13,
            pointStyle: 'circle',
        }});
    }}

    const allY = datasets.flatMap(ds => ds.data.map(p => p.y)).filter(v => v != null && v > 0);
    const yLogPad = 0.4;
    const yMin = allY.length ? Math.pow(10, Math.log10(Math.min(...allY)) - yLogPad) : 0.5;
    const yMax = allY.length ? Math.pow(10, Math.log10(Math.max(...allY)) + yLogPad) : 1e5;

    _scatterProduct = product;
    const ctx = document.getElementById('scatter-chart').getContext('2d');
    if (!scatterChart) {{
        scatterChart = new Chart(ctx, {{
            type: 'scatter',
            data: {{ datasets }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ position: 'top', labels: {{ usePointStyle: true, padding: 12, font: {{ size: 11 }} }} }},
                    tooltip: {{
                        callbacks: {{
                            label: item => {{
                                const m = item.raw._meta;
                                const regime = compositeRegime(m, _scatterProduct);
                                const hasSubsidy = m.subsidies && m.subsidies[_scatterProduct] != null && m.subsidies[_scatterProduct] > 0;
                                let sub;
                                if (hasSubsidy) {{
                                    sub = '$' + m.subsidies[_scatterProduct].toFixed(2);
                                }} else if (regime === 'Market' || regime === 'Price Control') {{
                                    sub = 'no subsidies';
                                }} else {{
                                    sub = 'no data';
                                }}
                                const gdp = m.gdp_per_capita != null
                                    ? '$' + Math.round(m.gdp_per_capita).toLocaleString()
                                    : 'N/A';
                                return [
                                    m.country + ' (' + m.wb_iso3 + ')',
                                    _scatterProduct + ' subsidy per capita: ' + sub,
                                    'GDP per capita: ' + gdp,
                                ];
                            }}
                        }}
                    }},
                }},
                scales: {{
                    x: {{
                        type: 'logarithmic',
                        display: true,
                        title: {{ display: true, text: 'GDP per capita (USD, log scale)' }},
                        ticks: {{
                            callback: function(value) {{
                                const log = Math.log10(value);
                                if (Math.abs(log - Math.round(log)) < 0.01) {{
                                    const exp = Math.round(log);
                                    const sups = '\u2070\u00b9\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079';
                                    const supStr = String(exp).split('').map(c => sups[+c]).join('');
                                    return '10' + supStr;
                                }}
                                return null;
                            }}
                        }}
                    }},
                    y: {{
                        type: 'logarithmic',
                        display: true,
                        min: yMin,
                        max: yMax,
                        title: {{ display: true, text: _scatterProduct + ' subsidy per capita (USD/person, log scale)' }},
                        ticks: {{
                            callback: function(value) {{
                                const log = Math.log10(value);
                                if (Math.abs(log - Math.round(log)) < 0.01) {{
                                    const exp = Math.round(log);
                                    const sups = '\u2070\u00b9\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079';
                                    const supStr = String(exp).split('').map(c => sups[+c]).join('');
                                    return '10' + supStr;
                                }}
                                return null;
                            }}
                        }}
                    }}
                }}
            }},
            plugins: [{{
                id: 'iso3labels',
                afterDatasetsDraw(chart) {{
                    const ctx = chart.ctx;
                    chart.data.datasets.forEach((ds, di) => {{
                        const meta = chart.getDatasetMeta(di);
                        meta.data.forEach((pt, pi) => {{
                            const m = ds.data[pi]._meta;
                            if (!m || !REGION_ISOS.has(m.wb_iso3)) return;
                            ctx.save();
                            ctx.font = 'bold 11px sans-serif';
                            ctx.fillStyle = '#333';
                            ctx.textAlign = 'center';
                            ctx.fillText(m.wb_iso3, pt.x, pt.y - 14);
                            ctx.restore();
                        }});
                    }});
                }}
            }}]
        }});
    }} else {{
        scatterChart.data.datasets = datasets;
        scatterChart.options.scales.y.min = yMin;
        scatterChart.options.scales.y.max = yMax;
        scatterChart.options.scales.y.title.text = _scatterProduct + ' subsidy per capita (USD/person, log scale)';
        scatterChart.update('none');
    }}
}}

// Tab 3: Economies Fuel Prices
const FUEL_DATA = JSON.parse({fuel_data_json});

const LABELS = {{
    diesel: "Diesel", gasoline: "Gasoline", lpg: "LPG",
    kerosene: "Kerosene", fuel_oil: "Fuel Oil",
    natural_gas: "Natural Gas", town_gas: "Town Gas",
    premium: "Premium", regular: "Regular",
    premix: "Premix", super_premium: "Super Premium",
    octane_95: "Premium",
}};

function lbl(v) {{ return (v && LABELS[v]) ? LABELS[v] : (v || "\u2014"); }}

function chipKey(r){{
    return r.series_key || r.fuel_product || "unknown";
}}

function chipLabel(key) {{
    // Build reverse lookup: series_key → display label from first matching record
    if (!chipLabel._map) {{
        chipLabel._map = {{}};
        Object.values(FUEL_DATA).forEach(function(recs) {{
            recs.forEach(function(r) {{
                var sk = r.series_key || r.fuel_product;
                if (sk && r.fuel_product && !chipLabel._map[sk]) {{
                    chipLabel._map[sk] = r.fuel_product;
                }}
            }});
        }});
    }}
    return chipLabel._map[key] || key || "\u2014";
}}

function getCheckedValues(containerId) {{
    return Array.from(
        document.querySelectorAll("#" + containerId + " input:checked")
    ).map(function(cb) {{ return cb.value; }});
}}

function formatYM(d) {{
    const dt = new Date(d);
    return dt.getFullYear() + '-' + String(dt.getMonth() + 1).padStart(2, '0') + '-' + String(dt.getDate()).padStart(2, '0');
}}

let fuelSliderDates = [];
let fuelSlider = null;

function getFuelSliderRange() {{
    if (!fuelSlider || !fuelSliderDates.length) return {{ from: '', to: '' }};
    const vals = fuelSlider.get().map(v => Math.round(v));
    return {{ from: fuelSliderDates[vals[0]], to: fuelSliderDates[vals[1]] }};
}}

function initFuelSlider() {{
    var rows = getFuelCountryRows();
    if (!rows || !rows.length) return;
    var dateSet = {{}};
    rows.forEach(function(r) {{ dateSet[r.observation_date] = true; }});
    fuelSliderDates = Object.keys(dateSet).sort();
    const maxIdx = fuelSliderDates.length - 1;
    if (maxIdx < 0) return;

    const lastFuelDate = new Date(fuelSliderDates[maxIdx]);
    const oneYearBeforeFuel = new Date(lastFuelDate);
    oneYearBeforeFuel.setFullYear(oneYearBeforeFuel.getFullYear() - 1);
    const defaultFuelStart = fuelSliderDates.findIndex(d => new Date(d) >= oneYearBeforeFuel);
    const startIdx = defaultFuelStart >= 0 ? defaultFuelStart : 0;

    const el = document.getElementById('fuel-date-slider');
    if (fuelSlider) {{ fuelSlider.destroy(); }}
    fuelSlider = noUiSlider.create(el, {{
        start: [startIdx, maxIdx],
        connect: true,
        step: 1,
        range: {{ min: 0, max: maxIdx || 1 }},
        tooltips: [
            {{ to: v => formatYM(fuelSliderDates[Math.round(v)]) }},
            {{ to: v => formatYM(fuelSliderDates[Math.round(v)]) }}
        ]
    }});
    const rangeLabel = document.getElementById('fuel-range-label');
    function updateFuelLabel() {{
        const vals = fuelSlider.get().map(v => Math.round(v));
        rangeLabel.textContent = formatYM(fuelSliderDates[vals[0]]) + '  \u2192  ' + formatYM(fuelSliderDates[vals[1]]);
    }}
    updateFuelLabel();
    fuelSlider.on('update', function() {{ updateFuelLabel(); }});
    fuelSlider.on('change', function() {{ rerenderFuel(); }});
}}

function buildFuelChips(containerId, keys, rows) {{
    var c = document.getElementById(containerId);
    c.innerHTML = "";
    keys.forEach(function(key) {{
        var lel = document.createElement("label");
        lel.className = "chip";
        var cb = document.createElement("input");
        cb.type = "checkbox"; cb.value = key; cb.checked = true;
        cb.addEventListener("change", rerenderFuel);
        lel.appendChild(cb);
        lel.appendChild(document.createTextNode(chipLabel(key)));
        c.appendChild(lel);
    }});
}}

function makeFuelDataset(label, points, color, isGray) {{
    return {{
        label:            label,
        data:             points,
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
    }};
}}

function updateFuelMeta(rows) {{
    var panel = document.getElementById("fuel-meta-panel");
    if (!rows || !rows.length) {{ panel.innerHTML = ""; return; }}
    var dates = rows.map(function(r) {{ return r.observation_date; }}).sort();
    panel.innerHTML = dates[0] + " \u2013 " + dates[dates.length - 1];
}}

function computeFuelYScale(datasets, yLabel) {{
    var allY = [];
    datasets.forEach(function(ds) {{
        (ds.data || []).forEach(function(pt) {{
            if (pt && pt.y != null && !ds._isGray) allY.push(pt.y);
        }});
    }});
    if (!allY.length) return {{ display: true, title: {{ display: true, text: yLabel }} }};
    var yMin = Math.min.apply(null, allY);
    var yMax = Math.max.apply(null, allY);
    var pad = (yMax - yMin) * 0.05 || yMax * 0.05 || 1;
    return {{
        display: true,
        title: {{ display: true, text: yLabel }},
        min: Math.max(0, yMin - pad),
        max: yMax + pad
    }};
}}

function _makeLineChartOptions(yScale, showLegend) {{
    return {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
            legend: {{
                display: showLegend !== false,
                position: "top",
                labels: {{
                    usePointStyle: true, padding: 14, font: {{ size: 11 }},
                    filter: function(item, data) {{ return !data.datasets[item.datasetIndex]._isGray; }}
                }}
            }},
            tooltip: {{
                mode: "index", intersect: false,
                backgroundColor: "rgba(0,0,0,0.82)", padding: 12,
                filter: function(item) {{ return !item.dataset._isGray; }},
                callbacks: {{
                    title: function(items) {{ return items.length ? items[0].raw.x : ""; }},
                    label: function(item) {{
                        var val = item.raw ? item.raw.y : null;
                        if (val == null) return null;
                        return item.dataset.label + ": " + val.toFixed(2);
                    }}
                }}
            }}
        }},
        scales: {{
            x: {{ type: "time", time: {{ unit: "month", tooltipFormat: "yyyy-MM-dd" }},
                  display: true, title: {{ display: true, text: "Date" }} }},
            y: yScale
        }}
    }};
}}

function drawFuelChart(datasets, yLabel) {{
    var ctx = document.getElementById("fuel-chart").getContext("2d");
    if (!datasets.length) {{
        if (window.fuelChart) {{ window.fuelChart.destroy(); window.fuelChart = null; }}
        return;
    }}
    var yScale = computeFuelYScale(datasets, yLabel);
    var opts = _makeLineChartOptions(yScale, true);
    if (!window.fuelChart) {{
        window.fuelChart = new Chart(ctx, {{ type: "line", data: {{ datasets: datasets }}, options: opts }});
    }} else {{
        window.fuelChart.data.datasets = datasets;
        window.fuelChart.options.scales.y = yScale;
        window.fuelChart.update('none');
    }}
}}

function drawDeltaChart(deltaDatasets, yLabel) {{
    var ctx = document.getElementById("fuel-delta-chart").getContext("2d");
    if (!deltaDatasets.length) {{
        if (window.fuelDeltaChart) {{ window.fuelDeltaChart.destroy(); window.fuelDeltaChart = null; }}
        return;
    }}
    var allY = [];
    deltaDatasets.forEach(function(ds) {{
        (ds.data || []).forEach(function(pt) {{
            if (pt && pt.y != null) allY.push(Math.abs(pt.y));
        }});
    }});
    var absMax = allY.length ? Math.max.apply(null, allY) : 5;
    var pad = absMax * 0.15 || 1;
    var yScale = {{
        display: true,
        title: {{ display: true, text: yLabel }},
        min: -(absMax + pad),
        max: absMax + pad,
        grid: {{ color: function(ctx) {{ return ctx.tick.value === 0 ? 'rgba(0,0,0,0.3)' : 'rgba(0,0,0,0.06)'; }} }}
    }};
    var opts = _makeLineChartOptions(yScale, false);
    opts.plugins.legend.display = false;
    if (!window.fuelDeltaChart) {{
        window.fuelDeltaChart = new Chart(ctx, {{ type: "line", data: {{ datasets: deltaDatasets }}, options: opts }});
    }} else {{
        window.fuelDeltaChart.data.datasets = deltaDatasets;
        window.fuelDeltaChart.options.scales.y = yScale;
        window.fuelDeltaChart.update('none');
    }}
}}

function computeDeltaDatasets(mainDatasets) {{
    return mainDatasets.filter(function(ds) {{ return !ds._isGray; }}).map(function(ds) {{
        var pts = (ds.data || []).filter(function(p) {{ return p && p.y != null; }});
        var deltas = pts.map(function(p, i) {{
            if (i === 0) return {{ x: p.x, y: null }};
            var prev = pts[i - 1];
            if (prev.y === 0 || prev.y == null) return {{ x: p.x, y: null }};
            return {{ x: p.x, y: ((p.y - prev.y) / prev.y) * 100 }};
        }});
        return makeFuelDataset(ds.label, deltas, ds.borderColor, false);
    }});
}}

function getFuelCountryRows() {{
    var country = document.getElementById("fuel-country-select").value;
    return FUEL_DATA[country] || [];
}}

var FUEL_FAMILY_ORDER = ["diesel","gasoline","lpg","kerosene","natural_gas","fuel_oil","electricity","crude_oil"];
var FUEL_FAMILY_LABELS = {{
    diesel: "Diesel", gasoline: "Gasoline", lpg: "LPG", kerosene: "Kerosene",
    natural_gas: "Natural Gas", fuel_oil: "Fuel Oil", electricity: "Electricity", crude_oil: "Crude Oil",
}};

function getFuelFamily() {{
    var el = document.querySelector('input[name="fuel-family-toggle"]:checked');
    return el ? el.value : "";
}}

function setFuelFamily() {{
    rebuildFuelChips();
    rerenderFuel();
}}

function rebuildFuelFamilyRadios() {{
    var rows = getFuelCountryRows();
    var present = new Set();
    rows.forEach(function(r) {{ if (r.fuel_family) present.add(r.fuel_family); }});
    var ordered = FUEL_FAMILY_ORDER.filter(function(k) {{ return present.has(k); }});
    var defaultKey = ordered.indexOf("diesel") >= 0 ? "diesel" : (ordered[0] || "");
    var html = "";
    ordered.forEach(function(k) {{
        var checked = (k === defaultKey) ? " checked" : "";
        var label = FUEL_FAMILY_LABELS[k] || k;
        html += '<label><input type="radio" name="fuel-family-toggle" value="' + k + '"' + checked + ' onchange="setFuelFamily()">' + label + '</label>';
    }});
    var container = document.getElementById("fuel-family-radios");
    if (container) container.innerHTML = html;
}}

function rebuildFuelChips() {{
    var rows = getFuelCountryRows();
    var family = getFuelFamily();
    if (family) rows = rows.filter(function(r) {{ return r.fuel_family === family; }});
    var keys = [...new Set(rows.map(chipKey))].sort();
    buildFuelChips("fuel-axis-chips", keys, rows);
}}

function rerenderFuel() {{
    var rows         = getFuelCountryRows();
    var family       = getFuelFamily();
    if (family) rows = rows.filter(function(r) {{ return r.fuel_family === family; }});
    window._fuelCountryRows = rows;
    var selectedKeys = getCheckedValues("fuel-axis-chips");
    var visibleRows  = rows.filter(function(r) {{ return selectedKeys.includes(chipKey(r)); }});
    var range = getFuelSliderRange();
    if (range.from) visibleRows = visibleRows.filter(function(r) {{ return r.observation_date >= range.from; }});
    if (range.to)   visibleRows = visibleRows.filter(function(r) {{ return r.observation_date <= range.to; }});
    updateFuelMeta(visibleRows);

    var priceField = 'price_local';

    if (!visibleRows.length) {{
        drawFuelChart([], "");
        drawDeltaChart([], "");
        var section = document.getElementById('fuel-regime-section');
        if (section) section.style.display = 'none';
        return;
    }}
    var firstRow  = visibleRows[0];
    var yLabel    = (firstRow.currency || "") + " / " + (firstRow.unit || "");
    var datasets  = [];
    var colorIdx  = 0;
    var keyColors = {{}};
    selectedKeys.forEach(function(key) {{
        var keyRows = visibleRows.filter(function(r) {{ return chipKey(r) === key; }});
        if (!keyRows.length) return;
        var color  = PALETTE[colorIdx % PALETTE.length];
        var serLbl = chipLabel(key);
        colorIdx++;
        keyColors[key] = color;
        var byDate = {{}};
        keyRows.forEach(function(r) {{
            var d = r.observation_date;
            var price = r[priceField];
            if (!d || price == null) return;
            var loc = (r.location || "").toLowerCase();
            var isNat = loc === "national" || loc === "national average";
            var sk = r.source_key || "_unknown";
            if (!byDate[d]) byDate[d] = {{}};
            if (!byDate[d][sk]) byDate[d][sk] = {{ nat: [], sub: [] }};
            if (isNat) byDate[d][sk].nat.push(price);
            else byDate[d][sk].sub.push(price);
        }});
        var avgPts = Object.keys(byDate).sort().map(function(d) {{
            var sources = byDate[d];
            var sourceAvgs = [];
            Object.keys(sources).forEach(function(sk) {{
                var s = sources[sk];
                var prices = s.sub.length ? s.sub : s.nat;
                if (!prices.length) return;
                var sum = prices.reduce(function(a, v) {{ return a + v; }}, 0);
                sourceAvgs.push(sum / prices.length);
            }});
            if (!sourceAvgs.length) return {{ x: d, y: null }};
            var total = sourceAvgs.reduce(function(a, v) {{ return a + v; }}, 0);
            return {{ x: d, y: total / sourceAvgs.length }};
        }});
        datasets.push(makeFuelDataset(serLbl, avgPts, color, false));
    }});
    drawFuelChart(datasets, yLabel);
    var deltaDatasets = computeDeltaDatasets(datasets);
    drawDeltaChart(deltaDatasets, "% change");
    updateFuelRegimeSection(document.getElementById("fuel-country-select").value, selectedKeys, keyColors);
}}

// Tab 3 price regime section
function fuelBaseProduct(row) {{
    const family = row && row.fuel_family;
    const f = String(family || '').toLowerCase();
    if (f === 'gasoline') return 'Gasoline';
    if (f === 'diesel') return 'Diesel';
    if (f === 'lpg') return 'LPG';
    if (f === 'kerosene') return 'Kerosene';

    const product = String((row && row.fuel_product) || '').toLowerCase();
    if (!product) return null;
    if (product.includes('diesel') || product.includes('gas oil')) return 'Diesel';
    if (product.includes('kerosene') || product.includes('paraffin')) return 'Kerosene';
    if (product.includes('lpg') || product.includes('liquefied petroleum')) return 'LPG';
    if (
        product.includes('gasoline')
        || product.includes('petrol')
        || product.includes('ron')
        || product.includes('unleaded')
        || product.includes('pertalite')
        || product.includes('pertamax')
        || product.includes('motor spirit')
    ) return 'Gasoline';
    return null;
}}

function updateFuelRegimeSection(countryName, selectedKeys, keyColors) {{
    const section = document.getElementById('fuel-regime-section');
    const marketSub = document.getElementById('fuel-regime-market-sub');
    const marketNoSub = document.getElementById('fuel-regime-market-nosub');
    const controlSub = document.getElementById('fuel-regime-control-sub');
    const controlNoSub = document.getElementById('fuel-regime-control-nosub');
    if (!section || !marketSub || !marketNoSub || !controlSub || !controlNoSub) return;

    const d = SCATTER_DATA.find(x => x.country === countryName);
    if (!d) {{ section.style.display = 'none'; return; }}
    const iso3 = d.wb_iso3 || '';
    const perProd = PRODUCT_REGIMES[iso3] || {{}};
    const subsidyMap = d.imf_has_subsidy || {{}};

    const rows = window._fuelCountryRows || [];
    const buckets = {{
        marketSub: [],
        marketNoSub: [],
        controlSub: [],
        controlNoSub: [],
    }};
    selectedKeys.forEach(function(key) {{
        const row = rows.find(r => chipKey(r) === key);
        if (!row) return;
        const baseProd = fuelBaseProduct(row);
        if (!baseProd) return;
        const info = perProd[baseProd];
        if (!info || !info.regime || info.regime === 'Unknown') return;
        const entry = {{
            key: key,
            label: chipLabel(key),
            color: keyColors[key] || '#666',
        }};
        const isSub = !!subsidyMap[baseProd];
        if (info.regime === 'Market') {{
            (isSub ? buckets.marketSub : buckets.marketNoSub).push(entry);
        }} else if (info.regime === 'Price Control') {{
            (isSub ? buckets.controlSub : buckets.controlNoSub).push(entry);
        }}
    }});

    function renderCell(entries, el) {{
        if (!entries.length) {{
            el.innerHTML = '';
            return;
        }}
        let html = '';
        entries.forEach(function(e) {{
            html += '<span class="regime-badge" style="background:' + e.color + '">' + e.label + '</span>';
        }});
        el.innerHTML = html;
    }}

    renderCell(buckets.marketSub, marketSub);
    renderCell(buckets.marketNoSub, marketNoSub);
    renderCell(buckets.controlSub, controlSub);
    renderCell(buckets.controlNoSub, controlNoSub);

    const total = buckets.marketSub.length + buckets.marketNoSub.length + buckets.controlSub.length + buckets.controlNoSub.length;
    section.style.display = total ? '' : 'none';
}}

document.getElementById("fuel-country-select").addEventListener("change", function() {{
    rebuildFuelFamilyRadios();
    rebuildFuelChips();
    initFuelSlider();
    rerenderFuel();
}});

// Tab 4: Cross-Economy Comparison
let compareSliderDates = [];
let compareSlider = null;

function getCompareFamily() {{
    var el = document.querySelector('input[name="compare-family-toggle"]:checked');
    return el ? el.value : 'diesel';
}}

function compareUnitFilter(unit, family) {{
    if (unit === 'L') return true;
    if (family === 'lpg' && unit === 'kg') return true;
    return false;
}}

function setCompareFamily() {{
    buildCompareCountryChips();
    initCompareSlider();
    rerenderCompare();
}}

var COMPARE_DEFAULT_COUNTRIES = new Set();
var COMPARE_EXCLUDE_COUNTRIES = new Set();

function buildCompareCountryChips() {{
    var family = getCompareFamily();
    var container = document.getElementById('compare-country-chips');
    container.innerHTML = '';
    var countries = Object.keys(FUEL_DATA).sort().filter(function(country) {{
        if (COMPARE_EXCLUDE_COUNTRIES.has(country)) return false;
        return (FUEL_DATA[country] || []).some(function(r) {{
            return r.fuel_family === family && compareUnitFilter(r.unit, family) && r.price_usd != null;
        }});
    }});
    var useDefaults = COMPARE_DEFAULT_COUNTRIES.size > 0;
    countries.forEach(function(country) {{
        var lel = document.createElement('label');
        lel.className = 'chip';
        var cb = document.createElement('input');
        cb.type = 'checkbox'; cb.value = country;
        cb.checked = useDefaults ? COMPARE_DEFAULT_COUNTRIES.has(country) : true;
        cb.addEventListener('change', rerenderCompare);
        lel.appendChild(cb);
        lel.appendChild(document.createTextNode(country));
        container.appendChild(lel);
    }});
}}

function initCompareSlider() {{
    var family = getCompareFamily();
    var dateSet = {{}};
    Object.keys(FUEL_DATA).forEach(function(country) {{
        if (COMPARE_EXCLUDE_COUNTRIES.has(country)) return;
        (FUEL_DATA[country] || []).forEach(function(r) {{
            if (r.fuel_family === family && compareUnitFilter(r.unit, family) && r.price_usd != null) {{
                dateSet[r.observation_date] = true;
            }}
        }});
    }});
    compareSliderDates = Object.keys(dateSet).sort();
    var maxIdx = compareSliderDates.length - 1;
    if (maxIdx < 0) return;

    var defaultStart = 0;
    for (var si = 0; si < compareSliderDates.length; si++) {{
        if (compareSliderDates[si] >= '2025-01-01') {{ defaultStart = si; break; }}
    }}

    var el = document.getElementById('compare-date-slider');
    if (compareSlider) {{ compareSlider.destroy(); }}
    compareSlider = noUiSlider.create(el, {{
        start: [defaultStart, maxIdx],
        connect: true,
        step: 1,
        range: {{ min: 0, max: maxIdx || 1 }},
        tooltips: [
            {{ to: function(v) {{ return formatYM(compareSliderDates[Math.round(v)]); }} }},
            {{ to: function(v) {{ return formatYM(compareSliderDates[Math.round(v)]); }} }}
        ]
    }});
    var rangeLabel = document.getElementById('compare-range-label');
    function updateCompareLabel() {{
        var vals = compareSlider.get().map(function(v) {{ return Math.round(v); }});
        rangeLabel.textContent = formatYM(compareSliderDates[vals[0]]) + '  \u2192  ' + formatYM(compareSliderDates[vals[1]]);
    }}
    updateCompareLabel();
    compareSlider.on('update', function() {{ updateCompareLabel(); }});
    compareSlider.on('change', function() {{ rerenderCompare(); }});
}}

function getCompareSliderRange() {{
    if (!compareSlider || !compareSliderDates.length) return {{ from: '', to: '' }};
    var vals = compareSlider.get().map(function(v) {{ return Math.round(v); }});
    return {{ from: compareSliderDates[vals[0]], to: compareSliderDates[vals[1]] }};
}}

function getCompareSeries(family) {{
    var result = {{}};
    Object.keys(FUEL_DATA).forEach(function(country) {{
        if (COMPARE_EXCLUDE_COUNTRIES.has(country)) return;
        var rows = (FUEL_DATA[country] || []).filter(function(r) {{
            return r.fuel_family === family && compareUnitFilter(r.unit, family) && r.price_usd != null;
        }});
        if (!rows.length) return;

        var byProduct = {{}};
        var allDatesSet = {{}};
        var LPG_KG_PER_L = 0.54;
        rows.forEach(function(r) {{
            var prod = r.fuel_product || '_';
            if (!byProduct[prod]) byProduct[prod] = {{}};
            var price = r.price_usd;
            if (family === 'lpg' && r.unit === 'L') price = price / LPG_KG_PER_L;
            byProduct[prod][r.observation_date] = price;
            allDatesSet[r.observation_date] = true;
        }});
        var sortedDates = Object.keys(allDatesSet).sort();
        if (!sortedDates.length) return;

        var products = Object.keys(byProduct);
        var lastVals = {{}};
        var pts = [];
        sortedDates.forEach(function(d) {{
            var sum = 0, count = 0;
            products.forEach(function(prod) {{
                var v = byProduct[prod][d];
                if (v != null) lastVals[prod] = v;
                if (lastVals[prod] != null) {{ sum += lastVals[prod]; count++; }}
            }});
            if (count > 0) {{
                pts.push({{ x: d, y: Math.round((sum / count) * 10000) / 10000 }});
            }}
        }});
        result[country] = pts;
    }});
    return result;
}}

function computeRegionalAverage(allCountrySeries) {{
    var allDates = new Set();
    Object.values(allCountrySeries).forEach(function(pts) {{
        pts.forEach(function(p) {{ allDates.add(p.x); }});
    }});
    var sortedDates = Array.from(allDates).sort();
    if (!sortedDates.length) return [];

    var startDate = new Date(sortedDates[0]);
    var endDate = new Date(sortedDates[sortedDates.length - 1]);
    var dailyDates = [];
    for (var d = new Date(startDate); d <= endDate; d.setDate(d.getDate() + 1)) {{
        dailyDates.push(d.toISOString().slice(0, 10));
    }}

    var countryDaily = {{}};
    Object.keys(allCountrySeries).forEach(function(country) {{
        var pts = allCountrySeries[country];
        var dateMap = {{}};
        pts.forEach(function(p) {{ dateMap[p.x] = p.y; }});
        var filled = [];
        var lastVal = null;
        dailyDates.forEach(function(dd) {{
            if (dateMap[dd] != null) lastVal = dateMap[dd];
            filled.push(lastVal);
        }});
        countryDaily[country] = filled;
    }});

    var countries = Object.keys(countryDaily);
    var avgPts = [];
    dailyDates.forEach(function(dd, i) {{
        var sum = 0, count = 0;
        countries.forEach(function(c) {{
            var val = countryDaily[c][i];
            if (val != null) {{ sum += val; count++; }}
        }});
        if (count > 0) {{
            avgPts.push({{ x: dd, y: Math.round((sum / count) * 10000) / 10000 }});
        }}
    }});
    return avgPts;
}}

function drawCompareChart(datasets, avgDataset, family) {{
    var ctx = document.getElementById('compare-chart').getContext('2d');
    var allDatasets = datasets.slice();
    if (avgDataset) allDatasets.push(avgDataset);

    if (!allDatasets.length) {{
        if (window.compareChart) {{ window.compareChart.destroy(); window.compareChart = null; }}
        return;
    }}

    var yLabel = (family === 'lpg') ? 'USD / kg' : 'USD / L';
    var allY = [];
    allDatasets.forEach(function(ds) {{
        (ds.data || []).forEach(function(pt) {{
            if (pt && pt.y != null && !ds._isGray) allY.push(pt.y);
        }});
    }});
    var yScale;
    if (!allY.length) {{
        yScale = {{ display: true, title: {{ display: true, text: yLabel }} }};
    }} else {{
        var yMin = Math.min.apply(null, allY);
        var yMax = Math.max.apply(null, allY);
        var pad = (yMax - yMin) * 0.08 || yMax * 0.05 || 0.1;
        yScale = {{
            display: true,
            title: {{ display: true, text: yLabel }},
            min: yMin - pad,
            max: yMax + pad
        }};
    }}
    var opts = _makeLineChartOptions(yScale, true);
    opts.plugins.legend.labels.filter = function(item, data) {{
        return !data.datasets[item.datasetIndex]._isGray;
    }};

    if (!window.compareChart) {{
        window.compareChart = new Chart(ctx, {{ type: 'line', data: {{ datasets: allDatasets }}, options: opts }});
    }} else {{
        window.compareChart.data.datasets = allDatasets;
        window.compareChart.options.scales.y = yScale;
        window.compareChart.update('none');
    }}
}}

function toggleCompareBreakdown() {{
    var panel = document.getElementById('compare-product-breakdown');
    var toggle = document.getElementById('compare-breakdown-toggle');
    if (panel.style.display === 'none') {{
        panel.style.display = '';
        toggle.innerHTML = '&#9662; What products are included for each country?';
    }} else {{
        panel.style.display = 'none';
        toggle.innerHTML = '&#9656; What products are included for each country?';
    }}
}}

function updateCompareBreakdown(family) {{
    var panel = document.getElementById('compare-product-breakdown');
    var items = [];
    Object.keys(FUEL_DATA).sort().forEach(function(country) {{
        if (COMPARE_EXCLUDE_COUNTRIES.has(country)) return;
        var products = {{}};
        (FUEL_DATA[country] || []).forEach(function(r) {{
            if (r.fuel_family === family && compareUnitFilter(r.unit, family) && r.price_usd != null) {{
                products[r.fuel_product] = true;
            }}
        }});
        var names = Object.keys(products).sort();
        if (names.length > 0) {{
            items.push('<b>' + country + ':</b> ' + names.join(', '));
        }}
    }});
    panel.innerHTML = items.length ? items.join(' &nbsp;|&nbsp; ') : 'No data for this fuel family.';
}}

function rerenderCompare() {{
    var family = getCompareFamily();
    var selectedCountries = getCheckedValues('compare-country-chips');
    var range = getCompareSliderRange();

    var allSeries = getCompareSeries(family);

    if (range.from || range.to) {{
        var filtered = {{}};
        Object.keys(allSeries).forEach(function(c) {{
            filtered[c] = allSeries[c].filter(function(p) {{
                return (!range.from || p.x >= range.from) && (!range.to || p.x <= range.to);
            }});
        }});
        allSeries = filtered;
    }}

    var avgPts = computeRegionalAverage(allSeries);
    var avgDataset = {{
        label: 'Regional Average',
        data: avgPts,
        borderColor: '#bbb',
        backgroundColor: '#bbb',
        borderWidth: 2,
        borderDash: [6, 4],
        fill: false,
        tension: 0.1,
        pointRadius: 0,
        pointHoverRadius: 3,
        order: 2,
        _isGray: true
    }};

    var datasets = [];
    var colorIdx = 0;
    selectedCountries.forEach(function(country) {{
        var pts = allSeries[country];
        if (!pts || !pts.length) return;
        var color = PALETTE[colorIdx % PALETTE.length];
        colorIdx++;
        datasets.push(makeFuelDataset(country, pts, color, false));
    }});

    drawCompareChart(datasets, avgDataset, family);
    updateCompareBreakdown(family);
}}
// Init
requestAnimationFrame(() => {{
    commTabInitialized = true;
    buildKPI(ALL_PRODUCTS[0]);
    buildCommChips();
    initCommSlider();
    renderComm();
}});
</script>
</body>
</html>"""

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  [policy] Created {out}")
