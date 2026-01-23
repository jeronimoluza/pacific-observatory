# Newspaper Scraper Configuration Schema

This document describes the complete schema for configuring newspaper scrapers in the Pacific Observatory project. Following this guide, you should be able to add a new newspaper configuration in under 30 minutes.

## Table of Contents

- [Required Fields](#required-fields)
- [Optional Fields](#optional-fields)
- [Listing Strategies](#listing-strategies)
- [Selector Patterns](#selector-patterns)
- [Cleaning Functions](#cleaning-functions)
- [Complete Examples](#complete-examples)
- [Decision Tree](#decision-tree)
- [Validation](#validation)
- [Common Pitfalls](#common-pitfalls)

## Required Fields

Every newspaper configuration file **must** include these fields:

### `name`
- **Type:** String
- **Description:** Unique identifier for the newspaper. Used in CLI commands and logging.
- **Example:** `"SIBC"`, `"Fiji Sun"`, `"ABC AU Fiji"`
- **Note:** Should match the filename (e.g., `sibc.yaml` → `name: "SIBC"`).

### `country`
- **Type:** String
- **Description:** Country code that matches the data directory name.
- **Example:** `"fiji"`, `"solomon_islands"`, `"pacific"`
- **Note:** Must match an existing directory in `src/text/scrapers/configs/`.

### `base_url`
- **Type:** String (URL)
- **Description:** The base URL of the newspaper website.
- **Example:** `"https://www.sibconline.com.sb"`, `"https://www.fijisun.com.fj"`
- **Note:** Should **not** end with a trailing slash.

### `listing`
- **Type:** Object
- **Description:** Configuration for how to discover article listings.
- **Required subfields:**
  - `type`: One of `"pagination"`, `"archive"`, `"api"`, or `"follow_link"`
  - Additional fields depend on the listing type (see [Listing Strategies](#listing-strategies))

### `selectors`
- **Type:** Object
- **Description:** CSS selectors for extracting data from HTML pages.
- **Required subfields:**
  - `thumbnail`: Selectors for article previews on listing pages
  - `article`: Selectors for full article content
- **Note:** Not required for pure API-based scrapers, but still needed if articles are scraped from HTML.

## Optional Fields

These fields have sensible defaults but can be customized for each newspaper:

### `client`
- **Type:** String
- **Default:** `"http"`
- **Options:** `"http"` or `"browser"`
- **Description:** Client type to use for scraping. Use `"browser"` for JavaScript-rendered content.
- **Example:**
```yaml
client: "http"  # Fast, for static HTML
# OR
client: "browser"  # Slower, for JavaScript-heavy sites
```

### `concurrency`
- **Type:** Integer
- **Default:** `10`
- **Description:** Maximum number of concurrent requests.
- **Example:**
```yaml
concurrency: 5   # Conservative for smaller sites
concurrency: 20  # Aggressive for robust sites
```

### `rate_limit`
- **Type:** Float (seconds)
- **Default:** `0.2`
- **Description:** Minimum delay between requests in seconds.
- **Example:**
```yaml
rate_limit: 0.5   # 2 requests per second
rate_limit: 0.01  # 100 requests per second (use carefully!)
```

### `retries`
- **Type:** Integer
- **Default:** `3`
- **Description:** Number of retry attempts for failed requests.
- **Example:**
```yaml
retries: 3  # Default
```

### `retry_seconds`
- **Type:** Float (seconds)
- **Default:** `2.0`
- **Description:** Wait time between retry attempts.
- **Example:**
```yaml
retry_seconds: 2.0  # Standard delay
```

### `headers`
- **Type:** Object
- **Default:** Basic User-Agent header
- **Description:** Custom HTTP headers to send with requests.
- **Example:**
```yaml
headers:
  User-Agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
  Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
  Accept-Language: "en-US,en;q=0.9"
  Referer: "https://www.example.com/category/news/"
```

### `cleaning`
- **Type:** Object
- **Default:** No cleaning functions applied
- **Description:** Cleaning functions to apply to extracted data.
- **Example:**
```yaml
cleaning:
  date: "handle_mixed_dates"
  body: "join_body_list"
  url: "clean_url"
  title: "clean_title"
```

### `max_pages`
- **Type:** Integer or `null`
- **Default:** `null` (unlimited)
- **Description:** Limit the number of listing pages to scrape (useful for testing).
- **Example:**
```yaml
max_pages: 5  # Test with first 5 pages only
max_pages: null  # Scrape all pages
```

### `max_articles`
- **Type:** Integer or `null`
- **Default:** `null` (unlimited)
- **Description:** Limit the total number of articles to scrape (useful for testing).
- **Example:**
```yaml
max_articles: 50  # Test with 50 articles only
max_articles: null  # Scrape all articles
```

## Listing Strategies

The `listing.type` field determines how the scraper discovers article URLs. There are four main strategies:

### 1. Pagination Strategy

**Use when:** The site uses numbered pages like `/news?page=1`, `/news?page=2`, etc.

**Configuration:**
```yaml
listing:
  type: "pagination"
  url_template: "https://example.com/news/page/{num}/"
  start_page: 1
  step: 1
  batch_size: 10
```

**Optional fields:**
- `start_url`: First URL to scrape (if different from page 1)
- `start_page`: Starting page number (default: 1)
- `step`: Page increment (default: 1)
- `batch_size`: Number of pages to process at a time (default: 10)

**Example (SIBC):**
```yaml
listing:
  type: "pagination"
  url_template: "https://www.sibconline.com.sb/?s&post_type=post&paged={num}"
  start_page: 1
  step: 1
  batch_size: 10
```

**Example with start_url (PINA):**
```yaml
listing:
  type: "pagination"
  url_template: "https://pina.com.fj/category/news/page/{num}/"
  start_url: "https://pina.com.fj/category/news/"  # Scraped FIRST
  start_page: 2  # Then starts at page 2
  batch_size: 10
```

### 2. Archive Strategy

**Use when:** Articles are organized by date in the URL structure (e.g., `/2024/01/`, `/2024/02/`).

**Configuration:**
```yaml
listing:
  type: "archive"
  url_template: "https://example.com/index/{year}-{month}-{day}/news"
  start_date: "2020-01-01"
  date_format: "daily"  # or "monthly"
  batch_size: 10
```

**Required fields:**
- `url_template`: URL pattern with `{year}`, `{month}`, `{day}` placeholders
- `start_date`: Starting date in YYYY-MM-DD format
- `date_format`: Either `"daily"` (one URL per day) or `"monthly"` (one URL per month)

**Example (Tempo):**
```yaml
listing:
  type: "archive"
  url_template: "https://en.tempo.co/index/{year}-{month}-{day}/news"
  start_date: "2003-07-21"
  date_format: "daily"
  batch_size: 10
```

### 3. API Strategy

**Use when:** The site has a JSON API that returns article data.

**Configuration:**
```yaml
listing:
  type: "api"
  url_template: "https://example.com/api/articles?page={page}&limit=10"
  pagination_type: "page"  # or "offset"
  page_start: 1
  page_step: 1
  json_paths:
    collection: "docs"  # Path to article array in JSON
    title: "title"
    url: "link"
    date: "publishDate"
    body: "content.text"  # Optional: extract body from API
    tags: "tags.slug"
```

**Required fields:**
- `pagination_type`: Either `"page"` (for page-based) or `"offset"` (for offset-based)
- `json_paths.collection`: JSONPath to the array of articles
- Additional json_paths for data extraction

**For page-based pagination:**
```yaml
pagination_type: "page"
page_start: 1
page_step: 1
url_template: "https://example.com/api?page={page}&size=10"
```

**For offset-based pagination:**
```yaml
pagination_type: "offset"
offset_start: 0
offset_step: 100
url_template: "https://example.com/api?offset={offset}&size={size}"
json_paths:
  total: "pagination.total"  # Total number of items (optional)
```

**Example (Fiji Sun - page-based):**
```yaml
listing:
  type: "api"
  url_template: "https://fijisun.com.fj/api/articles?page={page}&limit=10"
  pagination_type: "page"
  page_start: 1
  page_step: 1
  url_construction_template: "https://www.fijisun.com.fj/news/nation/{id}"
  json_paths:
    collection: "docs"
    id: "slug"  # Used to construct article URL
    title: "title"
    date: "publishDate"
    body: "content.root.children.children.text"
    tags: "tags.slug"
```

**Example (ABC AU - offset-based):**
```yaml
listing:
  type: "api"
  pagination_type: "offset"
  offset_start: 0
  offset_step: 100
  url_template: "https://www.abc.net.au/api/loader/topicstories?offset={offset}&size={size}"
  json_paths:
    collection: "paginated.collection"
    total: "paginated.pagination.total"
    url: "link"
    title: "title"
    date: "dates.firstPublished"
```

**Note:** For API-based scrapers:
- If article URLs are in the API response, use `json_paths.url`
- If URLs need to be constructed, use `url_construction_template` with `{id}`
- If article content is in the API, extract it via `json_paths.body`
- You still need `selectors.article.body` if you're fetching full articles from HTML

### 4. Follow Link Strategy

**Use when:** Pagination uses "Next Page" links instead of numbered pages.

**Configuration:**
```yaml
listing:
  type: "follow_link"
  start_url: "https://example.com/news/page1"
  follow_selector: "div.next a::attr(href)"
```

**Required fields:**
- `start_url`: Initial page URL
- `follow_selector`: CSS selector for the "next page" link

**Example (Philippine Star):**
```yaml
listing:
  type: "follow_link"
  start_url: "https://www.philstar.com/lazy_section.php?sid=28&pubid=3"
  follow_selector: "div.next a::attr(href)"
```

## Selector Patterns

CSS selectors are used to extract data from HTML pages. They follow the Parsel library syntax (similar to Scrapy).

### Basic Selector Structure

```yaml
selectors:
  thumbnail:  # For article previews on listing pages
    container: ".article-card"  # Container element for each article
    title: "h2 a::text"        # Article title text
    url: "h2 a::attr(href)"    # Article URL
    date: ".date::text"        # Publication date
  article:    # For full article content
    body: ".content p"         # Article body paragraphs
    date: "time::text"         # Publication date (if not in thumbnail)
    tags: ".tags a::text"      # Article tags/categories
```

### Selector Syntax

**Extract text:**
```yaml
title: "h1::text"
title: ".article-title::text"
```

**Extract attributes:**
```yaml
url: "a::attr(href)"
date: "time::attr(datetime)"
image: "img::attr(src)"
```

**Multiple selectors (fallback):**
If the first selector fails, try the next:
```yaml
title:
  - "h1.article-title::text"
  - "h1::text"
  - ".title::text"
```

**Multiple elements:**
For body paragraphs or tags, the scraper will automatically collect all matching elements:
```yaml
body: ".article-body p"  # Finds all <p> tags in .article-body
tags: ".tags a::text"    # Finds all tag links
```

### Common Selector Patterns

**Title selectors:**
```yaml
# Simple heading
title: "h1::text"

# Heading with class
title: "h1.article-title::text"

# Link text
title: "h2 a::text"

# Multiple fallbacks
title:
  - ".entry-title::text"
  - "h1::text"
```

**Body selectors:**
```yaml
# All paragraphs in a container
body: "div.article-body p"

# Multiple container options
body:
  - ".entry-body p"
  - "article div.content p"

# Specific div (for non-paragraph content)
body: "div.article-content"
```

**Date selectors:**
```yaml
# Time element
date: "time::text"

# Time with datetime attribute
date: "time::attr(datetime)"

# Meta tag
date: "meta[property='article:published_time']::attr(content)"

# Multiple fallbacks
date:
  - "time::attr(datetime)"
  - ".published-date::text"
  - "meta[property='article:published_time']::attr(content)"
```

**URL selectors:**
```yaml
# Link href
url: "a::attr(href)"

# Link within heading
url: "h2 a::attr(href)"

# Multiple options
url:
  - ".article-link::attr(href)"
  - "h2 a::attr(href)"
```

**Tag selectors:**
```yaml
# Links in tag container
tags: ".tags a::text"

# Alternative patterns
tags: ".entry-taxonomies a::text"
tags: ".tag-item::text"
```

### Thumbnail vs Article Selectors

**Thumbnail selectors** extract data from article preview cards on listing pages:
```yaml
selectors:
  thumbnail:
    container: ".article-card"  # Each preview card
    title: "h2 a::text"
    url: "h2 a::attr(href)"
    date: ".date::text"
```

**Article selectors** extract data from full article pages:
```yaml
selectors:
  article:
    body: ".article-content p"
    date: "time::attr(datetime)"
    tags: ".tags a::text"
```

**Note:** Date can be extracted from either thumbnail (listing page) or article (full page), or both as fallback.

## Cleaning Functions

Cleaning functions process extracted data before storage. They're registered in the `text.scrapers.pipelines.cleaning` package.

### Built-in Common Cleaning Functions

All of these are available in `text.scrapers.pipelines.cleaning.common`:

**Date cleaning:**
- `handle_mixed_dates` - Handles various date formats and normalizes to YYYY-MM-DD
- `normalize_date` - Alias for `handle_mixed_dates`
- `handle_unix_timestamp_ms` - Converts Unix timestamps (milliseconds) to YYYY-MM-DD

**Text cleaning:**
- `clean_html_text` - Removes HTML entities and extra whitespace
- `clean_title` - Cleans article titles by removing extra whitespace and artifacts
- `join_body_list` - Joins body paragraphs from a list into a single string

**URL cleaning:**
- `clean_url` - Makes relative URLs absolute using base_url

**Tag cleaning:**
- `normalize_tags` - Splits comma/semicolon-separated tags into a list

### Country-Specific Cleaning Functions

Some newspapers require custom cleaning functions. These are organized by country:

**Solomon Islands** (`text.scrapers.pipelines.cleaning.solomon_islands`):
- `clean_sibc_date` - Handles SIBC's specific date format
- `clean_sibc_body` - Removes author bylines from SIBC articles
- `clean_solomon_star_tags` - Cleans Solomon Star tag formatting

**Philippines** (`text.scrapers.pipelines.cleaning.philippines`):
- `clean_philstar_body` - Removes boilerplate from Philippine Star articles

**Indonesia** (`text.scrapers.pipelines.cleaning.indonesia`):
- `clean_tempo_body` - Removes navigation elements from Tempo articles

**Australia** (`text.scrapers.pipelines.cleaning.australia`):
- `filter_abc_au_articles` - Filters ABC AU articles by contentUri pattern

(See individual country modules for complete lists)

### Applying Cleaning Functions

```yaml
cleaning:
  date: "handle_mixed_dates"      # Normalize date format
  body: "join_body_list"          # Join paragraph list
  url: "clean_url"                # Make URLs absolute
  title: "clean_title"            # Clean title text
  tags: "normalize_tags"          # Split tag strings
  record_filter: "filter_abc_au_articles"  # Filter records
```

### Creating Custom Cleaning Functions

If you need a custom cleaning function:

1. Add it to the appropriate country module in `src/text/scrapers/pipelines/cleaning/`
2. Use the `@register_cleaner` decorator
3. Reference it in your config

**Example:**
```python
# In src/text/scrapers/pipelines/cleaning/fiji.py
from .registry import register_cleaner

@register_cleaner
def clean_fiji_sun_date(date_str: str) -> str:
    """Clean Fiji Sun date format."""
    # Your cleaning logic here
    return cleaned_date
```

Then in your config:
```yaml
cleaning:
  date: "clean_fiji_sun_date"
```

## Complete Examples

### Example 1: Simple Pagination Site (SIBC)

A straightforward HTML-based site with numbered pagination:

```yaml
# SIBC (Solomon Islands Broadcasting Corporation) Configuration
name: "SIBC"
country: "solomon_islands"
base_url: "https://www.sibconline.com.sb"

# Listing discovery configuration
listing:
  type: "pagination"
  url_template: "https://www.sibconline.com.sb/?s&post_type=post&paged={num}"
  start_page: 1
  step: 1
  batch_size: 10

# Client configuration
client: "http"
concurrency: 10
rate_limit: 0.01
retries: 3
retry_seconds: 2.0

# CSS selectors for data extraction
selectors:
  thumbnail:
    container: ".item-bot-content"
    title: ".item-title a::text"
    url: ".item-title a::attr(href)"
    date: ".item-date-time::text"
  article:
    body:
      - ".entry-body p"
      - "article div.entry-body div"
    tags: ".entry-taxonomies a::text"

# Data cleaning configuration
cleaning:
  date: "clean_sibc_date"
  body: "clean_sibc_body"

# Test/debug options
max_pages: null
max_articles: null
```

### Example 2: API-Based Site with Constructed URLs (Fiji Sun)

Uses a JSON API for article discovery, then scrapes article content from constructed URLs:

```yaml
# Fiji Sun Configuration
name: "Fiji Sun"
country: "fiji"
base_url: "https://www.fijisun.com.fj"

# Listing discovery using API strategy
listing:
  type: "api"
  url_template: "https://fijisun.com.fj/api/articles?page={page}&limit=10"
  pagination_type: "page"
  page_start: 1
  page_step: 1
  url_construction_template: "https://www.fijisun.com.fj/news/nation/{id}"
  json_paths:
    collection: "docs"  # Array of articles in JSON response
    id: "slug"          # Article ID for URL construction
    title: "title"
    date: "publishDate"
    body: "content.root.children.children.text"
    tags: "tags.slug"

# Client configuration
client: "http"
concurrency: 10
rate_limit: 0.2
retries: 3
retry_seconds: 2.0

headers:
  User-Agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
  Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
  Accept-Language: "en-US,en;q=0.9"
  Referer: "https://www.fijisun.com.fj/category/news/nation/"

# Selectors (placeholder for API strategy)
selectors:
  thumbnail:
    container: "filler"
    title: "filler"
    url: "filler"
    date: filler
  article:
    body: "filler"
    tags: "filler"

# Data cleaning
cleaning:
  date: "handle_mixed_dates"
  body: "join_body_list"

max_pages: null
max_articles: null
```

### Example 3: Archive Strategy (Tempo)

Date-based URL structure for historical archives:

```yaml
# Tempo English Configuration
name: "Tempo"
country: "indonesia"
base_url: "https://en.tempo.co"

# Listing discovery using archive strategy
listing:
  type: "archive"
  url_template: "https://en.tempo.co/index/{year}-{month}-{day}/news"
  start_date: "2003-07-21"
  date_format: "daily"
  batch_size: 10

# Client configuration
client: "http"
concurrency: 2
rate_limit: 3
retries: 1
retry_seconds: 2.0

headers:
  User-Agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
  Accept-Language: "en-US,en;q=0.9"
  Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"

# CSS selectors
selectors:
  thumbnail:
    container: "main.main-left article.text-card"
    title: "h2.title::text"
    url: "h2.title a::attr(href)"
  article:
    body: "div.detail-in"
    date:
      - "meta[property='article:published_time']::attr(content)"
      - "meta[property='article:published time']::attr(content)"
    tags: "div.box-tag-detail a::text"

# Data cleaning
cleaning:
  date: "handle_mixed_dates"

max_pages: null
max_articles: null
```

### Example 4: Follow Link Strategy (Philippine Star)

Uses "Next Page" link following for pagination:

```yaml
# Philippine Star Configuration
name: "Philippine Star"
country: "philippines"
base_url: "https://www.philstar.com/"

# Listing discovery using follow link strategy
listing:
  type: "follow_link"
  start_url: "https://www.philstar.com/lazy_section.php?sid=28&pubid=3"
  follow_selector: "div.next a::attr(href)"

# Client configuration
client: "http"
concurrency: 10
rate_limit: 0.2
retries: 3
retry_seconds: 2.0

headers:
  User-Agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
  Accept-Language: "en-US,en;q=0.9"

# CSS selectors
selectors:
  thumbnail:
    container: 'div[class="news_column latest"] div[class="TilesText spec"]'
    title: "div.news_title a::text"
    url: "div.news_title a::attr(href)"
  article:
    body: "div.article__writeup p"
    date: "#sports_article_credits > div.article__date-published::text"

# Data cleaning
cleaning:
  date: "handle_mixed_dates"
  body: "clean_philstar_body"

max_pages: null
max_articles: null
```

## Decision Tree

Use this decision tree to choose the right listing strategy:

```
START: What type of pagination does the site use?

├─ Does the site have a JSON API that returns article lists?
│  └─ YES → Use "api" strategy
│     ├─ Does the API use page numbers (page=1, page=2)?
│     │  └─ Use pagination_type: "page"
│     └─ Does the API use offsets (offset=0, offset=100)?
│        └─ Use pagination_type: "offset"
│
├─ Are articles organized by date in the URL structure?
│  (e.g., /2024/01/, /2024/02/, /2024-01-15/)
│  └─ YES → Use "archive" strategy
│     ├─ URLs by day? → Use date_format: "daily"
│     └─ URLs by month? → Use date_format: "monthly"
│
├─ Does pagination use numbered pages in the URL?
│  (e.g., ?page=1, ?page=2 or /page/1/, /page/2/)
│  └─ YES → Use "pagination" strategy
│
└─ Does pagination use "Next Page" or "Load More" links?
   └─ YES → Use "follow_link" strategy
```

## Validation

Always validate your configuration before committing:

### Validate a Single Config

```bash
python -m text.scrapers.orchestration.validate src/text/scrapers/configs/fiji/fiji_sun.yaml
```

### Validate with Connectivity Test

```bash
python -m text.scrapers.orchestration.validate src/text/scrapers/configs/fiji/fiji_sun.yaml --live
```

### Validate All Configs

```bash
python -m text.scrapers.orchestration.validate --all
```

### Validation Output

The validator will check:
- Required fields present
- Field types correct
- Listing strategy configuration complete
- Cleaning functions registered
- URL formats valid
- (With `--live`) Base URL accessible

**Example output:**
```
Validating: src/text/scrapers/configs/fiji/fiji_sun.yaml
--------------------------------------------------
[+] Base URL accessible (200 OK)
[!] Config name 'Fiji Sun' doesn't match filename 'fiji_sun'

Validation complete: 0 error(s), 1 warning(s)
```

## Common Pitfalls

### 1. JavaScript-Rendered Content

**Problem:** Site uses JavaScript to load article content.

**Solution:** Use `client: "browser"` instead of `client: "http"`:
```yaml
client: "browser"
```

**Warning:** Browser-based scraping is significantly slower.

### 2. Trailing Slashes in URLs

**Problem:** Inconsistent trailing slashes can cause duplicate URLs.

**Solution:** Don't use trailing slashes in `base_url`:
```yaml
base_url: "https://example.com"  # GOOD
base_url: "https://example.com/"  # BAD
```

### 3. CSV Selectors

**Problem:** Using comma-separated selectors instead of array syntax.

**Wrong:**
```yaml
body: "div.content p, div.article p"  # This is treated as ONE selector
```

**Correct:**
```yaml
body:
  - "div.content p"
  - "div.article p"
```

### 4. Forgetting `::text` or `::attr()`

**Problem:** Extracting element instead of text/attribute.

**Wrong:**
```yaml
title: "h1"  # Returns full element
url: "a"     # Returns full element
```

**Correct:**
```yaml
title: "h1::text"
url: "a::attr(href)"
```

### 5. Incorrect JSONPath

**Problem:** JSONPath doesn't match API response structure.

**Solution:** Test the API endpoint first and verify the JSON structure:
```bash
curl "https://example.com/api/articles?page=1" | jq '.'
```

Then match your `json_paths.collection` to the actual JSON structure.

### 6. Missing Selectors for API Scrapers

**Problem:** Using `"filler"` selectors when you still need to scrape article HTML.

**Solution:** If your API provides URLs but not full content, you still need proper `selectors.article` fields:
```yaml
selectors:
  thumbnail:
    container: "filler"  # Not used for API
  article:
    body: "div.article-content p"  # NEEDED if scraping article HTML
```

### 7. Rate Limiting Too Aggressive

**Problem:** Getting blocked or causing server issues with high request rates.

**Solution:** Start conservative:
```yaml
concurrency: 5
rate_limit: 0.5  # 2 requests/second
```

Then increase gradually if the site handles it well.

### 8. Incorrect Country Directory

**Problem:** `country` field doesn't match an existing directory.

**Solution:** Verify the directory exists:
```bash
ls src/text/scrapers/configs/
```

Use the exact directory name:
```yaml
country: "solomon_islands"  # Match directory name exactly
```

### 9. Date Extraction Failures

**Problem:** Dates not being extracted or parsed correctly.

**Solution:** Add multiple fallback selectors and use `handle_mixed_dates`:
```yaml
selectors:
  article:
    date:
      - "time::attr(datetime)"
      - "time::text"
      - ".published::text"
      - "meta[property='article:published_time']::attr(content)"

cleaning:
  date: "handle_mixed_dates"
```

### 10. Not Testing with Limits

**Problem:** Running full scrape during development and debugging.

**Solution:** Always test with limits first:
```yaml
max_pages: 2
max_articles: 20
```

Remove limits only after confirming everything works correctly.

---

## Quick Reference Card

**Minimal working config:**
```yaml
name: "Example News"
country: "example"
base_url: "https://example.com"

listing:
  type: "pagination"
  url_template: "https://example.com/news/page/{num}/"
  start_page: 1

selectors:
  thumbnail:
    container: ".article"
    title: "h2::text"
    url: "a::attr(href)"
  article:
    body: ".content p"

cleaning:
  date: "handle_mixed_dates"
```

**Most common cleaning functions:**
- `handle_mixed_dates` - Date normalization
- `join_body_list` - Join body paragraphs
- `clean_url` - Make URLs absolute
- `clean_title` - Clean title text

**Testing workflow:**
1. Create config with `max_pages: 2` and `max_articles: 20`
2. Validate: `python -m text.scrapers.orchestration.validate config.yaml --live`
3. Test scrape: `python -m text.scrapers.cli --newspaper example --mode test`
4. Review output
5. Remove limits and commit

---

**Questions or issues?** Check existing configs in `src/text/scrapers/configs/` for working examples.
