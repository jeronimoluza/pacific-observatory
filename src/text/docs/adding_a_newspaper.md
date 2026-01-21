# Adding a New Newspaper

This guide walks through the process of adding a new newspaper scraper.

## Prerequisites

- Python 3.11+
- Browser developer tools (for inspecting HTML)
- Basic understanding of CSS selectors

## Step 1: Analyze the Website

Before creating a config, analyze the target newspaper website:

### 1.1 Identify the Listing Strategy

Visit the news listing pages and determine how articles are organized:

| Pattern | Strategy Type | Example |
|---------|--------------|---------|
| `/news?page=1`, `/news?page=2` | `pagination` | Most common |
| `/archive/2024/01`, `/archive/2024/02` | `archive` | Date-based archives |
| `/search?q=news&page=1` | `search` | Search-based listing |
| `/api/articles?page=1` | `api` | JSON API endpoint |

### 1.2 Find the Selectors

Use browser developer tools (F12) to find CSS selectors:

1. **Listing Page:**
   - Container element for each article
   - Title, link, date, excerpt elements

2. **Article Page:**
   - Title element
   - Body content element
   - Date element

### 1.3 Check for Dynamic Content

- If content loads via JavaScript, you may need `client: browser`
- Look for API endpoints that might be easier to scrape

## Step 2: Create the Config File

Create a new YAML file in the appropriate country directory:

```bash
# Create the config file
touch src/text/scrapers/configs/fiji/new_newspaper.yaml
```

### Minimal Config Template

```yaml
name: new_newspaper
country: fiji
language: en
base_url: https://newnewspaper.com

client: http
concurrency: 5
rate_limit: 1.0

listing:
  type: pagination
  start_url: /news
  page_param: page

thumbnails:
  container: article.news-item
  title: h2.title
  link: a

article:
  title: h1.article-title
  body: div.article-content
```

## Step 3: Validate the Config

```bash
python -m text.scrapers.orchestration.validate src/text/scrapers/configs/fiji/new_newspaper.yaml
```

The validator checks:
- Schema validation
- Required fields
- Base URL accessibility

## Step 4: Test with Limited Scrape

Run a limited test scrape:

```bash
# Scrape only 2 pages, 5 articles max
python -m text.scrapers.orchestration.main new_newspaper --max-pages 2 --max-articles 5
```

Check the output in `data/text/fiji/new_newspaper/`:
- `urls.csv` - Discovered URLs
- `news.csv` - Scraped articles
- `failed.csv` - Failed URLs (if any)

## Step 5: Add Cleaning Functions (If Needed)

If the scraped data needs cleaning, add functions to `cleaning.py`:

```python
# src/text/scrapers/pipelines/cleaning.py

def clean_new_newspaper_body(body: str) -> str:
    """Clean body text from New Newspaper."""
    # Remove footer text
    body = body.replace("Copyright New Newspaper", "")
    # Remove read more links
    body = re.sub(r"Read more:.*$", "", body)
    return body.strip()

# Register the function
CLEANING_FUNCTIONS["clean_new_newspaper_body"] = clean_new_newspaper_body
```

Then reference it in your config:

```yaml
cleaning:
  body: clean_new_newspaper_body
  date: handle_mixed_dates
```

## Step 6: Test Full Scrape

Run a full scrape to verify everything works:

```bash
python -m text.scrapers.orchestration.main new_newspaper
```

## Step 7: Document and Commit

1. Verify the data looks correct
2. Commit the config file
3. Update any documentation if needed

## Common Issues

### No Articles Found

**Symptoms:** `thumbnails_found: 0`

**Solutions:**
1. Verify the listing URL is correct
2. Check the container selector matches elements
3. Try using browser client if JavaScript rendering is needed:
   ```yaml
   client: browser
   ```

### Missing Dates

**Symptoms:** Dates are empty or malformed

**Solutions:**
1. Check the date selector
2. Add a cleaning function for the date format:
   ```yaml
   cleaning:
     date: handle_mixed_dates
   ```

### Rate Limiting

**Symptoms:** 429 errors or connection resets

**Solutions:**
1. Increase rate limit (slower):
   ```yaml
   rate_limit: 2.0  # 2 seconds between requests
   ```
2. Reduce concurrency:
   ```yaml
   concurrency: 3
   ```

### JavaScript-Rendered Content

**Symptoms:** Content visible in browser but not scraped

**Solutions:**
1. Use browser client:
   ```yaml
   client: browser
   ```
2. Look for API endpoints in Network tab

### Authentication Required

**Symptoms:** 403 errors or login pages

**Solutions:**
1. Enable cookie authentication:
   ```yaml
   auth:
     cookies: true
   ```
2. Add custom headers:
   ```yaml
   auth:
     headers:
       User-Agent: "Mozilla/5.0..."
   ```

## Selector Tips

### CSS Selectors

```yaml
# Class selector
title: h2.article-title

# ID selector
title: "#main-title"

# Attribute selector
link: "a[href^='/news']"

# Child selector
title: "article > h2"

# Descendant selector
body: "div.content p"
```

### XPath Selectors

```yaml
# Use xpath: prefix
title: "xpath://h2[@class='title']"
link: "xpath://a[@class='link']/@href"
```

### Extracting Attributes

```yaml
# Extract href attribute
link:
  selector: a.article-link
  attribute: href

# Extract src attribute
image:
  selector: img.thumbnail
  attribute: src
```

## Example Configs

### Pagination-Based

```yaml
name: fiji_sun
country: fiji
language: en
base_url: https://fijisun.com.fj

listing:
  type: pagination
  start_url: /category/local-news
  page_param: page
  start_page: 1

thumbnails:
  container: article.post
  title: h2.entry-title
  link: h2.entry-title a
  date: time.entry-date
```

### Archive-Based

```yaml
name: solomon_star
country: solomon_islands
language: en
base_url: https://www.solomonstarnews.com

listing:
  type: archive
  start_url: /archive/{year}/{month}
  start_year: 2020

thumbnails:
  container: div.archive-item
  title: h3.title
  link: a.read-more
  date: span.date
```

### API-Based

```yaml
name: khmer_times
country: cambodia
language: en
base_url: https://www.khmertimeskh.com

listing:
  type: api
  endpoint: /api/articles
  page_param: page
  response_path: data.articles

thumbnails:
  title: title
  link: url
  date: published_at
```
