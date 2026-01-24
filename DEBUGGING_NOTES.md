# Debugging Notes: caixin_global NaN Dates Bug

**Date:** 2026-01-23
**Bug:** caixin_global newspaper producing NaN/empty dates in urls.csv and news.csv
**Root Cause:** Missing `apply_cleaning()` call in UPDATE mode for API strategy
**Location:** `src/text/scrapers/scraper.py:902` (run_update_scrape method)

---

## Summary

The caixin_global scraper runs "successfully" with no errors logged, but produces empty date fields in the CSV output. The API returns Unix timestamps as integers, which should be converted to "YYYY-MM-DD" format by the `handle_unix_timestamp_ms` cleaning function, but the cleaning step was being skipped in UPDATE mode.

---

## What Worked

### 1. Testing Components in Isolation
```python
# Tested the cleaning function directly
handle_unix_timestamp_ms(1769168119000)  # → "2026-01-23" ✓
```
This confirmed the cleaning function itself was correct, narrowing the problem to "where is it being called?"

### 2. Fetching Real API Data
```bash
curl "https://gateway.caixinglobal.com/api/data/getNewsListByCate?page=1&size=5&pids=101652028"
```
Seeing the actual API response structure (`"timestamp": 1769168119000`) confirmed the data type coming from the source.

### 3. Checking Actual Output
```bash
tail -20 data/text/china/caixin_global/urls.csv
```
Confirmed the symptom: recent entries had empty date fields while older entries had proper dates.

### 4. Simulating the Pipeline Step-by-Step
Manually walked through:
- API extraction (`ApiStrategy._get_nested_value()`)
- Cleaning application (`apply_cleaning()`)
- Model creation (`ThumbnailRecord(**data)`)

This revealed that ThumbnailRecord silently accepts `int` for the `date` field (typed as `Optional[str]`) and Pydantic coerces it to `None`.

### 5. Comparing Code Paths
Comparing FULL mode (line 195) vs UPDATE mode (line 902) revealed the discrepancy:
- FULL mode: calls `apply_cleaning()` before creating ThumbnailRecord ✓
- UPDATE mode: creates ThumbnailRecord directly without cleaning ✗

---

## What Was Misleading

### 1. "Success" Indicators Were False Positives
- Logs: `"Processed API batch: 20 thumbnails"` with no errors
- Metadata: `"success": true, "errors": []`
- Exit code: 0

**Lesson:** Success ≠ data quality. Need explicit field-level validation.

### 2. Pydantic's Silent Type Coercion
```python
ThumbnailRecord(date=1769168119000)  # int → None, no error raised
```
Pydantic's `Optional[str]` field silently accepts incompatible types and converts to `None`. This hid the problem.

**Lesson:** Need runtime validation that fields have expected values, not just types.

### 3. Cleaning Function Was Correct
Spent time verifying `handle_unix_timestamp_ms()` worked correctly, but the bug was that it wasn't being called at all.

**Lesson:** When a function works in isolation but fails in practice, check the call sites.

### 4. Recent Runs Showed "0 new articles"
The most recent run metadata showed:
```json
"new_urls_discovered": 0,
"articles_scraped": 0
```
This was because UPDATE mode stops when it hits existing URLs, so the bug only appears when there are actually new URLs to scrape.

**Lesson:** Testing needs to exercise the "new data" code path, not just the "already scraped" path.

---

## What Would Make Debugging Faster

### 1. Structured Logging with Field-Level Results
Instead of:
```
INFO - Processed API batch: 20 thumbnails
```

Log:
```
INFO - Processed API batch: 20 thumbnails
  Fields extracted: url=20/20, title=20/20, date=20/20
  After cleaning: date=0/20 valid (20 None/empty)  # ← Would catch the bug immediately!
```

### 2. Real-Time Data Quality Warnings
During the run:
```
WARNING - caixin_global: 20/20 articles have empty 'date' field after extraction
```

This would have made the bug obvious immediately.

### 3. Post-Extraction Validation
After creating each `ThumbnailRecord`, validate:
- Required fields are non-empty
- Date fields match expected format (`YYYY-MM-DD`)
- URLs are valid

Log validation failures with context about which extraction step failed.

### 4. Test Coverage for All Scrape Modes
The bug existed in UPDATE mode but not FULL mode. Need integration tests that:
- Run each mode (UPDATE, RESUME, FULL_DISCOVERY, FULL_FROM_SCRATCH)
- Validate actual CSV output
- Check field-level data quality

### 5. CSV Diff on Each Run
Compare new URLs/articles to previous run:
```
New URLs: 20
  Date field populated: 0/20 (REGRESSION from last run: 100%)
```

This would catch quality degradation immediately.

### 6. Better Error Context in Logs
When Pydantic validation fails (e.g., creating ArticleRecord), log the **actual data**:
```
ERROR - Failed to create ArticleRecord from API data: validation error
  Data: {"url": "...", "title": "...", "date": 1769168119000, ...}
  Expected: date should be str, got int
```

---

## Issues That Make Debugging Harder

### 1. Code Duplication Across Scrape Modes
The API strategy handling appears in multiple places:
- `_original_discover_and_scrape_thumbnails()` (line 170-228, FULL mode)
- `run_update_scrape()` (line 854-913, UPDATE mode)
- `run_resume_scrape()` (line 1350-1410, RESUME mode)

Each has slightly different logic. The cleaning bug existed in UPDATE and RESUME but not FULL.

**Impact:** Bug fixes need to be applied in multiple places. Easy to miss one.

**Solution:** Extract API thumbnail processing into a single method used by all modes.

### 2. Large Methods
`run_update_scrape()`: ~300 lines
`_original_discover_and_scrape_thumbnails()`: ~400 lines

**Impact:** Hard to see the entire flow. Easy to miss a step (like cleaning).

**Solution:** Break into smaller, focused methods. Each should have a single responsibility.

### 3. Silent Pydantic Coercion
`Optional[str]` fields accept `int` and convert to `None` without error.

**Impact:** Type errors become data quality errors, which are harder to trace.

**Solution:**
- Use strict Pydantic validators
- Add `@field_validator` that raises on unexpected types
- Log warnings when fields are None/empty

### 4. No Field-Level Logging
Logs show "20 thumbnails processed" but not "date field: 0/20 populated".

**Impact:** Can't see data quality issues in real-time.

**Solution:** Structured logging with field-level extraction metrics.

### 5. Missing Data Validation Layer
Data flows from extraction → model creation → CSV write with no validation in between.

**Impact:** Bad data makes it all the way to CSV before anyone notices.

**Solution:** Add validation layer after extraction, before CSV write.

### 6. Inconsistent Cleaning Application
Some code paths apply cleaning, others don't. No clear pattern.

**Impact:** Easy to forget the cleaning step (as happened here).

**Solution:**
- Always apply cleaning in a single place (e.g., inside the model's `__init__`)
- OR: Make it impossible to create a model without cleaning (builder pattern)

### 7. Test Gap: No Integration Tests for Scrape Modes
Unit tests exist for cleaning functions, but no integration tests that:
- Run the actual scraper in each mode
- Validate CSV output quality

**Impact:** Regressions in specific modes go undetected.

**Solution:** Add integration tests that run real scrapers and validate output.

### 8. Metadata Doesn't Capture Data Quality
Metadata JSON tracks:
```json
"articles_scraped": 20,
"articles_failed": 0
```

But not:
```json
"articles_scraped": 20,
"field_quality": {
  "date_missing": 20,
  "body_missing": 0,
  "tags_missing": 5
}
```

**Impact:** Can't detect silent quality degradation over time.

**Solution:** Track field-level quality metrics in metadata.

---

## Debugging Process That Found the Bug

1. ✓ Confirmed symptom: Recent URLs in `urls.csv` have empty date field
2. ✓ Checked config: `cleaning.date: "handle_unix_timestamp_ms"` is correct
3. ✓ Tested cleaning function: Works correctly in isolation
4. ✓ Fetched real API data: Confirmed timestamps are integers
5. ✓ Simulated extraction pipeline: Found Pydantic silently coerces int → None
6. ✓ Checked code paths: Found UPDATE mode skips `apply_cleaning()`
7. ✓ Compared to FULL mode: Confirmed FULL mode includes cleaning step

**Key insight:** The problem wasn't in the *data* or the *function*, but in the *call site*.

---

## Recommendations for Future

### Immediate Fixes
1. Fix the bug: Add `apply_cleaning()` call in UPDATE and RESUME modes
2. Add field-level logging after extraction
3. Add data quality validation before CSV write

### Medium-Term Improvements
1. Deduplicate API strategy handling across modes
2. Break large methods into smaller functions
3. Add Pydantic strict validators for date fields
4. Add integration tests for all scrape modes

### Long-Term Architecture
1. Structured logging with field-level metrics
2. Real-time data quality warnings
3. Post-run CSV validation tool
4. Comprehensive observability layer (the design we're about to create!)

---

## Questions This Raises for the Design

1. **Where should cleaning be applied?**
   - Currently: Ad-hoc in various code paths (inconsistent)
   - Better: Single point of responsibility (model constructor? extraction layer?)

2. **What is "success"?**
   - Currently: No exceptions thrown
   - Better: Data meets quality standards (required fields populated, dates valid, etc.)

3. **How do we make silent failures visible?**
   - Field-level extraction metrics
   - Real-time warnings during scraping
   - Post-run validation reports

4. **How do we prevent this class of bug?**
   - Eliminate code duplication (DRY)
   - Smaller, focused methods
   - Comprehensive test coverage
   - Strict type validation

These insights should inform the observability system design.
