"""Generate standalone HTML dashboard with Chart.js tables for CPI analysis.

This script creates HTML tables showing:
1. Overview metrics by country (N items, N obs, min/max dates)
2. Overview metrics by source (with country column)
3. COICOP Level 2 breakdown (N items, N obs by title)

Usage:
    python src/cpi/analysis/plotting.py
"""

import json
from pathlib import Path
import pandas as pd
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from labels import load_labels, get_country_label, get_source_label


def load_data(report_dir: Path):
    """Load all necessary data files from the report directory."""
    # Load summary
    summary_path = report_dir / "summary.json"
    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    # Load coverage data - Level 1, 2, and 3
    coverage_coicop_l1_country = pd.read_csv(
        report_dir / "coverage_coicop_l1_country.csv", encoding="utf-8"
    )
    coverage_coicop_l1_country_source = pd.read_csv(
        report_dir / "coverage_coicop_l1_country_source.csv", encoding="utf-8"
    )
    coverage_coicop_l2_country = pd.read_csv(
        report_dir / "coverage_coicop_l2_country.csv", encoding="utf-8"
    )
    coverage_coicop_l2_country_source = pd.read_csv(
        report_dir / "coverage_coicop_l2_country_source.csv", encoding="utf-8"
    )
    coverage_coicop_l3_country = pd.read_csv(
        report_dir / "coverage_coicop_l3_country.csv", encoding="utf-8"
    )
    coverage_coicop_l3_country_source = pd.read_csv(
        report_dir / "coverage_coicop_l3_country_source.csv", encoding="utf-8"
    )

    return (
        summary,
        coverage_coicop_l1_country,
        coverage_coicop_l1_country_source,
        coverage_coicop_l2_country,
        coverage_coicop_l2_country_source,
        coverage_coicop_l3_country,
        coverage_coicop_l3_country_source,
    )


def create_country_coicop_pivot(coverage_coicop_l2_country, labels):
    """Create pivot table: COICOP categories as rows, countries as columns."""
    # Add country labels
    df = coverage_coicop_l2_country.copy()
    df["Country"] = df["country"].apply(lambda x: get_country_label(x, labels))

    # Create combined index with title and code
    # Determine which code column to use based on available columns
    code_col = None
    if "coicop_1digit" in df.columns:
        code_col = "coicop_1digit"
    elif "coicop_2digit" in df.columns:
        code_col = "coicop_2digit"
    elif "coicop_3digit" in df.columns:
        code_col = "coicop_3digit"

    if code_col:
        df["coicop_display"] = (
            df["coicop_title"] + " (" + df[code_col].astype(str) + ")"
        )
    else:
        df["coicop_display"] = df["coicop_title"]

    # Pivot: COICOP titles with codes as rows, countries as columns, n_items as values
    pivot = df.pivot_table(
        index="coicop_display",
        columns="Country",
        values="n_items",
        aggfunc="sum",
        fill_value=0,
    )

    # Sort columns by total items descending
    col_totals = pivot.sum(axis=0).sort_values(ascending=False)
    pivot = pivot[col_totals.index]

    # Add Total column (sum across countries for each COICOP)
    pivot["Total"] = pivot.sum(axis=1)

    # Sort rows by total items descending
    pivot = pivot.sort_values("Total", ascending=False)

    # Add Total row at the top (sum across COICOP for each country)
    total_row = pivot.sum(axis=0)
    total_row.name = "TOTAL"
    pivot = pd.concat([pd.DataFrame([total_row]), pivot])

    return pivot


def create_source_coicop_pivot(coverage_coicop_l2_country_source, labels):
    """Create pivot table: COICOP categories as rows, sources as columns."""
    # Add labels
    df = coverage_coicop_l2_country_source.copy()
    df["Source"] = df["source"].apply(lambda x: get_source_label(x, labels))
    df["Country"] = df["country"].apply(lambda x: get_country_label(x, labels))
    df["Source_Country"] = df["Source"] + " (" + df["Country"] + ")"

    # Create combined index with title and code
    # Determine which code column to use based on available columns
    code_col = None
    if "coicop_1digit" in df.columns:
        code_col = "coicop_1digit"
    elif "coicop_2digit" in df.columns:
        code_col = "coicop_2digit"
    elif "coicop_3digit" in df.columns:
        code_col = "coicop_3digit"

    if code_col:
        df["coicop_display"] = (
            df["coicop_title"] + " (" + df[code_col].astype(str) + ")"
        )
    else:
        df["coicop_display"] = df["coicop_title"]

    # Pivot: COICOP titles with codes as rows, source-country as columns, n_items as values
    pivot = df.pivot_table(
        index="coicop_display",
        columns="Source_Country",
        values="n_items",
        aggfunc="sum",
        fill_value=0,
    )

    # Sort columns by total items descending
    col_totals = pivot.sum(axis=0).sort_values(ascending=False)
    pivot = pivot[col_totals.index]

    # Add Total column (sum across sources for each COICOP)
    pivot["Total"] = pivot.sum(axis=1)

    # Sort rows by total items descending
    pivot = pivot.sort_values("Total", ascending=False)

    # Add Total row at the top (sum across COICOP for each source)
    total_row = pivot.sum(axis=0)
    total_row.name = "TOTAL"
    pivot = pd.concat([pd.DataFrame([total_row]), pivot])

    return pivot


def pivot_to_json(pivot_df):
    """Convert pivot DataFrame to JSON for JavaScript."""
    # Convert to dict with index as keys
    data = {}
    for idx in pivot_df.index:
        row_data = {}
        for col in pivot_df.columns:
            val = pivot_df.loc[idx, col]
            row_data[col] = int(val) if not pd.isna(val) else 0
        data[idx] = row_data
    return data


def generate_html(
    summary,
    country_pivot_l1,
    source_pivot_l1,
    country_pivot_l2,
    source_pivot_l2,
    country_pivot_l3,
    source_pivot_l3,
    output_path,
):
    """Generate complete HTML dashboard with interactive tables."""

    # Convert pivots to JSON for L1, L2, and L3
    country_data_l1 = pivot_to_json(country_pivot_l1)
    source_data_l1 = pivot_to_json(source_pivot_l1)
    country_data_l2 = pivot_to_json(country_pivot_l2)
    source_data_l2 = pivot_to_json(source_pivot_l2)
    country_data_l3 = pivot_to_json(country_pivot_l3)
    source_data_l3 = pivot_to_json(source_pivot_l3)

    country_columns_l1 = list(country_pivot_l1.columns)
    source_columns_l1 = list(source_pivot_l1.columns)
    country_columns_l2 = list(country_pivot_l2.columns)
    source_columns_l2 = list(source_pivot_l2.columns)
    country_columns_l3 = list(country_pivot_l3.columns)
    source_columns_l3 = list(source_pivot_l3.columns)

    # CSS styling
    css_styles = """
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            padding: 30px;
            background: #f5f5f5;
            color: #333;
        }
        .container {
            max-width: 100%;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        h1 {
            font-size: 2em;
            margin-bottom: 10px;
            color: #1a1a1a;
        }
        .subtitle {
            font-size: 0.9em;
            color: #666;
            margin-bottom: 30px;
        }
        .metrics {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        .metric-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 6px;
            border-left: 4px solid #667eea;
        }
        .metric-label {
            font-size: 0.85em;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }
        .metric-value {
            font-size: 1.8em;
            font-weight: 600;
            color: #1a1a1a;
        }
        .section {
            margin-bottom: 50px;
        }
        .section h2 {
            font-size: 1.5em;
            margin-bottom: 15px;
            color: #1a1a1a;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }
        .controls {
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 15px;
        }
        .radio-group {
            display: flex;
            gap: 20px;
            align-items: center;
        }
        .radio-group label {
            display: flex;
            align-items: center;
            gap: 5px;
            cursor: pointer;
            font-size: 0.95em;
        }
        .radio-group input[type="radio"] {
            cursor: pointer;
        }
        .table-wrapper {
            overflow-x: auto;
            margin-top: 15px;
        }
        .data-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85em;
            min-width: 800px;
        }
        .data-table thead {
            background: #667eea;
            color: white;
            position: sticky;
            top: 0;
            z-index: 10;
        }
        .data-table th {
            padding: 10px 8px;
            text-align: right;
            font-weight: 600;
            font-size: 0.8em;
            letter-spacing: 0.3px;
            white-space: nowrap;
        }
        .data-table th:first-child {
            text-align: left;
            position: sticky;
            left: 0;
            background: #667eea;
            z-index: 11;
        }
        .data-table td {
            padding: 8px;
            border-bottom: 1px solid #e0e0e0;
            text-align: right;
        }
        .data-table td:first-child {
            text-align: left;
            font-weight: 500;
            position: sticky;
            left: 0;
            background: white;
            z-index: 5;
        }
        .data-table tbody tr:hover td {
            background: #f8f9fa;
        }
        .data-table tbody tr:nth-child(even) td {
            background: #fafafa;
        }
        .data-table tbody tr:nth-child(even):hover td {
            background: #f0f0f0;
        }
        .data-table tbody tr:hover td:first-child,
        .data-table tbody tr:nth-child(even) td:first-child {
            background: white;
        }
        .data-table tbody tr:hover td:first-child {
            background: #f8f9fa;
        }
        .data-table tbody tr:nth-child(even):hover td:first-child {
            background: #f0f0f0;
        }
        .total-col {
            font-weight: 600;
            background: #f0f0f0 !important;
        }
        .total-row td {
            font-weight: 700;
            background: #e8eaf6 !important;
            border-top: 2px solid #667eea;
            border-bottom: 2px solid #667eea;
        }
        .total-row td:first-child {
            background: #e8eaf6 !important;
        }
        .table-subtitle {
            font-size: 0.95em;
            color: #666;
            margin: 10px 0 15px 0;
            font-weight: normal;
            font-style: italic;
        }
    """

    # JavaScript for interactive tables
    js_script = f"""
        const countryDataL1 = {json.dumps(country_data_l1)};
        const sourceDataL1 = {json.dumps(source_data_l1)};
        const countryDataL2 = {json.dumps(country_data_l2)};
        const sourceDataL2 = {json.dumps(source_data_l2)};
        const countryDataL3 = {json.dumps(country_data_l3)};
        const sourceDataL3 = {json.dumps(source_data_l3)};

        const countryColumnsL1 = {json.dumps(country_columns_l1)};
        const sourceColumnsL1 = {json.dumps(source_columns_l1)};
        const countryColumnsL2 = {json.dumps(country_columns_l2)};
        const sourceColumnsL2 = {json.dumps(source_columns_l2)};
        const countryColumnsL3 = {json.dumps(country_columns_l3)};
        const sourceColumnsL3 = {json.dumps(source_columns_l3)};

        function formatNumber(num) {{
            return num.toLocaleString('en-US');
        }}

        function formatPercent(num) {{
            return num.toFixed(1) + '%';
        }}

        function updateTableTitle(elementId, level, isPercent, tableType) {{
            const levelText = level === 'l1' ? '1' : (level === 'l2' ? '2' : '3');
            const viewText = isPercent ? 'Percentage of items' : 'Number of unique items';
            const byText = tableType === 'country' ? 'by country' : 'by source';
            const percentDetail = isPercent ? ` (% of ${{tableType}} total)` : '';

            const title = `${{viewText}} in each COICOP level ${{levelText}} category ${{byText}}${{percentDetail}}`;
            document.getElementById(elementId).textContent = title;
        }}

        function renderTable(tableId, data, columns, isPercent) {{
            const tbody = document.querySelector(`#${{tableId}} tbody`);
            tbody.innerHTML = '';

            for (const [rowName, rowData] of Object.entries(data)) {{
                const tr = document.createElement('tr');

                // Add total-row class if this is the TOTAL row
                if (rowName === 'TOTAL') {{
                    tr.className = 'total-row';
                }}

                // Row header (COICOP category name)
                const th = document.createElement('td');
                th.textContent = rowName;
                tr.appendChild(th);

                // Calculate row total for percentages
                const rowTotal = rowData['Total'] || 0;

                // Data cells (countries/sources)
                columns.forEach(col => {{
                    const td = document.createElement('td');
                    const value = rowData[col] || 0;

                    if (col === 'Total') {{
                        td.className = 'total-col';
                        td.textContent = formatNumber(value);
                    }} else {{
                        // For TOTAL row or when in absolute mode, show numbers
                        // For other rows in percent mode, calculate percentage
                        if (rowName === 'TOTAL' || !isPercent) {{
                            td.textContent = formatNumber(value);
                        }} else {{
                            // Calculate percentage: (value / column total) * 100
                            // Column total is in the TOTAL row
                            const colTotal = data['TOTAL'][col] || 0;
                            if (colTotal > 0) {{
                                const pct = (value / colTotal) * 100;
                                td.textContent = formatPercent(pct);
                            }} else {{
                                td.textContent = '0.0%';
                            }}
                        }}
                    }}
                    tr.appendChild(td);
                }});

                tbody.appendChild(tr);
            }}
        }}

        function updateCountryTable() {{
            const isPercent = document.querySelector('input[name="country-view"]:checked').value === 'percent';
            const level = document.querySelector('input[name="country-level"]:checked').value;
            let data, columns;
            if (level === 'l1') {{
                data = countryDataL1;
                columns = countryColumnsL1;
            }} else if (level === 'l2') {{
                data = countryDataL2;
                columns = countryColumnsL2;
            }} else {{
                data = countryDataL3;
                columns = countryColumnsL3;
            }}
            renderTable('country-table', data, columns, isPercent);
            updateTableTitle('country-title', level, isPercent, 'country');
        }}

        function updateSourceTable() {{
            const isPercent = document.querySelector('input[name="source-view"]:checked').value === 'percent';
            const level = document.querySelector('input[name="source-level"]:checked').value;
            let data, columns;
            if (level === 'l1') {{
                data = sourceDataL1;
                columns = sourceColumnsL1;
            }} else if (level === 'l2') {{
                data = sourceDataL2;
                columns = sourceColumnsL2;
            }} else {{
                data = sourceDataL3;
                columns = sourceColumnsL3;
            }}
            renderTable('source-table', data, columns, isPercent);
            updateTableTitle('source-title', level, isPercent, 'source');
        }}

        // Event listeners
        document.querySelectorAll('input[name="country-view"]').forEach(radio => {{
            radio.addEventListener('change', updateCountryTable);
        }});
        document.querySelectorAll('input[name="country-level"]').forEach(radio => {{
            radio.addEventListener('change', updateCountryTable);
        }});

        document.querySelectorAll('input[name="source-view"]').forEach(radio => {{
            radio.addEventListener('change', updateSourceTable);
        }});
        document.querySelectorAll('input[name="source-level"]').forEach(radio => {{
            radio.addEventListener('change', updateSourceTable);
        }});

        // Initial render
        updateCountryTable();
        updateSourceTable();
    """

    # Generate column headers (COICOP Category as first column, then countries/sources)
    country_headers = "<th>COICOP Category (Code)</th>" + "".join(
        f"<th>{col}</th>" for col in country_columns_l2
    )
    source_headers = "<th>COICOP Category (Code)</th>" + "".join(
        f"<th>{col}</th>" for col in source_columns_l2
    )

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>CPI Analysis Dashboard</title>
    <style>{css_styles}</style>
</head>
<body>
    <div class="container">
        <h1>📊 CPI Analysis Dashboard</h1>
        <p class="subtitle">Price scraping coverage since 2025-11-12</p>

        <!-- Overview Metrics -->
        <div class="metrics">
            <div class="metric-card">
                <div class="metric-label">Unique Items</div>
                <div class="metric-value">{summary['n_items']:,}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Registers</div>
                <div class="metric-value">{summary['n_obs']:,}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Countries</div>
                <div class="metric-value">{summary['n_countries']}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Sources</div>
                <div class="metric-value">{summary['n_sources']}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Oldest Date</div>
                <div style="font-size: 0.75em; font-style: italic; color: #999; margin-top: 4px;">From Wayback Machine</div>
                <div class="metric-value" style="font-size: 1.2em;">{summary['min_date']}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Updated On</div>
                <div class="metric-value" style="font-size: 1.2em;">{summary['max_date']}</div>
            </div>
        </div>

        <!-- By COICOP by Country Table -->
        <div class="section">
            <h2>COICOP by Country</h2>
            <div class="controls">
                <div class="radio-group">
                    <strong>Level:</strong>
                    <label>
                        <input type="radio" name="country-level" value="l1" checked>
                        Level 1
                    </label>
                    <label>
                        <input type="radio" name="country-level" value="l2">
                        Level 2
                    </label>
                    <label>
                        <input type="radio" name="country-level" value="l3">
                        Level 3
                    </label>
                </div>
                <div class="radio-group">
                    <strong>View:</strong>
                    <label>
                        <input type="radio" name="country-view" value="absolute" checked>
                        Absolute (N Items)
                    </label>
                    <label>
                        <input type="radio" name="country-view" value="percent">
                        Percentage (% of Country Total)
                    </label>
                </div>
            </div>
            <p id="country-title" class="table-subtitle">Number of unique items in each COICOP level 1 category by country</p>
            <div class="table-wrapper">
                <table id="country-table" class="data-table">
                    <thead>
                        <tr>{country_headers}</tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>

        <!-- By COICOP by Source Table -->
        <div class="section">
            <h2>COICOP by Source</h2>
            <div class="controls">
                <div class="radio-group">
                    <strong>Level:</strong>
                    <label>
                        <input type="radio" name="source-level" value="l1" checked>
                        Level 1
                    </label>
                    <label>
                        <input type="radio" name="source-level" value="l2">
                        Level 2
                    </label>
                    <label>
                        <input type="radio" name="source-level" value="l3">
                        Level 3
                    </label>
                </div>
                <div class="radio-group">
                    <strong>View:</strong>
                    <label>
                        <input type="radio" name="source-view" value="absolute" checked>
                        Absolute (N Items)
                    </label>
                    <label>
                        <input type="radio" name="source-view" value="percent">
                        Percentage (% of Source Total)
                    </label>
                </div>
            </div>
            <p id="source-title" class="table-subtitle">Number of unique items in each COICOP level 1 category by source</p>
            <div class="table-wrapper">
                <table id="source-table" class="data-table">
                    <thead>
                        <tr>{source_headers}</tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
    </div>
    <script>{js_script}</script>
</body>
</html>"""

    # Write to file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✓ Dashboard saved to: {output_path}")


def main():
    """Main execution function."""
    # Define paths
    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    REPORT_DIR = PROJECT_ROOT / "data/cpi/analysis/reports/latest"
    OUTPUT_DIR = PROJECT_ROOT / "src/cpi/plotting/outputs"
    OUTPUT_FILE = OUTPUT_DIR / "index.html"

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading data...")
    labels = load_labels()
    (
        summary,
        coverage_coicop_l1_country,
        coverage_coicop_l1_country_source,
        coverage_coicop_l2_country,
        coverage_coicop_l2_country_source,
        coverage_coicop_l3_country,
        coverage_coicop_l3_country_source,
    ) = load_data(REPORT_DIR)

    print("Creating Country × COICOP Level 1 pivot table...")
    country_pivot_l1 = create_country_coicop_pivot(coverage_coicop_l1_country, labels)

    print("Creating Source × COICOP Level 1 pivot table...")
    source_pivot_l1 = create_source_coicop_pivot(
        coverage_coicop_l1_country_source, labels
    )

    print("Creating Country × COICOP Level 2 pivot table...")
    country_pivot_l2 = create_country_coicop_pivot(coverage_coicop_l2_country, labels)

    print("Creating Source × COICOP Level 2 pivot table...")
    source_pivot_l2 = create_source_coicop_pivot(
        coverage_coicop_l2_country_source, labels
    )

    print("Creating Country × COICOP Level 3 pivot table...")
    country_pivot_l3 = create_country_coicop_pivot(coverage_coicop_l3_country, labels)

    print("Creating Source × COICOP Level 3 pivot table...")
    source_pivot_l3 = create_source_coicop_pivot(
        coverage_coicop_l3_country_source, labels
    )

    print("Generating interactive HTML dashboard...")
    generate_html(
        summary,
        country_pivot_l1,
        source_pivot_l1,
        country_pivot_l2,
        source_pivot_l2,
        country_pivot_l3,
        source_pivot_l3,
        OUTPUT_FILE,
    )

    print(f"\n{'='*60}")
    print("Dashboard generation complete!")
    print(f"{'='*60}")
    print(f"Open: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
