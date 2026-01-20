## Interactive dashboard

The dashboard (`plotting.py`) generates a standalone HTML file with Chart.js visualizations.

Features:

- Overview metrics (n_items, n_obs, n_countries, n_sources, date range)
- Interactive tables with radio button controls:
  - **COICOP Level**: Toggle between Level 1 (divisions), Level 2 (groups), Level 3 (classes)
  - **View Mode**: Toggle between absolute counts and percentages
- Two table views:
  - COICOP × Country
  - COICOP × Source
- Dynamic titles that update based on selected options

Generate dashboard:
```bash
poetry run python src/cpi/plotting/plotting.py
```

Output: `src/cpi/plotting/dashboard/index.html`
