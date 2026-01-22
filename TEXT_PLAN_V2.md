# Text Module Improvement Plan (v2)

> **Created:** January 2026
> **Supersedes:** TEXT_PLAN.md
> **Approach:** Focused, practical improvements based on actual workflow needs
> **Constraints:** Output CSV format must stay stable; breaking code changes OK

---

## Context

The text module is a data pipeline that:
- Scrapes 50+ Pacific newspapers weekly
- Calculates EPU (Economic Policy Uncertainty) indices
- Feeds into downstream docs and reports

**Operator:** Single person (you), running manually every Friday

**Current pain points:**
1. Silent failures — don't know something broke until reports are wrong
2. Hard debugging — can't figure out why things failed
3. Manual recovery — fixing requires manual intervention
4. Some newspapers hang, blocking the entire run

---

## The Plan: Three Layers

```
┌─────────────────────────────────────────────┐
│  Layer 1: MAKE FRIDAYS WORK                 │
│  Timeouts + Run Summary                     │
│  ↑ Unblocks your actual workflow            │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  Layer 2: MAKE CODE NAVIGABLE               │
│  Split large files + Consolidate modes      │
│  ↑ Makes future changes less painful        │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  Layer 3: MAKE ADDING NEWSPAPERS EASIER     │
│  Config docs + Validation CLI               │
│  ↑ DX polish once code is cleaner           │
└─────────────────────────────────────────────┘
```

---

## Layer 1: Make Fridays Work

**Goal:** Run the scraper on Friday, walk away, come back to a clear answer.

### Deliverables

#### 1.1 Automatic Timeouts

Each newspaper gets a configurable timeout (default: 10 minutes). If a scraper hangs:
- It gets killed and marked as failed
- The run continues to the next newspaper
- The failure is logged with reason "timeout"

#### 1.2 Run Summary

When the run finishes, print a clear summary:

```
=== Scrape Complete ===

Succeeded: 28 newspapers (1,247 articles)
Failed:    3 newspapers
  - post_courier: timeout after 10m
  - solomon_star: HTTP 503
  - vanuatu_daily: parse error (no articles found)
Skipped:   0 newspapers

Duration: 47 minutes
Output: data/text/
```

#### 1.3 Failure Log

Write failures to `data/text/last_run_failures.json`:

```json
{
  "run_timestamp": "2026-01-24T10:30:00",
  "failures": [
    {"newspaper": "post_courier", "reason": "timeout", "duration_seconds": 600},
    {"newspaper": "solomon_star", "reason": "http_error", "status_code": 503},
    {"newspaper": "vanuatu_daily", "reason": "parse_error", "message": "no articles found"}
  ]
}
```

### What's NOT in Layer 1

- SQLite database — JSON file is enough
- Real-time notifications — you check results afterward anyway
- Event emission system — overengineered for weekly manual runs

---

## Layer 2: Make Code Navigable

**Goal:** When you need to change something, you can find where and understand how it connects.

### Deliverables

#### 2.1 Split `newspaper_scraper.py` (1890 lines)

```
scrapers/
├── scraper.py          # Main NewspaperScraper class (slim orchestrator)
├── modes.py            # ScrapeMode enum + mode-specific logic
├── discovery.py        # URL discovery orchestration
└── extraction.py       # Article fetching + parsing coordination
```

#### 2.2 Split `listing_strategies.py` (1151 lines)

```
scrapers/strategies/
├── __init__.py         # Strategy registry + factory
├── base.py             # Base class + shared utilities
├── pagination.py       # PaginationStrategy
├── archive.py          # ArchiveStrategy
├── api.py              # APIStrategy
└── follow_link.py      # FollowLinkStrategy
```

#### 2.3 Split `cleaning.py` (897 lines)

```
pipelines/cleaning/
├── __init__.py         # Registry + get_cleaner()
├── registry.py         # @register_cleaner decorator
├── common.py           # Shared cleaning utilities (dates, urls, text)
├── fiji.py             # Fiji newspaper cleaners
├── cambodia.py         # Cambodia newspaper cleaners
├── png.py              # PNG newspaper cleaners
└── ...                 # Other countries as needed
```

#### 2.4 Split `storage.py` (890 lines)

```
pipelines/storage/
├── __init__.py         # Public API
├── csv_writer.py       # CSV operations (output format stays stable!)
├── metadata.py         # metadata.json handling
└── urls.py             # urls.csv, failed.csv handling
```

#### 2.5 Consolidate Run Modes

Replace the current 7 run methods with 4 clear modes:

| Mode | URLs | News | Use case |
|------|------|------|----------|
| `--resume` | Use existing `urls.csv` | Scrape URLs not yet in `news.csv` | Run got interrupted |
| `--update` | Discover new, append to `urls.csv` | Scrape only new URLs | Normal Friday run |
| `--full-discovery` | Discover all, overwrite `urls.csv` | Don't scrape | Recovery (rebuild URLs) |
| `--full-from-scratch` | Discover all, overwrite `urls.csv` | Scrape everything | Nuclear option |

**Scope flags** (orthogonal to mode):
- `--run-all` — All newspapers (default)
- `<newspaper_name>` — Single newspaper
- `--country <country>` — All newspapers in a country

**Default:** `--run-all --update`

**`--update` behavior:** Discovers URLs until it hits ones already in `urls.csv` (assumes listings are chronological, newest first), then scrapes only the new ones.

### Constraints

- **Output CSV format stays stable** — `news.csv` columns don't change
- **Config YAML structure stays stable** — existing newspaper configs keep working

### What's NOT in Layer 2

- Dependency injection refactoring — adds complexity without clear benefit
- Type hints everywhere — nice but not the priority
- Comprehensive test suite — not a priority right now

---

## Layer 3: Make Adding Newspapers Easier

**Goal:** Know what to do when adding a newspaper, validate before full scrape.

### Deliverables

#### 3.1 Config Schema Documentation

A single reference doc (`src/text/docs/config_schema.md`) explaining:
- Every YAML option with descriptions
- Examples for each listing strategy type
- Common patterns ("if the site looks like X, use this config")

Example section:
```yaml
# Required fields
name: fiji_sun                    # Unique identifier
country: fiji                     # Country code (matches data directory)
base_url: https://fijisun.com.fj  # Base URL for the newspaper

# Listing configuration
listing:
  type: pagination                # Options: pagination, archive, api, follow_link
  start_url: /category/local-news # Starting point for URL discovery
  page_param: page                # Query parameter for pagination
  max_pages: 100                  # Stop after N pages (optional)
```

#### 3.2 Validation CLI

```bash
python -m text.scrapers.orchestration.validate fiji_sun.yaml
```

Output:
```
Validating: fiji_sun.yaml

✓ YAML syntax valid
✓ Required fields present (name, country, base_url, listing, thumbnails, article)
✓ Base URL reachable (200 OK)
✓ Listing page loads, found 15 thumbnail elements
✓ Sample article page loads, found title + body
⚠ Warning: No cleaning function for 'clean_fiji_sun_date' (will use defaults)

Validation passed with 1 warning
```

#### 3.3 Quick-Start Guide

Short doc (`src/text/docs/adding_a_newspaper.md`) with essential steps:

1. **Analyze the site** — What listing strategy? What CSS selectors?
2. **Copy a similar config** — Find a newspaper with similar structure
3. **Modify the config** — Update URLs, selectors, cleaning functions
4. **Validate** — Run `validate` to check it works
5. **Test scrape** — Run `--update` on just that newspaper
6. **Done** — Commit the config

### What's NOT in Layer 3

- Comprehensive architecture docs — code split makes this less necessary
- Pre-commit hooks — nice but not essential
- Makefile — you already know the commands

---

## What's Cut (vs. Original Plan)

| Original item | Why cut |
|---------------|---------|
| SQLite run tracking database | JSON file is enough for weekly manual runs |
| Event emission system | Overengineered for the use case |
| Comprehensive test suite (80%+ coverage) | Not a priority right now |
| Circuit breaker pattern | Timeouts solve the hanging problem more simply |
| Complex checkpoint/resume system | `--resume` mode covers this simply |
| Pre-commit hooks | Polish, not essential |
| Makefile | Polish, not essential |
| Dependency injection refactor | Adds complexity without clear benefit |
| Per-domain rate limiting | Current rate limiting is sufficient |

---

## Implementation Order

```
Layer 1 (Make Fridays Work)
├── 1.1 Timeout handling
├── 1.2 Run summary
└── 1.3 Failure log
        ↓
Layer 2 (Make Code Navigable)
├── 2.1 Split newspaper_scraper.py
├── 2.2 Split listing_strategies.py
├── 2.3 Split cleaning.py
├── 2.4 Split storage.py
└── 2.5 Consolidate run modes
        ↓
Layer 3 (Make Adding Newspapers Easier)
├── 3.1 Config schema doc
├── 3.2 Validation CLI
└── 3.3 Quick-start guide
```

---

## Success Criteria

| Layer | Success looks like |
|-------|-------------------|
| Layer 1 | Friday run completes even if some newspapers hang; you know what failed and why |
| Layer 2 | No file >500 lines; you can find where to make changes; modes are clear |
| Layer 3 | You can add a new newspaper in <30 minutes using docs + validation |

---

## Files to Update/Create

### Layer 1
- `src/text/scrapers/orchestration/main.py` — Add timeout handling, summary output
- `data/text/last_run_failures.json` — Created automatically on each run

### Layer 2
- `src/text/scrapers/scraper.py` — New (from newspaper_scraper.py)
- `src/text/scrapers/modes.py` — New (from newspaper_scraper.py)
- `src/text/scrapers/discovery.py` — New (from newspaper_scraper.py)
- `src/text/scrapers/extraction.py` — New (from newspaper_scraper.py)
- `src/text/scrapers/strategies/` — New directory
- `src/text/scrapers/pipelines/cleaning/` — New directory structure
- `src/text/scrapers/pipelines/storage/` — New directory structure
- `src/text/scrapers/newspaper_scraper.py` — Delete after migration

### Layer 3
- `src/text/docs/config_schema.md` — New
- `src/text/docs/adding_a_newspaper.md` — New
- `src/text/scrapers/orchestration/validate.py` — Update/enhance

---

*This plan prioritizes your actual workflow (reliable Friday runs) over theoretical best practices (comprehensive testing, complex patterns). The code improvements serve the workflow, not the other way around.*
