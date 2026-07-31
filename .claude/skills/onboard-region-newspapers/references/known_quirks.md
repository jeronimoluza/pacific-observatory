# Known Site Quirks (Pre-empt Rather Than Rediscover)

Patterns and traps from prior onboarding runs. Check this list when a probe returns 0 thumbnails or 0 successful articles before re-debugging from scratch.

## WordPress REST API quirks

### Premium Times Nigeria (premiumtimesng.com) — `_fields` + `categories=` returns HTML
**Symptom**: Manual curl with `?categories=3,60` returns JSON, but the same URL with `&_fields=id,date,link,title` returns the website HTML (CDN serves a 404 page). Pipeline probe → 0 thumbnails.

**Fix**: drop `_fields` from the URL template entirely. Pipeline parses the full JSON without it.

```yaml
# WORKS:
url_template: "https://www.premiumtimesng.com/wp-json/wp/v2/posts?per_page=100&page={page}&categories=3,60"

# BROKEN:
url_template: "https://www.premiumtimesng.com/wp-json/wp/v2/posts?per_page=100&page={page}&categories=3,60&_fields=id,date,link,title,excerpt,content"
```

**Generalize**: if any WP site's `?categories=X&_fields=...title...` returns HTML while plain `?categories=X` returns JSON, drop `_fields` from the URL.

### Lesotho Times (lestimes.com) — pretty REST permalinks disabled
**Symptom**: `/wp-json/wp/v2/posts` returns HTML (redirect/404). Standard probe says "no API".

**Fix**: try the legacy form `?rest_route=/wp/v2/posts` instead.

```yaml
url_template: "https://lestimes.com/?rest_route=/wp/v2/posts&per_page=100&page={page}&categories=3,15,6"
```

**Generalize**: when initial WP API probe fails on a site that "looks like WordPress" (has `<link rel="https://api.w.org/" href=".../wp-json/">` in the HTML response), try `?rest_route=/wp/v2/posts` once before classifying as Tier 3.

### Per-page cap is 100 (almost universally)
WordPress defaults to capping `per_page` at 100. Use `per_page=100` for max throughput; pipeline pagination handles the rest.

## HTML pagination quirks

### Eswatini Times (times.co.sz) — single wrapping container, NOT per-article
**Symptom**: Selector `div.col-md-6.HNews` matches once on the page (the entire news-list wrapper); pipeline finds 0 or 1 thumbnails.

**Truth**: per-article cards are mixed:
- 22 articles in `div.col-md-4`
- 3 articles in `div.col-md-3`
- 1 lead in `div.col-md-6.HNews`

**Fix**: use `div.col-md-4` (covers the bulk). Title/URL anchor uses `a[href*='readmore.php']`.

### Eswatini Times — relative `readmore.php?...` URLs need section prefix
**Symptom**: Pipeline auto-applies `urljoin(base_url, relative_url)` BEFORE the custom cleaner runs, producing `https://www.times.co.sz/readmore.php?...` (missing the `/news/` segment) → 404 on every fetch.

**Fix**: a country-specific cleaner that handles BOTH relative AND wrong-absolute forms.

```python
# src/text/scrapers/pipelines/cleaning/eswatini.py
from .registry import register_cleaner

@register_cleaner
def clean_times_eswatini_url(url: str, base_url: str = None) -> str:
    if not url:
        return ""
    url = url.strip()
    # CRITICAL: pipeline pre-cleans relative→absolute before this runs.
    # We must catch the wrong-absolute form too:
    if url.startswith("https://www.times.co.sz/readmore.php"):
        return url.replace("/readmore.php", "/news/readmore.php", 1)
    if url.startswith(("http://", "https://")):
        return url
    if url.startswith("readmore.php"):
        return f"https://www.times.co.sz/news/{url}"
    return url
```

Register in `src/text/scrapers/pipelines/cleaning/__init__.py` and reference in YAML:

```yaml
cleaning:
  url: clean_times_eswatini_url
```

**Generalize**: when a site uses relative URLs that resolve against a path (not the domain root), write a country-specific cleaner that catches the wrong-absolute form. The pipeline auto-applies a default `urljoin` first, so the cleaner needs to handle the post-urljoin string.

### Eswatini Times — `?paged=N` is silently ignored
The `?paged` query param doesn't actually advance pagination — every page returns the same ~25 articles. The site has no real archive accessible.

**Mitigation**: set `max_pages: null` in the config; the pipeline's pagination strategy stops on duplicate-content detection. Result: ~25 articles per scrape, useful for fresh content going forward but no historical depth.

## Anti-bot / access barriers

### Cloudflare-protected (skip on first pass)
Probe returns `<title>Just a moment...</title>` or `cf-ray:` headers. These need browser automation (Tier 3) — defer.

Known Cloudflare blocks: `lusakatimes.com`, `herald.co.zw`, `chronicle.co.zw`, `modernghana.com`, `guardian.ng`, `vanguardngr.com`, `maroelamedia.co.za`, `news24.com`, `iol.co.za`, `clubk.net`, `netwerk24.com`.

### Paywalls (look for "please log in")
Probe articles successfully but `body` returns "Please note: To read the article, please enter your details below." — paywall, the body content is gated. Mark as Tier 3.

Known paywall: `namibiansun.com`.

### Arc Publishing CMS (Times Live, Sunday Times, Business Live, Sowetan)
Identifying mark: `data-arc-site="..."` in the HTML. No WP API. Bundle paths are obfuscated. Tier 2/3, defer.

### `/feed/` returns HTML (403 wrapper)
Some Cloudflare sites block `/feed/` while serving an HTML "403 Forbidden" wrapper. Don't mistake it for an RSS feed; verify `Content-Type: application/rss+xml`. Also verify with a GET, not just HEAD — CDN/WAF-fronted domains can return a valid XML content-type on an access-denied or empty stub (seen on `eleconomista.com.mx` → S3 `<Error><Code>AccessDenied`, `pulzo.com` → empty body). The body must open with `<rss`/`<feed`/`<rdf:RDF` and contain repeating `<item>`/`<entry>`.

### RSS/Atom feed strategy (`type: rss`) — onboarding quirks
The `rss` listing strategy (see `yaml_templates.md` §2b) parses feeds with the lxml **XML** parser, which differs from `html.parser`:
- **Selectors are case-sensitive** — `pubDate::text` works, `pubdate::text` matches nothing. Same for `link`/`title`/`published`.
- Feeds are **front-page-only** (latest ~10–100 items) unless the site is WordPress and `<feed>?paged=N` returns genuinely older items — only then set `page_param: paged`. Arc Publishing (`/arc/outboundfeeds/rss/`, common on big LAC/digital outlets) and most custom CMSs **ignore** pagination params.
- RSS 2.0 dominates globally; working Atom/RDF feeds are rare. WordPress feeds expose `content:encoded` (full body) + honor `?paged=N`; non-WP CMSs (Nuxt, Drupal, in-house "Witter"/"feeder") often ship only a truncated `<description>` teaser.
- Some feeds CDATA-wrap even `<link>` (The Hindu's `/feeder/default.rss`) — the XML parser unwraps CDATA transparently, so `link::text` still works.
- **Language-tag mismatch:** a feed's own `<language>` tag can lie (Online Khabar declares `en-US` but is Nepali). Always set the YAML `language:` explicitly from the actual content, never trust the feed tag.
- The strategy fetches the **body from the article page** via `article.body` (like pagination) **unless** `body_in_feed: true` is set — then the body is read straight from the feed item (`content:encoded`, then `description`) and the article-page fetch is skipped. Use `body_in_feed` for feeds carrying the full body (esp. WordPress) and for full-content feeds whose article pages are JS/WAF-blocked (e.g. `citizen.digital` Nuxt, `thepress.mv`). Verify it's the *full* body not a teaser before enabling. Gotcha: `el.find("content:encoded")` resolves only because real feeds declare `xmlns:content` on `<rss>` — test fixtures must include that namespace.

## Pagination on category-only sites (no per-page archive)

### Times of Eswatini — see above (`?paged=N` ignored)

### Daily Maverick (dailymaverick.co.za) — no archive index
Homepage has 100+ article links; section paths return 404 on `?page=N`. URLs follow `/article/YYYY-MM-DD-<slug>` but there's no listing endpoint exposing them. Tier 2, defer or use sitemap if exposed.

### Mmegi (mmegi.bw) — AJAX-loaded pagination
Homepage shows ~45 articles; all `/news/?page=N` and `/2026/04/27/` paths return identical HTML. Content is loaded client-side after initial render. Tier 3.

## Regional aggregator behavior

The skill's "regional aggregator fallback" concept currently has **only one validated instance**: AllAfrica, scoped to SSA. Notes below are AllAfrica-specific. When onboarding a non-SSA region, do not transfer these defaults blindly — re-derive the selectors and pagination behavior from a fresh `assess-newspaper-source` pass.

### AllAfrica.com (SSA only)

- Country path is **single-word lowercase** (e.g. `southafrica`, `cotedivoire`, `burkinafaso`).
- `?page=N` does increment but has a depth ceiling (varies by country, often ~20-50 pages).
- Aggressively rate-limits: a fresh probe right after heavy use will return 0 thumbnails or `Connection refused` — wait and retry later.
- Title selector `ul.stories li a::text` may concatenate title + snippet ("Read more »" suffix). Body content is correct. Acceptable for EPU since EPU keys on body.
- **Do not point this template at non-African countries.** AllAfrica's content is geographically Africa-only — using it as a fallback for, e.g., South Asia or LAC would inject off-region content into the EPU index.

## Useful CDN-bypass tricks (use sparingly)

These are NOT magic bullets — most Cloudflare blocks need real browser automation. But these sometimes work:
- Try `?rest_route=/wp/v2/posts` instead of `/wp-json/wp/v2/posts` (Lesotho Times case).
- Drop suspicious query params one by one (`_fields`, `_embed`, `categories_exclude`).
- Vary `User-Agent` between desktop Chrome / iPad / Googlebot — but Googlebot UA on a real bot-protected site usually fails verification anyway.

## When the site is genuinely unsuitable

If after 2-3 probe iterations a candidate still fails (Cloudflare challenge, SPA with no API, paywall, dead domain), DO NOT keep iterating. Either:
- Drop it from the candidate list and pick the next one, OR
- If it's a high-value source the user might want to revisit, write a `_0_<name>.yaml` stub with top-of-file comments explaining why it failed (per the `assess-newspaper-source` skill convention).

The pipeline skips files starting with `_`; this preserves the research without activating the broken config.
