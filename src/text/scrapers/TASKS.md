# Scraper Revamp Implementation Tasks

This document outlines the comprehensive implementation plan for revamping the newspaper scraper CLI with new modes and behaviors.

---

## Overview

### New CLI Structure

| Command | Description |
|---------|-------------|
| `{newspaper}` | **Default**: Discover new URLs → Append to `urls.csv` → Scrape pending articles |
| `{newspaper} --discover` | Discover new URLs → Append to `urls.csv` → No scraping |
| `{newspaper} --discover-full` | Discover ALL URLs → Overwrite `urls.csv` → No scraping |
| `{newspaper} --resume` | No discovery → Scrape pending articles from `urls.csv` |
| `--run-all [mode]` | Apply selected mode to all scrapers |

### Removed Flags
- `--full` (removed)
- `--download-urls-only` (removed)

---

## Source of Truth

- **`urls.csv`**: Source of truth for discovered article URLs
- **`news.csv`**: Source of truth for scraped article content

### Key Principle
`urls.csv` is checked for discovery stopping rules. `news.csv` is checked for article scraping decisions.

---

## Discovery Stopping Rules

All discovery modes (default, `--discover`, `--discover-full`) must implement these stopping rules:

### Rule 1: HTTP 404 / Error on Entire Batch
```
IF all URLs in batch return 404 or error:
    STOP discovery
```

### Rule 2: Empty Thumbnails Batch
```
IF batch returns 0 thumbnails:
    STOP discovery
```

### Rule 3: Identical Batch Data
```
IF current batch thumbnails == previous batch thumbnails:
    STOP discovery (duplicate content detected)
```

### Rule 4: Batch Already in urls.csv (NEW - for `--discover` and default only)
```
IF all URLs in current batch already exist in urls.csv:
    STOP discovery (reached previously discovered content)
```

**Note**: Rule 4 does NOT apply to `--discover-full` mode.

---

## File Modifications

### 1. `src/text/scrapers/pipelines/storage.py`

#### Task 1.1: Add `get_existing_urls()` method
```python
def get_existing_urls(self, country: str, newspaper: str) -> set:
    """
    Load existing URLs from urls.csv for stopping rule checks.

    Args:
        country: Country code
        newspaper: Newspaper name

    Returns:
        Set of existing URL strings, empty set if file doesn't exist
    """
```

**Implementation details:**
- Read `urls.csv` if it exists
- Extract URL column
- Return as set for O(1) lookup
- Return empty set if file doesn't exist (not an error)

#### Task 1.2: Add `append_thumbnails_to_urls()` method
```python
def append_thumbnails_to_urls(
    self,
    thumbnails: List[ThumbnailRecord],
    country: str,
    newspaper: str,
) -> Path:
    """
    Append new thumbnails to existing urls.csv with deduplication.

    Args:
        thumbnails: List of ThumbnailRecord objects to append
        country: Country code
        newspaper: Newspaper name

    Returns:
        Path to the urls.csv file
    """
```

**Implementation details:**
- Load existing `urls.csv` if it exists
- Merge with new thumbnails
- Deduplicate by URL (keep first occurrence)
- Save back to `urls.csv`
- Create file if it doesn't exist

#### Task 1.3: Add `ensure_urls_csv_from_news()` method
```python
def ensure_urls_csv_from_news(self, country: str, newspaper: str) -> bool:
    """
    Create urls.csv from news.csv if urls.csv does NOT exist.

    IMPORTANT: Only creates urls.csv if it does not already exist.
    Never overwrites existing urls.csv to preserve pending URLs.

    Args:
        country: Country code
        newspaper: Newspaper name

    Returns:
        True if urls.csv was created, False if it already existed or news.csv doesn't exist
    """
```

**Implementation details:**
- Check if `urls.csv` exists → return False (do nothing)
- Check if `news.csv` exists → if not, return False
- Read `news.csv`, extract url, title, date columns
- Write to `urls.csv`
- Return True

---

### 2. `src/text/scrapers/newspaper_scraper.py`

#### Task 2.1: Add `run_discover()` method
```python
async def run_discover(self) -> Dict[str, Any]:
    """
    Incremental URL discovery mode.

    Behavior:
    1. Ensure urls.csv exists (create from news.csv if needed)
    2. Load existing URLs from urls.csv
    3. Discover thumbnails batch-by-batch
    4. Apply stopping rules:
       - 404 on entire batch
       - Empty thumbnails batch
       - Identical batch data
       - Entire batch already in urls.csv
    5. Append new URLs to urls.csv (deduplicated)
    6. NO article scraping

    Returns:
        Dictionary with discovery results and statistics
    """
```

#### Task 2.2: Add `run_discover_full()` method
```python
async def run_discover_full(self) -> Dict[str, Any]:
    """
    Full URL discovery mode.

    Behavior:
    1. Discover ALL thumbnails (no urls.csv stopping rule)
    2. Apply stopping rules:
       - 404 on entire batch
       - Empty thumbnails batch
       - Identical batch data
    3. OVERWRITE urls.csv with all discovered URLs
    4. NO article scraping

    Returns:
        Dictionary with discovery results and statistics
    """
```

#### Task 2.3: Add `run_resume()` method
```python
async def run_resume(self) -> Dict[str, Any]:
    """
    Resume article scraping mode.

    Behavior:
    1. Ensure urls.csv exists (create from news.csv if needed)
    2. Load URLs from urls.csv
    3. Load existing article URLs from news.csv
    4. Identify pending articles: urls.csv - news.csv
    5. Scrape pending articles
    6. Append to news.csv
    7. NO discovery

    Returns:
        Dictionary with scraping results and statistics
    """
```

#### Task 2.4: Refactor default mode to `run_default()` method
```python
async def run_default(self) -> Dict[str, Any]:
    """
    Default smart update mode.

    Behavior:
    1. Ensure urls.csv exists (create from news.csv if needed)
    2. Load existing URLs from urls.csv
    3. Discover thumbnails batch-by-batch
    4. Apply stopping rules:
       - 404 on entire batch
       - Empty thumbnails batch
       - Identical batch data
       - Entire batch already in urls.csv
    5. Append new URLs to urls.csv (deduplicated)
    6. Load existing article URLs from news.csv
    7. Identify pending articles: urls.csv - news.csv
    8. Scrape pending articles
    9. Append to news.csv

    Returns:
        Dictionary with discovery and scraping results
    """
```

#### Task 2.5: Remove/refactor old methods
- Remove `run_full_scrape()` or mark as deprecated
- Remove `run_update_scrape()` or mark as deprecated
- Remove `run_urls_only()` or mark as deprecated
- Keep `discover_and_scrape_thumbnails()` as internal helper
- Keep `scrape_articles()` as internal helper

#### Task 2.6: Add helper method for discovery with stopping rules
```python
async def _discover_thumbnails_incremental(
    self,
    existing_urls: set,
    check_existing: bool = True,
) -> List[ThumbnailRecord]:
    """
    Discover thumbnails with all stopping rules.

    Args:
        existing_urls: Set of URLs already in urls.csv
        check_existing: If True, stop when batch is in existing_urls

    Returns:
        List of newly discovered ThumbnailRecord objects
    """
```

**Stopping rules implementation:**
```python
async for result_batch in self.listing_strategy.discover_and_scrape(...):
    # Extract thumbnails from batch
    batch_thumbnails = self._extract_thumbnails_from_batch(result_batch)

    # Rule 1: 404/error - handled by listing_strategy (no successful results)
    if not batch_thumbnails:
        # Rule 2: Empty thumbnails
        logger.info("Empty batch. Stopping discovery.")
        break

    # Rule 3: Identical batch data
    batch_data = [thumb.model_dump() for thumb in batch_thumbnails]
    if previous_batch_data and batch_data == previous_batch_data:
        logger.info("Identical batch. Stopping discovery.")
        break

    # Rule 4: Batch already in urls.csv (only if check_existing=True)
    if check_existing:
        batch_urls = {str(thumb.url) for thumb in batch_thumbnails}
        if batch_urls.issubset(existing_urls):
            logger.info("Batch already in urls.csv. Stopping discovery.")
            break

    # Add to results
    all_thumbnails.extend(batch_thumbnails)
    previous_batch_data = batch_data
```

---

### 3. `src/text/scrapers/orchestration/run_scraper.py`

#### Task 3.1: Update `run_single_scraper()` function
```python
async def run_single_scraper(
    config_path: Path,
    storage_dir: Optional[Path] = None,
    save_results: bool = True,
    mode: str = "default",  # NEW: "default", "discover", "discover_full", "resume"
    project_root: Optional[Path] = None,
) -> dict:
```

**Implementation details:**
- Remove `full_mode` parameter
- Remove `download_urls_only` parameter
- Add `mode` parameter with values: "default", "discover", "discover_full", "resume"
- Call appropriate scraper method based on mode:
  ```python
  if mode == "discover":
      results = await scraper.run_discover()
  elif mode == "discover_full":
      results = await scraper.run_discover_full()
  elif mode == "resume":
      results = await scraper.run_resume()
  else:  # default
      results = await scraper.run_default()
  ```

#### Task 3.2: Update `run_scraper_by_name()` function
```python
async def run_scraper_by_name(
    newspaper_name: str,
    country: str = None,
    mode: str = "default",  # NEW
    configs_dir: Path = None,
    project_root: Path = None,
    **kwargs,
):
```

**Implementation details:**
- Remove `full_mode` parameter
- Remove `download_urls_only` parameter
- Add `mode` parameter
- Pass `mode` to `run_single_scraper()`

---

### 4. `src/text/scrapers/orchestration/main.py`

#### Task 4.1: Update argument parser
```python
# REMOVE these arguments:
# --full
# --download-urls-only

# ADD these arguments:
parser.add_argument(
    "--discover",
    action="store_true",
    help="Discover new URLs and append to urls.csv (no article scraping)",
)

parser.add_argument(
    "--discover-full",
    action="store_true",
    help="Discover ALL URLs and overwrite urls.csv (no article scraping)",
)

parser.add_argument(
    "--resume",
    action="store_true",
    help="Skip discovery, scrape pending articles from urls.csv",
)
```

#### Task 4.2: Add mode validation
```python
# Ensure mutually exclusive modes
mode_flags = [args.discover, args.discover_full, args.resume]
if sum(mode_flags) > 1:
    parser.error("Only one of --discover, --discover-full, --resume can be specified")
```

#### Task 4.3: Determine mode from args
```python
def get_mode_from_args(args) -> str:
    if args.discover:
        return "discover"
    elif args.discover_full:
        return "discover_full"
    elif args.resume:
        return "resume"
    else:
        return "default"
```

#### Task 4.4: Update help text and examples
```python
epilog="""
Examples:
  # Default mode: discover new URLs + scrape pending articles
  python src/text/scrapers/orchestration/main.py sibc

  # Discover mode: discover new URLs only (no scraping)
  python src/text/scrapers/orchestration/main.py sibc --discover

  # Discover-full mode: discover ALL URLs (overwrite urls.csv)
  python src/text/scrapers/orchestration/main.py sibc --discover-full

  # Resume mode: scrape pending articles from urls.csv
  python src/text/scrapers/orchestration/main.py sibc --resume

  # Multi-scraper runner
  python src/text/scrapers/orchestration/main.py --run-all
  python src/text/scrapers/orchestration/main.py --run-all --discover
  python src/text/scrapers/orchestration/main.py --run-all --resume
"""
```

#### Task 4.5: Update scraper invocation
```python
success, results = asyncio.run(
    run_scraper_by_name(
        newspaper_name=args.newspaper,
        country=args.country,
        mode=get_mode_from_args(args),  # NEW
        configs_dir=get_default_configs_dir(),
        project_root=project_root,
        storage_dir=args.storage_dir,
        no_save=args.no_save,
    )
)
```

---

### 5. `src/text/scrapers/orchestration/run_multiple.py`

#### Task 5.1: Update `run_scraper_subprocess()` function
```python
def run_scraper_subprocess(
    newspaper: str,
    country: str,
    project_root: Path,
    mode: str = "default",  # NEW
    ...
) -> subprocess.CompletedProcess:
```

**Implementation details:**
- Remove `full_mode` parameter
- Add `mode` parameter
- Build command with appropriate flag:
  ```python
  cmd = [...]
  if mode == "discover":
      cmd.append("--discover")
  elif mode == "discover_full":
      cmd.append("--discover-full")
  elif mode == "resume":
      cmd.append("--resume")
  # default mode: no flag needed
  ```

#### Task 5.2: Update `run_all_scrapers()` function
```python
def run_all_scrapers(
    configs_dir: Path,
    project_root: Path,
    sequential: bool = False,
    dry_run: bool = False,
    mode: str = "default",  # NEW
) -> bool:
```

**Implementation details:**
- Remove `full_mode` parameter
- Add `mode` parameter
- Pass `mode` to subprocess calls

#### Task 5.3: Update `run_multi_country_group_sequential()` function
- Update to accept and pass `mode` parameter

---

## Implementation Order

1. **Phase 1: Storage Layer** (Task 1.1 - 1.3)
   - Implement new storage methods

2. **Phase 2: Scraper Methods** (Task 2.1 - 2.6)
   - Implement new scraper methods
   - Refactor/remove old methods

3. **Phase 3: Orchestration** (Task 3.1 - 3.2)
   - Update run_scraper.py

4. **Phase 4: CLI** (Task 4.1 - 4.5)
   - Update main.py argument parser
   - Update help text

5. **Phase 5: Multi-Scraper** (Task 5.1 - 5.3)
   - Update run_multiple.py

---

## Notes

### Backward Compatibility
- Old flags `--full` and `--download-urls-only` are removed
- Default behavior changes from "update mode" to "smart default mode"
- Existing `urls.csv` and `news.csv` files are preserved

### Performance Considerations
- `get_existing_urls()` loads entire urls.csv into memory (acceptable for typical sizes)
- Deduplication uses set operations for O(n) performance
- Batch processing continues to use async for efficiency

### Error Handling
- Missing files are handled gracefully (not errors)
- Network errors during discovery trigger stopping rules
- Partial progress is saved (urls.csv updated incrementally)
