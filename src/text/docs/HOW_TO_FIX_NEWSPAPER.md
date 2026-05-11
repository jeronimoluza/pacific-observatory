# How to Fix a Broken Newspaper Config

Guide for diagnosing and fixing YAML configs that were batch-generated but don't
actually scrape articles. The goal is YAML-only fixes — no Python code changes.
If a site can't be fixed with existing strategies, mark it and move on.

## File Naming Convention

| Prefix | Meaning | Action |
|--------|---------|--------|
| `{name}.yaml` | Working config | Normal pipeline source |
| `_0_{name}.yaml` | Broken, no viable path | Skipped by pipeline |
| `_1_rss_{name}.yaml` | Broken pagination, but RSS feed exists | Future: implement RSS strategy, then rename back to `{name}.yaml` |

**The `_` prefix is required.** The pipeline's `discover_pipeline_configs()` skips
any path component starting with `_`. The digit after `_` is a priority hint:
`_0_` = unfixable, `_1_rss_` = fixable once RSS strategy exists.

---

## Step 1: Verify Pagination Actually Works

The most common failure: the config has `url_template: ...?page={num}` but the
site ignores the page parameter and returns the same HTML every time.

```bash
# Fetch page 1 and page 2, compare sizes
START_URL="https://example.com/news/"
PAGE2_URL="https://example.com/news/?page=2"

s1=$(curl -sL -o /dev/null -w "%{size_download}" --max-time 10 -A "Mozilla/5.0" "$START_URL")
s2=$(curl -sL -o /dev/null -w "%{size_download}" --max-time 10 -A "Mozilla/5.0" "$PAGE2_URL")
echo "Page 1: $s1 bytes, Page 2: $s2 bytes"
```

**Same size (±100 bytes)** → pagination is broken. The `?page=N` parameter is ignored.

**Different size** → pagination may work. Verify articles are actually different:

```python
import re, urllib.request
req1 = urllib.request.Request(url1, headers={"User-Agent": "Mozilla/5.0"})
req2 = urllib.request.Request(url2, headers={"User-Agent": "Mozilla/5.0"})
html1 = urllib.request.urlopen(req1, timeout=10).read().decode("utf-8", errors="replace")
html2 = urllib.request.urlopen(req2, timeout=10).read().decode("utf-8", errors="replace")

# Extract article URLs (adjust regex for the site)
links1 = set(re.findall(r'href="(https://[^"]*example\.com/\d+/[^"]+)"', html1))
links2 = set(re.findall(r'href="(https://[^"]*example\.com/\d+/[^"]+)"', html2))
overlap = links1 & links2
print(f"Page1: {len(links1)}, Page2: {len(links2)}, Overlap: {len(overlap)}")
```

If overlap is 100% → pagination is fake. If page 2 has unique articles → it works.

---

## Step 2: Check for WordPress API

```bash
curl -sI --max-time 10 -A "Mozilla/5.0" "https://example.com/wp-json/" | head -1
```

- **HTTP 200** → WordPress confirmed. Switch to `api` strategy (see Fix A below).
- **HTTP 404** → Not WordPress. Continue to Step 3.
- **HTTP 403** → Possibly WordPress behind Cloudflare. Mark as `_0_`.

If WordPress, verify posts endpoint works:

```bash
curl -sL --max-time 10 -A "Mozilla/5.0" \
  "https://example.com/wp-json/wp/v2/posts?per_page=3&_fields=id,date,link,title,excerpt"
```

Should return a JSON array of post objects. Check `X-WP-TotalPages` header to
confirm there's historical data:

```bash
curl -sI --max-time 10 -A "Mozilla/5.0" \
  "https://example.com/wp-json/wp/v2/posts?per_page=100&page=1" | grep -i x-wp-total
```

---

## Step 3: Check for RSS Feed

```bash
for path in /rss /feed /rss.xml /feed/rss /atom.xml; do
  code=$(curl -sL -o /dev/null -w "%{http_code}" --max-time 6 -A "Mozilla/5.0" \
    "https://example.com${path}")
  [ "$code" = "200" ] && echo "RSS found at ${path}"
done
```

RSS feeds typically contain only the last 20-50 articles (no historical depth).
If pagination is broken but RSS exists, rename to `_1_rss_{name}.yaml` — it can
be used for forward collection once an RSS strategy is built.

---

## Step 4: Check for Cloudflare / Anti-bot

```bash
curl -sL --max-time 15 -A "Mozilla/5.0" "https://example.com/" -o /tmp/probe.html
head -50 /tmp/probe.html | grep -i "cloudflare\|cf-ray\|challenge\|captcha"
```

If you get a challenge page or an empty `<div id="app">` → Tier 3. Mark as `_0_`.

---

## Step 5: Verify Selectors on Live HTML

Even if pagination works, the selectors may be wrong. Fetch a listing page and
an article page, then check:

### Listing page selectors

```bash
curl -sL --max-time 10 -A "Mozilla/5.0" "$LISTING_URL" -o /tmp/listing.html

# Find repeating containers
grep -Eo '<(article|div|li)[^>]*class="[^"]*"' /tmp/listing.html \
  | sort | uniq -c | sort -rn | head -15
```

Look for the article card container and check that `title` and `url` selectors
match actual elements inside it. Common issues:

| Problem | Symptom | Fix |
|---------|---------|-----|
| Title in nested `<h2>` not direct `<a>` text | Empty titles | Use `h2::text` instead of `a::text` |
| URL in `<a>` with specific class | Wrong or missing URLs | Use `a.specific-class::attr(href)` |
| CSS module hash classes (`card_Ab3xY`) | Selectors break on deploy | Use `[class*='card_']` |
| Date in `<meta itemprop>` not `<meta property>` | Missing dates | Use `meta[itemprop='datePublished']::attr(content)` |

### Article page selectors

```bash
curl -sL --max-time 10 -A "Mozilla/5.0" "$ARTICLE_URL" -o /tmp/article.html

# Check date meta tag exists
grep -o 'article:published_time.*content="[^"]*"' /tmp/article.html

# Check body selector returns content
grep -c '<p' /tmp/article.html
```

---

## Fix A: Switch to WordPress API (discovery + HTML body)

When `/wp-json/wp/v2/posts` returns JSON, use the API for **article discovery**
(URLs, titles, dates) but **scrape the article page** for the full body text.

**Why not use the API body?** The WP `excerpt.rendered` field is a truncated
teaser (~100-150 chars ending with `[…]`). If you include `body` in `json_paths`,
the pipeline creates "prefetched articles" directly from the API data and **never
visits the article page** — you get excerpts instead of full articles.

The pattern: API discovers → scraper visits each article URL → extracts body from
HTML using `selectors.article.body`.

```yaml
name: "Example News"
language: et
country: estonia
base_url: https://example.com

listing:
  type: api
  pagination_type: page
  page_start: 1
  page_step: 1
  url_template: "https://example.com/wp-json/wp/v2/posts?per_page=100&page={page}&_fields=id,date,link,title"
  json_paths:
    url: link
    title: title.rendered
    date: date
    # NO body here — forces HTML scraping of article pages

client: http
concurrency: 5
rate_limit: 0.5
retries: 3
retry_seconds: 2.0

selectors:
  thumbnail:
    container: filler
    title: filler
    url: filler
  article:
    body: "div.entry-content p"     # real CSS selector for the article page
    date: meta[property='article:published_time']::attr(content)

cleaning:
  date: handle_mixed_dates

max_pages: null
max_articles: null
stop_date: '2025-12-01'
```

Key points:
- `json_paths` has `url`, `title`, `date` but **NOT `body`** — this is critical
- `selectors.article.body` must be a **real selector** (not `filler`) for the article page
- Standard WP body container: `div.entry-content p` (works for most WP themes)
- `selectors.thumbnail` still uses `filler` (API doesn't use HTML selectors for discovery)
- `per_page=100` maximizes articles per request (WP API max)
- `rate_limit: 0.5` is slightly conservative to avoid hitting article pages too fast

### How the flow works internally

```
API json_paths has body? ──YES──> Prefetched article (API excerpt used, page NOT visited)
         │
         NO
         │
         v
    Scraper visits article URL → extract_article_data_from_soup()
         │                        uses selectors.article.body
         v
    Full body text from HTML
```

### Finding the right body selector

Fetch one article page from the WP API `link` field and inspect:

```bash
curl -sL --max-time 10 -A "Mozilla/5.0" "$ARTICLE_URL" -o /tmp/article.html

# Standard WP: div.entry-content contains the article body
grep -c 'class="entry-content' /tmp/article.html

# Count paragraphs inside entry-content
python3 -c "
import re
html = open('/tmp/article.html').read()
start = html.find('class=\"entry-content')
chunk = html[start:start+20000]
ps = re.findall(r'<p[^>]*>(.{20,}?)</p>', chunk, re.DOTALL)
print(f'{len(ps)} paragraphs, {sum(len(re.sub(\"<[^>]+>\", \"\", p)) for p in ps)} chars')
"
```

Common WP body selectors:
- `div.entry-content p` — standard WP theme
- `div.post-content p` — some themes
- `div.article-body p` — custom themes
- `article p` — catch-all fallback

---

## Fix B: Fix Broken Selectors

When pagination works but selectors are wrong, inspect the actual HTML and update:

```yaml
selectors:
  thumbnail:
    container: article                          # the repeating card element
    title: h2::text                             # where the title text lives
    url: a.list-article__url::attr(href)        # the article link
  article:
    body: "div.article-body p"                  # paragraphs in article body
    date: meta[property='article:published_time']::attr(content)
```

Use fallback chains for resilience:
```yaml
body: ["div.article-body p", ".post-content p", "article p"]
date: ["time[datetime]::attr(datetime)", "meta[property='article:published_time']::attr(content)"]
```

---

## Fix C: Wrong Pagination URL Pattern

Some sites use `/page/2/` (path) instead of `?page=2` (query string), or vice versa.
Check the HTML for pagination links:

```bash
grep -Eo 'href="[^"]*(/page/[0-9]+|\?page=[0-9]+|&page=[0-9]+)' /tmp/listing.html | head -5
```

Update `url_template` accordingly. Also check `start_page` — some sites start from
page 0, not page 1.

---

## Batch Workflow

When fixing an entire country directory:

### 1. Quick triage (5 min per country)

```bash
# For each config, test if pagination returns different content
for yaml in src/text/configs/eca/central_europe/{country}/*.yaml; do
  name=$(basename "$yaml" .yaml)
  start_url=$(grep 'start_url:' "$yaml" | head -1 | sed 's/.*start_url: *//')
  url_template=$(grep 'url_template:' "$yaml" | head -1 | sed 's/.*url_template: *//')
  page2=$(echo "$url_template" | sed 's/{num}/2/')
  s1=$(curl -sL -o /dev/null -w "%{http_code}:%{size_download}" --max-time 10 -A "Mozilla/5.0" "$start_url")
  s2=$(curl -sL -o /dev/null -w "%{http_code}:%{size_download}" --max-time 10 -A "Mozilla/5.0" "$page2")
  echo "$name  page1=$s1  page2=$s2"
done
```

### 2. Check WordPress API on all sources

```bash
for yaml in src/text/configs/eca/central_europe/{country}/*.yaml; do
  base=$(grep 'base_url:' "$yaml" | head -1 | sed 's/.*base_url: *//')
  code=$(curl -sI --max-time 8 -A "Mozilla/5.0" "$base/wp-json/" 2>/dev/null | head -1 | tr -d '\r\n')
  echo "$(basename $yaml .yaml): $base → $code"
done
```

### 3. Check RSS on broken sources

```bash
# Only for sources where pagination failed
for url in "https://broken-site.com"; do
  for path in /rss /feed /rss.xml; do
    code=$(curl -sL -o /dev/null -w "%{http_code}" --max-time 6 -A "Mozilla/5.0" "${url}${path}")
    [ "$code" = "200" ] && echo "$url: RSS at $path"
  done
done
```

### 4. Apply fixes

- **WP API found** → Fix A (switch to api strategy)
- **Pagination works, selectors wrong** → Fix B (update selectors)
- **Pagination broken, RSS exists** → rename to `_1_rss_{name}.yaml`
- **Pagination broken, no RSS, no API** → rename to `_0_{name}.yaml`

### 5. Validate fixes

```bash
# Rebuild with small limits to verify end-to-end
poetry run po text collect --source {newspaper} --rebuild --max-pages 2 --max-articles 5
```

After each run, spot-check the output CSV:

```python
import csv, random
with open("data/text/{region}/{subregion}/{country}/{newspaper}/news.csv") as f:
    rows = list(csv.DictReader(f))
    row = random.choice(rows)
    print(f"title:  {row['title'][:80]}")
    print(f"date:   {row['date']}")
    print(f"url:    {row['url']}")
    print(f"body:   ({len(row['body'])} chars) {row['body'][:150]}...")
```

Check for:
- **Title**: actual headline text (not empty, not nav text, no leftover HTML tags)
- **Date**: ISO format YYYY-MM-DD (not null, not 1970-01-01)
- **URL**: full article URL pointing to the newspaper domain (not relative, not garbage)
- **Body**: 200+ chars of real article text (not a truncated WP excerpt like `[…]`,
  not nav/footer junk). WP API excerpts are typically 100-150 chars — if you see
  that, you have the prefetched-article problem (see Fix A)

---

## Worked Example: Estonia

### Triage results

| Source | Pagination | WP API | RSS | Action |
|--------|-----------|--------|-----|--------|
| edasi | Works (WP /page/N/) | 200 ✅ | — | Fix A: switch to api |
| objektiiv | Works (WP /page/N/) | 200 ✅ | — | Fix A: switch to api |
| propastop | Works (WP /page/N/) | 200 ✅ | — | Fix A: switch to api |
| postimees | Works (?page=N) | 404 | — | Fix B: fix selectors |
| postimees_english | Works (?page=N) | 404 | — | Fix B: fix selectors |
| tartu_postimees | Works (?page=N) | 404 | — | Fix B: fix selectors |
| aripaev | Broken (same page) | 308 | /rss ✅ | → `_1_rss_aripaev.yaml` |
| bns | Broken (same page) | 302 | /rss ✅ | → `_1_rss_bns.yaml` |
| err | Broken (same page) | 302 | /rss ✅ | → `_1_rss_err.yaml` |
| err_english | Broken (same page) | 302 | /rss ✅ | → `_1_rss_err_english.yaml` |
| lsm_estonia | Broken (same page) | 302 | /rss ✅ | → `_1_rss_lsm_estonia.yaml` |
| liberaalne_kodanik | 404 on page 2 | 404 | None | → `_0_liberaalne_kodanik.yaml` |

### What was fixed

**WordPress sites (edasi, objektiiv, propastop):** Switched from `pagination` to
`api` strategy using WP REST API for **discovery** (URL, title, date) but HTML
**body scraping** via `div.entry-content p`. `json_paths` intentionally omits
`body` so the pipeline visits each article page for full text instead of using the
truncated WP excerpt (~120 chars → 3000-9000 chars per article).
Combined: ~30,000 historical articles accessible.

**Postimees family (3 sites):** Fixed selector issues:
- `title`: `a[href]::text` → `h2::text` (title text is inside nested `<h2>`, not direct `<a>` text)
- `url`: `a[href]::attr(href)` → `a.list-article__url::attr(href)` (specific class avoids nav links)
- `body`: `div.article-body` → `div.article-body p` (need `p` tags for paragraph extraction)
- Note: Postimees uses Piano paywall — free articles return full body, paywalled articles return lead only.

### What was deferred

- **5 ERR-family sites** have RSS at `/rss` (~50 recent articles per feed). Their HTML
  listing uses AJAX `loadMore` which the `pagination` strategy can't handle. Marked
  `_1_rss_*` for future RSS strategy implementation.
- **liberaalne.ee** returns 404 on page 2, has no WP API and no RSS. Marked `_0_`.

---

## Decision Tree Summary

```
Does ?page=2 / /page/2/ return different articles?
  YES → Are the current selectors correct?
    YES → Config is working, no fix needed
    NO  → Fix B (update selectors)
  NO  → Does /wp-json/wp/v2/posts return JSON?
    YES → Fix A (switch to api strategy)
    NO  → Does /rss or /feed return XML?
      YES → Rename to _1_rss_{name}.yaml (defer)
      NO  → Is it a JS SPA or Cloudflare-protected?
        YES → Rename to _0_{name}.yaml (unfixable with current strategies)
        NO  → Check for other API endpoints or archive URLs
```
