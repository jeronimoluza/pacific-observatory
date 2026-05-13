# Known Stuck-Source Patterns

The four canonical patterns observed in production. Each pattern has a recognition signature, a root cause, and the canonical fix.

## Pattern 1 — Empty-body posts (cubanet / proceso / dagblad pattern)

**Signature:**
- WP API listing returns thumbnails fine, discovery proceeds
- For affected pending URLs: WP API `/wp-json/wp/v2/posts?slug=<slug>` returns either empty results array OR `content.rendered` of length 0
- HTML page returns 200 but only the page chrome (header, footer, newsletter signup) is in `<p>` tags
- All article body selectors return 0 substantial paragraphs
- Affected URLs span all years equally — not a recent change
- URLs match patterns like `portada-*`, `resumen-*`, `wist-u-*`, image-only or scan-of-print posts
- ⚠ warning fires: `after N article attempts, 0 were successfully scraped`

**Root cause:** the live site doesn't render an article body for these specific posts. They may be:
- Image-only or scan-of-print posts where the body was never digitized
- Excerpt-only posts (Elementor `theme-post-excerpt` widget without `theme-post-content`)
- Content-protected posts that strip body server-side
- Posts deprecated to placeholder pages

**Fix:**
1. Confirm the body selector still works on **fresh** articles in `news.csv` (sample 3 recent dates with `body` length >200 chars from news.csv; verify configured selector matches their HTML).
2. If selector still works for fresh content: keep it. The pending URLs are a known-bad subset.
3. Add `date: meta[property='article:published_time']::attr(content)` if missing.
4. **Pre-seed `failed_urls_seen.csv`** with all pending URLs as `last_status=NO_BODY`.
5. Smoke test should report `Skipped (ledger): N` matching the seed count.

**Worked examples in this codebase (memory: project_lac_stuck_sources_2026_05_04):**
- `cuba/cubanet`: 4,121 pending → ledger seeded; selector changed to `div.elementor-widget-theme-post-content p`
- `honduras/proceso`: 6,826 pending → ledger seeded; date selector added
- `suriname/dagblad_suriname`: 3,287 pending → ledger seeded; selector changed from `"filler"` to `.entry-content p`

## Pattern 2 — Wrong selector, body actually present

**Signature:**
- WP API returns content normally for fresh articles (or doesn't but HTML works)
- HTML page returns 200, has substantial `<p>` content
- Configured `body` selector returns 0 paragraphs
- ONE of the fallback selectors returns >100 chars consistently across years
- ⚠ warning may fire if running

**Root cause:** the YAML `article.body` selector is wrong for this site's theme. Common reasons:
- Site migrated from Newspaper theme (`.td-post-content p`) to Elementor (`div.elementor-widget-theme-post-content p`)
- Site uses a custom theme with `.entry-content p` instead of `article p`
- Onboarding template's `body: "filler"` placeholder was never replaced

**Fix:**
1. From the stratified probe, identify which fallback selector returned text consistently.
2. Update the YAML `article.body` to that selector.
3. Add date selector if missing.
4. Smoke test: `--max-articles 5` should now report `Articles Scraped > 0`.
5. **No ledger seed needed** — the existing pending URLs will scrape successfully on the next run.

## Pattern 3 — Cloudflare / rate-limit / bot block

**Signature:**
- HTML response status 403, 429, 503, or 200 with body containing `cloudflare`, `challenge`, `captcha`, `Just a moment`
- WP API may also return HTML challenge page instead of JSON
- Pattern affects ALL URLs from the site, not a subset
- May be transient — site behaves normally to a fresh browser

**Root cause:** the site has anti-bot protection that the `client: http` (httpx) path can't pass.

**Fix this skill should NOT auto-apply:**
- Switching `client: browser` (Playwright) is a real config change with cost implications — escalate to human.
- Adding fresh per-slug Playwright fetch (the investing.com pattern) is even more involved.
- Mark source as **DEFERRED** in the report. Do not pre-seed the ledger — the URLs aren't permanently broken, they're just blocked right now.

The escalation message should mention:
- Whether the WP API also fails (suggests stronger block)
- Whether `curl` from the terminal works (suggests TLS-fingerprint discrimination)
- Suggestion: try `client: browser` with `concurrency: 1` and `rate_limit: 5.0`, or move to per-slug Playwright with fresh context.

## Pattern 4 — Site genuinely silent

**Signature:**
- pending == 0 (urls.csv === news.csv after dedup)
- OR pending > 0 but all pending URLs have dates older than several years AND every recent run finds 0 new thumbnails
- po text status shows "X days ago" but selector and ledger are healthy
- No ⚠ warning fires (because no per-URL failures occur — there's just nothing to fetch)
- Iter rate is fast OR the run skips straight to "Articles Scraped: 0 / Thumbnails Discovered: 0"

**Root cause:** the site simply hasn't published in those category filters lately. Common with:
- Small national outlets over weekends/holidays
- Outlets that post only weekly/monthly under the configured categories
- Outlets that switched their primary publishing to a category not in our `categories=` filter

**Fix:**
- **Not a fix-needed condition.** Mark the source as `current — no new articles in target categories` in the report.
- If the operator wants broader coverage, they can widen the WP API category filter — but that's an onboarding-quality decision, not a refresh-time fix.
- Don't pre-seed the ledger. Don't kill anything.

## Decision tree (apply during diagnose loop)

```
                 stratified probe complete
                          │
            ┌─────────────┼─────────────┐
            │             │             │
       all return    fallback sel    pending == 0
       empty (API+   matches >100    or all old
       all sels)     chars
            │             │             │
            ▼             ▼             ▼
        Pattern 1     Pattern 2     Pattern 4
       (seed ledger) (fix selector) (no fix)

    if HTML status ∈ {403,429,503} OR body contains
    "cloudflare|challenge|captcha|Just a moment":
            │
            ▼
        Pattern 3
       (DEFER, escalate)
```

## Empirical priors (where to spend probe budget)

When time-limited, sample in this order:
1. One recent (current year) URL — fastest signal of "is this current behavior or historical breakage?"
2. One mid-history URL (5 years ago) — disambiguates "selector changed recently" from "always broken"
3. One oldest URL — confirms universality

The skill's diagnose loop already does stratified-by-year sampling; this prior is just to make sure those three samples reach the API+HTML probe even if other years time out.
