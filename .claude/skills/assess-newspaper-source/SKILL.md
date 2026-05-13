---
name: assess-newspaper-source
description: "This skill should be used when the user asks to assess a newspaper URL, check whether a news site has an API, check whether a news site is scrapeable HTML, add a new text source, or asks about scraping feasibility for a publication. Also trigger when the user references newspapers_list.md, wants to expand country coverage in src/text/configs/, or asks which scraper strategy fits a site."
---

# Assess Newspaper Source

Inspect a newspaper website, identify which existing listing strategy fits it,
estimate how much code (if any) is needed, and produce a ready-to-use YAML result.
Decide quickly whether the site is usable through scrapeable HTML, a verified
JSON API, or unusable with the current pipeline. The goal is to minimise code
changes, ideally to zero.

## Model Guidance

Prefer running this skill on a small, fast model. The workflow is mostly
deterministic probing and classification, so it should usually fit models such as
Haiku 4.6, gpt-5.2-codex, or codex-mini. Escalate to a larger model only when the
signals conflict, the site is borderline Tier 2/3, or selector extraction is
ambiguous.

## Input

The user provides a newspaper URL and optionally a country. Parse these from the
user's message. If the country is missing, infer it from the domain or ask.

## Step 0: Read the HOW_TOs

Before probing, read `src/text/HOW_TO_ADD_NEW_SCRAPER.md` and
`src/text/docs/HOW_TO_FIX_NEWSPAPER.md` to understand what strategies,
client types, cleaning functions, and disabled-file naming conventions are
already available. These are the authoritative references for what the pipeline
supports. Use them to:
- Know which listing types exist and what their YAML fields are
- Know which cleaning functions are built-in (avoid writing new ones)
- Confirm the decision tree for identifying listing type
- Confirm how unusable sources must be recorded with `_0_{name}.yaml`

## Step 1: Fetch & Classify (HTML-first)

The goal of this step is to fetch actual HTML and determine if the site is
scrapeable. Start with HTML — most sites end up being HTML pagination, not API.

### 1a. Fetch homepage HTML

```bash
curl -sL --max-time 15 \
  -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36" \
  -o /tmp/newspaper_probe.html "<BASE_URL>" 2>/dev/null
wc -c /tmp/newspaper_probe.html   # sanity check — should be >10KB
```

### 1b. Check for protection

```bash
head -50 /tmp/newspaper_probe.html | grep -i "cloudflare\|challenge\|captcha\|recaptcha\|verify.*human\|bot.*detect"
```

If challenge/captcha page → note as blocker (may still have API). Continue.

### 1c. Check rendering model

```bash
# SSR signals (good — selectors will work)
grep -c '<article\|<div class.*post\|<div class.*story\|<div class.*article\|<div class.*news' /tmp/newspaper_probe.html

# SPA signals (bad — HTML will be empty shell)
grep -c '<div id="app">\|<div id="root">\|<div id="__next">\|__NEXT_DATA__' /tmp/newspaper_probe.html
```

- Many article/post elements → SSR → proceed with HTML selectors
- Empty app/root div → SPA → Tier 3 unless API found in Step 2

### 1d. Find article links

```bash
# Look for article-like URLs in the homepage HTML
grep -Eo 'href="[^"]*"' /tmp/newspaper_probe.html | grep -E '/article/|/news/|/press/|/story/|/post/' | head -15
```

If no article links on homepage, **check section/category pages**:
```bash
# Extract section URLs first
grep -Eo 'href="[^"]*category[^"]*"|href="[^"]*section[^"]*"|href="[^"]*service[^"]*"' /tmp/newspaper_probe.html | head -10

# Then fetch a section page and look for articles there
curl -sL --max-time 15 -A "Mozilla/5.0..." "<SECTION_URL>" -o /tmp/section_page.html
grep -Eo 'href="[^"]*"' /tmp/section_page.html | grep -E '/article/|/news/|/press/|/story/' | head -15
```

**Critical**: Many news sites have no article links on the homepage but have them
on category/section pages. Always check at least one section page before
classifying as unusable.

## Step 2: Identify Listing Strategy

Apply this decision tree to the HTML from Step 1.

### 2a. Pagination signals

```bash
grep -Eo 'href="[^"]*(/page/[0-9]+|[?&]page=[0-9]+|/[0-9]+/)[^"]*"' /tmp/newspaper_probe.html | head -10
# Also check section pages
grep -Eo 'class="[^"]*pag[^"]*"' /tmp/newspaper_probe.html | head -5
```

If `/page/2`, `?page=2`, `/category/news/2/` etc. appear → `pagination`.

### 2b. Date archive signals

```bash
grep -Eo 'href="[^"]*/(20[0-9]{2})/[0-9]{2}[^"]*"' /tmp/newspaper_probe.html | head -10
grep -Eo 'dateFrom=[^&"]*' /tmp/newspaper_probe.html | head -5
```

- `/YYYY/MM/` or `/YYYY/MM/DD/` → `archive` or `paginated_archive`
- `dateFrom=...&dateTo=...` → `paginated_archive` with `date_format: "range"`

When date-archive signals found, probe one date page for sub-pagination:
```bash
curl -sL --max-time 15 "<ARCHIVE_URL>" -o /tmp/archive_page.html 2>/dev/null
grep -Eo 'href="[^"]*(/page/[0-9]+|[?&]page=[0-9]+)' /tmp/archive_page.html | head -5
```

### 2c. Follow-link signals

```bash
grep -Eo 'class="[^"]*next[^"]*"' /tmp/newspaper_probe.html | head -5
grep -i '"next page"\|"older posts"\|»' /tmp/newspaper_probe.html | head -5
```

If a "next" link exists but URL pattern is relative/opaque → `follow_link`.

### 2d. JSON API discovery

Only check after HTML analysis. A working API is a bonus, not the default path.

```bash
# Check for WordPress REST API — MUST verify the posts endpoint, not just /wp-json/
curl -sL --max-time 10 \
  -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36" \
  "<BASE_URL>/wp-json/wp/v2/posts?per_page=1&_fields=id,date,link,title" 2>/dev/null | head -5
```

**IMPORTANT — Verifying a JSON API:**

A `/wp-json/` returning 200 or 301 does NOT mean the API works. You MUST check
the actual posts endpoint. Common false positives:

| Signal | Reality |
|--------|---------|
| `/wp-json/` returns 301/308 redirect | Often just URL rewriting, posts endpoint may 404 |
| `/wp-json/` returns 200 with JSON | May be API index only, posts endpoint may be disabled |
| Posts endpoint returns HTML | Bot protection serving challenge page instead of JSON |
| Posts endpoint returns JSON to curl | May return HTML/captcha to Python httpx (different TLS fingerprint) |

**A JSON API is only confirmed when the posts endpoint returns a JSON array
starting with `[{` containing `id`, `date`, `link`, `title` keys.**

If no WordPress API, check for custom APIs:
```bash
grep -i '__NEXT_DATA__\|/api/\|/graphql\|algolia' /tmp/newspaper_probe.html | head -5
```

### Decision summary

| Signal found | Listing type |
|-------------|-------------|
| `?page=N` or `/page/N/` in links | `pagination` |
| `/YYYY/MM/` paths, no sub-pagination | `archive` |
| `/YYYY/MM/` paths + sub-pagination | `paginated_archive` (daily/monthly) |
| `?dateFrom=&dateTo=` in links | `paginated_archive` (range) |
| Only a "next" link, no URL pattern | `follow_link` |
| Verified JSON posts endpoint | `api` |
| Empty JS shell, no API | Tier 3 |

## Step 3: Verify Selectors

This is where most configs break. Wrong selectors → 0 thumbnails even with
correct URLs.

### 3a. Find the article container

Use `poetry run python3` with BeautifulSoup to verify selectors match real HTML:

```bash
poetry run python3 -c "
import httpx
from bs4 import BeautifulSoup
r = httpx.get('<LISTING_URL>', headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}, timeout=15, follow_redirects=True)
soup = BeautifulSoup(r.text, 'html.parser')

# Find article links and inspect parent containers
articles = [a for a in soup.find_all('a', href=True) if '/article/' in a.get('href', '')]
print(f'Found {len(articles)} article links')

# Check parent hierarchy (what is the repeating container?)
for a in articles[:3]:
    p = a.parent
    gp = p.parent
    print(f'  Container: <{p.name} class=\"{\" \".join(p.get(\"class\", []))}\"> -> <{gp.name} class=\"{\" \".join(gp.get(\"class\", []))}\">')
    print(f'  Title: {a.get_text().strip()[:60]}')
    print(f'  URL: {a[\"href\"]}')
"
```

Replace `/article/` in the grep with whatever URL pattern the site uses
(`/news/`, `/story/`, `/press/`, etc.).

### 3b. Find article page selectors

```bash
poetry run python3 -c "
import httpx
from bs4 import BeautifulSoup
r = httpx.get('<ARTICLE_URL>', headers={'User-Agent': 'Mozilla/5.0...'}, timeout=15, follow_redirects=True)
soup = BeautifulSoup(r.text, 'html.parser')

# Date — prefer meta tag
meta = soup.find('meta', attrs={'property': 'article:published_time'})
print('Meta date:', meta['content'] if meta else 'NOT FOUND')

# Body — find div with most <p> children
for div in soup.find_all('div'):
    ps = div.find_all('p', recursive=False)
    if len(ps) >= 3:
        cls = ' '.join(div.get('class', []))
        print(f'Body: div.{cls} ({len(ps)} paragraphs)')
        print(f'  First: {ps[0].get_text().strip()[:80]}')
        break
"
```

**Why BeautifulSoup verification matters**: The pipeline uses BeautifulSoup
internally. If a selector matches in BeautifulSoup but not in grep (or vice
versa), the pipeline will fail. Always verify selectors with the actual parser.

### 3c. Verify the pipeline client can reach the page

```bash
poetry run python3 -c "
import httpx
r = httpx.get('<LISTING_URL>', headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36'}, timeout=15, follow_redirects=True)
print('Status:', r.status_code)
print('Content-Type:', r.headers.get('content-type', ''))
print('Size:', len(r.text))
# Check for bot protection in response
if 'captcha' in r.text.lower() or 'challenge' in r.text.lower() or 'verify' in r.text.lower():
    print('WARNING: Bot protection detected in response body')
"
```

This catches cases where curl succeeds but the Python pipeline (httpx) gets
blocked by bot protection (different TLS fingerprint).

## Step 4: Assess Code Extension Needed

Be explicit about this. Map findings to one of:

| Situation | Code needed | Where |
|-----------|------------|-------|
| Standard listing type + clean HTML | None — YAML only | — |
| Non-standard date format | Custom cleaning function (~10-20 lines) | `src/text/scrapers/pipelines/cleaning/{country}.py` |
| Non-WP JSON API with unusual structure | Extend `json_paths` or `ApiStrategy` | `src/text/scrapers/strategies/api.py` |
| New archive URL pattern (not daily/monthly/range) | Extend `PaginatedArchiveStrategy` (~30-40 lines) | `src/text/scrapers/strategies/archive.py` |
| JS-rendered content | `client: "browser"` in YAML (no new code) | YAML only |
| No viable API, unusable HTML, or heavy anti-bot | No code now — create `_0_{name}.yaml` with top comments explaining why it failed | `src/text/configs/{region}/{subregion}/{country}/_0_{name}.yaml` |

If a cleaning function is needed, first check whether one already exists:
```bash
ls src/text/scrapers/pipelines/cleaning/
grep "def " src/text/scrapers/pipelines/cleaning/common.py
```

## Step 5: Generate the YAML Result

Produce a ready-to-use YAML file based on the identified result.

If the site is usable, generate the normal `{name}.yaml` skeleton and fill in
actual selectors from Step 3 where possible. Flag TODOs only when necessary.

If the site is unusable with current strategies, still generate a YAML stub named
`_0_{name}.yaml`. Add a few comment lines at the top explaining why it did not
work before the YAML fields begin.

Use short comments such as:

```yaml
# Unusable with current pipeline strategies.
# Reason: Cloudflare challenge page blocks article discovery.
# Reason: No public API found and homepage HTML is not scrapeable.
```

Use the examples in `src/text/HOW_TO_ADD_NEW_SCRAPER.md` as templates —
do not invent new fields.

## Output Format

```
## Assessment: <Newspaper Name> (<Country>)

**URL**: <base_url>
**Listing type**: <api|pagination|archive|paginated_archive|follow_link>
**Code extension needed**: <None | ~N lines in file.py (reason)>
**Tier**: <0|1|2|3>
**Blockers**: <none, or description>

### Probe Results
- JSON API: <verified (posts endpoint returns JSON) | not found | blocked>
- Framework: <WordPress | Custom CMS | Next.js | Bitwize | etc.>
- Rendering: <SSR | SPA | Mixed>
- Protection: <none | Cloudflare (light) | Cloudflare JS challenge | reCAPTCHA>
- Listing pattern: <description of what was found in HTML>
- Pipeline compatibility: <httpx gets same content as curl | httpx blocked>

### Integration Path
<One paragraph: which strategy, why, any caveats>

### YAML Result
<Normal YAML block for usable sources, or `_0_{name}.yaml` stub with top comments for unusable sources>
```

## Tier Definitions

| Tier | Meaning | Example |
|------|---------|---------|
| 0 | Verified JSON API — posts endpoint returns JSON array, works with httpx | La Nation (Djibouti) |
| 1 | Clean HTML with standard pagination/archive — selectors verified via BeautifulSoup | Times of Oman, Gulf Times |
| 2 | Scrapeable but needs custom work (selectors, cleaning, browser client) | Al Watan Oman (AJAX), Oman Daily (Sucuri) |
| 3 | Unusable — SPA with no API, heavy bot protection, dead domain | Al Bayan (Next.js CSR), Al-Ittihad (domain dead) |

## Batch Mode

When the user provides multiple URLs, probe all homepages first (cheapest), then
classify by HTML signals:

```bash
for url in <URL1> <URL2> <URL3>; do
  size=$(curl -sL --max-time 10 -A "Mozilla/5.0..." "$url" -o /tmp/probe_batch.html 2>/dev/null && wc -c < /tmp/probe_batch.html)
  articles=$(grep -cE '/article/|/news/|/story/|/press/' /tmp/probe_batch.html 2>/dev/null)
  pag=$(grep -cE '/page/[0-9]+|[?&]page=[0-9]' /tmp/probe_batch.html 2>/dev/null)
  spa=$(grep -c '<div id="app">\|<div id="root">\|__NEXT_DATA__' /tmp/probe_batch.html 2>/dev/null)
  echo "$url → ${size}B, ${articles} article links, ${pag} pagination links, ${spa} SPA signals"
done
```

Focus full probing on sites with article links and pagination signals first.

## Common Pitfalls (from production experience)

1. **`/wp-json/` redirect ≠ working WordPress API**: A 301/308 on `/wp-json/`
   often means URL rewriting, not a functional API. Always verify
   `/wp-json/wp/v2/posts?per_page=1`. Out of 6 sites initially flagged as
   "WordPress", only 1 actually had a working posts endpoint.

2. **curl vs httpx give different responses**: Some sites serve JSON to curl but
   reCAPTCHA/challenge pages to Python httpx (different TLS fingerprints). Always
   verify with `poetry run python3` using httpx.

3. **Homepage ≠ listing page**: Many sites show a carousel/featured layout on the
   homepage with no pagination. The actual listing with pagination is on
   category/section pages (e.g., `/category/politics/page/2`).

4. **Same CMS, different page structures**: Page 1 and the default page of a
   category may have completely different HTML structures (different container
   classes, different layouts). Always test the paginated URL, not just the default.

5. **Container selectors must match the pipeline's parser**: The pipeline uses
   BeautifulSoup with `html.parser`. Verify selectors in Python, not just grep.
   CSS selector lists (comma-separated) may not work as expected in all contexts.

6. **Tailwind CSS sites have no semantic classes**: Sites using Tailwind
   (e.g., `class="flex items-center gap-2"`) have no stable semantic selectors.
   Use `<a>` tag structure and parent hierarchy instead of class names.

## Key Principle

The pipeline is designed so new sources need only a YAML file. Probing exists to
confirm a site fits an existing strategy — not to design a new one. If it doesn't
fit, say so honestly rather than forcing a broken config. When the site is not
usable with current strategies, record it explicitly as `_0_{name}.yaml` with
top-of-file comments that explain the failure. When extending the framework is
required, describe the minimum change needed and point to the existing pattern in
`archive.py` as a reference.

**HTML pagination is the most common outcome.** Most news sites are server-rendered
with paginated category pages. Approach every assessment expecting pagination —
API is a lucky bonus, not the default.
