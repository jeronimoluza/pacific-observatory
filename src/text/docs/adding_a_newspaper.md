# Quick-Start Guide: Adding a New Newspaper

This guide will help you add a new newspaper scraper to the Pacific Observatory in under 30 minutes.

## Prerequisites

Before you begin, make sure you have:

- A publicly accessible newspaper website
- Basic understanding of HTML and CSS selectors
- Browser developer tools knowledge (F12 in Chrome/Firefox)
- Python environment set up with Poetry
- Access to the Pacific Observatory repository

**Estimated time: 20-30 minutes**

## Overview: The 7-Step Process

1. Analyze the Site (5 minutes)
2. Copy a Similar Config (2 minutes)
3. Modify the Config (10 minutes)
4. Validate (3 minutes)
5. Test Scrape (5 minutes)
6. Add Cleaning Functions if Needed (5 minutes)
7. Commit (2 minutes)

---

## Step 1: Analyze the Site (5 minutes)

Open the newspaper website in your browser and answer these three questions:

### Question 1: Which Listing Strategy?

Visit the news section and check how articles are organized. Click through multiple pages to see the URL pattern.

**Common patterns:**

| URL Pattern | Listing Strategy | Example |
|------------|-----------------|---------|
| `/news?page=1`, `/news?page=2` | `pagination` | SIBC, PINA |
| `/news/page/1/`, `/news/page/2/` | `pagination` | SIBC variant |
| `/2024/01/`, `/2024/02/` | `archive` | Tempo |
| Look in Network tab for JSON | `api` | Fiji Sun, ABC AU |
| "Next Page" button with href | `follow_link` | Philippine Star |

**How to check:**
1. Go to the news section
2. Click "Next Page" or scroll to pagination
3. Look at the URL bar - what changes?

### Question 2: What Are the CSS Selectors?

Use browser developer tools to find selectors:

**For listing pages (thumbnail selectors):**
1. Right-click an article preview → Inspect
2. Find the container element (usually `<article>`, `<div class="post">`, etc.)
3. Note selectors for:
   - Container: The element wrapping each article
   - Title: Where the headline is
   - URL: Where the link to the full article is
   - Date: Where the publication date appears

**For article pages:**
1. Click into any article
2. Right-click the main content → Inspect
3. Note selectors for:
   - Body: Paragraph container (usually `<p>` tags within a div)
   - Date: Publication date (if not on listing page)
   - Tags: Article categories/tags

### Question 3: Any Special Requirements?

Check if the site needs special handling:

- **JavaScript rendering**: Does content appear in browser but not in "View Source"? → Use `client: "browser"`
- **403 errors**: Does the site block scrapers? → Add custom headers
- **API available**: Do you see JSON requests in Network tab? → Use `api` strategy
- **Login required**: Not currently supported - skip these sites

---

## Step 2: Copy a Similar Config (2 minutes)

Find an existing config file that matches your newspaper's listing strategy and copy it.

### Find Existing Configs

```bash
# List all configs by country
ls src/text/scrapers/configs/

# View all configs
find src/text/scrapers/configs -name "*.yaml"
```

### Pick a Template Based on Strategy

**For pagination sites**, copy SIBC:
```bash
cp src/text/scrapers/configs/solomon_islands/sibc.yaml \
   src/text/scrapers/configs/samoa/samoa_observer.yaml
```

**For API sites**, copy Fiji Sun:
```bash
cp src/text/scrapers/configs/fiji/fiji_sun.yaml \
   src/text/scrapers/configs/fiji/fiji_times.yaml
```

**For archive sites**, copy Tempo:
```bash
cp src/text/scrapers/configs/indonesia/tempo.yaml \
   src/text/scrapers/configs/indonesia/jakarta_post.yaml
```

**For follow-link sites**, copy Philippine Star:
```bash
cp src/text/scrapers/configs/philippines/philstar.yaml \
   src/text/scrapers/configs/philippines/inquirer.yaml
```

---

## Step 3: Modify the Config (10 minutes)

Open your new config file and update it section by section.

### 3.1 Update Basic Information

```yaml
name: "Samoa Observer"
country: "samoa"
base_url: "https://www.samoaobserver.ws"
```

**Rules:**
- `name`: Human-readable name (spaces OK)
- `country`: Must match the directory name exactly
- `base_url`: No trailing slash

### 3.2 Update Listing Configuration

Update based on your analysis from Step 1.

**For pagination:**
```yaml
listing:
  type: "pagination"
  url_template: "https://www.samoaobserver.ws/category/local/page/{num}/"
  start_page: 1
  step: 1
  batch_size: 10
```

**For archive:**
```yaml
listing:
  type: "archive"
  url_template: "https://example.com/archive/{year}-{month}-{day}/"
  start_date: "2020-01-01"
  date_format: "daily"  # or "monthly"
  batch_size: 10
```

**For API:**
```yaml
listing:
  type: "api"
  url_template: "https://example.com/api/articles?page={page}&limit=10"
  pagination_type: "page"  # or "offset"
  page_start: 1
  page_step: 1
  json_paths:
    collection: "docs"  # Path to article array
    title: "title"
    url: "link"
    date: "publishDate"
```

**For follow_link:**
```yaml
listing:
  type: "follow_link"
  start_url: "https://example.com/news/page1"
  follow_selector: "div.next a::attr(href)"
```

### 3.3 Update Selectors

Replace the selectors with ones you found in Step 1.

```yaml
selectors:
  thumbnail:
    container: ".article-card"           # Container for each article
    title: "h2 a::text"                  # Title text
    url: "h2 a::attr(href)"              # Article URL
    date: ".post-date::text"             # Date (optional here)
  article:
    body: ".article-content p"           # Body paragraphs
    date: "time::attr(datetime)"         # Date on article page
    tags: ".tags a::text"                # Tags/categories
```

**Important selector tips:**
- Use `::text` to extract text content
- Use `::attr(href)` to extract attributes
- For multiple fallbacks, use a list:
  ```yaml
  body:
    - ".article-content p"
    - "article div.content p"
    - ".entry-content p"
  ```

### 3.4 Adjust Client Settings (Optional)

Most sites work with these defaults:

```yaml
client: "http"       # Use "browser" if JavaScript-rendered
concurrency: 10      # Parallel requests
rate_limit: 0.2      # Seconds between requests
retries: 3
retry_seconds: 2.0
```

**When to change:**
- JavaScript rendering needed: `client: "browser"`
- Site is slow/unstable: `concurrency: 5`, `rate_limit: 1.0`
- Getting blocked: Add headers (see troubleshooting)

### 3.5 Add Initial Cleaning

Start with these common cleaners:

```yaml
cleaning:
  date: "handle_mixed_dates"  # Normalizes dates to YYYY-MM-DD
  body: "join_body_list"      # Joins body paragraphs into single text
```

More cleaning functions can be added later if needed (see Step 6).

### 3.6 Set Test Limits

For testing, limit the scrape:

```yaml
max_pages: 2         # Only scrape 2 listing pages
max_articles: 20     # Only scrape 20 articles
```

**Remember to remove these before production!**

---

## Step 4: Validate (3 minutes)

Validate your configuration file to catch errors early.

### Basic Validation

```bash
poetry run python src/text/scrapers/orchestration/validate.py \
    src/text/scrapers/configs/samoa/samoa_observer.yaml
```

This checks:
- Required fields present
- Field types correct
- Listing strategy configured properly
- Cleaning functions registered

### Validation with Live Test

Add `-v` for verbose output:

```bash
poetry run python src/text/scrapers/orchestration/validate.py \
    src/text/scrapers/configs/samoa/samoa_observer.yaml -v
```

**Expected output:**
```
Validating: src/text/scrapers/configs/samoa/samoa_observer.yaml
--------------------------------------------------
✓ Required fields present
✓ Listing strategy: pagination
✓ Selectors configured
✓ Cleaning functions registered
✓ Base URL format valid

Validation complete: 0 error(s), 0 warning(s)
```

**If you see errors:**
- Missing fields: Add them to your config
- Invalid cleaning function: Check the function name spelling
- Invalid URL: Check `base_url` format

---

## Step 5: Test Scrape (5 minutes)

Run a small test scrape to verify everything works.

### Run Test Scrape

```bash
poetry run python src/text/scrapers/orchestration/main.py samoa_observer
```

This will:
1. Discover article URLs from listing pages (max 2 pages due to `max_pages: 2`)
2. Scrape article content (max 20 articles due to `max_articles: 20`)
3. Save results to `data/text/samoa/samoa_observer/`

### Check the Output

```bash
# Check discovered URLs
head data/text/samoa/samoa_observer/urls.csv

# Check scraped articles
head data/text/samoa/samoa_observer/news.csv

# Check for failures
cat data/text/samoa/samoa_observer/failed.csv
```

**Expected files:**
- `urls.csv`: List of discovered article URLs
- `news.csv`: Scraped articles with title, body, date, etc.
- `failed.csv`: Failed URLs (should be empty or minimal)

### Verify the Data

Open `news.csv` and check:
- **Titles**: Are they correct?
- **Bodies**: Do they contain article content (not empty, not full HTML)?
- **Dates**: Are they in YYYY-MM-DD format?
- **URLs**: Do they look correct?

**Common issues at this stage:**
- Empty bodies → Wrong body selector
- HTML in bodies → Need cleaning function
- No dates → Wrong date selector
- Dates not formatted → Need `handle_mixed_dates` cleaner

---

## Step 6: Add Cleaning Functions (if needed) (5 minutes)

If your scraped data needs cleaning (e.g., dates not parsing, unwanted text in bodies), add custom cleaning functions.

### When Are Cleaning Functions Needed?

**You need cleaning if:**
- Dates aren't in YYYY-MM-DD format after `handle_mixed_dates`
- Bodies contain boilerplate text (copyright notices, "Read more", etc.)
- URLs are relative instead of absolute
- Bodies are returned as lists instead of strings

### Check Available Cleaners

Built-in cleaners are in `src/text/scrapers/pipelines/cleaning/`:

**Common cleaners** (available for all newspapers):
- `handle_mixed_dates` - Normalizes various date formats
- `join_body_list` - Joins body paragraph lists
- `clean_url` - Makes relative URLs absolute
- `clean_title` - Removes extra whitespace from titles
- `normalize_tags` - Splits comma-separated tags

**Country-specific cleaners** (examples):
- Solomon Islands: `clean_sibc_date`, `clean_sibc_body`
- Philippines: `clean_philstar_body`
- Indonesia: `clean_tempo_body`
- Australia: `filter_abc_au_articles`

### Create a Custom Cleaner

If you need a custom cleaner, add it to the appropriate country module.

**Example: Create a Samoa cleaner**

1. Create or edit `src/text/scrapers/pipelines/cleaning/samoa.py`:

```python
"""Cleaning functions for Samoa newspapers."""
from .registry import register_cleaner

@register_cleaner
def clean_samoa_observer_body(body: str) -> str:
    """Remove boilerplate from Samoa Observer articles."""
    # Remove copyright notice
    if "© Samoa Observer" in body:
        body = body.split("© Samoa Observer")[0]

    # Remove "Read more" links
    body = body.replace("Read the full story here", "")

    return body.strip()

@register_cleaner
def clean_samoa_observer_date(date_str: str) -> str:
    """Parse Samoa Observer date format."""
    # Example: "Monday, 15 January 2024" → "2024-01-15"
    from dateutil import parser
    try:
        dt = parser.parse(date_str)
        return dt.strftime("%Y-%m-%d")
    except:
        return date_str
```

2. Import the module in `src/text/scrapers/pipelines/cleaning/__init__.py`:

```python
from . import samoa  # Add this line
```

3. Reference the cleaner in your config:

```yaml
cleaning:
  date: "clean_samoa_observer_date"
  body: "clean_samoa_observer_body"
```

4. Re-run validation to ensure the cleaner is registered:

```bash
poetry run python src/text/scrapers/orchestration/validate.py \
    src/text/scrapers/configs/samoa/samoa_observer.yaml
```

---

## Step 7: Commit (2 minutes)

Once your test scrape looks good, finalize and commit.

### Remove Test Limits

Edit your config and remove the test limits:

```yaml
max_pages: null      # Change from 2 to null
max_articles: null   # Change from 20 to null
```

### Commit the Config

```bash
# Add the config file
git add src/text/scrapers/configs/samoa/samoa_observer.yaml

# If you created cleaning functions
git add src/text/scrapers/pipelines/cleaning/samoa.py
git add src/text/scrapers/pipelines/cleaning/__init__.py

# Commit
git commit -m "feat: add Samoa Observer scraper

- Pagination-based listing strategy
- CSS selectors for articles and thumbnails
- Custom date and body cleaning functions
- Validated and tested with 20 sample articles"
```

---

## Troubleshooting

### "No articles found" Error

**Symptoms:**
- `urls.csv` is empty or has very few URLs
- Logs show "Found 0 articles on page"

**Solutions:**

1. **Check the listing URL**:
   ```bash
   # Verify the URL loads in browser
   curl -I "https://example.com/news/page/1/"
   ```

2. **Verify container selector**:
   - Open listing page in browser
   - Inspect an article preview
   - Copy the container selector
   - Test it: Right-click → Copy → Copy selector

3. **Use browser client** (if JavaScript-rendered):
   ```yaml
   client: "browser"
   ```

4. **Check for API alternative**:
   - Open browser DevTools → Network tab
   - Refresh the page
   - Look for JSON requests
   - Consider using `api` strategy instead

### "Dates not parsing" Error

**Symptoms:**
- Dates are empty in `news.csv`
- Dates are malformed (e.g., "Monday, Jan 15" instead of "2024-01-15")

**Solutions:**

1. **Add date selector fallbacks**:
   ```yaml
   selectors:
     article:
       date:
         - "time::attr(datetime)"
         - "time::text"
         - ".post-date::text"
         - "meta[property='article:published_time']::attr(content)"
   ```

2. **Use date cleaner**:
   ```yaml
   cleaning:
     date: "handle_mixed_dates"
   ```

3. **Create custom date cleaner** (see Step 6)

### "403 Forbidden" Error

**Symptoms:**
- Getting 403 HTTP errors
- Site loads in browser but not in scraper

**Solutions:**

1. **Add custom headers**:
   ```yaml
   headers:
     User-Agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
     Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
     Accept-Language: "en-US,en;q=0.9"
     Referer: "https://example.com/"
   ```

2. **Slow down requests**:
   ```yaml
   rate_limit: 1.0      # 1 second between requests
   concurrency: 5       # Only 5 parallel requests
   ```

### "Content appears but body is empty"

**Symptoms:**
- Titles and URLs are scraped correctly
- Bodies are empty or contain placeholder text

**Solutions:**

1. **Check if JavaScript-rendered**:
   - View page source (Ctrl+U)
   - If content is missing, use `client: "browser"`

2. **Verify body selector**:
   ```yaml
   selectors:
     article:
       body:
         - "div.article-content p"
         - "article p"
         - ".entry-content p"
   ```

3. **Check for API content**:
   - Look for JSON in Network tab
   - Extract body from API response with `json_paths.body`

### "Rate limiting / Getting blocked"

**Symptoms:**
- 429 errors
- Temporary bans
- Connection resets

**Solutions:**

1. **Slow down**:
   ```yaml
   concurrency: 3
   rate_limit: 2.0      # 2 seconds between requests
   ```

2. **Add headers**:
   ```yaml
   headers:
     User-Agent: "Mozilla/5.0..."
   ```

3. **Use browser client**:
   ```yaml
   client: "browser"
   ```

---

## Common Patterns

### WordPress Sites

Most WordPress sites use similar structures:

```yaml
selectors:
  thumbnail:
    container: "article.post"
    title: "h2.entry-title a::text"
    url: "h2.entry-title a::attr(href)"
    date: "time.entry-date::text"
  article:
    body: "div.entry-content p"
    date: "time.entry-date::attr(datetime)"
    tags: ".entry-taxonomies a::text"

cleaning:
  date: "handle_mixed_dates"
  body: "join_body_list"
```

### JSON API Sites

Many modern sites have JSON APIs:

```yaml
listing:
  type: "api"
  url_template: "https://example.com/api/articles?page={page}"
  pagination_type: "page"
  page_start: 1
  page_step: 1
  json_paths:
    collection: "data.articles"
    title: "title"
    url: "url"
    date: "publishedAt"
    body: "content"  # Optional: if API returns full content

# Selectors not needed if API returns everything
selectors:
  thumbnail:
    container: "filler"
  article:
    body: "filler"  # Only needed if fetching HTML after API
```

---

## Checklist

Before considering the newspaper "done", verify:

- [ ] Config file created in correct country directory
- [ ] Config validated successfully with no errors
- [ ] Test scrape completes successfully
- [ ] `urls.csv` contains discovered article URLs
- [ ] `news.csv` contains articles with:
  - [ ] Titles (not empty, not HTML)
  - [ ] Bodies (not empty, not full HTML)
  - [ ] Dates (YYYY-MM-DD format)
  - [ ] URLs (absolute, clean)
- [ ] `failed.csv` is empty or has minimal failures
- [ ] `max_pages` and `max_articles` removed from config
- [ ] Cleaning functions created (if needed)
- [ ] Config committed to git with descriptive message

---

## Reference: Config File Structure

Here's a minimal working config for reference:

```yaml
name: "Example News"
country: "example"
base_url: "https://example.com"

listing:
  type: "pagination"
  url_template: "https://example.com/news/page/{num}/"
  start_page: 1
  step: 1
  batch_size: 10

client: "http"
concurrency: 10
rate_limit: 0.2
retries: 3
retry_seconds: 2.0

selectors:
  thumbnail:
    container: ".article"
    title: "h2::text"
    url: "a::attr(href)"
    date: ".date::text"
  article:
    body: ".content p"
    date: "time::attr(datetime)"
    tags: ".tags a::text"

cleaning:
  date: "handle_mixed_dates"
  body: "join_body_list"

max_pages: null
max_articles: null
```

---

## Additional Resources

- **Detailed schema reference**: See `config_schema.md` for complete field documentation
- **Existing configs**: Browse `src/text/scrapers/configs/` for examples
- **Run modes**: See Task 2.5 documentation for `--update`, `--resume`, `--full-discovery`, `--full-from-scratch`
- **Validation tool**: Task 3.2 documentation for advanced validation options

---

## Questions?

If you get stuck:
1. Check existing configs in the same country for patterns
2. Review `config_schema.md` for detailed field documentation
3. Run validation with `-v` for detailed error messages
4. Try a different listing strategy if the current one isn't working
