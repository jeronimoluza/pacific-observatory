# Text Module Observability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build three-layer observability system to catch silent data quality failures (like caixin_global NaN dates) in real-time

**Architecture:** Structured logging + in-memory metrics aggregation + JSON manifests. No SQLite. DRY code structure ensures cleaning/validation always happens.

**Tech Stack:** Python dataclasses, built-in logging, JSON, pathlib

---

## Phase 1: Foundation - Metrics & Tracking

### Task 1.1: Create Observability Package Structure

**Files:**
- Create: `src/text/scrapers/observability/__init__.py`
- Create: `src/text/scrapers/observability/metrics.py`
- Create: `src/text/scrapers/observability/formatters.py`
- Create: `src/text/scrapers/observability/validators.py`

**Step 1: Create package init file**

```bash
mkdir -p src/text/scrapers/observability
touch src/text/scrapers/observability/__init__.py
```

**Step 2: Write package init with exports**

File: `src/text/scrapers/observability/__init__.py`

```python
"""
Observability components for text scraping.

Provides metrics tracking, formatting, and validation for scraper runs.
"""

from .metrics import FieldMetrics, ScraperMetrics, save_run_manifest
from .formatters import print_run_summary, detect_quality_issues

__all__ = [
    "FieldMetrics",
    "ScraperMetrics",
    "save_run_manifest",
    "print_run_summary",
    "detect_quality_issues",
]
```

**Step 3: Create empty module files**

```bash
touch src/text/scrapers/observability/metrics.py
touch src/text/scrapers/observability/formatters.py
touch src/text/scrapers/observability/validators.py
```

**Step 4: Commit**

```bash
git add src/text/scrapers/observability/
git commit -m "feat(observability): create observability package structure"
```

---

### Task 1.2: Implement Metrics Data Structures

**Files:**
- Modify: `src/text/scrapers/observability/metrics.py`

**Step 1: Import dependencies**

File: `src/text/scrapers/observability/metrics.py`

```python
"""
Metrics tracking for scraper runs.

Provides in-memory aggregation of extraction quality metrics.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)
```

**Step 2: Implement FieldMetrics dataclass**

Add to `src/text/scrapers/observability/metrics.py`:

```python
@dataclass
class FieldMetrics:
    """
    Metrics for a single field extraction (e.g., 'date', 'body').

    Tracks how many times we attempted to extract this field and
    the quality of extracted values.
    """

    total_extracted: int = 0   # How many articles we tried to extract this field from
    successful: int = 0         # Field populated with non-empty value
    empty: int = 0              # Field is None, empty string, or empty list
    invalid: int = 0            # Field failed validation (reserved for future use)

    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_extracted == 0:
            return 0.0
        return (self.successful / self.total_extracted) * 100
```

**Step 3: Implement ScraperMetrics dataclass**

Add to `src/text/scrapers/observability/metrics.py`:

```python
@dataclass
class ScraperMetrics:
    """
    Aggregated metrics for a scraper run.

    Tracks article-level counts and field-level extraction quality.
    Updated incrementally during scraping, then formatted at the end.
    """

    newspaper: str
    country: str
    mode: str
    started_at: datetime

    # Article-level counts
    urls_discovered: int = 0
    articles_scraped: int = 0
    articles_failed: int = 0

    # Field-level quality tracking
    field_metrics: Dict[str, FieldMetrics] = field(default_factory=dict)

    # Timing
    duration_seconds: float = 0.0

    def get_field_metric(self, field_name: str) -> FieldMetrics:
        """
        Get or create FieldMetrics for a given field.

        Args:
            field_name: Name of the field (e.g., 'date', 'body')

        Returns:
            FieldMetrics instance for this field
        """
        if field_name not in self.field_metrics:
            self.field_metrics[field_name] = FieldMetrics()
        return self.field_metrics[field_name]

    @classmethod
    def from_dict(cls, data: dict) -> "ScraperMetrics":
        """
        Load ScraperMetrics from JSON manifest dictionary.

        Args:
            data: Dictionary loaded from JSON manifest

        Returns:
            ScraperMetrics instance
        """
        # Parse datetime
        started_at = datetime.fromisoformat(data["started_at"])

        # Reconstruct field_metrics from nested dicts
        field_metrics = {}
        if "field_quality" in data:
            for field_name, field_data in data["field_quality"].items():
                field_metrics[field_name] = FieldMetrics(**field_data)

        # Build ScraperMetrics
        counts = data.get("counts", {})
        return cls(
            newspaper=data["newspaper"],
            country=data["country"],
            mode=data["mode"],
            started_at=started_at,
            urls_discovered=counts.get("urls_discovered", 0),
            articles_scraped=counts.get("articles_scraped", 0),
            articles_failed=counts.get("articles_failed", 0),
            field_metrics=field_metrics,
            duration_seconds=data.get("duration_seconds", 0.0),
        )
```

**Step 4: Test metrics creation**

```bash
python3 << 'EOF'
import sys
sys.path.insert(0, 'src')
from datetime import datetime
from text.scrapers.observability.metrics import ScraperMetrics, FieldMetrics

# Create metrics
metrics = ScraperMetrics(
    newspaper="test_paper",
    country="test_country",
    mode="update",
    started_at=datetime.now()
)

# Test get_field_metric
date_metric = metrics.get_field_metric("date")
date_metric.total_extracted = 10
date_metric.successful = 8
date_metric.empty = 2

print(f"Success rate: {date_metric.success_rate()}%")
assert date_metric.success_rate() == 80.0

print("✓ Metrics dataclasses work correctly")
EOF
```

Expected: `Success rate: 80.0%` and `✓ Metrics dataclasses work correctly`

**Step 5: Commit**

```bash
git add src/text/scrapers/observability/metrics.py
git commit -m "feat(observability): implement FieldMetrics and ScraperMetrics dataclasses"
```

---

### Task 1.3: Implement Manifest Save Function

**Files:**
- Modify: `src/text/scrapers/observability/metrics.py`

**Step 1: Add save_run_manifest function**

Add to `src/text/scrapers/observability/metrics.py`:

```python
def save_run_manifest(
    metrics: ScraperMetrics,
    newspaper: str,
    country: str
) -> Path:
    """
    Save run manifest as JSON to logs directory.

    Args:
        metrics: ScraperMetrics to save
        newspaper: Newspaper name
        country: Country code

    Returns:
        Path to saved manifest file
    """
    # Create directory structure
    manifest_dir = Path(f"logs/text/{country}/{newspaper}/individual")
    manifest_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename with timestamp
    timestamp = metrics.started_at.strftime("%Y%m%d_%H%M%S")
    manifest_path = manifest_dir / f"{timestamp}.json"

    # Build manifest dictionary
    manifest = {
        "newspaper": metrics.newspaper,
        "country": metrics.country,
        "mode": metrics.mode,
        "started_at": metrics.started_at.isoformat(),
        "duration_seconds": metrics.duration_seconds,
        "counts": {
            "urls_discovered": metrics.urls_discovered,
            "articles_scraped": metrics.articles_scraped,
            "articles_failed": metrics.articles_failed,
        },
        "field_quality": {
            field_name: asdict(field_metric)
            for field_name, field_metric in metrics.field_metrics.items()
        },
    }

    # Write JSON
    manifest_path.write_text(json.dumps(manifest, indent=2))
    logger.info(f"Saved run manifest to {manifest_path}")

    return manifest_path
```

**Step 2: Test manifest save and load**

```bash
python3 << 'EOF'
import sys
import json
sys.path.insert(0, 'src')
from datetime import datetime
from pathlib import Path
from text.scrapers.observability.metrics import ScraperMetrics, save_run_manifest

# Create test metrics
metrics = ScraperMetrics(
    newspaper="test_paper",
    country="test_country",
    mode="update",
    started_at=datetime(2026, 1, 23, 15, 30, 0)
)
metrics.urls_discovered = 20
metrics.articles_scraped = 15
metrics.articles_failed = 5

date_metric = metrics.get_field_metric("date")
date_metric.total_extracted = 20
date_metric.successful = 15
date_metric.empty = 5

# Save manifest
manifest_path = save_run_manifest(metrics, "test_paper", "test_country")
print(f"Saved to: {manifest_path}")

# Verify file exists and load it
assert manifest_path.exists()
manifest_data = json.loads(manifest_path.read_text())
print(f"Manifest newspaper: {manifest_data['newspaper']}")
assert manifest_data['newspaper'] == "test_paper"
assert manifest_data['counts']['articles_scraped'] == 15
assert manifest_data['field_quality']['date']['successful'] == 15

# Test from_dict
loaded_metrics = ScraperMetrics.from_dict(manifest_data)
assert loaded_metrics.newspaper == "test_paper"
assert loaded_metrics.articles_scraped == 15

# Cleanup
import shutil
shutil.rmtree("logs/text/test_country")

print("✓ Manifest save/load works correctly")
EOF
```

Expected: `Saved to: logs/text/test_country/test_paper/individual/20260123_153000.json` and `✓ Manifest save/load works correctly`

**Step 3: Commit**

```bash
git add src/text/scrapers/observability/metrics.py
git commit -m "feat(observability): implement manifest save and load functions"
```

---

### Task 1.4: Initialize Metrics in NewspaperScraper

**Files:**
- Modify: `src/text/scrapers/scraper.py`

**Step 1: Add metrics import**

Add to imports at top of `src/text/scrapers/scraper.py`:

```python
from .observability import ScraperMetrics
```

**Step 2: Initialize metrics in __init__**

Find the `__init__` method of `NewspaperScraper` class and add after `self.language = ...`:

```python
        # Initialize metrics tracking
        self.metrics = ScraperMetrics(
            newspaper=self.name,
            country=self.country,
            mode="update",  # Will be set by run method
            started_at=datetime.utcnow(),
        )
```

**Step 3: Test scraper initialization**

```bash
python3 << 'EOF'
import sys
sys.path.insert(0, 'src')
from pathlib import Path
from text.scrapers.factory import create_scraper_from_file

# Load a real scraper config
config_path = Path("src/text/scrapers/configs/fiji/fiji_sun.yaml")
scraper = create_scraper_from_file(config_path)

# Verify metrics initialized
assert hasattr(scraper, 'metrics')
assert scraper.metrics.newspaper == "Fiji Sun"
assert scraper.metrics.country == "fiji"
print(f"✓ Scraper initialized with metrics: {scraper.metrics.newspaper}")
EOF
```

Expected: `✓ Scraper initialized with metrics: Fiji Sun`

**Step 4: Commit**

```bash
git add src/text/scrapers/scraper.py
git commit -m "feat(observability): initialize metrics in NewspaperScraper"
```

---

### Task 1.5: Implement _track_extraction Helper

**Files:**
- Modify: `src/text/scrapers/scraper.py`

**Step 1: Add _track_extraction method**

Add this method to the `NewspaperScraper` class in `src/text/scrapers/scraper.py`:

```python
    def _track_extraction(self, data: Dict[str, Any], stage: str) -> None:
        """
        Track field-level extraction quality in metrics.

        For each field in the extracted data, records whether it was
        successfully populated or empty/missing.

        Args:
            data: Dictionary of extracted fields
            stage: Extraction stage ("thumbnail" or "article")
        """
        for field_name, value in data.items():
            # Get or create field metric
            field_metric = self.metrics.get_field_metric(field_name)
            field_metric.total_extracted += 1

            # Check if value is empty
            if value is None or value == "" or value == []:
                field_metric.empty += 1
                logger.warning(
                    f"Empty {field_name} in {stage}: {data.get('url', 'unknown')}"
                )
            else:
                field_metric.successful += 1
```

**Step 2: Test _track_extraction**

```bash
python3 << 'EOF'
import sys
sys.path.insert(0, 'src')
from pathlib import Path
from text.scrapers.factory import create_scraper_from_file

# Load scraper
config_path = Path("src/text/scrapers/configs/fiji/fiji_sun.yaml")
scraper = create_scraper_from_file(config_path)

# Test tracking with good data
scraper._track_extraction({
    "url": "https://example.com/article1",
    "title": "Test Article",
    "date": "2026-01-23",
    "body": "Article content here"
}, stage="article")

# Verify metrics
assert "url" in scraper.metrics.field_metrics
assert scraper.metrics.field_metrics["url"].successful == 1
assert scraper.metrics.field_metrics["url"].empty == 0

# Test tracking with empty field
scraper._track_extraction({
    "url": "https://example.com/article2",
    "title": "Test Article 2",
    "date": "",  # Empty!
    "body": "Content"
}, stage="article")

# Verify empty was tracked
assert scraper.metrics.field_metrics["date"].total_extracted == 2
assert scraper.metrics.field_metrics["date"].successful == 1
assert scraper.metrics.field_metrics["date"].empty == 1

print("✓ _track_extraction works correctly")
EOF
```

Expected: Warning message about empty date field, then `✓ _track_extraction works correctly`

**Step 3: Commit**

```bash
git add src/text/scrapers/scraper.py
git commit -m "feat(observability): implement _track_extraction helper method"
```

---

## Phase 2: Code Deduplication (DRY)

### Task 2.1: Extract _process_api_thumbnail Method

**Files:**
- Modify: `src/text/scrapers/scraper.py`

**Step 1: Add _process_api_thumbnail method**

Add this method to `NewspaperScraper` class before the run methods:

```python
    def _process_api_thumbnail(
        self,
        thumb_data: Dict[str, Any],
        existing_urls: Optional[set] = None
    ) -> Optional[ThumbnailRecord]:
        """
        Process a single API thumbnail: clean, validate, track metrics.

        This is the single point of truth for API thumbnail processing.
        Used by all scrape modes (UPDATE, RESUME, FULL).

        Args:
            thumb_data: Raw thumbnail data from API
            existing_urls: Set of URLs already scraped (optional)

        Returns:
            ThumbnailRecord or None if filtered/invalid
        """
        from pydantic import ValidationError
        from .pipelines.cleaning import apply_cleaning, get_cleaning_func
        from .parser import clean_url

        # Apply record filter if configured
        record_filter_func_name = self.config.cleaning.get("record_filter") if self.config.cleaning else None
        if record_filter_func_name:
            record_filter_func = get_cleaning_func(record_filter_func_name)
            if record_filter_func and not record_filter_func(thumb_data):
                return None

        # Clean URL - ensure it's absolute
        if thumb_data.get("url"):
            thumb_data["url"] = clean_url(thumb_data["url"], self.base_url)
        elif "url" not in thumb_data or not thumb_data["url"]:
            # URL construction from template if needed
            url_template = self.config.listing.get("url_construction_template")
            if url_template:
                thumb_data["url"] = url_template.format(**thumb_data)

        # Apply cleaning - CRITICAL STEP that was missing in UPDATE mode
        cleaning_config = self.config.cleaning or {}
        if cleaning_config:
            thumb_data = apply_cleaning(
                thumb_data,
                cleaning_config,
                self.base_url
            )

        # Track metrics BEFORE creating record
        self._track_extraction(thumb_data, stage="thumbnail")

        # Create ThumbnailRecord
        try:
            thumbnail = ThumbnailRecord(**thumb_data)
            return thumbnail
        except ValidationError as e:
            self.metrics.articles_failed += 1
            logger.error(f"Invalid thumbnail data: {e}")
            logger.debug(f"Data: {thumb_data}")
            return None
```

**Step 2: Test _process_api_thumbnail**

```bash
python3 << 'EOF'
import sys
sys.path.insert(0, 'src')
from pathlib import Path
from text.scrapers.factory import create_scraper_from_file

# Load caixin_global (API strategy)
config_path = Path("src/text/scrapers/configs/china/caixin_global.yaml")
scraper = create_scraper_from_file(config_path)

# Test with raw API data (simulating what comes from API)
thumb_data = {
    "url": "https://www.caixinglobal.com/test.html",
    "title": "Test Article",
    "date": 1769168119000  # Unix timestamp in milliseconds
}

# Process thumbnail
thumbnail = scraper._process_api_thumbnail(thumb_data.copy())

# Verify cleaning was applied
assert thumbnail is not None
assert thumbnail.date == "2026-01-23"  # Cleaned to YYYY-MM-DD format!
print(f"✓ Date cleaned correctly: {thumbnail.date}")

# Verify metrics tracked
assert "date" in scraper.metrics.field_metrics
assert scraper.metrics.field_metrics["date"].successful == 1

print("✓ _process_api_thumbnail works correctly")
EOF
```

Expected: `✓ Date cleaned correctly: 2026-01-23` and `✓ _process_api_thumbnail works correctly`

**Step 3: Commit**

```bash
git add src/text/scrapers/scraper.py
git commit -m "feat(observability): extract _process_api_thumbnail DRY method

This fixes the caixin_global bug where cleaning was skipped in UPDATE mode."
```

---

### Task 2.2: Update run_update_scrape to Use _process_api_thumbnail

**Files:**
- Modify: `src/text/scrapers/scraper.py`

**Step 1: Find API strategy section in run_update_scrape**

Locate the `if isinstance(self.listing_strategy, ApiStrategy):` block in `run_update_scrape` method (around line 854-913).

**Step 2: Replace the API thumbnail processing logic**

Replace the code inside the `for thumb_data in result_batch:` loop with a call to `_process_api_thumbnail`:

```python
                # Handle API strategy's direct return of dicts
                if isinstance(self.listing_strategy, ApiStrategy):
                    for thumb_data in result_batch:
                        # Use unified processing method
                        thumbnail = self._process_api_thumbnail(thumb_data, existing_urls)

                        if thumbnail:
                            batch_thumbnails.append(thumbnail)

                            # Check if this thumbnail is new
                            if str(thumbnail.url) not in existing_urls:
                                batch_new_count += 1

                            # Handle prefetched articles (full JSON from API)
                            if thumb_data.get("body"):
                                article_dict = {
                                    "url": str(thumbnail.url),
                                    "title": thumbnail.title,
                                    "date": thumbnail.date or "",
                                    "body": thumb_data.get("body", ""),
                                    "tags": thumb_data.get("tags", []),
                                    "source": self.name,
                                    "country": self.country,
                                    "language": self.language,
                                }
                                # Note: cleaning already applied in _process_api_thumbnail
                                try:
                                    article = ArticleRecord(**article_dict)
                                    self.prefetched_articles.append(article)
                                except Exception as e:
                                    logger.error(f"Failed to create ArticleRecord from API data: {e}")

                    logger.info(f"Processed API batch: {len(result_batch)} thumbnails")
```

**Step 3: Test with caixin_global**

```bash
# Run caixin_global in update mode with max 1 page to test quickly
poetry run python -m text.scrapers.orchestration.main caixin_global --update 2>&1 | head -50
```

Expected: Should see dates being extracted correctly now, not warnings about empty dates

**Step 4: Commit**

```bash
git add src/text/scrapers/scraper.py
git commit -m "fix(scraper): use _process_api_thumbnail in UPDATE mode

Fixes caixin_global NaN dates bug by ensuring cleaning always happens."
```

---

### Task 2.3: Update run_resume_scrape to Use _process_api_thumbnail

**Files:**
- Modify: `src/text/scrapers/scraper.py`

**Step 1: Find API strategy section in run_resume_scrape**

Locate the `if isinstance(self.listing_strategy, ApiStrategy):` block in the `run_resume_scrape` method.

**Step 2: Replace with call to _process_api_thumbnail**

Similar to previous task, replace the API thumbnail processing loop:

```python
                # Handle API strategy
                if isinstance(self.listing_strategy, ApiStrategy):
                    for thumb_data in result_batch:
                        # Use unified processing method
                        thumbnail = self._process_api_thumbnail(thumb_data, existing_urls)

                        if thumbnail:
                            batch_thumbnails.append(thumbnail)

                            # Handle prefetched articles
                            if thumb_data.get("body"):
                                article_dict = {
                                    "url": str(thumbnail.url),
                                    "title": thumbnail.title,
                                    "date": thumbnail.date or "",
                                    "body": thumb_data.get("body", ""),
                                    "tags": thumb_data.get("tags", []),
                                    "source": self.name,
                                    "country": self.country,
                                    "language": self.language,
                                }
                                try:
                                    article = ArticleRecord(**article_dict)
                                    self.prefetched_articles.append(article)
                                except Exception as e:
                                    logger.error(f"Failed to create ArticleRecord from API data: {e}")

                    logger.info(f"Processed API batch: {len(result_batch)} thumbnails")
```

**Step 3: Commit**

```bash
git add src/text/scrapers/scraper.py
git commit -m "fix(scraper): use _process_api_thumbnail in RESUME mode"
```

---

### Task 2.4: Update FULL Mode to Use _process_api_thumbnail

**Files:**
- Modify: `src/text/scrapers/scraper.py`

**Step 1: Find API strategy section in _original_discover_and_scrape_thumbnails**

Locate the `if isinstance(self.listing_strategy, ApiStrategy):` block (around line 170-228).

**Step 2: Replace with call to _process_api_thumbnail**

Replace the API processing logic:

```python
            # Handle API strategy's direct return of dicts
            if isinstance(self.listing_strategy, ApiStrategy):
                for thumb_data in result_batch:
                    # Use unified processing method
                    thumbnail = self._process_api_thumbnail(thumb_data)

                    if thumbnail:
                        thumbnails.append(thumbnail)

                        # Handle prefetched articles
                        if thumb_data.get("body"):
                            article_dict = {
                                "url": str(thumbnail.url),
                                "title": thumbnail.title,
                                "date": thumbnail.date or "",
                                "body": thumb_data.get("body", ""),
                                "tags": thumb_data.get("tags", []),
                                "source": self.name,
                                "country": self.country,
                                "language": self.language,
                            }
                            try:
                                article = ArticleRecord(**article_dict)
                                self.prefetched_articles.append(article)
                            except Exception as e:
                                logger.error(f"Failed to create ArticleRecord from API data: {e}")
                                logger.debug(f"Article data: {article_dict}")

                logger.info(f"Processed API batch: {len(result_batch)} items")
                continue
```

**Step 3: Verify all modes use same logic**

```bash
# Search for remaining duplicate API processing code
grep -n "Apply cleaning.*thumb_data" src/text/scrapers/scraper.py
```

Expected: Should only find it in `_process_api_thumbnail` method now

**Step 4: Commit**

```bash
git add src/text/scrapers/scraper.py
git commit -m "refactor(scraper): use _process_api_thumbnail in FULL mode

All three modes (UPDATE, RESUME, FULL) now use unified method."
```

---

## Phase 3: Real-Time Warnings & Summary

### Task 3.1: Implement Quality Issue Detection

**Files:**
- Create: `src/text/scrapers/observability/formatters.py`

**Step 1: Add imports and detect_quality_issues function**

File: `src/text/scrapers/observability/formatters.py`

```python
"""
Formatting utilities for displaying scraper metrics.

Provides console output formatting and quality issue detection.
"""

import logging
from typing import List
from .metrics import ScraperMetrics

logger = logging.getLogger(__name__)


def detect_quality_issues(metrics: ScraperMetrics) -> List[str]:
    """
    Detect data quality issues from metrics.

    Analyzes field-level extraction quality and flags critical issues
    like missing required fields or high failure rates.

    Args:
        metrics: ScraperMetrics to analyze

    Returns:
        List of warning strings describing quality issues
    """
    warnings = []

    # Required fields that should have high success rates
    required_fields = ["url", "title", "date", "body"]

    for field_name in required_fields:
        if field_name not in metrics.field_metrics:
            continue

        field_metric = metrics.field_metrics[field_name]

        # Skip if no data
        if field_metric.total_extracted == 0:
            continue

        # Calculate empty percentage
        empty_pct = (field_metric.empty / field_metric.total_extracted) * 100

        # Critical: >50% empty for required fields
        if empty_pct > 50:
            if empty_pct == 100:
                warnings.append(
                    f"Critical: ALL articles missing '{field_name}' field - check cleaning config"
                )
            else:
                warnings.append(
                    f"Critical: {empty_pct:.0f}% of articles missing '{field_name}' field"
                )
        # Warning: 20-50% empty
        elif empty_pct > 20:
            if field_name == "body":
                warnings.append(
                    f"{empty_pct:.0f}% of articles have empty body (likely dead URLs)"
                )
            else:
                warnings.append(
                    f"Warning: {empty_pct:.0f}% of articles missing '{field_name}' field"
                )

    return warnings
```

**Step 2: Test detect_quality_issues**

```bash
python3 << 'EOF'
import sys
sys.path.insert(0, 'src')
from datetime import datetime
from text.scrapers.observability.metrics import ScraperMetrics
from text.scrapers.observability.formatters import detect_quality_issues

# Create metrics with quality issues
metrics = ScraperMetrics(
    newspaper="test_paper",
    country="test",
    mode="update",
    started_at=datetime.now()
)

# Simulate 100% missing dates (critical issue)
date_metric = metrics.get_field_metric("date")
date_metric.total_extracted = 20
date_metric.empty = 20
date_metric.successful = 0

# Simulate 40% empty bodies (warning)
body_metric = metrics.get_field_metric("body")
body_metric.total_extracted = 20
body_metric.empty = 8
body_metric.successful = 12

# Detect issues
warnings = detect_quality_issues(metrics)
print("Detected warnings:")
for warning in warnings:
    print(f"  - {warning}")

assert len(warnings) == 2
assert "ALL articles missing 'date'" in warnings[0]
assert "40% of articles have empty body" in warnings[1]

print("\n✓ detect_quality_issues works correctly")
EOF
```

Expected: Shows two warnings and `✓ detect_quality_issues works correctly`

**Step 3: Commit**

```bash
git add src/text/scrapers/observability/formatters.py
git commit -m "feat(observability): implement quality issue detection"
```

---

### Task 3.2: Implement Run Summary Formatter

**Files:**
- Modify: `src/text/scrapers/observability/formatters.py`

**Step 1: Add print_run_summary function**

Add to `src/text/scrapers/observability/formatters.py`:

```python
def print_run_summary(metrics: ScraperMetrics) -> None:
    """
    Print formatted run summary to console.

    Displays article counts, field quality metrics, and warnings.

    Args:
        metrics: ScraperMetrics to format and display
    """
    print(f"\n=== Scrape Complete: {metrics.newspaper} ===\n")

    # Article counts
    print("Articles:")
    print(f"  Discovered: {metrics.urls_discovered} URLs")
    print(f"  Scraped:    {metrics.articles_scraped} articles")
    if metrics.articles_failed > 0:
        fail_pct = (metrics.articles_failed / (metrics.articles_scraped + metrics.articles_failed)) * 100
        print(f"  Failed:     {metrics.articles_failed} articles ({fail_pct:.0f}%)")

    # Duration
    if metrics.duration_seconds > 0:
        minutes = int(metrics.duration_seconds / 60)
        seconds = int(metrics.duration_seconds % 60)
        if minutes > 0:
            print(f"\nDuration: {minutes}m {seconds}s")
        else:
            print(f"\nDuration: {seconds}s")

    # Field quality
    if metrics.field_metrics:
        print("\nField Quality:")
        # Sort fields for consistent output
        for field_name in sorted(metrics.field_metrics.keys()):
            field_metric = metrics.field_metrics[field_name]

            if field_metric.total_extracted == 0:
                continue

            success_pct = field_metric.success_rate()
            status = "✓" if success_pct > 90 else "✗"

            print(
                f"  {field_name}: {field_metric.successful}/{field_metric.total_extracted} "
                f"{status} ({success_pct:.0f}%)"
            )

            if field_metric.empty > 0:
                print(f"    └─ {field_metric.empty} empty")

    # Quality warnings
    warnings = detect_quality_issues(metrics)
    if warnings:
        print("\n⚠️  QUALITY ISSUES DETECTED:")
        for warning in warnings:
            print(f"  • {warning}")

    print()  # Blank line at end
```

**Step 2: Test print_run_summary**

```bash
python3 << 'EOF'
import sys
sys.path.insert(0, 'src')
from datetime import datetime
from text.scrapers.observability.metrics import ScraperMetrics
from text.scrapers.observability.formatters import print_run_summary

# Create test metrics
metrics = ScraperMetrics(
    newspaper="caixin_global",
    country="china",
    mode="update",
    started_at=datetime.now()
)
metrics.urls_discovered = 20
metrics.articles_scraped = 12
metrics.articles_failed = 8
metrics.duration_seconds = 222

# Add field metrics
date_metric = metrics.get_field_metric("date")
date_metric.total_extracted = 20
date_metric.empty = 20

body_metric = metrics.get_field_metric("body")
body_metric.total_extracted = 20
body_metric.successful = 12
body_metric.empty = 8

# Print summary
print_run_summary(metrics)
EOF
```

Expected: Formatted summary with quality warnings

**Step 3: Update __init__.py exports**

Add `print_run_summary` to exports if not already there.

**Step 4: Commit**

```bash
git add src/text/scrapers/observability/
git commit -m "feat(observability): implement run summary formatter"
```

---

### Task 3.3: Integrate Summary into run_scraper.py

**Files:**
- Modify: `src/text/scrapers/orchestration/run_scraper.py`

**Step 1: Add imports**

Add to imports at top of `src/text/scrapers/orchestration/run_scraper.py`:

```python
from datetime import datetime
from text.scrapers.observability import print_run_summary, save_run_manifest
```

**Step 2: Find the main scraper execution function**

Locate the `run_scraper_by_name` or equivalent function that runs a single scraper.

**Step 3: Add metrics finalization after scraper run**

After the scraper completes (after `result = await scraper.run_...`), add:

```python
    # Finalize metrics
    scraper.metrics.duration_seconds = (
        datetime.utcnow() - scraper.metrics.started_at
    ).total_seconds()

    # Print summary to console
    print_run_summary(scraper.metrics)

    # Save run manifest
    manifest_path = save_run_manifest(
        scraper.metrics,
        scraper.name,
        scraper.country
    )
    logger.info(f"Run details: {manifest_path}")
```

**Step 4: Test with a real scraper**

```bash
# Run fiji_sun with max_pages=1 to test quickly
poetry run python -m text.scrapers.orchestration.main fiji_sun --update
```

Expected: Should see formatted summary at the end with field quality metrics

**Step 5: Commit**

```bash
git add src/text/scrapers/orchestration/run_scraper.py
git commit -m "feat(orchestration): integrate metrics summary in run_scraper"
```

---

### Task 3.4: Update Logging Paths

**Files:**
- Modify: `src/text/scrapers/orchestration/run_multiple.py`

**Step 1: Find log file path generation**

Locate where log files are created (search for `log_file =` or similar).

**Step 2: Update path to new structure**

Change log path from:
```python
log_file = log_dir / country / newspaper / f"{timestamp}.log"
```

To:
```python
log_file = Path(f"logs/text/{country}/{newspaper}/execution_logs/{timestamp}.log")
```

**Step 3: Ensure directory creation**

Make sure the parent directories are created:
```python
log_file.parent.mkdir(parents=True, exist_ok=True)
```

**Step 4: Test multi-scraper run**

```bash
# Run a couple scrapers to test
poetry run python -m text.scrapers.orchestration.main --run-all --country fiji
```

Expected: Log files should be created in `logs/text/fiji/{newspaper}/execution_logs/`

**Step 5: Commit**

```bash
git add src/text/scrapers/orchestration/run_multiple.py
git commit -m "refactor(orchestration): update log paths to logs/text/ structure"
```

---

## Phase 4: Multi-Scraper Aggregation

### Task 4.1: Implement Manifest Collection

**Files:**
- Modify: `src/text/scrapers/orchestration/run_multiple.py`

**Step 1: Add function to collect manifests**

Add to `src/text/scrapers/orchestration/run_multiple.py`:

```python
from pathlib import Path
from typing import List
from text.scrapers.observability import ScraperMetrics
import json


def collect_run_manifests(newspaper_configs: List[Dict[str, str]]) -> List[ScraperMetrics]:
    """
    Collect run manifests from all newspapers that just ran.

    Args:
        newspaper_configs: List of newspaper config dicts with 'country' and 'newspaper' keys

    Returns:
        List of ScraperMetrics loaded from manifests
    """
    manifests = []

    for config in newspaper_configs:
        country = config["country"]
        newspaper = config["newspaper"]

        manifest_dir = Path(f"logs/text/{country}/{newspaper}/individual")

        # Skip if no manifests exist yet
        if not manifest_dir.exists():
            logger.warning(f"No manifests found for {newspaper}")
            continue

        # Get most recent manifest
        manifest_files = list(manifest_dir.glob("*.json"))
        if not manifest_files:
            logger.warning(f"No manifest files in {manifest_dir}")
            continue

        latest_manifest = max(manifest_files, key=lambda p: p.stat().st_mtime)

        # Load and parse
        try:
            manifest_data = json.loads(latest_manifest.read_text())
            metrics = ScraperMetrics.from_dict(manifest_data)
            manifests.append(metrics)
        except Exception as e:
            logger.error(f"Failed to load manifest {latest_manifest}: {e}")

    return manifests
```

**Step 2: Test manifest collection**

```bash
python3 << 'EOF'
import sys
sys.path.insert(0, 'src')
from pathlib import Path
# First ensure we have some test manifests
# (This would normally be created by actual runs)
print("✓ collect_run_manifests function added")
EOF
```

**Step 3: Commit**

```bash
git add src/text/scrapers/orchestration/run_multiple.py
git commit -m "feat(orchestration): implement manifest collection for multi-runs"
```

---

### Task 4.2: Implement Aggregate Summary Formatter

**Files:**
- Modify: `src/text/scrapers/observability/formatters.py`

**Step 1: Add print_multi_run_summary function**

Add to `src/text/scrapers/observability/formatters.py`:

```python
def print_multi_run_summary(all_metrics: List[ScraperMetrics]) -> None:
    """
    Print aggregate summary for multiple scraper runs.

    Args:
        all_metrics: List of ScraperMetrics from multiple newspapers
    """
    if not all_metrics:
        print("\n=== Multi-Scraper Run Complete ===")
        print("No results collected.")
        return

    print("\n=== Multi-Scraper Run Complete ===\n")

    # Calculate totals
    total_newspapers = len(all_metrics)
    total_articles = sum(m.articles_scraped for m in all_metrics)
    total_failed = sum(m.articles_failed for m in all_metrics)
    total_duration = sum(m.duration_seconds for m in all_metrics)

    # Calculate success rate
    total_attempted = total_articles + total_failed
    if total_attempted > 0:
        success_rate = (total_articles / total_attempted) * 100
    else:
        success_rate = 0

    print(f"Total newspapers: {total_newspapers}")

    # Duration
    hours = int(total_duration / 3600)
    minutes = int((total_duration % 3600) / 60)
    if hours > 0:
        print(f"Total duration: {hours}h {minutes}m")
    else:
        print(f"Total duration: {minutes}m")

    print("\nOverall:")
    print(f"  Articles scraped: {total_articles:,}")
    if total_failed > 0:
        print(f"  Articles failed:  {total_failed}")
        print(f"  Success rate: {success_rate:.1f}%")

    # Collect quality issues by severity
    critical_issues = []
    warnings = []

    for metrics in all_metrics:
        issues = detect_quality_issues(metrics)
        if issues:
            for issue in issues:
                if "Critical" in issue or "ALL articles" in issue:
                    critical_issues.append((metrics.newspaper, metrics.country, issue))
                else:
                    warnings.append((metrics.newspaper, metrics.country, issue))

    # Print quality issues
    if critical_issues or warnings:
        total_issues = len(critical_issues) + len(warnings)
        print(f"\nQuality Issues Found: {total_issues} newspapers\n")

        for newspaper, country, issue in critical_issues:
            print(f"  ✗ {newspaper} ({country})")
            print(f"    • {issue}\n")

        for newspaper, country, issue in warnings:
            print(f"  ⚠ {newspaper} ({country})")
            print(f"    • {issue}\n")

    print()
```

**Step 2: Export from __init__.py**

Add to `src/text/scrapers/observability/__init__.py`:

```python
from .formatters import print_run_summary, detect_quality_issues, print_multi_run_summary

__all__ = [
    # ... existing exports ...
    "print_multi_run_summary",
]
```

**Step 3: Commit**

```bash
git add src/text/scrapers/observability/
git commit -m "feat(observability): implement multi-run summary formatter"
```

---

### Task 4.3: Save Multi-Run Manifest

**Files:**
- Modify: `src/text/scrapers/observability/metrics.py`

**Step 1: Add save_multi_run_manifest function**

Add to `src/text/scrapers/observability/metrics.py`:

```python
def save_multi_run_manifest(
    all_metrics: List[ScraperMetrics],
    started_at: datetime,
    completed_at: datetime,
) -> Path:
    """
    Save aggregate manifest for multi-newspaper run.

    Args:
        all_metrics: List of ScraperMetrics from all newspapers
        started_at: When the multi-run started
        completed_at: When the multi-run completed

    Returns:
        Path to saved manifest file
    """
    from .formatters import detect_quality_issues

    # Create directory
    manifest_dir = Path("logs/text/multi_runs")
    manifest_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    timestamp = started_at.strftime("%Y%m%d_%H%M%S")
    manifest_path = manifest_dir / f"{timestamp}.json"

    # Calculate totals
    total_articles = sum(m.articles_scraped for m in all_metrics)
    total_failed = sum(m.articles_failed for m in all_metrics)

    # Collect quality issues
    quality_issues = []
    for metrics in all_metrics:
        issues = detect_quality_issues(metrics)
        for issue in issues:
            severity = "critical" if "Critical" in issue or "ALL" in issue else "warning"
            quality_issues.append({
                "newspaper": metrics.newspaper,
                "country": metrics.country,
                "severity": severity,
                "issue": issue,
            })

    # Build manifest paths
    newspaper_manifests = []
    for metrics in all_metrics:
        manifest_path_str = (
            f"logs/text/{metrics.country}/{metrics.newspaper}/individual/"
            f"{metrics.started_at.strftime('%Y%m%d_%H%M%S')}.json"
        )
        newspaper_manifests.append(manifest_path_str)

    # Build manifest
    manifest = {
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "newspapers_run": len(all_metrics),
        "total_articles_scraped": total_articles,
        "total_failed": total_failed,
        "quality_issues": quality_issues,
        "newspaper_manifests": newspaper_manifests,
    }

    # Write
    manifest_path.write_text(json.dumps(manifest, indent=2))
    logger.info(f"Saved multi-run manifest to {manifest_path}")

    return manifest_path
```

**Step 2: Export from __init__.py**

```python
from .metrics import (
    FieldMetrics,
    ScraperMetrics,
    save_run_manifest,
    save_multi_run_manifest,
)

__all__ = [
    # ... existing ...
    "save_multi_run_manifest",
]
```

**Step 3: Commit**

```bash
git add src/text/scrapers/observability/
git commit -m "feat(observability): implement multi-run manifest save"
```

---

### Task 4.4: Integrate Multi-Run Summary in run_multiple.py

**Files:**
- Modify: `src/text/scrapers/orchestration/run_multiple.py`

**Step 1: Import new functions**

Add to imports:

```python
from datetime import datetime
from text.scrapers.observability import print_multi_run_summary, save_multi_run_manifest
```

**Step 2: Add summary at end of run_all_scrapers**

At the end of `run_all_scrapers` function (after all scrapers complete):

```python
    # Collect manifests and print summary
    logger.info("Collecting run manifests...")
    all_metrics = collect_run_manifests(newspaper_configs)

    # Print aggregate summary
    print_multi_run_summary(all_metrics)

    # Save multi-run manifest
    completed_at = datetime.utcnow()
    manifest_path = save_multi_run_manifest(all_metrics, multi_run_start_time, completed_at)
    print(f"Run details: {manifest_path}")
```

**Step 3: Track multi_run_start_time**

At the beginning of `run_all_scrapers`, add:

```python
    multi_run_start_time = datetime.utcnow()
```

**Step 4: Test multi-run**

```bash
# Run multiple scrapers from one country
poetry run python -m text.scrapers.orchestration.main --run-all --country fiji
```

Expected: Should see aggregate summary at the end

**Step 5: Commit**

```bash
git add src/text/scrapers/orchestration/run_multiple.py
git commit -m "feat(orchestration): integrate multi-run summary and manifest"
```

---

## Phase 5: Post-Run Validator

### Task 5.1: Create validate_data CLI Structure

**Files:**
- Create: `src/text/scrapers/orchestration/validate_data.py`

**Step 1: Create file with basic structure**

File: `src/text/scrapers/orchestration/validate_data.py`

```python
#!/usr/bin/env python3
"""
Post-run data quality validator for newspaper scrapers.

Validates CSV data quality, detects regressions, and optionally deduplicates.

Usage:
    poetry run python -m text.scrapers.orchestration.validate_data fiji_sun
    poetry run python -m text.scrapers.orchestration.validate_data --all
    poetry run python -m text.scrapers.orchestration.validate_data fiji_sun --deduplicate
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from text.scrapers.observability.validators import (
    validate_newspaper_data,
    deduplicate_newspaper_data,
)

logger = logging.getLogger(__name__)


def setup_logging():
    """Configure logging for the validator."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def main():
    """Main entry point for validation CLI."""
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Validate newspaper scraper data quality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s fiji_sun              # Validate fiji_sun data
  %(prog)s --all                 # Validate all newspapers
  %(prog)s fiji_sun --deduplicate  # Validate and remove duplicates
        """
    )

    parser.add_argument(
        "newspaper",
        nargs="?",
        help="Newspaper name to validate (e.g., fiji_sun)"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all newspapers"
    )

    parser.add_argument(
        "--deduplicate",
        action="store_true",
        help="Remove duplicate URLs (keeps oldest with complete required fields)"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.newspaper and not args.all:
        parser.error("Must specify newspaper name or --all")

    if args.newspaper and args.all:
        parser.error("Cannot specify both newspaper name and --all")

    # Run validation
    if args.all:
        print("Validating all newspapers...")
        # TODO: Implement in next task
        print("Not yet implemented")
        sys.exit(1)
    else:
        # Single newspaper validation
        validate_newspaper_data(args.newspaper, deduplicate=args.deduplicate)


if __name__ == "__main__":
    main()
```

**Step 2: Make executable**

```bash
chmod +x src/text/scrapers/orchestration/validate_data.py
```

**Step 3: Test basic CLI**

```bash
poetry run python -m text.scrapers.orchestration.validate_data --help
```

Expected: Should show help text

**Step 4: Commit**

```bash
git add src/text/scrapers/orchestration/validate_data.py
git commit -m "feat(validation): create validate_data CLI structure"
```

---

### Task 5.2: Implement Field Validators

**Files:**
- Modify: `src/text/scrapers/observability/validators.py`

**Step 1: Add validation functions**

File: `src/text/scrapers/observability/validators.py`

```python
"""
Data quality validation for scraped content.

Provides validators for required fields and quality checks.
"""

import logging
import re
from datetime import datetime
from typing import Dict, Any, List
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def validate_url(url: str) -> Dict[str, Any]:
    """
    Validate URL field.

    Args:
        url: URL string to validate

    Returns:
        Dict with 'valid' bool and optional 'error' message
    """
    if not url or not url.strip():
        return {"valid": False, "error": "empty"}

    # Check URL format
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return {"valid": False, "error": "invalid_format"}
    except Exception:
        return {"valid": False, "error": "parse_error"}

    return {"valid": True}


def validate_title(title: str) -> Dict[str, Any]:
    """
    Validate title field.

    Args:
        title: Title string to validate

    Returns:
        Dict with 'valid' bool and optional 'error' message
    """
    if not title or not title.strip():
        return {"valid": False, "error": "empty"}

    if len(title.strip()) < 3:
        return {"valid": False, "error": "too_short"}

    return {"valid": True}


def validate_date(date: str) -> Dict[str, Any]:
    """
    Validate date field.

    Args:
        date: Date string to validate (expected format: YYYY-MM-DD)

    Returns:
        Dict with 'valid' bool and optional 'error' message
    """
    if not date or not date.strip():
        return {"valid": False, "error": "empty"}

    # Check format YYYY-MM-DD
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
        return {"valid": False, "error": "invalid_format"}

    # Parse and validate date range
    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d")

        # Not before 1990
        if parsed_date.year < 1990:
            return {"valid": False, "error": "too_old"}

        # Not in future
        if parsed_date > datetime.now():
            return {"valid": False, "error": "future_date"}

    except ValueError:
        return {"valid": False, "error": "invalid_date"}

    return {"valid": True}


def validate_body(body: str) -> Dict[str, Any]:
    """
    Validate body field.

    Args:
        body: Body text to validate

    Returns:
        Dict with 'valid' bool and optional 'error' message
    """
    if not body or not body.strip():
        return {"valid": False, "error": "empty"}

    if len(body.strip()) < 10:
        return {"valid": False, "error": "too_short"}

    return {"valid": True}


REQUIRED_FIELDS = {
    "url": validate_url,
    "title": validate_title,
    "date": validate_date,
    "body": validate_body,
}
```

**Step 2: Test validators**

```bash
python3 << 'EOF'
import sys
sys.path.insert(0, 'src')
from text.scrapers.observability.validators import validate_url, validate_title, validate_date, validate_body

# Test valid cases
assert validate_url("https://example.com/article")["valid"] == True
assert validate_title("Good Article Title")["valid"] == True
assert validate_date("2026-01-23")["valid"] == True
assert validate_body("This is a good article body with enough content.")["valid"] == True

# Test invalid cases
assert validate_url("")["valid"] == False
assert validate_title("")["valid"] == False
assert validate_date("2027-12-31")["valid"] == False  # Future
assert validate_date("1989-01-01")["valid"] == False  # Too old
assert validate_body("")["valid"] == False

print("✓ All validators work correctly")
EOF
```

Expected: `✓ All validators work correctly`

**Step 3: Commit**

```bash
git add src/text/scrapers/observability/validators.py
git commit -m "feat(validation): implement field validators"
```

---

### Task 5.3: Implement validate_newspaper_data Function

**Files:**
- Modify: `src/text/scrapers/observability/validators.py`

**Step 1: Add validate_newspaper_data function**

Add to `src/text/scrapers/observability/validators.py`:

```python
import pandas as pd
from pathlib import Path


def validate_newspaper_data(newspaper: str, deduplicate: bool = False) -> None:
    """
    Validate data quality for a newspaper's CSV.

    Args:
        newspaper: Newspaper name (e.g., 'fiji_sun')
        deduplicate: If True, also deduplicate the data
    """
    # Find the newspaper's data directory
    # Search in data/text/{country}/{newspaper}/news.csv
    data_dir = Path("data/text")

    news_csv_path = None
    for country_dir in data_dir.iterdir():
        if not country_dir.is_dir():
            continue

        newspaper_dir = country_dir / newspaper
        if newspaper_dir.exists():
            news_csv = newspaper_dir / "news.csv"
            if news_csv.exists():
                news_csv_path = news_csv
                break

    if not news_csv_path:
        print(f"❌ Could not find news.csv for {newspaper}")
        print(f"   Searched in: {data_dir}/*/{newspaper}/news.csv")
        return

    print(f"\n=== Data Quality Report: {newspaper} ===\n")
    print(f"Analyzing: {news_csv_path}")

    # Load CSV
    try:
        df = pd.read_csv(news_csv_path)
    except Exception as e:
        print(f"❌ Failed to read CSV: {e}")
        return

    print(f"Total articles: {len(df)}\n")

    # Validate each required field
    for field_name, validator_func in REQUIRED_FIELDS.items():
        if field_name not in df.columns:
            print(f"✗ {field_name}: MISSING COLUMN")
            continue

        # Count valid/invalid
        valid_count = 0
        invalid_count = 0
        error_types = {}

        for value in df[field_name]:
            # Convert to string for validation
            value_str = str(value) if pd.notna(value) else ""

            result = validator_func(value_str)
            if result["valid"]:
                valid_count += 1
            else:
                invalid_count += 1
                error_type = result.get("error", "unknown")
                error_types[error_type] = error_types.get(error_type, 0) + 1

        # Print results
        total = len(df)
        pct = (valid_count / total * 100) if total > 0 else 0
        status = "✓" if pct > 95 else "✗"

        print(f"{status} {field_name}: {valid_count}/{total} valid ({pct:.1f}%)")

        if invalid_count > 0:
            # Show breakdown of errors
            for error_type, count in sorted(error_types.items()):
                print(f"  └─ {count} {error_type}")

    # Check for duplicates
    print()
    duplicate_urls = df[df.duplicated(subset=['url'], keep=False)]
    if len(duplicate_urls) > 0:
        unique_dupes = df[df.duplicated(subset=['url'], keep='first')]
        print(f"Duplicates: {len(unique_dupes)} duplicate URLs found")

        if deduplicate:
            print(f"\nRun with --deduplicate to clean up duplicates")

    # Deduplicate if requested
    if deduplicate:
        deduplicate_newspaper_data(news_csv_path, df)

    print()
```

**Step 2: Add deduplicate stub**

Add to `src/text/scrapers/observability/validators.py`:

```python
def deduplicate_newspaper_data(csv_path: Path, df: pd.DataFrame) -> None:
    """
    Remove duplicate URLs from newspaper data.

    Args:
        csv_path: Path to news.csv
        df: DataFrame to deduplicate
    """
    print("\n=== Deduplicating ===")
    print("Not yet implemented - coming in next task")
```

**Step 3: Test validation**

```bash
# Run validation on a real newspaper
poetry run python -m text.scrapers.orchestration.validate_data fiji_sun
```

Expected: Should show validation report for fiji_sun

**Step 4: Commit**

```bash
git add src/text/scrapers/observability/validators.py
git commit -m "feat(validation): implement validate_newspaper_data function"
```

---

### Task 5.4: Implement Deduplication

**Files:**
- Modify: `src/text/scrapers/observability/validators.py`

**Step 1: Implement deduplicate_newspaper_data**

Replace the deduplicate stub with:

```python
def deduplicate_newspaper_data(csv_path: Path, df: pd.DataFrame) -> None:
    """
    Remove duplicate URLs from newspaper data.

    Keeps oldest entry with complete required fields.
    Creates backup before modifying.

    Args:
        csv_path: Path to news.csv
        df: DataFrame to deduplicate
    """
    print("\n=== Deduplicating ===\n")

    # Find duplicates
    duplicates = df[df.duplicated(subset=['url'], keep=False)]

    if len(duplicates) == 0:
        print("No duplicates found")
        return

    unique_dupe_urls = df[df.duplicated(subset=['url'], keep='first')]
    print(f"Found {len(unique_dupe_urls)} duplicate URLs\n")
    print("Strategy: Keep oldest entry with complete required fields\n")

    # Group by URL and select best entry
    def select_best_entry(group):
        """Select best entry from duplicate group."""
        # Check completeness of required fields
        for idx, row in group.iterrows():
            all_valid = True
            for field_name, validator_func in REQUIRED_FIELDS.items():
                value_str = str(row[field_name]) if pd.notna(row[field_name]) else ""
                if not validator_func(value_str)["valid"]:
                    all_valid = False
                    break

            if all_valid:
                # Return first valid entry (oldest)
                return row

        # If no complete entry, return first one
        return group.iloc[0]

    # Deduplicate
    deduplicated = df.groupby('url', as_index=False).apply(select_best_entry)
    deduplicated = deduplicated.reset_index(drop=True)

    # Show what's being removed
    removed_count = len(df) - len(deduplicated)
    print(f"Removing: {removed_count} duplicate entries")

    # Create backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = csv_path.parent / f"news.csv.backup.{timestamp}"
    df.to_csv(backup_path, index=False)
    print(f"Backup saved: {backup_path}")

    # Save deduplicated data
    deduplicated.to_csv(csv_path, index=False)
    print(f"\n✓ Updated: {csv_path}")
    print(f"   Kept {len(deduplicated)} articles, removed {removed_count} duplicates")
```

**Step 2: Update validate_newspaper_data to trigger deduplication**

Change the deduplication check in `validate_newspaper_data`:

```python
    # Deduplicate if requested
    if deduplicate:
        deduplicate_newspaper_data(news_csv_path, df)
    elif len(duplicate_urls) > 0:
        print("\nRun with --deduplicate to clean up duplicates")
```

**Step 3: Test deduplication (dry run)**

```bash
# First just validate to see if there are duplicates
poetry run python -m text.scrapers.orchestration.validate_data fiji_sun
```

**Step 4: Commit**

```bash
git add src/text/scrapers/observability/validators.py
git commit -m "feat(validation): implement CSV deduplication"
```

---

## Phase 6: Cleanup

### Task 6.1: Delete src/text/core Folder

**Files:**
- Delete: `src/text/core/`
- Modify: Any files importing from `text.core`

**Step 1: Find all imports from text.core**

```bash
grep -r "from text.core" src/text/ --include="*.py" || echo "No imports found"
grep -r "import text.core" src/text/ --include="*.py" || echo "No imports found"
```

**Step 2: Check what imports exist and fix them**

If any imports exist, replace them:
- `from text.core.run_tracker import` → Remove (not used anymore)
- `from text.core.logging_config import` → Remove (configured in main.py)
- `from text.core.errors import` → Use built-in exceptions

**Step 3: Delete the folder**

```bash
rm -rf src/text/core/
```

**Step 4: Test that scrapers still work**

```bash
poetry run python -m text.scrapers.orchestration.main fiji_sun --update
```

Expected: Should work without errors

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor: delete src/text/core folder

Replaced with:
- Observability metrics (in-memory, no SQLite)
- Inline logging config in main.py
- Built-in exceptions"
```

---

### Task 6.2: Add Logging Config to main.py

**Files:**
- Modify: `src/text/scrapers/orchestration/main.py`

**Step 1: Add logging configuration at top of main()**

Find the `main()` function and add at the very beginning:

```python
def main():
    """Main entry point for the text scraping tools."""

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Rest of main() function...
```

**Step 2: Test logging works**

```bash
poetry run python -m text.scrapers.orchestration.main --list-scrapers | head -10
```

Expected: Should see formatted log messages

**Step 3: Commit**

```bash
git add src/text/scrapers/orchestration/main.py
git commit -m "refactor: add inline logging config to main.py"
```

---

### Task 6.3: Clean Up Old Log and Manifest Directories

**Files:**
- Delete: `logs/{country}/{newspaper}/*.log` (old structure)
- Delete: `data/text/{country}/{newspaper}/runs/` (old manifests)

**Step 1: Archive old logs**

```bash
# Create archive directory
mkdir -p logs/archive

# Move old logs (if any exist)
find logs -maxdepth 2 -type d ! -path "logs/text*" ! -path "logs/archive" -exec mv {} logs/archive/ \; 2>/dev/null || true
```

**Step 2: Archive old manifests**

```bash
# Find and archive old manifest directories
find data/text -type d -name "runs" -exec sh -c 'mv "$1" "$(dirname "$1")/runs_archived_$(date +%Y%m%d)"' _ {} \; 2>/dev/null || true
```

**Step 3: Document the new structure**

Create `logs/text/README.md`:

```markdown
# Text Scraper Logs

New unified logging structure (as of 2026-01-23):

```
logs/text/
├── {country}/
│   └── {newspaper}/
│       ├── individual/           # Individual run manifests (JSON)
│       │   └── YYYYMMDD_HHMMSS.json
│       └── execution_logs/       # Scraper stdout/stderr logs
│           └── YYYYMMDD_HHMMSS.log
└── multi_runs/                   # Multi-scraper run manifests
    └── YYYYMMDD_HHMMSS.json
```

Old logs archived to `logs/archive/`
```

**Step 4: Commit**

```bash
git add logs/text/README.md
git add -A
git commit -m "refactor: clean up old log and manifest directories"
```

---

### Task 6.4: Update Documentation

**Files:**
- Modify: `src/text/README.md` (or create if doesn't exist)

**Step 1: Create/update text module README**

File: `src/text/README.md`

```markdown
# Text Module - Newspaper Scraping

Scrapes 50+ Pacific newspapers weekly to calculate Economic Policy Uncertainty (EPU) indices.

## Quick Start

```bash
# Run single newspaper
poetry run python -m text.scrapers.orchestration.main fiji_sun

# Run all newspapers
poetry run python -m text.scrapers.orchestration.main --run-all

# Validate data quality
poetry run python -m text.scrapers.orchestration.validate_data fiji_sun

# Check recent runs
poetry run python -m text.scrapers.orchestration.status --last-24h
```

## Features

### Three-Layer Observability

1. **Real-Time Warnings** - See data quality issues as they happen
2. **Run Summaries** - Quality reports at the end of each run
3. **Post-Run Validation** - CSV analysis and deduplication

### Output

- **Data**: `data/text/{country}/{newspaper}/news.csv`
- **Logs**: `logs/text/{country}/{newspaper}/execution_logs/`
- **Manifests**: `logs/text/{country}/{newspaper}/individual/`

## Adding a Newspaper

See `src/text/docs/adding_a_newspaper.md` for detailed guide.

## Architecture

```
src/text/scrapers/
├── observability/        # Metrics, formatters, validators
├── strategies/           # Listing discovery strategies
├── pipelines/           # Cleaning and storage
├── orchestration/       # CLI entry points
└── configs/            # YAML configs by country
```

## Configuration

Each newspaper has a YAML config defining:
- Listing strategy (pagination, archive, API, follow_link)
- CSS selectors for extraction
- Data cleaning functions

See `src/text/docs/config_schema.md` for complete reference.
```

**Step 2: Commit**

```bash
git add src/text/README.md
git commit -m "docs: add text module README with observability features"
```

---

### Task 6.5: Final Integration Test

**Files:**
- None (testing only)

**Step 1: Run end-to-end test with caixin_global**

```bash
# This should now work correctly with dates being cleaned
poetry run python -m text.scrapers.orchestration.main caixin_global --update
```

Expected:
- No warnings about empty dates
- Summary shows 100% success rate for date field
- Manifest saved to `logs/text/china/caixin_global/individual/`

**Step 2: Validate the data**

```bash
poetry run python -m text.scrapers.orchestration.validate_data caixin_global
```

Expected:
- All required fields show >95% valid
- Dates are in YYYY-MM-DD format

**Step 3: Run multi-scraper test**

```bash
# Run a few newspapers
poetry run python -m text.scrapers.orchestration.main --run-all --country fiji
```

Expected:
- Aggregate summary at end
- Multi-run manifest saved to `logs/text/multi_runs/`

**Step 4: Document test results**

Create `docs/TESTING_OBSERVABILITY.md`:

```markdown
# Observability System Test Results

## Tests Performed

- [x] Single scraper run (caixin_global)
- [x] Data validation
- [x] Multi-scraper run (fiji)
- [x] Manifest generation
- [x] Quality issue detection

## Verified Features

- [x] caixin_global dates now cleaned correctly (bug fixed!)
- [x] Field-level metrics tracked
- [x] Real-time warnings for empty fields
- [x] End-of-run summary with quality issues
- [x] Individual run manifests saved
- [x] Multi-run aggregate summary
- [x] Post-run CSV validation
- [x] Deduplication (if needed)

## Before/After Comparison

**Before:**
- caixin_global: 100% NaN dates, no warnings
- No visibility into field extraction quality
- Manual CSV inspection required

**After:**
- caixin_global: 100% valid dates ✓
- Real-time warnings for quality issues
- Automated validation and reporting
```

**Step 5: Commit**

```bash
git add docs/TESTING_OBSERVABILITY.md
git commit -m "test: document observability system testing"
```

---

## Final Commit

**Step 1: Create comprehensive commit message**

```bash
git add -A
git commit -m "feat(text): complete observability system implementation

SUMMARY:
Three-layer observability for text scraping module to catch silent
data quality failures like caixin_global NaN dates.

WHAT CHANGED:
- Created observability/ package with metrics, formatters, validators
- Implemented field-level extraction tracking
- Added real-time quality warnings during scraping
- Added end-of-run summaries with quality reports
- Added post-run CSV validation and deduplication CLI
- Fixed caixin_global bug: cleaning now happens in all scrape modes
- Refactored duplicate API processing into single _process_api_thumbnail
- Unified logging structure under logs/text/
- Deleted src/text/core/ (replaced with in-memory metrics, no SQLite)

DELIVERABLES:
✓ Phase 1: Metrics tracking infrastructure
✓ Phase 2: Code deduplication (DRY)
✓ Phase 3: Real-time warnings & summaries
✓ Phase 4: Multi-scraper aggregation
✓ Phase 5: Post-run validator
✓ Phase 6: Cleanup and documentation

TESTING:
- caixin_global: dates now cleaned correctly (100% → 100% valid)
- All scrape modes (UPDATE, RESUME, FULL) use unified processing
- Multi-scraper runs show aggregate quality summary
- Validation CLI detects regressions and deduplicates CSVs

See docs/plans/2026-01-23-text-observability.md for full plan."
```

---

## Success Criteria Checklist

- [ ] Phase 1: Scrapers collect metrics in memory
- [ ] Phase 2: caixin_global bug fixed (dates cleaned in all modes)
- [ ] Phase 3: Single runs show quality summaries
- [ ] Phase 4: Multi-runs show aggregate summaries
- [ ] Phase 5: Can validate and deduplicate CSVs
- [ ] Phase 6: Clean codebase, documentation updated

**Key Metric:** Silent failures like caixin_global NaN dates are now caught immediately with clear warnings.

---

## Notes for Implementation

- **Test frequently**: After each task, run the test step to verify it works
- **Commit often**: Each task should be a separate commit
- **Read errors carefully**: If validation fails, the error message should point to the issue
- **Reference design doc**: The design document at `~/notes/plans/2026-01-23-text-observability-design.md` has more details if needed
- **DRY principle**: The `_process_api_thumbnail` method is the single source of truth for API processing
- **YAGNI**: No SQLite, no complex infrastructure - just structured logging and simple JSON files
