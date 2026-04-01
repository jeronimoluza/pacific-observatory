# src/text/

Newspaper scraping and Economic Policy Uncertainty (EPU) analysis
pipeline. Collects articles from newspapers, computes EPU indices
and sentiment scores, and publishes interactive dashboards.

## Data Flow

```
configs/{region}/{subregion}/{country}/{newspaper}.yaml  -> Newspaper definitions
scrapers/                                     -> HTTP/browser clients, strategies
         |
collect.py                                    -> Discover articles, dedup by URL, store
         |
data/text/{region}/{subregion}/{country}/{newspaper}/news.csv
         |
analysis/                                     -> EPU index, sentiment, topic indices
process.py                                    -> Orchestrate analysis (country + aggregates)
         |
outputs/text/{region}/{subregion}/{country}/epu/epu.csv
outputs/text/{region}/{subregion}/_aggregate/epu/epu.csv
         |
publish.py                                    -> dashboard_data.json + HTML dashboard
         |
outputs/text/dashboard_data.json
outputs/text/small_dashboard_integrated.html
```

## Commands

### Collect — scrape articles

```bash
po text collect                                          # All newspapers
po text collect --region eap                             # One region
po text collect --subregion pacific_islands              # One subregion
po text collect --country fiji                           # One country
po text collect --source fiji_times                      # One newspaper
po text collect --country fiji --max-pages 3             # Limit pages
po text collect --region eca --dry-run                   # Preview without scraping
po text collect -y                                       # Skip confirmation prompt
```

| Flag | Description |
|------|-------------|
| `--region, -r` | Filter by WB region slug (e.g., `eap`, `eca`) |
| `--subregion` | Filter by subregion slug (e.g., `pacific_islands`, `eastern_europe`) |
| `--country, -c` | Filter by country slug (e.g., `ukraine`, `fiji`) |
| `--source, -s` | Run a single newspaper by source key |
| `--max-pages` | Limit listing pages per newspaper |
| `--max-articles` | Limit articles per newspaper |
| `--dry-run` | Show plan without executing |
| `--rebuild` | Full re-scrape, bypass URL dedup |
| `--yes, -y` | Skip confirmation prompt |

### Build — compute EPU index

```bash
po text build --country ukraine                          # Incremental update (country only)
po text build --subregion eastern_europe                 # All countries + subregion aggregate
po text build --region eap                               # All countries + all aggregates
po text build --country ukraine --rebuild                # Full recompute
po text build --country ukraine --rebuild --cutoff 2025-12-31  # Custom cutoff
po text build -y                                         # Skip confirmation
```

When `--country` is specified, only that country is processed (no aggregates).
When `--subregion` or `--region` is specified, constituent countries + aggregates are built.

| Flag | Description |
|------|-------------|
| `--region, -r` | Filter by WB region slug |
| `--subregion` | Filter by subregion slug |
| `--country, -c` | Filter by country slug |
| `--rebuild` | Force recalculation of params.json and all cached outputs |
| `--cutoff` | Cutoff date (YYYY-MM-DD) for EPU standardization period |
| `--yes, -y` | Skip confirmation prompt |

### Publish — generate dashboards

```bash
po text publish                                          # All units → dashboard_data.json + HTML
po text publish --country ukraine                        # Filter to one country
po text publish --subregion eastern_europe               # One subregion
po text publish -y                                       # Skip confirmation
```

Publish writes `outputs/text/dashboard_data.json` (all unit data + hierarchical tree), then
generates `outputs/text/small_dashboard_integrated.html` with a hierarchical region/subregion/country dropdown.

| Flag | Description |
|------|-------------|
| `--region, -r` | Filter by WB region slug |
| `--subregion` | Filter by subregion slug |
| `--country, -c` | Filter by country slug |
| `--yes, -y` | Skip confirmation prompt |

## Structure

```
text/
├── configs/               YAML newspaper configs
│   ├── eap/pacific_islands/fiji/  Per-country by subregion
│   ├── eca/eastern_europe/ukraine/
│   ├── _examples/         Annotated template
│   └── README.md
├── scrapers/              Scraping framework
│   ├── strategies/        Listing discovery (pagination, API, archive, etc.)
│   ├── pipelines/         Storage (CSV, URLs, metadata)
│   ├── client_http.py     Async HTTP client
│   ├── client_browser.py  Selenium browser client
│   └── README.md
├── analysis/              EPU, sentiment, topic indices
│   ├── keywords/          Per-language keyword sets (26 languages)
│   └── README.md
├── plotting/              Interactive Plotly dashboards
│   └── README.md
├── collect.py             Collect stage: scrape articles
├── process.py             Build stage: compute indices
└── publish.py             Publish stage: dashboards
```

## Adding a New Newspaper

See [HOW_TO_ADD_NEW_SCRAPER.md](HOW_TO_ADD_NEW_SCRAPER.md)
