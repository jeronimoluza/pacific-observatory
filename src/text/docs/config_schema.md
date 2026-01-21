# Newspaper Configuration Schema

This document describes the YAML configuration schema for newspaper scrapers.

## Complete Example

```yaml
# Required fields
name: fiji_sun                    # Unique identifier
country: fiji                     # Country code
language: en                      # ISO language code
base_url: https://fijisun.com.fj  # Base URL for the newspaper

# Client configuration
client: http                      # Client type: http or browser
concurrency: 10                   # Max concurrent requests
rate_limit: 0.5                   # Seconds between requests
timeout: 30                       # Request timeout in seconds
retries: 3                        # Retry attempts on failure
active: true                      # Whether scraper is active

# Listing strategy configuration
listing:
  type: pagination                # Strategy type
  start_url: /category/local-news # Starting URL
  page_param: page                # Pagination parameter
  start_page: 1                   # First page number
  max_pages: 100                  # Maximum pages to scrape

# Thumbnail selectors (for listing pages)
thumbnails:
  container: article.news-item    # Container element
  title: h2.article-title         # Title selector
  link: a.article-link            # Link selector
  date: span.article-date         # Date selector
  excerpt: p.article-excerpt      # Excerpt selector (optional)
  image: img.article-thumbnail    # Image selector (optional)
  author: span.author             # Author selector (optional)
  category: span.category         # Category selector (optional)

# Article selectors (for article pages)
article:
  title: h1.article-title         # Title selector
  body: div.article-body          # Body selector
  date: time.publish-date         # Date selector
  author: span.author             # Author selector (optional)
  category: span.category         # Category selector (optional)
  tags: div.tags a                # Tags selector (optional)

# Cleaning functions (optional)
cleaning:
  date: handle_mixed_dates        # Date cleaning function
  body: clean_fiji_sun_body       # Body cleaning function
  title: clean_title              # Title cleaning function

# Authentication (optional)
auth:
  cookies: true                   # Use browser cookies
  headers:                        # Custom headers
    User-Agent: "Custom Agent"
```

## Required Fields

### `name`
- **Type:** string
- **Description:** Unique identifier for the newspaper
- **Example:** `fiji_sun`, `khmer_times`

### `country`
- **Type:** string
- **Description:** Country code for organizing data
- **Example:** `fiji`, `cambodia`, `png`

### `language`
- **Type:** string
- **Description:** ISO 639-1 language code
- **Example:** `en`, `km`, `tl`

### `base_url`
- **Type:** string
- **Description:** Base URL of the newspaper website
- **Example:** `https://fijisun.com.fj`

## Client Configuration

### `client`
- **Type:** string
- **Options:** `http`, `browser`
- **Default:** `http`
- **Description:** Client type to use for requests
  - `http`: Async HTTP client (faster, less resource-intensive)
  - `browser`: Selenium browser (for JavaScript-rendered pages)

### `concurrency`
- **Type:** integer
- **Default:** `10`
- **Description:** Maximum number of concurrent requests

### `rate_limit`
- **Type:** float
- **Default:** `0.5`
- **Description:** Minimum seconds between requests

### `timeout`
- **Type:** integer
- **Default:** `30`
- **Description:** Request timeout in seconds

### `retries`
- **Type:** integer
- **Default:** `3`
- **Description:** Number of retry attempts on failure

### `active`
- **Type:** boolean
- **Default:** `true`
- **Description:** Whether the scraper should be included in batch runs

## Listing Strategy Configuration

### `listing.type`
- **Type:** string
- **Options:** `pagination`, `archive`, `search`, `category`, `api`
- **Description:** Strategy for discovering article URLs

### Pagination Strategy
```yaml
listing:
  type: pagination
  start_url: /news
  page_param: page          # URL parameter for page number
  start_page: 1             # First page number
  max_pages: 100            # Maximum pages to scrape
```

### Archive Strategy
```yaml
listing:
  type: archive
  start_url: /archive/{year}/{month}
  start_year: 2020
  start_month: 1
```

### API Strategy
```yaml
listing:
  type: api
  endpoint: /api/v1/articles
  page_param: page
  response_path: data.articles  # JSONPath to articles array
```

## Selector Configuration

### Thumbnail Selectors

Selectors for extracting data from listing pages.

| Field | Required | Description |
|-------|----------|-------------|
| `container` | Yes | Parent element containing each article |
| `title` | Yes | Article title |
| `link` | Yes | Article URL |
| `date` | No | Publication date |
| `excerpt` | No | Article excerpt/summary |
| `image` | No | Thumbnail image URL |
| `author` | No | Author name |
| `category` | No | Article category |

### Article Selectors

Selectors for extracting data from article pages.

| Field | Required | Description |
|-------|----------|-------------|
| `title` | Yes | Article title |
| `body` | Yes | Article body content |
| `date` | No | Publication date |
| `author` | No | Author name |
| `category` | No | Article category |
| `tags` | No | Article tags |

## Cleaning Functions

Map fields to cleaning function names defined in `cleaning.py`.

### Available Cleaning Functions

| Function | Description |
|----------|-------------|
| `handle_mixed_dates` | Normalize various date formats to YYYY-MM-DD |
| `clean_html_text` | Remove HTML artifacts and normalize whitespace |
| `normalize_tags` | Split and clean tag strings |
| `clean_url` | Normalize URLs and make relative URLs absolute |
| `clean_title` | Clean article titles |

### Newspaper-Specific Functions

Many newspapers have custom cleaning functions:

- `clean_kosmo_body`
- `clean_inquirer_body`
- `clean_philstar_body`
- `clean_jakarta_post_body`
- `clean_solomon_star_content`
- etc.

## Authentication

### Cookie-Based Authentication

```yaml
auth:
  cookies: true                   # Use cookies from browser
```

### Custom Headers

```yaml
auth:
  headers:
    User-Agent: "Mozilla/5.0..."
    Accept-Language: "en-US,en;q=0.9"
```

## XPath Support

Selectors can use XPath by prefixing with `xpath:`:

```yaml
thumbnails:
  title: "xpath://h2[@class='title']"
  link: "xpath://a[@class='article-link']/@href"
```

## Attribute Extraction

To extract attributes instead of text:

```yaml
thumbnails:
  link:
    selector: a.article-link
    attribute: href
  image:
    selector: img.thumbnail
    attribute: src
```

## Validation

Validate your configuration with:

```bash
python -m text.scrapers.orchestration.validate path/to/config.yaml
```

This will check:
- Schema validation
- Base URL accessibility
- Selector validity (if `--live` flag is used)
