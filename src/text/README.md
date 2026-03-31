# src/text/

Newspaper scraping and Economic Policy Uncertainty (EPU) analysis
pipeline. Collects articles from newspapers, computes EPU indices
and sentiment scores, and publishes interactive dashboards.

## Data Flow

```
configs/{region}/{country}/{newspaper}.yaml  → Newspaper definitions
scrapers/                                    → HTTP/browser clients, strategies
         ↓
collect.py                                   → Discover articles, dedup by URL, store
         ↓
data/text/{country}/{newspaper}/news.csv
data/text/{country}/{newspaper}/urls.csv
         ↓
analysis/                                    → EPU index, sentiment, topic indices
process.py                                   → Orchestrate analysis
         ↓
data/text/{country}/epu_index.csv
         ↓
publish.py                                   → Dashboards, regional charts
```

## Structure

```
text/
├── configs/               YAML newspaper configs by region/country
│   ├── pacific/fiji/      Per-country newspaper configs
│   ├── _examples/         Annotated template
│   └── README.md
├── scrapers/              Scraping framework
│   ├── strategies/        Listing discovery (pagination, API, archive, etc.)
│   ├── pipelines/         Storage (CSV, URLs, metadata)
│   ├── client_http.py     Async HTTP client
│   ├── client_browser.py  Selenium browser client
│   └── README.md
├── analysis/              EPU, sentiment, topic indices
│   ├── keywords/          Per-language keyword sets
│   └── README.md
├── keywords/              Region-specific keyword overrides
├── collect.py             Collect stage: scrape articles
├── process.py             Build stage: compute indices
└── publish.py             Publish stage: dashboards
```

## Commands

```bash
po text collect                          # Scrape all newspapers
po text collect --country fiji           # Scrape Fiji newspapers
po text collect --source fiji_sun        # Scrape one newspaper
po text build --country fiji             # Compute EPU for Fiji
po text publish                          # Generate dashboards
```

## Adding a New Newspaper

See [docs/text/HOW_TO_ADD_NEW_SCRAPER.md](../../docs/text/HOW_TO_ADD_NEW_SCRAPER.md)
