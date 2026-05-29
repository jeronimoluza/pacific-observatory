# src/text/plotting/

Interactive visualizations for EPU and text analysis outputs.

## Key Files

| File | Purpose |
|------|---------|
| `small_dashboard_integrated.py` | Main integrated dashboard with tabs |
| `small_dashboard.py` | Summary dashboard variant |
| `interactive.py` | Plotly-based interactive charts |
| `regional_note_charts.py` | Regional analysis visualizations |

## Data Flow

Reads EPU index CSVs from `data/text/{country}/` and generates
standalone HTML dashboards with Plotly charts.

## Output

HTML files with embedded Plotly charts. No server required —
dashboards are self-contained and can be opened in any browser.
