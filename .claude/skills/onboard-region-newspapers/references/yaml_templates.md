# YAML Config Templates

Three patterns cover the vast majority of newspapers in this pipeline. Pick by listing strategy. Replace `<...>` placeholders.

The third template — **regional aggregator fallback** — is for cross-country aggregator sites that publish a per-country localized stream (e.g. `<aggregator>/<country-slug>/`). It is only valid when a region-appropriate aggregator exists and produces localized content for the country being onboarded. AllAfrica is the only validated case so far, and it is **SSA-only**. Do not reuse it (or any other aggregator) outside its actual geographic coverage.

## 1. Tier 0: WordPress REST API (the most common — try this first)

Use when `<base>/wp-json/wp/v2/posts?per_page=1` returns JSON `[{...}]`. Encode the category filter inline in the URL template.

```yaml
name: <Display Name>
country: <country_slug>
language: <en|fr|portuguese|arabic|es|swahili|amharic|afrikaans>
base_url: <https://example.com>

# Categories: <Name1>(<id1>), <Name2>(<id2>)
listing:
  type: api
  pagination_type: page
  page_start: 1
  page_step: 1
  url_template: "<base>/wp-json/wp/v2/posts?per_page=100&page={page}&categories=<id1>,<id2>&_fields=id,date,link,title,excerpt,content"
  json_paths:
    url: "link"
    title: "title.rendered"
    date: "date"
    body: "content.rendered"

client: http
concurrency: 5
rate_limit: 0.3
retries: 3
retry_seconds: 2.0

selectors:
  thumbnail:
    container: "filler"
    title: "filler"
    url: "filler"
  article:
    body: "<article-body-selector>"   # real CSS selector — see note below
    date: "meta[property='article:published_time']::attr(content)"

cleaning:
  date: handle_mixed_dates
  body: clean_wp_html_body

max_pages: null
max_articles: null
```

**Variants:**
- If the site returns HTML when `_fields=...title...` is included (Premium Times Nigeria pattern), drop `_fields` entirely:
  ```yaml
  url_template: "<base>/wp-json/wp/v2/posts?per_page=100&page={page}&categories=<id1>,<id2>"
  ```
- If `/wp-json/` returns HTML but `?rest_route=/wp/v2/posts` returns JSON (Lesotho Times pattern), use the legacy form:
  ```yaml
  url_template: "<base>/?rest_route=/wp/v2/posts&per_page=100&page={page}&categories=<id1>,<id2>"
  ```

**Selectors block — read this carefully (NOT optional for `type: api`).**

The `thumbnail` block IS unused for `type: api` (the API returns titles/URLs directly) — `"filler"` is fine there.

The `article` block IS used as a **fallback** whenever the API listing returns an empty `content.rendered` for a particular post (common with WP sites that have post-format variants, Elementor / TagDiv builders, or content-protection plugins). When that happens, the scraper falls back to per-URL HTML scraping using these selectors. If the selectors are placeholders (`"filler"`), the fallback fails silently — pending URLs accumulate forever and `failed_urls_seen.csv` doesn't persist (project_text_failure_ledger_bug).

So:
- `article.body`: a real CSS selector that matches the article body on a normal HTML article page. Common WP defaults to try in order: `.entry-content p`, `article p`, `.td-post-content p`, `div.elementor-widget-theme-post-content p`. Verify with BeautifulSoup before committing — see SKILL.md Step 3.
- `article.date`: `meta[property='article:published_time']::attr(content)` works on >90% of WordPress sites (Yoast plugin standard). Use this default unless you've verified the site doesn't ship Yoast.

When API content is non-empty (the happy path), the article goes through `prefetched_articles` and these selectors are never invoked — they're pure safety net.

## 2. Tier 1: HTML pagination (numbered pages)

Use when the site has `?page=N`, `/page/N/`, or `/category/news/N/` URLs that increment.

```yaml
name: <Display Name>
country: <country_slug>
language: <en|fr|...>
base_url: <https://example.com>

listing:
  type: pagination
  url_template: "<base>/category/news/?page={num}"
  start_page: 1
  step: 1

client: http
concurrency: 3
rate_limit: 1.0
retries: 3
retry_seconds: 2.0

selectors:
  thumbnail:
    container: "<per-article-card-selector>"   # MUST match per article — verify with BeautifulSoup before writing
    title: "<within-card> a::text"
    url: "<within-card> a::attr(href)"
  article:
    body: "<article-page-body p selector>"
    date: "meta[property='article:published_time']::attr(content)"

cleaning:
  date: handle_mixed_dates
  url: clean_url

max_pages: null
max_articles: null
```

**Critical**: verify `container` matches PER ARTICLE — not the whole listing wrapper. A common trap: a class like `div.col-md-6.HNews` may match exactly once (the entire grid wrapper) when you expected ~25 (per article). Test with:

```python
import httpx; from bs4 import BeautifulSoup
r = httpx.get(listing_url, headers={'User-Agent':'Mozilla/5.0'}, timeout=15, follow_redirects=True)
soup = BeautifulSoup(r.text, 'html.parser')
print('container matches:', len(soup.select(container)))  # expect 10-30
```

## 2b. RSS / Atom feed (listing-only)

Use when the site publishes a valid RSS 2.0 / Atom feed but has no WordPress API and no clean HTML pagination — or when pagination/API is blocked (WAF/SPA) yet `/feed/` still serves XML. The feed supplies the article **URL + title + date**; the body is fetched from the article page via the `article` selectors (same as pagination). Best for incremental "latest-N" refresh; most feeds are front-page-only.

**Confirm it's a real feed first** (a known Cloudflare trick serves an HTML 403 wrapper at `/feed/`):
```bash
curl -sIL --max-time 20 -A "Mozilla/5.0" <feed_url>   # content-type must be application/rss+xml / atom+xml / xml — NOT text/html
curl -sL  --max-time 20 -A "Mozilla/5.0" <feed_url> | head -c 2000   # must open with <rss / <feed / <rdf:RDF and repeat <item>/<entry>
```

**RSS 2.0** (the overwhelmingly dominant format — WordPress `/feed/`, Arc Publishing `/arc/outboundfeeds/rss/`, most CMSs):
```yaml
name: <Display Name>
country: <country_slug>
language: <en|fr|es|arabic|portuguese|...>
base_url: <https://example.com>

listing:
  type: rss
  feed_urls:
    - "<https://example.com/feed/>"      # one or more; section feeds are fine
  # page_param: paged                      # ONLY for WordPress feeds that honor ?paged=N (walks older items). Omit for front-page-only.
  # url_regex: "/20\\d\\d/"               # optional: keep only item <link>s matching this

client: http
concurrency: 3
rate_limit: 0.5
retries: 3
retry_seconds: 2.0

selectors:
  thumbnail:
    container: "item"
    url: "link::text"
    title: "title::text"
    date: "pubDate::text"
  article:
    body: "<article-page-body p selector>"   # real selector, verify with BeautifulSoup — same as pagination
    date: "meta[property='article:published_time']::attr(content)"

cleaning:
  date: handle_mixed_dates
  url: clean_url

max_pages: null
max_articles: null
```

**Atom variant** — change the thumbnail selectors only:
```yaml
selectors:
  thumbnail:
    container: "entry"
    url: "link::attr(href)"
    title: "title::text"
    date: "published::text"      # or "updated::text"
```

**Critical mechanics (feeds are parsed with the lxml XML parser, which behaves differently from `html.parser`):**
- **Selectors are CASE-SENSITIVE.** Use exact tag case: `pubDate::text`, not `pubdate::text` — the latter silently matches nothing. Same for `link`, `title`, `published`.
- `<link>` text survives (it's a void element only in `html.parser`), so `link::text` is correct for RSS. Atom's URL is the `href` attribute → `link::attr(href)`.
- `content:encoded` / `description` (full or partial body carried in the feed) are **not usable** here — the namespaced colon breaks CSS `select`, and this strategy fetches the body from the article page. (Pulling body straight from `content:encoded` is a separate not-yet-shipped mode.)
- **Front-page-only by default.** RSS feeds serve only the latest ~10–100 items. Set `page_param: paged` ONLY when you've confirmed the site is WordPress and `<feed>?paged=2` returns genuinely older items (Arc Publishing and most custom CMSs ignore it).

**Verify the feed extraction before committing** (mirrors the pipeline's own extractor):
```python
import httpx; from bs4 import BeautifulSoup
xml = httpx.get(feed_url, headers={'User-Agent':'Mozilla/5.0'}, timeout=20, follow_redirects=True).text
soup = BeautifulSoup(xml, 'xml')
items = soup.select('item')  # or 'entry' for Atom
print('items:', len(items))
it = items[0]
print('url  :', it.select_one('link').get_text(strip=True))   # Atom: it.select_one('link').get('href')
print('title:', it.select_one('title').get_text(strip=True))
print('date :', it.select_one('pubDate').get_text(strip=True)) # Atom: 'published'
```

## 3. Regional aggregator fallback (per country)

Use as a 3rd source when native sources are sparse, OR when no native WP API exists at all. **Only valid when a region-appropriate aggregator exists.** Do not invent one and do not reuse an aggregator outside its actual geographic coverage.

### Validated aggregators

| Region | Aggregator | Per-country URL pattern | File-name convention |
|---|---|---|---|
| SSA (Sub-Saharan Africa) | AllAfrica | `https://allafrica.com/<aggregator_path>/?page={num}` | `allafrica_<country>.yaml` |

If your region is not in this table, treat the regional-aggregator step as "not yet validated" — see SKILL.md for guidance. Do **not** point the AllAfrica template at non-African countries.

### Generic shape

```yaml
name: <Aggregator Display Name> <Country Title Case>
country: <country_slug>
language: <en|fr|es|portuguese|...>
base_url: <https://aggregator-domain.com>

# <Region> aggregator covering <Country>
listing:
  type: pagination
  url_template: "<https://aggregator-domain.com>/<aggregator_path_for_country>/?page={num}"
  start_page: 1
  step: 1

client: http
concurrency: 3
rate_limit: 1.0
retries: 3
retry_seconds: 2.0

selectors:
  thumbnail:
    container: "<per-article-card-selector>"
    title: "<within-card> a::text"
    url: "<within-card> a::attr(href)"
  article:
    body: "<article-page-body selector>"
    date: "meta[property='article:published_time']::attr(content)"

cleaning:
  date: handle_mixed_dates
  url: clean_url

max_pages: null
max_articles: null
```

### Worked example: AllAfrica (SSA only)

```yaml
name: AllAfrica <Country Title Case>
country: <country_slug>
language: en
base_url: https://allafrica.com

# Pan-African EN aggregator covering <Country>
listing:
  type: pagination
  url_template: "https://allafrica.com/<allafrica_path>/?page={num}"
  start_page: 1
  step: 1

client: http
concurrency: 3
rate_limit: 1.0
retries: 3
retry_seconds: 2.0

selectors:
  thumbnail:
    container: "ul.stories li"
    title: "a::text"
    url: "a::attr(href)"
  article:
    body: ".story-body p"
    date: "meta[property='article:published_time']::attr(content)"

cleaning:
  date: handle_mixed_dates
  url: clean_url

max_pages: null
max_articles: null
```

#### AllAfrica path map (single-word country slugs)

| country slug | allafrica path |
|---|---|
| nigeria | nigeria |
| ghana | ghana |
| kenya | kenya |
| south_africa | southafrica |
| burkina_faso | burkinafaso |
| cabo_verde | capeverde |
| cote_divoire | cotedivoire |
| guinea_bissau | guineabissau |
| sierra_leone | sierraleone |
| eswatini (formerly Swaziland) | swaziland |
| ... | (otherwise, lowercase concat with no separators) |

**Caveat:** regional aggregators (including AllAfrica) tend to rate-limit aggressively. A probe right after a heavy run may return 0 thumbnails. Write the config anyway — it activates later when the aggregator accepts requests again.

### Onboarding a new aggregator

When you encounter a candidate regional aggregator for a not-yet-validated region (e.g. a LAC, MENAAP, South Asia, EAP, or Pacific aggregator), do **not** add it directly. Instead:

1. Run `assess-newspaper-source` against one of its per-country pages to confirm the listing structure and probe behavior.
2. Add the aggregator to the **Validated aggregators** table above with its URL pattern and file-name convention before reusing it across countries.
3. Only then write per-country YAMLs using it as a fallback.

## Naming the YAML file

The source key (used as `--source <key>`) is the YAML basename without `.yaml`. Conventions:
- Snake-case, lowercase
- Drop "the" / "online" prefixes-suffixes when they don't disambiguate
- Use `<paper>_<country>` only when the paper name conflicts with another country's paper
- For category-split single-paper configs: `<paper>_<section>` (e.g. `times_eswatini_news`, `times_eswatini_business`)

Examples:
- `mail_and_guardian.yaml` (M&G is unique enough)
- `the_citizen.yaml` (Citizen SA — file path makes country obvious)
- `lesotho_times.yaml`
- `premium_times.yaml`
- `news_diggers.yaml`
- For a regional-aggregator fallback, prefix with the aggregator's name: `<aggregator>_<country>.yaml` (e.g. `allafrica_<country>.yaml` for SSA). Keep the prefix consistent across all countries that use the same aggregator so they're easy to find.
