# How to Add a New Newspaper Scraper

This guide walks through adding a new newspaper to the text
analysis pipeline. Most newspapers only need a YAML config file —
no Python code required.

## Prerequisites

- Python 3.11+
- The repository cloned and installed: `pip install -e ".[scraping]"`
- The country must exist in `src/configs/countries.yaml`

## Quick Start

1. Create config: `src/text/configs/{region}/{country}/{newspaper}.yaml`
2. Test: `po text collect --source {newspaper} --dry-run`
3. Run: `po text collect --source {newspaper}`

Most newspapers work with just a YAML config. You only need custom
Python code if the newspaper requires special authentication, JavaScript
rendering, or non-standard pagination.

## Step 1: Assess the Newspaper Source

Before writing a config, check:

1. **Does it have a sitemap or RSS feed?** Check `/sitemap.xml`,
   `/feed/`, `/rss/`. These are the easiest to scrape.
2. **Does it have a WordPress API?** Check `/wp-json/wp/v2/posts`.
   If it returns JSON, use `listing.type: "api"`.
3. **Does it paginate?** Look at the URL pattern when clicking
   "Next" or "Older posts". If the URL has `?page=2` or `/page/2/`,
   use `listing.type: "pagination"`.
4. **Does it require JavaScript?** If the page is blank without JS,
   set `client: "browser"`.

## Step 2: Create the YAML Config

Copy the template:
```bash
mkdir -p src/text/configs/{region}/{country}
cp src/text/configs/_examples/newspaper_template.yaml \
   src/text/configs/{region}/{country}/{newspaper}.yaml
```

### Minimal Config (pagination)

```yaml
name: "Fiji Sun"
country: "fiji"
base_url: "https://fijisun.com.fj"
language: "en"

listing:
  type: "pagination"
  url_template: "https://fijisun.com.fj/category/local-news/page/{num}/"
  start_page: 1
  step: 1

client: "http"
concurrency: 5
rate_limit: 0.5

selectors:
  thumbnail:
    container: "article"
    title: "h2 a::text"
    url: "h2 a::attr(href)"
  article:
    body: ["article .entry-content p", ".post-content p"]
    date: ["time::attr(datetime)", ".post-date::text"]
    tags: ".post-tags a::text"
```

### API Config (WordPress JSON API)

```yaml
name: "ABC Australia"
country: "australia"
base_url: "https://www.abc.net.au"
language: "en"

listing:
  type: "api"
  url_template: "https://www.abc.net.au/news-api/search?offset={offset}&size=50"
  pagination_type: "offset"
  json_paths:
    collection: "collection"
    total: "pagination.total"
    url: "link"
    title: "title"
    date: "dates.firstPublished"

client: "http"
concurrency: 5
rate_limit: 0.5

selectors:
  article:
    body: [".Article p", "#content p"]
    date: ["time::attr(datetime)"]
    tags: "[data-component='RelatedTopics'] a::text"
```

### Listing Types

| Type | When to use | Key fields |
|------|-------------|------------|
| `pagination` | URL with page number | `url_template`, `start_page`, `step` |
| `api` | JSON API endpoint | `url_template`, `pagination_type`, `json_paths` |
| `archive` | Archive/date-based listing | `url_template` (with date placeholders) |
| `follow_link` | "Next" link on each page | `start_url`, `next_selector` |

### Client Types

| Type | When to use |
|------|-------------|
| `http` | Default. Fast async HTTP. Works for most sites. |
| `browser` | Site requires JavaScript rendering (Selenium). Slower. |

## Step 3: Test

```bash
# Preview — shows what would be scraped, no data written
po text collect --source fiji_sun --dry-run

# Scrape with a limit (for testing)
# Edit config temporarily: max_pages: 3, max_articles: 20

# Run for real
po text collect --source fiji_sun

# Check output
head data/text/fiji/fiji_sun/news.csv
wc -l data/text/fiji/fiji_sun/news.csv
```

## Step 4: Verify Data Quality

After the first scrape, check:

- [ ] Article dates are parsed correctly (not null or wrong year)
- [ ] Article bodies have meaningful content (not just navigation text)
- [ ] Tags are relevant (not JavaScript artifacts)
- [ ] No duplicate articles in news.csv
- [ ] Reasonable article count for the newspaper

## Step 5: Commit

Commit the YAML config:
- `src/text/configs/{region}/{country}/{newspaper}.yaml`

Update `src/text/configs/README.md` if adding a new country directory.

## Advanced: Custom Scraping Logic

If a newspaper needs custom code (authentication, JS rendering,
non-standard data formats), create a custom pipeline callable:

```python
# src/text/scrapers/custom/{newspaper}.py

def filter_articles(record: dict) -> bool:
    """Return False to exclude a record."""
    # Example: skip opinion/editorial articles
    return "/opinion/" not in record.get("url", "")
```

Reference it in your config:
```yaml
cleaning:
  record_filter: "filter_articles"
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| 403 / blocked | Try `client: "browser"`, or add `rate_limit: 2.0` |
| Empty articles | Check `selectors.article.body` — inspect the HTML |
| Wrong dates | Add a `cleaning.date: "handle_mixed_dates"` callable |
| Duplicate content | Check `selectors.thumbnail.url` — ensure full URLs |
| Encoding issues | Most sites are UTF-8. For others, add `encoding:` to config |

## Reference

- Config template: `src/text/configs/_examples/newspaper_template.yaml`
- Config schema: [docs/text/YAML_CONFIG_REFERENCE.md](YAML_CONFIG_REFERENCE.md)
- Pipeline docs: [docs/text/PIPELINE.md](PIPELINE.md)
- Scraper architecture: `src/text/scrapers/README.md`
