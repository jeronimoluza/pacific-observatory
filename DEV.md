# Scraper Workflow Revamp

## Overview

Revamped the newspaper scraper CLI to introduce granular control over thumbnail discovery and article scraping with four distinct modes.

## New CLI Modes

| Mode | Command | Behavior |
|------|---------|----------|
| **Default** | `python main.py {newspaper}` | Discover new URLs → Append to `urls.csv` → Scrape pending articles |
| **Discover** | `python main.py {newspaper} --discover` | Discover new URLs → Append to `urls.csv` → No scraping |
| **Discover-Full** | `python main.py {newspaper} --discover-full` | Discover ALL URLs → Overwrite `urls.csv` → No scraping |
| **Resume** | `python main.py {newspaper} --resume` | Skip discovery → Scrape pending articles from `urls.csv` |

Multi-scraper runner: `python main.py --run-all [--discover|--discover-full|--resume]`

## Removed Flags

- `--full` (replaced by `--discover-full`)
- `--download-urls-only` (replaced by `--discover`)

## Key Principles

- **`urls.csv`**: Source of truth for discovered URLs
- **`news.csv`**: Source of truth for scraped articles
- **Auto-create**: If `urls.csv` doesn't exist but `news.csv` does, auto-generate `urls.csv` from `news.csv`
- **Deduplication**: When appending URLs, deduplicate by URL (keep first occurrence)

## Discovery Stopping Rules

All discovery modes implement these rules:

1. **HTTP 404 / Error Batch**: Stop if entire batch returns 404s
2. **Empty Batch**: Stop if batch has 0 thumbnails
3. **Identical Batch**: Stop if batch data matches previous batch
4. **Batch in urls.csv**: Stop if all URLs in batch already exist in `urls.csv` (default & discover modes only)

## Implementation Summary

| Phase | File | Changes |
|-------|------|---------|
| 1 | `storage.py` | Added `get_existing_urls()`, `append_thumbnails_to_urls()`, `ensure_urls_csv_from_news()` |
| 2 | `newspaper_scraper.py` | Added `run_discover()`, `run_discover_full()`, `run_resume()`, `run_default()`, `_discover_thumbnails_incremental()` |
| 3 | `run_scraper.py` | Replaced `full_mode`/`download_urls_only` with `mode` parameter |
| 4 | `main.py` | Replaced `--full`/`--download-urls-only` with `--discover`/`--discover-full`/`--resume` |
| 5 | `run_multiple.py` | Updated all functions to use `mode` parameter |

## Usage Examples

```bash
# Default mode: discover new URLs + scrape pending articles
python src/text/scrapers/orchestration/main.py sibc

# Discover new URLs only (append to urls.csv)
python src/text/scrapers/orchestration/main.py sibc --discover

# Rediscover all URLs (overwrite urls.csv)
python src/text/scrapers/orchestration/main.py sibc --discover-full

# Resume scraping pending articles (no discovery)
python src/text/scrapers/orchestration/main.py sibc --resume

# Multi-scraper with modes
python src/text/scrapers/orchestration/main.py --run-all --discover
python src/text/scrapers/orchestration/main.py --run-all --resume
python src/text/scrapers/orchestration/main.py --run-all --sequential
```

## Backward Compatibility

- Existing `--run-all` functionality remains compatible
- Old methods (`run_full_scrape`, `run_update_scrape`, `run_urls_only`) kept for now but deprecated
- Default mode provides smart update behavior (similar to old update mode)

## Refactoring TODO

After implementation is tested and verified working, perform cleanup:

### Code Cleanup Tasks

1. **Remove deprecated methods from `newspaper_scraper.py`**:
   - `run_full_scrape()` - replaced by `run_discover_full()` + `run_default()`
   - `run_update_scrape()` - replaced by `run_default()`
   - `run_urls_only()` - replaced by `run_discover()`

2. **Remove unused parameters from `run_scraper.py`**:
   - Remove `full_mode` parameter (replaced by `mode`)
   - Remove `download_urls_only` parameter (replaced by `mode`)

3. **Remove unused parameters from `run_multiple.py`**:
   - Remove `full_mode` parameter (replaced by `mode`)

4. **Remove unused CLI flags from `main.py`**:
   - `--full` (replaced by `--discover-full`)
   - `--download-urls-only` (replaced by `--discover`)

5. **General cleanup**:
   - Remove any debug logging statements
   - Remove unused imports
   - Remove unused helper functions

## Files Modified

- `src/text/scrapers/pipelines/storage.py` (Phase 1)
- `src/text/scrapers/newspaper_scraper.py` (Phase 2)
- `src/text/scrapers/orchestration/run_scraper.py` (Phase 3)
- `src/text/scrapers/orchestration/main.py` (Phase 4)
- `src/text/scrapers/orchestration/run_multiple.py` (Phase 5)

New additions: added follow_redirect=True to client_http.py and max_redirects=5
