# src/text/scrapers/

Newspaper scraping framework. Config-driven, async-capable, with
pluggable listing discovery strategies and per-country cleaning.

**Configs live at `src/text/configs/`**, not here. This directory
contains only framework code.

## Key Files

| File | Purpose |
|------|---------|
| `scraper.py` | `NewspaperScraper` — main orchestrator class |
| `client_http.py` | `AsyncHttpClient` — async HTTP with rate limiting |
| `client_browser.py` | `BrowserClient` — Selenium for JS-heavy sites |
| `models.py` | Pydantic models: ThumbnailRecord, ArticleRecord, NewspaperConfig |
| `parser.py` | CSS selector extraction with fallback chains |
| `factory.py` | `create_scraper_from_file()` — YAML config → scraper |
| `modes.py` | ScrapeMode enum: UPDATE, RESUME, FULL_DISCOVERY |
| `filters.py` | URL filtering DSL (allow/deny domains, paths) |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `strategies/` | Listing discovery: pagination, API, archive, follow_link |
| `pipelines/storage/` | CSV storage: news.csv, urls.csv, metadata.json |
| `pipelines/cleaning/` | Per-country cleaning functions (registry pattern) |
| `observability/` | Metrics, progress tracking, quality validation |
| `orchestration/` | CLI entry points, multi-scraper runner |

## Scraper Flow

```
YAML config → factory.create_scraper_from_file()
  → NewspaperScraper(config)
    → ListingStrategy.discover_and_scrape()  (find article URLs)
    → parser.extract_article_data()          (scrape content)
    → cleaning.apply_cleaning()              (normalize)
    → CSVStorage.save_articles()             (persist)
```

## Adding a Cleaning Function

1. Create `pipelines/cleaning/{country}.py`
2. Use `@register_cleaner` decorator on each function
3. Import in `pipelines/cleaning/__init__.py`

See `pipelines/cleaning/ukraine.py` for an example.
