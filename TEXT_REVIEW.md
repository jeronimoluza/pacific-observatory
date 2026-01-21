# Text Module Code Review

> **Review Date:** January 2026
> **Scope:** `src/text/` (analysis, scrapers, plotting modules)
> **Context:** Occasional manual runs, priorities are developer experience and monitoring/observability

---

## Executive Summary

The text module is a sophisticated newspaper scraping and EPU (Economic Policy Uncertainty) analysis system covering 50+ news sources across 20+ Pacific countries. While the architecture is well-designed with good patterns (factory, strategy, pipeline), there are significant opportunities for improvement in **reliability**, **observability**, **testability**, and **code maintainability**.

### Key Statistics
| Metric | Value |
|--------|-------|
| Total Lines of Code | ~10,000+ |
| Test Lines of Code | 65 (integration only) |
| Test Coverage | ~0.6% (no unit tests) |
| Large Files (>500 LOC) | 6 files |
| Newspaper Configs | 30+ YAML files |
| Languages Supported | 28+ |

---

## Table of Contents

1. [Module Structure Overview](#1-module-structure-overview)
2. [Reliability Issues](#2-reliability-issues)
3. [Observability & Monitoring Gaps](#3-observability--monitoring-gaps)
4. [Code Maintainability](#4-code-maintainability)
5. [Unused & Dead Code](#5-unused--dead-code)
6. [Performance Concerns](#6-performance-concerns)
7. [Testing Gaps](#7-testing-gaps)
8. [Security Considerations](#8-security-considerations)
9. [Architecture Blindspots](#9-architecture-blindspots)
10. [Recommendations Summary](#10-recommendations-summary)

---

## 1. Module Structure Overview

```
src/text/
├── analysis/           # EPU calculation, sentiment, modeling
│   ├── main.py         # Entry point for analysis pipeline
│   ├── epu.py          # Core EPU index calculation
│   ├── modeling.py     # LASSO regression for inflation prediction
│   ├── sentiment.py    # VADER sentiment analysis
│   ├── data.py         # Data loading helpers
│   ├── utils.py        # Text preprocessing utilities
│   ├── lda.py          # LDA topic modeling
│   └── gui.py          # Network visualization
├── scrapers/           # Web scraping framework
│   ├── newspaper_scraper.py   # Main orchestrator (1890 lines)
│   ├── client_http.py         # Async HTTP client
│   ├── client_browser.py      # Selenium browser client
│   ├── listing_strategies.py  # URL discovery strategies (1151 lines)
│   ├── parser.py              # HTML data extraction
│   ├── factory.py             # Scraper factory
│   ├── models.py              # Pydantic data models
│   ├── configs/               # 30+ YAML newspaper configs
│   ├── pipelines/
│   │   ├── storage.py         # CSV storage (890 lines)
│   │   └── cleaning.py        # Site-specific cleaning (897 lines)
│   └── orchestration/         # CLI and batch processing
└── plotting/           # Interactive Bokeh visualizations
```

### Data Flow

```
[YAML Configs] → [Factory] → [NewspaperScraper]
                                    ↓
               [ListingStrategy] → [Discover URLs]
                                    ↓
               [AsyncHttpClient] → [Fetch Pages]
                                    ↓
               [Parser] → [Extract Data]
                                    ↓
               [Cleaning Pipeline] → [CSVStorage]
                                    ↓
               [EPU Analysis] → [Outputs]
```

---

## 2. Reliability Issues

### 2.1 Error Handling Gaps

| File | Location | Issue | Severity |
|------|----------|-------|----------|
| `newspaper_scraper.py` | Lines 196-200 | Generic `except Exception` with no recovery strategy | High |
| `listing_strategies.py` | Lines 900-905 | JSON parsing errors break loop without context logging | High |
| `client_http.py` | Line 101-102 | `refresh_cookies()` silently catches all exceptions | Medium |
| `epu.py` | Line 195-204 | `get_count()` catches KeyError but only prints, doesn't raise | Medium |
| `storage.py` | Row parsing failures logged but could corrupt state | Medium |

**Example - Silent failure in `client_http.py:94-102`:**
```python
def refresh_cookies(self):
    if self.domain:
        try:
            new_cookies = self._cookies(self.domain)
            self.cookies.update(new_cookies)
        except Exception as e:
            logger.warning(f"Failed to refresh cookies for {self.domain}: {e}")
            # Continues execution silently - could cause auth failures downstream
```

### 2.2 Retry Logic Issues

- **Excessive retries**: `scrape_thumbnails_with_retry()` allows 25 retries × 2 seconds = 50 seconds per URL
- **No circuit breaker**: Consistently failing newspapers continue to be retried indefinitely
- **Duplicated retry logic**: Both HTTP and browser client paths implement their own retry mechanisms
- **Missing backoff**: Linear retry delays instead of exponential backoff

### 2.3 Missing Error Recovery

- **No checkpoint/resume**: If a multi-newspaper run fails midway, no way to resume from last successful point
- **No transaction safety**: Partial CSV writes could corrupt data if interrupted
- **No graceful degradation**: Single strategy failure stops entire scraping flow

### 2.4 Edge Cases Not Handled

- Empty `news.csv` files (EPU processing would fail at line 246)
- Websites returning HTML error pages with 200 status codes
- Rate-limited responses (429) not distinguished from other HTTP errors
- Date strings in unexpected formats silently fall back instead of flagging

---

## 3. Observability & Monitoring Gaps

### 3.1 Logging Deficiencies

| Module | Logger Calls | Lines of Code | Ratio |
|--------|--------------|---------------|-------|
| `analysis/` | ~5 | 2500+ | 0.2% |
| `scrapers/` | ~100 | 7000+ | 1.4% |

**Issues:**
- No structured logging (JSON format) for log aggregation
- No correlation IDs for tracing requests across components
- Inconsistent log levels (many errors logged as warnings)
- No request/response logging for debugging failed scrapes

### 3.2 Missing Metrics

The system has **zero metrics collection**. Recommended metrics:

**Scraping Health:**
- `scraper_runs_total{newspaper, mode, status}` - Counter
- `scraper_duration_seconds{newspaper}` - Histogram
- `articles_scraped_total{newspaper}` - Counter
- `http_requests_total{newspaper, status_code}` - Counter

**Data Quality:**
- `articles_missing_date{newspaper}` - Gauge
- `articles_missing_body{newspaper}` - Gauge
- `cleaning_errors_total{function_name}` - Counter

**System Health:**
- `concurrent_requests` - Gauge
- `retry_attempts_total{newspaper}` - Counter

### 3.3 Missing Alerting

No alerting infrastructure for:
- Scraper failures (0 articles scraped)
- Data quality degradation
- Unusual patterns (sudden drop in article counts)
- System health issues (memory, disk space)

### 3.4 No Dashboard Visibility

No way to answer basic operational questions:
- "Which scrapers ran today and succeeded?"
- "What's the success rate over the last week?"
- "Which newspapers are consistently failing?"

---

## 4. Code Maintainability

### 4.1 Large Files Needing Decomposition

| File | Lines | Recommended Split |
|------|-------|-------------------|
| `newspaper_scraper.py` | 1890 | `scraper_core.py`, `scraper_modes.py`, `scraper_utils.py` |
| `listing_strategies.py` | 1151 | One file per strategy type |
| `cleaning.py` | 897 | Group by country/newspaper or create registry pattern |
| `storage.py` | 890 | `csv_operations.py`, `metadata.py`, `serialization.py` |

### 4.2 Tight Coupling

**Hard-coded dependencies:**
```python
# newspaper_scraper.py:85
self._storage = CSVStorage()  # Should be injected

# epu.py:58-61
_topics_data = load_topics_words(language="en")  # Global state at module level
```

**Circular import risks:**
- `models.py` imports from `pipelines/cleaning.py` for date handling
- Consider moving date parsing to a separate utilities module

### 4.3 Complex API Surface

`NewspaperScraper` has **7 different run modes**, making the interface confusing:
- `run_full_scrape()`
- `run_update_scrape()`
- `run_urls_only()`
- `run_discover()`
- `run_discover_full()`
- `run_resume()`
- `run_default()`

These should be consolidated or moved to a Command pattern.

### 4.4 Missing Type Hints

Several modules lack comprehensive type hints:
- `gui.py` - No type annotations
- `sentiment.py` - Partial coverage
- Many cleaning functions return untyped `Any`

### 4.5 Documentation Gaps

- No docstrings in `client_browser.py` for main methods
- `listing_strategies.py` strategies lack usage examples
- No API documentation for cleaning function registry
- Missing schema documentation for YAML configs

---

## 5. Unused & Dead Code

### 5.1 Potentially Dead Code Paths

| Location | Issue |
|----------|-------|
| `client_browser.py:609` | `pass` in else block (incomplete implementation) |
| `newspaper_scraper.py` | `discover_listing_urls()` and `scrape_thumbnails()` appear superseded by `discover_and_scrape_thumbnails()` |
| `epu.py:353-354` | Commented logic (should be removed or documented) |

### 5.2 Potentially Unused Cleaning Functions

- `clean_matangi_url()` makes synchronous HTTP calls - may be unused or problematic
- Several newspaper-specific cleaning functions may no longer be referenced by configs

### 5.3 Recommendations

Run static analysis tools:
- `vulture` for dead code detection
- `pylint` with unused-import checks
- Review all `# TODO` and `# FIXME` comments

---

## 6. Performance Concerns

### 6.1 I/O Bottlenecks

**Synchronous file I/O in async context (`storage.py`):**
```python
# Opens/closes file for EACH article - very inefficient
def append_article(self, article: ArticleRecord, ...):
    with open(filepath, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=self.ARTICLE_COLUMNS)
        writer.writerow(article_dict)
```

Should buffer writes or use async file I/O.

### 6.2 Memory Concerns

- `thumbnail_elements` accumulated in memory during discovery
- `serialize_for_json()` recursively processes entire result dictionaries
- Large DataFrames loaded entirely into memory in EPU processing

### 6.3 Rate Limiting Issues

**Global rate limiter (`client_http.py:92`):**
```python
self._last_request_time = 0  # Single timestamp shared by all concurrent tasks
```

Should be per-domain to allow parallel requests to different newspapers.

### 6.4 Inefficient Pandas Operations

`epu.py:176-178` - String operations applied row-by-row instead of vectorized:
```python
df["body"] = df["body"].replace("\n", "").str.lower()
```

### 6.5 Redundant HTTP Requests

`FollowLinkStrategy.discover_and_scrape()` re-fetches pages for link extraction (lines 1089-1098)

---

## 7. Testing Gaps

### 7.1 Current State

**Single test file:** `tests/test_scrapers.py` (65 lines)
- Integration tests only (require network access)
- No unit tests
- No mocking infrastructure
- No test fixtures for sample HTML/JSON responses

```python
# Current test - requires live network access
@pytest.mark.asyncio
async def test_scraper_config(config_path: Path) -> None:
    scraper = NewspaperScraper(config)
    results = await scraper.run_full_scrape()
    assert results['success']
```

### 7.2 What's Missing

| Category | Status | Impact |
|----------|--------|--------|
| Unit tests for `epu.py` | Missing | Can't validate EPU calculation logic |
| Unit tests for `parser.py` | Missing | Can't test selector extraction |
| Unit tests for `cleaning.py` | Missing | Can't verify date parsing |
| Mocked HTTP tests | Missing | Tests fail without network |
| Regression tests | Missing | No safety net for refactoring |
| Property-based tests | Missing | Edge cases not explored |

### 7.3 Test Infrastructure Needed

- HTTP mocking (pytest-httpx or respx)
- Sample HTML fixtures per newspaper
- Sample JSON fixtures for API strategies
- Factory functions for test data
- Coverage reporting

---

## 8. Security Considerations

### 8.1 Input Validation

- Config YAML files are loaded without schema validation
- URL parameters in configs could potentially inject malicious values
- No sanitization of extracted article content before storage

### 8.2 Credentials Management

- Cookie management in `client_http.py` should use secure storage
- No mention of secrets management for authenticated scrapers

### 8.3 Recommendations

- Add JSON Schema validation for YAML configs
- Sanitize extracted content (especially for display)
- Review cookie/auth handling for security best practices

---

## 9. Architecture Blindspots

### 9.1 No State Management

- No database for tracking scraper runs, success/failure history
- CSV files as primary storage limits querying capability
- No way to track "last successful run" per newspaper

### 9.2 No Scheduling Infrastructure

- Manual runs only - no scheduler integration
- No automatic retry for failed scrapers
- No backfill capability for missed dates

### 9.3 No Notification System

- No way to notify on failures
- No daily summary reports
- No integration with alerting systems (PagerDuty, Slack, etc.)

### 9.4 Limited Extensibility

- Adding a new output format requires code changes
- No plugin architecture for custom strategies
- Cleaning functions must be manually registered

### 9.5 Data Lineage

- No tracking of which config version produced which data
- No audit trail for data modifications
- No ability to reproduce historical results

---

## 10. Recommendations Summary

### Immediate Priority (Developer Experience + Observability)

| # | Recommendation | Effort | Impact |
|---|----------------|--------|--------|
| 1 | Add structured logging (JSON format) | Medium | High |
| 2 | Implement metrics collection (Prometheus/StatsD) | Medium | High |
| 3 | Add correlation IDs for request tracing | Low | High |
| 4 | Create unit tests with HTTP mocking | High | Critical |
| 5 | Add type hints throughout codebase | Medium | High |
| 6 | Document YAML config schema | Low | Medium |

### Medium Priority (Reliability)

| # | Recommendation | Effort | Impact |
|---|----------------|--------|--------|
| 7 | Implement circuit breaker pattern | Medium | High |
| 8 | Add checkpoint/resume capability | High | High |
| 9 | Standardize error handling patterns | Medium | High |
| 10 | Handle rate limiting (429) explicitly | Low | Medium |
| 11 | Add validation for 200-status error pages | Low | Medium |

### Longer Term (Architecture)

| # | Recommendation | Effort | Impact |
|---|----------------|--------|--------|
| 12 | Split large files into focused modules | High | Medium |
| 13 | Implement dependency injection | Medium | Medium |
| 14 | Add database for state management | High | High |
| 15 | Create dashboard for scraping status | Medium | Medium |
| 16 | Add scheduling infrastructure | Medium | High |

---

## Appendix: Files Requiring Attention

### Critical Path (Scraper)
- `/src/text/scrapers/newspaper_scraper.py` - Core orchestration
- `/src/text/scrapers/client_http.py` - Network layer
- `/src/text/scrapers/pipelines/storage.py` - Data persistence
- `/src/text/scrapers/listing_strategies.py` - URL discovery

### Critical Path (Analysis)
- `/src/text/analysis/epu.py` - EPU calculation
- `/src/text/analysis/modeling.py` - Inflation prediction

### Testing
- `/tests/test_scrapers.py` - Needs expansion with unit tests

---

*This review is intended to guide improvements, not criticize existing work. The system demonstrates solid architectural thinking with room for hardening around reliability, observability, and maintainability.*
