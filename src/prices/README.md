# src/prices/

Supermarket price scraping, COICOP classification, and CPI
construction pipeline. Collects product prices from retailers,
classifies them using COICOP categories, extracts quantities,
and constructs consumer price indices.

## Data Flow

```
configs/{region}/{country}/{retailer}.yaml   → Retailer definitions
scrapers/                                    → Scrapy spiders
         ↓
collect.py                                   → Run spiders, store raw data
         ↓
data/prices/{country}/{retailer}/raw_items/
         ↓
coicop/                                      → COICOP classification (Gemini AI)
         ↓                                      Quantity extraction
process.py                                   → Orchestrate classify + build CPI
         ↓
index/                                       → CPI construction (Jevons + weighted)
         ↓
data/prices/{country}/cpi_index.csv
         ↓
publish.py                                   → CPI dashboards
```

## Structure

```
prices/
├── configs/               YAML retailer configs by region/country
│   ├── pacific/fiji/
│   ├── _examples/         Annotated template
│   └── README.md
├── scrapers/              Scrapy spiders for supermarket sites
│   └── README.md
├── coicop/                COICOP classification and quantity extraction
│   └── README.md
├── index/                 CPI index construction (Jevons methodology)
│   └── README.md
├── collect.py             Collect stage: run spiders
├── process.py             Build stage: classify + construct CPI
└── publish.py             Publish stage: CPI dashboards
```

## Commands

```bash
po prices collect --country fiji        # Scrape Fiji retailers
po prices build --country fiji          # Classify + build CPI
po prices publish                       # Generate CPI dashboards
```

## Adding a New Retailer

See [docs/prices/HOW_TO_ADD_NEW_SPIDER.md](../../docs/prices/HOW_TO_ADD_NEW_SPIDER.md)
