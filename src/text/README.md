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
python run.py text collect                                          # All newspapers
python run.py text collect --region eap                             # One region
python run.py text collect --subregion pacific_islands              # One subregion
python run.py text collect --country fiji                           # One country
python run.py text collect --source fiji_times                      # One configured newspaper key
python run.py text collect --country fiji --max-pages 3             # Limit pages
python run.py text collect --region eca --dry-run                   # Preview without scraping
```

| Flag | Description |
|------|-------------|
| `--region, -r` | Filter by WB region slug (e.g., `eap`, `eca`) |
| `--subregion` | Filter by subregion slug (e.g., `pacific_islands`, `eastern_europe`) |
| `--country, -c` | Filter by country slug (e.g., `ukraine`, `fiji`) |
| `--source, -s` | Run a single configured newspaper key (YAML filename) |
| `--max-pages` | Limit listing pages per newspaper |
| `--max-articles` | Limit articles per newspaper |
| `--dry-run` | Show plan without executing |
| `--rebuild` | Full re-scrape, bypass URL dedup |

### Build — compute EPU index

```bash
python run.py text build --country ukraine                          # Incremental update (country only)
python run.py text build --subregion eastern_europe                 # All countries + subregion aggregate
python run.py text build --region eap                               # All countries + all aggregates
python run.py text build --country ukraine --rebuild                # Full recompute
python run.py text build --country ukraine --rebuild --cutoff-start-date 2020-01-01 --cutoff-end-date 2022-12-31  # Custom baseline window
```

When `--country` is specified, only that country is processed (no aggregates).
When `--subregion` or `--region` is specified, constituent countries + aggregates are built.

A baseline window is required: pass `--cutoff-start-date` and/or `--cutoff-end-date`.

| Flag | Description |
|------|-------------|
| `--region, -r` | Filter by WB region slug |
| `--subregion` | Filter by subregion slug |
| `--country, -c` | Filter by country slug |
| `--rebuild` | Force recalculation of params.json and all cached outputs |
| `--cutoff-start-date` | Inclusive baseline start date (YYYY-MM-DD) for EPU standardization |
| `--cutoff-end-date` | Inclusive baseline end date (YYYY-MM-DD) for EPU standardization |

### Publish — generate dashboards

```bash
python run.py text publish                                          # All units → dashboard_data.json + HTML
python run.py text publish --country ukraine                        # Filter to one country
python run.py text publish --subregion eastern_europe               # One subregion
```

Publish writes `outputs/text/dashboard_data.json` (all unit data + hierarchical tree), then
generates `outputs/text/small_dashboard_integrated.html` with a hierarchical region/subregion/country dropdown.

| Flag | Description |
|------|-------------|
| `--region, -r` | Filter by WB region slug |
| `--subregion` | Filter by subregion slug |
| `--country, -c` | Filter by country slug |

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
