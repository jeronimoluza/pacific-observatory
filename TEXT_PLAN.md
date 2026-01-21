# Text Module Improvement Plan

> **Created:** January 2026
> **Approach:** Phased Rewrite
> **Compatibility:** Breaking changes allowed
> **Infrastructure:** Python/local only (no external services)

---

## Vision Statement

Transform the text module into a **robust, observable, and maintainable** system that provides:
1. **Clear visibility** into what's running, what succeeded, what failed
2. **Easy debugging** when things go wrong
3. **Simple extension** when adding new newspapers or analysis methods
4. **Confidence** through comprehensive testing

---

## Phased Roadmap Overview

```
Phase 1: Observability Foundation     [Foundation]
    ↓
Phase 2: Testing Infrastructure       [Safety Net]
    ↓
Phase 3: Core Module Refactoring      [Maintainability]
    ↓
Phase 4: Reliability Improvements     [Robustness]
    ↓
Phase 5: Developer Experience         [Polish]
```

---

## Phase 1: Observability Foundation

**Goal:** See what's happening without digging through logs

### 1.1 Structured Logging System

Create a centralized logging configuration with JSON output for machine parsing.

**New file: `src/text/core/logging_config.py`**
```python
# Features:
# - JSON-formatted logs to files (one per day)
# - Console output for interactive use
# - Correlation IDs for request tracing
# - Log levels configurable via environment
```

**Implementation:**
- Use Python's `logging` with `python-json-logger` for JSON formatting
- Add correlation ID context manager for tracing requests
- Log rotation with `logging.handlers.RotatingFileHandler`
- Logs stored in `logs/text/{date}.jsonl`

### 1.2 Run Tracking Database

Use SQLite to track scraper runs and provide historical visibility.

**New file: `src/text/core/run_tracker.py`**

**Schema:**
```sql
-- Track each scraper execution
CREATE TABLE scraper_runs (
    id INTEGER PRIMARY KEY,
    run_id TEXT UNIQUE,           -- UUID for correlation
    newspaper TEXT NOT NULL,
    country TEXT NOT NULL,
    mode TEXT NOT NULL,           -- full, update, discover
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT,                  -- running, success, failed
    articles_found INTEGER,
    articles_scraped INTEGER,
    articles_failed INTEGER,
    error_message TEXT,
    config_hash TEXT              -- Track config version
);

-- Track individual article scrape results
CREATE TABLE article_results (
    id INTEGER PRIMARY KEY,
    run_id TEXT REFERENCES scraper_runs(run_id),
    url TEXT NOT NULL,
    status TEXT,                  -- success, failed, skipped
    error_type TEXT,
    scraped_at TIMESTAMP
);
```

**Capabilities:**
- Query "which newspapers failed in the last 7 days?"
- Track success rates over time
- Identify consistently problematic newspapers

### 1.3 Simple CLI Dashboard

**New file: `src/text/scrapers/orchestration/status.py`**

```bash
# Example usage:
python -m text.scrapers.orchestration.status --last-24h
python -m text.scrapers.orchestration.status --failures
python -m text.scrapers.orchestration.status --newspaper fiji_sun
```

**Output format:**
```
=== Scraper Status (Last 24 Hours) ===

Newspaper         | Country    | Last Run    | Status  | Articles
------------------|------------|-------------|---------|----------
fiji_sun          | fiji       | 2h ago      | SUCCESS | 45
khmer_times       | cambodia   | 3h ago      | SUCCESS | 128
post_courier      | png        | 4h ago      | FAILED  | 0 (timeout)
solomon_star      | solomons   | 6h ago      | SUCCESS | 23

Summary: 28 SUCCESS, 2 FAILED, 3 PENDING
```

### 1.4 Event Emission System

Create a lightweight event system for observability hooks.

**New file: `src/text/core/events.py`**

```python
@dataclass
class ScrapeEvent:
    event_type: str  # started, discovered, scraped, failed, completed
    newspaper: str
    country: str
    run_id: str
    timestamp: datetime
    details: dict

class EventEmitter:
    def __init__(self):
        self._handlers = defaultdict(list)

    def on(self, event_type: str, handler: Callable):
        self._handlers[event_type].append(handler)

    def emit(self, event: ScrapeEvent):
        for handler in self._handlers[event.event_type]:
            handler(event)
```

**Built-in handlers:**
- `LoggingHandler` - Write to structured logs
- `DatabaseHandler` - Update run_tracker database
- `ConsoleHandler` - Real-time progress output

### Deliverables Phase 1
- [ ] `src/text/core/` directory with logging, events, run_tracker
- [ ] SQLite database auto-created on first run
- [ ] CLI status command
- [ ] Migration guide for updating existing scraper calls

---

## Phase 2: Testing Infrastructure

**Goal:** Build a safety net before refactoring

### 2.1 Test Fixtures

Create sample HTML/JSON responses for each newspaper type.

**New directory: `tests/fixtures/`**
```
tests/fixtures/
├── html/
│   ├── pagination_listing.html      # Sample listing page
│   ├── archive_listing.html
│   ├── article_standard.html
│   └── article_paywall.html
├── json/
│   ├── api_response.json
│   └── api_error.json
└── configs/
    └── test_newspaper.yaml
```

### 2.2 HTTP Mocking Infrastructure

**New file: `tests/conftest.py`**

```python
import pytest
from pytest_httpx import HTTPXMock

@pytest.fixture
def mock_newspaper_http(httpx_mock: HTTPXMock):
    """Fixture that mocks common newspaper HTTP patterns."""
    # Load fixtures
    with open("tests/fixtures/html/pagination_listing.html") as f:
        listing_html = f.read()

    httpx_mock.add_response(
        url=re.compile(r".*example\.com/news.*"),
        html=listing_html
    )
    return httpx_mock
```

### 2.3 Unit Tests by Module

**Priority order:**

| Module | Test File | Coverage Target |
|--------|-----------|-----------------|
| `parser.py` | `tests/unit/test_parser.py` | 90% |
| `cleaning.py` | `tests/unit/test_cleaning.py` | 85% |
| `epu.py` | `tests/unit/test_epu.py` | 90% |
| `client_http.py` | `tests/unit/test_client_http.py` | 80% |
| `listing_strategies.py` | `tests/unit/test_strategies.py` | 75% |
| `storage.py` | `tests/unit/test_storage.py` | 80% |

**Example test structure:**
```python
# tests/unit/test_parser.py

class TestExtractThumbnailData:
    def test_extracts_title_from_css_selector(self, sample_html):
        ...

    def test_handles_missing_title_gracefully(self):
        ...

    def test_extracts_date_in_multiple_formats(self):
        ...
```

### 2.4 Integration Test Improvements

**Update: `tests/integration/test_scrapers.py`**
- Add `--record` mode to save HTTP responses as fixtures
- Add `--replay` mode to test from saved fixtures (no network)
- Tag tests by newspaper for selective running

### 2.5 Test Configuration

**New file: `pyproject.toml` additions**
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "unit: Unit tests (no network)",
    "integration: Integration tests (requires network)",
    "slow: Tests that take >10 seconds",
]

[tool.coverage.run]
source = ["src/text"]
omit = ["*/tests/*", "*/__init__.py"]
```

### Deliverables Phase 2
- [ ] Test fixtures for common HTML/JSON patterns
- [ ] HTTP mocking setup with pytest-httpx
- [ ] Unit tests achieving 80%+ coverage on critical modules
- [ ] Coverage reporting in CI
- [ ] Test documentation

---

## Phase 3: Core Module Refactoring

**Goal:** Break apart large files, improve interfaces

### 3.1 Split `newspaper_scraper.py` (1890 lines)

**New structure:**
```
src/text/scrapers/
├── scraper/
│   ├── __init__.py           # Public API
│   ├── core.py               # NewspaperScraper base class
│   ├── modes.py              # ScrapeMode implementations
│   ├── discovery.py          # URL discovery logic
│   └── extraction.py         # Article extraction logic
```

**Simplify API:**
```python
# Before: 7 different run methods
scraper.run_full_scrape()
scraper.run_update_scrape()
scraper.run_urls_only()
# ... etc

# After: Single method with mode parameter
scraper.run(mode=ScrapeMode.FULL)
scraper.run(mode=ScrapeMode.UPDATE)
scraper.run(mode=ScrapeMode.DISCOVER_ONLY)
```

### 3.2 Split `cleaning.py` (897 lines)

**New structure:**
```
src/text/scrapers/pipelines/cleaning/
├── __init__.py               # Public API, registry
├── registry.py               # Cleaning function registry
├── dates.py                  # Date parsing functions
├── urls.py                   # URL normalization
├── text.py                   # Text cleaning utilities
└── newspapers/               # Newspaper-specific cleaners
    ├── fiji.py
    ├── cambodia.py
    └── png.py
```

**Registry pattern:**
```python
# cleaning/registry.py
_CLEANING_REGISTRY: Dict[str, Callable] = {}

def register_cleaner(name: str):
    def decorator(func):
        _CLEANING_REGISTRY[name] = func
        return func
    return decorator

def get_cleaner(name: str) -> Optional[Callable]:
    return _CLEANING_REGISTRY.get(name)

# cleaning/newspapers/fiji.py
@register_cleaner("clean_fiji_sun_date")
def clean_fiji_sun_date(date_str: str) -> str:
    ...
```

### 3.3 Split `storage.py` (890 lines)

**New structure:**
```
src/text/scrapers/pipelines/storage/
├── __init__.py               # Public API
├── csv_storage.py            # CSV operations
├── metadata.py               # Metadata JSON handling
├── serialization.py          # Record serialization
└── buffered_writer.py        # Buffered write implementation
```

### 3.4 Dependency Injection

**Before:**
```python
class NewspaperScraper:
    def __init__(self, config):
        self._storage = CSVStorage()  # Hard-coded
```

**After:**
```python
class NewspaperScraper:
    def __init__(
        self,
        config: NewspaperConfig,
        storage: StorageProtocol = None,
        client: ClientProtocol = None,
        event_emitter: EventEmitter = None,
    ):
        self._storage = storage or CSVStorage()
        self._client = client or AsyncHttpClient()
        self._events = event_emitter or EventEmitter()
```

### 3.5 Add Type Hints Throughout

Use `mypy` for type checking:
```toml
# pyproject.toml
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true
```

**Priority files for type hints:**
1. `models.py` (already has Pydantic)
2. `epu.py`
3. `client_http.py`
4. `parser.py`

### Deliverables Phase 3
- [ ] `newspaper_scraper.py` split into focused modules
- [ ] `cleaning.py` split with registry pattern
- [ ] `storage.py` split with buffered writer
- [ ] Dependency injection for testability
- [ ] Type hints added, mypy passing
- [ ] Migration guide for API changes

---

## Phase 4: Reliability Improvements

**Goal:** Make the system resilient to failures

### 4.1 Circuit Breaker Pattern

**New file: `src/text/core/circuit_breaker.py`**

```python
class CircuitBreaker:
    """
    Prevents repeated requests to failing newspapers.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failing, all requests rejected immediately
    - HALF_OPEN: Testing if target recovered
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: timedelta = timedelta(minutes=30),
        half_open_requests: int = 1,
    ):
        ...

    async def call(self, func: Callable, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            if self._should_attempt_recovery():
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitOpenError(f"Circuit open until {self._recovery_time}")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise
```

**Integration:**
```python
# In NewspaperScraper
class NewspaperScraper:
    _circuit_breakers: ClassVar[Dict[str, CircuitBreaker]] = {}

    def _get_circuit_breaker(self) -> CircuitBreaker:
        if self.name not in self._circuit_breakers:
            self._circuit_breakers[self.name] = CircuitBreaker()
        return self._circuit_breakers[self.name]
```

### 4.2 Checkpoint/Resume System

**New file: `src/text/core/checkpoints.py`**

```python
@dataclass
class ScrapeCheckpoint:
    run_id: str
    newspaper: str
    discovered_urls: List[str]
    scraped_urls: List[str]
    failed_urls: List[str]
    last_updated: datetime

class CheckpointManager:
    def __init__(self, checkpoint_dir: Path = Path("checkpoints")):
        self.checkpoint_dir = checkpoint_dir

    def save(self, checkpoint: ScrapeCheckpoint):
        path = self.checkpoint_dir / f"{checkpoint.run_id}.json"
        path.write_text(checkpoint.to_json())

    def load(self, run_id: str) -> Optional[ScrapeCheckpoint]:
        ...

    def get_pending_urls(self, checkpoint: ScrapeCheckpoint) -> List[str]:
        return [u for u in checkpoint.discovered_urls
                if u not in checkpoint.scraped_urls
                and u not in checkpoint.failed_urls]
```

### 4.3 Standardized Error Handling

**New file: `src/text/core/errors.py`**

```python
class TextModuleError(Exception):
    """Base exception for text module."""
    pass

class ScraperError(TextModuleError):
    """Base exception for scraper errors."""
    pass

class NetworkError(ScraperError):
    """Network-related errors (timeouts, connection failures)."""
    pass

class RateLimitError(NetworkError):
    """Rate limiting (429) errors."""
    retry_after: Optional[int] = None

class ParseError(ScraperError):
    """HTML/JSON parsing errors."""
    selector: Optional[str] = None

class ConfigError(TextModuleError):
    """Configuration validation errors."""
    pass
```

**Error handling pattern:**
```python
async def scrape_article(self, url: str) -> ArticleRecord:
    try:
        content, status = await self.client.request_url(url)

        if status == 429:
            retry_after = ...  # Extract from headers
            raise RateLimitError(f"Rate limited", retry_after=retry_after)

        if status == 404:
            raise NetworkError(f"Article not found: {url}")

        if not content:
            raise NetworkError(f"Empty response from {url}")

        return self.parse_article(content)

    except httpx.TimeoutException:
        raise NetworkError(f"Timeout fetching {url}")
    except Exception as e:
        raise ScraperError(f"Unexpected error: {e}") from e
```

### 4.4 Rate Limiting Improvements

**Enhance `client_http.py`:**

```python
class PerDomainRateLimiter:
    """Rate limit requests per domain, not globally."""

    def __init__(self, default_rate: float = 0.5):
        self._last_request: Dict[str, float] = {}
        self._rate_limits: Dict[str, float] = {}
        self.default_rate = default_rate

    async def acquire(self, domain: str):
        rate = self._rate_limits.get(domain, self.default_rate)
        last = self._last_request.get(domain, 0)
        wait = rate - (time.time() - last)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_request[domain] = time.time()

    def set_rate(self, domain: str, rate: float):
        """Adjust rate limit (e.g., after 429 response)."""
        self._rate_limits[domain] = rate
```

### 4.5 Validation for Error Pages

Detect websites returning HTML error pages with 200 status:

```python
def is_error_page(content: bytes, url: str) -> bool:
    """Detect soft-404 and error pages."""
    text = content.decode('utf-8', errors='ignore').lower()

    error_indicators = [
        "page not found",
        "404 error",
        "article not available",
        "content has been removed",
        "access denied",
    ]

    return any(indicator in text for indicator in error_indicators)
```

### Deliverables Phase 4
- [ ] Circuit breaker implementation
- [ ] Checkpoint/resume system
- [ ] Standardized error hierarchy
- [ ] Per-domain rate limiting
- [ ] Error page detection
- [ ] Retry with exponential backoff

---

## Phase 5: Developer Experience

**Goal:** Make the system pleasant to work with

### 5.1 Config Schema Documentation

**New file: `src/text/docs/config_schema.md`**

Document all YAML config options with examples:
```yaml
# Annotated example configuration
name: fiji_sun                    # REQUIRED: Unique identifier
country: fiji                     # REQUIRED: Country code
base_url: https://fijisun.com.fj  # REQUIRED: Base URL

# Client configuration
client: http                      # Options: http, browser
concurrency: 10                   # Max concurrent requests
rate_limit: 0.5                   # Seconds between requests
retries: 3                        # Retry attempts on failure

# Listing strategy
listing:
  type: pagination                # Options: pagination, archive, api
  start_url: /category/local-news
  page_param: page
  # ...
```

### 5.2 Config Validation CLI

**New command:**
```bash
python -m text.scrapers.orchestration.validate configs/fiji/fiji_sun.yaml
```

**Output:**
```
Validating: configs/fiji/fiji_sun.yaml

✓ Schema validation passed
✓ Base URL accessible (200 OK)
✓ Listing selectors found elements
✓ Article selectors found elements
⚠ Warning: No cleaning function registered for 'clean_fiji_sun_date'

Validation complete: 3 passed, 1 warning, 0 errors
```

### 5.3 Scraper Development Guide

**New file: `src/text/docs/adding_a_newspaper.md`**

Step-by-step guide:
1. Analyze the newspaper website
2. Create a YAML config
3. Test selectors with validation CLI
4. Add cleaning functions if needed
5. Run integration test
6. Commit and document

### 5.4 Pre-commit Hooks

**New file: `.pre-commit-config.yaml`**
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.1.0
    hooks:
      - id: black

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8

  - repo: local
    hooks:
      - id: mypy
        name: mypy
        entry: mypy src/text
        language: system
        types: [python]
```

### 5.5 Makefile for Common Tasks

**New file: `Makefile`**
```makefile
.PHONY: test lint format scrape status

test:
	pytest tests/unit -v

test-integration:
	pytest tests/integration -v --tb=short

lint:
	flake8 src/text
	mypy src/text

format:
	black src/text tests
	isort src/text tests

scrape:
	python -m text.scrapers.orchestration.main $(NEWSPAPER)

status:
	python -m text.scrapers.orchestration.status --last-24h

validate:
	python -m text.scrapers.orchestration.validate $(CONFIG)
```

### 5.6 Module README

**New file: `src/text/README.md`**

Developer entry point explaining:
- Module overview and purpose
- Directory structure
- Quick start commands
- How to add a newspaper
- How to run analysis
- Links to detailed docs

```markdown
# Text Module

Newspaper scraping and EPU analysis for the Pacific Observatory.

## Quick Start

# Scrape a newspaper
python -m text.scrapers.orchestration.main fiji_sun

# Check status
python -m text.scrapers.orchestration.status

# Run EPU analysis
python -m text.analysis.main

## Documentation
- [Adding a Newspaper](docs/adding_a_newspaper.md)
- [Config Schema](docs/config_schema.md)
- [Architecture](docs/architecture.md)
```

### Deliverables Phase 5
- [ ] `src/text/README.md` - Developer entry point
- [ ] `src/text/docs/config_schema.md` - YAML config reference
- [ ] `src/text/docs/adding_a_newspaper.md` - Step-by-step guide
- [ ] `src/text/docs/architecture.md` - System overview
- [ ] Config validation CLI tool
- [ ] Pre-commit hooks configured
- [ ] Makefile for common tasks

---

## Implementation Timeline

| Phase | Focus | Dependencies |
|-------|-------|--------------|
| Phase 1 | Observability | None |
| Phase 2 | Testing | Phase 1 (for fixtures) |
| Phase 3 | Refactoring | Phase 2 (safety net) |
| Phase 4 | Reliability | Phase 3 (clean interfaces) |
| Phase 5 | DX Polish | All previous phases |

**Suggested order:**
1. Start Phase 1 and Phase 2 in parallel
2. Complete Phase 3 after Phase 2 tests are in place
3. Phase 4 can start after Phase 3 core is done
4. Phase 5 can happen incrementally throughout

---

## Success Criteria

### Observability
- [ ] Can answer "what ran and succeeded in the last 24 hours?" in <5 seconds
- [ ] Failures include enough context to debug without additional investigation
- [ ] Logs are machine-parseable and searchable

### Testing
- [ ] >80% test coverage on critical modules
- [ ] Tests run in <30 seconds without network
- [ ] Can run tests for a single newspaper in isolation

### Maintainability
- [ ] No file >500 lines of code
- [ ] All public functions have type hints
- [ ] Adding a new newspaper requires only YAML config

### Reliability
- [ ] System recovers gracefully from network failures
- [ ] Can resume interrupted scraping runs
- [ ] Failing newspapers don't impact healthy ones

### Developer Experience
- [ ] New developer can add a newspaper in <30 minutes
- [ ] Clear error messages guide troubleshooting
- [ ] Documentation is complete and current

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Refactoring breaks existing functionality | Comprehensive tests in Phase 2 before changes |
| Scope creep in phases | Strict phase boundaries, deliver incrementally |
| SQLite performance with large datasets | SQLite handles millions of rows; can migrate later if needed |
| Learning curve for new patterns | Good documentation, pair programming |

---

## Next Steps

1. Review and approve this plan
2. Create GitHub issues for Phase 1 tasks
3. Set up branch strategy (feature branches per phase)
4. Begin Phase 1 implementation

---

*This plan prioritizes your stated goals: developer experience and observability, while keeping infrastructure simple (Python/local only) and allowing breaking changes for cleaner architecture.*
