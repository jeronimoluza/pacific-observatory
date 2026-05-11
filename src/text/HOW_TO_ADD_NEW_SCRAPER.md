# How to Add a New Newspaper Scraper

This guide walks through adding a new newspaper to the text analysis pipeline.
The default path is YAML-only — no Python required. Custom Python is only needed
for non-standard date formats, body cleaning, or new strategy modes.

## Prerequisites

- Python 3.11+, installed with `make install`
- The country must exist in `src/configs/countries.yaml`
- Config location: `src/text/configs/{region}/{subregion}/{country}/{newspaper}.yaml`

## Step 1: Identify the Listing Type

**This is the most important step.** The listing type determines the YAML structure,
which selectors you need, and whether any Python code is required. Get this wrong
and nothing else matters.

Fetch the homepage HTML and inspect it:

```bash
curl -sL --max-time 15 -o /tmp/probe.html "https://example.com"
```

Then work through this decision tree:

```
Does /wp-json/wp/v2/posts return JSON?
  YES → listing.type: "api"  (WordPress, Tier 0 — no selectors needed)

Is there a JSON API endpoint (non-WP)?
  YES → listing.type: "api"  (Tier 2 — inspect JSON structure)

Does the listing URL contain a page number that increments?
  e.g. /page/2/, ?page=2, /category/news/2/
  YES → listing.type: "pagination"

Does the site use a date-based archive URL?
  e.g. /2025/03/, /2025/03/08/, /archives/2025/
  Does each date page also have numbered sub-pages?
    NO  → listing.type: "archive"
    YES → listing.type: "paginated_archive"  (date_format: "daily" or "monthly")

Does the archive use a date range query string?
  e.g. ?dateFrom=01.03.2025&dateTo=31.03.2025
  YES → listing.type: "paginated_archive"  (date_format: "range")

Is there only a "Next" or "Previous" link (no URL pattern)?
  YES → listing.type: "follow_link"

None of the above — SPA, Cloudflare JS challenge, or no archive?
  → Tier 3 — browser client or API reverse-engineering needed
```

### What to look for in the HTML

Open `/tmp/probe.html` and scan for:

| Signal | Listing type |
|--------|-------------|
| `/wp-json/` in headers or `<link>` tags | `api` (WordPress) |
| `<a href="/category/news/page/2/">` or `?page=2` | `pagination` |
| `<a href="/2025/03/08/">` in archive nav | `archive` or `paginated_archive` |
| `?dateFrom=...&dateTo=...` in pagination links | `paginated_archive` (range) |
| `<a class="next" href="...">` (relative, changes each page) | `follow_link` |
| Empty `<div id="app">` + JS bundles | Tier 3 (SPA) |
| `cf-ray` header or challenge page | Tier 3 (Cloudflare) |

If the listing URL has dates **and** you see paginated sub-pages (page 2, page 3…
under the same date), use `paginated_archive`. If each date URL has only one page
of articles, use `archive`.

---

## Step 2: Create the YAML Config

```bash
cp src/text/configs/_examples/newspaper_template.yaml \
   src/text/configs/{region}/{subregion}/{country}/{newspaper}.yaml
```

Below are complete examples for each listing type.

---

### `pagination` — Numbered pages

Use when the listing URL has a `{num}` that increments:

```yaml
name: "Antara"
country: "indonesia"
base_url: "https://www.antaranews.com"
language: "indo"

listing:
  type: "pagination"
  url_template: "https://www.antaranews.com/berita/terkini?page={num}"
  start_page: 1
  step: 1
  batch_size: 5

client: "http"
concurrency: 5
rate_limit: 0.5
retries: 3
retry_seconds: 2.0

selectors:
  thumbnail:
    container: "article.simple-post"
    title: "h2 a::text"
    url: "h2 a::attr(href)"
  article:
    body: ".post-content p"
    date: "time::attr(datetime)"

cleaning:
  date: "handle_mixed_dates"

max_pages: null
max_articles: null
```

Key fields: `url_template` must contain `{num}`. `step` defaults to 1.
Optional `start_url` can be a single URL or list to scrape before pagination begins.

---

### `api` — WordPress REST API (Tier 0)

Use when `/wp-json/wp/v2/posts` returns JSON:

```yaml
name: "Frontier Myanmar"
country: "myanmar"
base_url: "https://www.frontiermyanmar.net"
language: "en"

listing:
  type: "api"
  pagination_type: "page"
  page_start: 1
  page_step: 1
  url_template: "https://www.frontiermyanmar.net/wp-json/wp/v2/posts?per_page=100&page={page}&_fields=id,date,link,title,excerpt"
  json_paths:
    url: "link"
    title: "title.rendered"
    date: "date"
    body: "excerpt.rendered"

client: "http"
concurrency: 5
rate_limit: 0.2
retries: 3
retry_seconds: 2.0

selectors:
  thumbnail:
    container: "filler"
    title: "filler"
    url: "filler"
  article:
    body: "filler"

cleaning:
  date: "handle_mixed_dates"
  body: "clean_wp_html_body"

max_pages: null
max_articles: null
```

`selectors` are unused for `api` type but required by the config schema — use
`"filler"` as placeholder values.

---

### `archive` — Date-based, one page per date

Use when the site has `/YYYY/MM/` or `/YYYY/MM/DD/` archive URLs and each date
page has all its articles on a single page (no pagination within a date):

```yaml
name: "Japan Today"
country: "japan"
base_url: "https://japantoday.com"
language: "en"

listing:
  type: "archive"
  url_template: "https://japantoday.com/category/national/{year}/{month}/"
  date_format: "monthly"   # "monthly" = {year}/{month}, "daily" = {year}/{month}/{day}
  start_date: "2022-01-01"
  batch_size: 5

client: "http"
concurrency: 3
rate_limit: 1.0
retries: 3
retry_seconds: 2.0

selectors:
  thumbnail:
    container: "article"
    title: "h3 a::text"
    url: "h3 a::attr(href)"
  article:
    body: ".article-body p"
    date: "time::attr(datetime)"

cleaning:
  date: "handle_mixed_dates"

max_pages: null
max_articles: null
```

`date_format` options: `"monthly"` (iterates month by month), `"daily"` (day by
day). The strategy steps **backward** from today (or `end_date`) to `start_date`.

---

### `paginated_archive` — Date-based with pagination per date

Use when the site organises articles by date AND each date can have multiple
pages. The strategy scrapes page 1 via `start_url` then paginates via
`url_template` until 404, no thumbnails, or duplicate content.

#### Daily / monthly mode

```yaml
name: "NZ Herald"
country: "new_zealand"
base_url: "https://www.nzherald.co.nz"
language: "en"

listing:
  type: "paginated_archive"
  date_format: "daily"          # or "monthly"
  start_url: "https://www.nzherald.co.nz/latest-news/{year}/{month}/{day}/"
  url_template: "https://www.nzherald.co.nz/latest-news/{year}/{month}/{day}/page/{num}/"
  start_date: "2022-01-01"
  start_page: 2
  batch_size: 5

client: "http"
concurrency: 3
rate_limit: 1.0
retries: 3
retry_seconds: 2.0

selectors:
  thumbnail:
    container: "article"
    title: "h3 a::text"
    url: "h3 a::attr(href)"
  article:
    body: ".article-body p"
    date: "time::attr(datetime)"

cleaning:
  date: "handle_mixed_dates"

max_pages: null
max_articles: null
```

#### Range mode — date-range query parameters

Use when the archive is accessed via `?dateFrom=...&dateTo=...` (e.g. fontanka.ru):

```yaml
name: "Fontanka"
country: "russian_federation"
base_url: "https://www.fontanka.ru"
language: "ru"

listing:
  type: "paginated_archive"
  date_format: "range"
  range_days: 30                          # window width; keep ≤30 to stay under 250-page cap
  range_date_format: "%d.%m.%Y"          # Python strftime for {date_from}/{date_to}
  start_url: "https://www.fontanka.ru/24hours/?dateFrom={date_from}&dateTo={date_to}&content=news"
  url_template: "https://www.fontanka.ru/24hours/page-{num}/?dateFrom={date_from}&dateTo={date_to}&content=news"
  start_date: "2022-01-01"
  start_page: 2
  batch_size: 5

client: "http"
concurrency: 3
rate_limit: 1.0
retries: 3
retry_seconds: 2.0

headers:
  Accept-Language: "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"

selectors:
  thumbnail:
    container: "[class*='announcement_']"
    title: "a[data-announcement-title]::attr(data-announcement-title)"
    url: "a[data-announcement-title]::attr(href)"
  article:
    body: "#articleBody p"
    date: "time[datetime]::attr(datetime)"

cleaning:
  date: "handle_mixed_dates"

max_pages: null
max_articles: null
```

Range mode fields: `range_days` (required, positive int), `range_date_format`
(Python strftime, default `"%d.%m.%Y"`). URL templates must contain `{date_from}`
and `{date_to}` (and `url_template` must also contain `{num}`). The strategy steps
backward in windows of `range_days` days from `end_date` to `start_date`.

---

### `follow_link` — "Next page" link only

Use when the site has a "Next" or "Older" link but no predictable URL pattern:

```yaml
name: "Example News"
country: "fiji"
base_url: "https://example.fj"
language: "en"

listing:
  type: "follow_link"
  start_url: "https://example.fj/news/"
  follow_selector: "a.pagination-next::attr(href)"

client: "http"
concurrency: 3
rate_limit: 1.0
retries: 3
retry_seconds: 2.0

selectors:
  thumbnail:
    container: "article"
    title: "h2 a::text"
    url: "h2 a::attr(href)"
  article:
    body: ".article-body p"
    date: "time::attr(datetime)"

cleaning:
  date: "handle_mixed_dates"

max_pages: null
max_articles: null
```

`follow_selector` must point to the `href` attribute of the next-page link.
Traversal stops when the selector finds no link.

---

## Step 3: Write Selectors

All selectors use CSS syntax with two pseudo-selectors:

- `"h2 a::text"` — extract text content
- `"h2 a::attr(href)"` — extract an attribute value

**Fallback chains** — pass a list to try each selector until one matches:
```yaml
body: ["article .entry-content p", ".post-content p", "#main p"]
date: ["time::attr(datetime)", "meta[property='article:published_time']::attr(content)"]
```

### Thumbnail selectors

| Field | Purpose | Typical pattern |
|-------|---------|-----------------|
| `container` | Article card element | `article`, `[class*='post-card']`, `li.story` |
| `title` | Article title | `h2 a::text`, `a::attr(title)` |
| `url` | Article URL | `h2 a::attr(href)`, `a::attr(href)` |

> **CSS module hashes** — frameworks like Next.js and CSS Modules generate class names
> like `card_Ab3xY`. These change on every deploy. Use attribute-substring selectors
> instead: `[class*='card_']` matches any class containing `card_`.
> Prefer `id=` attributes and `data-*` attributes — they never get hashed.

### Article selectors

| Field | Purpose | Typical pattern |
|-------|---------|-----------------|
| `body` | Article text paragraphs | `#articleBody p`, `.post-content p` |
| `date` | Publication date | `time[datetime]::attr(datetime)`, `meta[property='article:published_time']::attr(content)` |
| `tags` | Topic tags (optional) | `.tags a::text` |

Prefer `time[datetime]::attr(datetime)` (ISO 8601 from the HTML attribute)
over date text nodes — it requires no parsing.

---

## Step 4: Test

```bash
# Dry run — shows thumbnails found, no data written
poetry run po text collect --source {newspaper} --max-pages 2 --dry-run

# Real run with limits
poetry run po text collect --source {newspaper} --max-pages 5 --max-articles 100

# Full rebuild from scratch
poetry run po text collect --source {newspaper} --rebuild
```

Check the output:
- `data/text/{region}/{subregion}/{country}/{newspaper}/news.csv` — articles
- Article dates are parsed (not null or year 1970)
- Article bodies have content (not just nav/footer text)
- No garbage/navigation URLs in the URL column

---

## Step 5: Cleaning Functions

Most configs only need `cleaning.date: "handle_mixed_dates"`.

### Built-in cleaners (`src/text/scrapers/pipelines/cleaning/common.py`)

| Function | Purpose |
|----------|---------|
| `handle_mixed_dates` | Normalize 30+ date formats → YYYY-MM-DD (use by default) |
| `handle_unix_timestamp_ms` | Convert millisecond Unix timestamps |
| `handle_unix_timestamp_ms_or_iso` | Handle both Unix ms and ISO datetime strings |
| `clean_wp_html_body` | Strip HTML tags from WordPress API body content |
| `clean_html_text` | Remove HTML entities and normalize whitespace |
| `clean_url` | Make relative URLs absolute |
| `join_body_list` | Join array of body text strings into single string |

Use `record_filter` to exclude records:
```yaml
cleaning:
  record_filter: "filter_articles"
```

### Custom cleaners

Only write a custom cleaner if nothing built-in works. Add a function to
`src/text/scrapers/pipelines/cleaning/{country}.py`:

```python
from .registry import register_cleaner

@register_cleaner
def filter_articles(record: dict) -> bool:
    """Return False to exclude a record from news.csv."""
    return "fontanka.ru" in record.get("url", "")
```

Country-specific cleaners already exist for: Australia, Indonesia, Laos, Malaysia,
Myanmar, New Zealand, Palau, Philippines, Singapore, Solomon Islands, Tonga.

---

## When Do You Need New Python Code?

| Situation | What to write | Where |
|-----------|--------------|-------|
| Non-standard date or body format | Custom cleaning function (~10-20 lines) | `src/text/scrapers/pipelines/cleaning/{country}.py` |
| New archive URL pattern | Extend `PaginatedArchiveStrategy.__init__`, `_format_url`, `_get_previous_date` (~30-40 lines) | `src/text/scrapers/strategies/archive.py` |
| JavaScript-rendered content | Nothing — use `client: "browser"` in YAML | YAML only |
| Custom JSON API structure | Extend `ApiStrategy` or add `json_paths` support | `src/text/scrapers/strategies/api.py` |

If you need to extend a strategy, check the existing `date_format` branches first —
the pattern for adding a new mode is well-established in `archive.py`.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| 403 / blocked | Add `headers:` with `User-Agent`. If still blocked, try `client: "browser"` or increase `rate_limit` |
| Empty articles | Inspect `selectors.article.body` against the actual article HTML. Try fallback selectors. |
| Wrong dates | Add `cleaning.date: "handle_mixed_dates"`. For Unix ms, use `handle_unix_timestamp_ms`. |
| Duplicate articles | Check `selectors.thumbnail.url` returns full URLs |
| Garbage URLs in output | The pipeline deduplicates via `urls.csv`. Sponsored/external URLs that return empty bodies are filtered by Pydantic validation automatically. |
| Selector stops working after site update | CSS module hashes changed. Switch to `[class*='stable-prefix_']` or `data-*` attributes. |
| EPU not calculated | Check `language:` matches a directory in `src/text/analysis/keywords/` |
| Strategy not found | Check `src/text/scrapers/strategies/__init__.py` for the exported class |

## Reference

- Config examples: `src/text/configs/_examples/newspaper_template.yaml`
- Strategies: `src/text/scrapers/strategies/` (pagination, archive, api, follow_link)
- Cleaning functions: `src/text/scrapers/pipelines/cleaning/common.py`
- Countries/regions: `src/configs/countries.yaml`, `src/configs/regions.yaml`
