# CPI Visualization

Stage: `publish` inside `price_atlas`.

This folder holds standalone CPI coverage dashboards and tables built from structured report outputs.

## Main Script

- `src/cpi/visualization/plotting.py` - builds a standalone HTML dashboard from the latest CPI report outputs.
- `src/cpi/visualization/tables.py` - generates markdown-ready coverage and quality tables.

## Dashboard Inputs

`plotting.py` expects the latest report bundle under `data/cpi/analysis/reports/latest/`, including summary and coverage CSVs.

## Run

```bash
poetry run python src/cpi/visualization/plotting.py
```

## Output

The current script writes the dashboard to `src/cpi/plotting/outputs/index.html`.
